#!/usr/bin/env python3
"""
PDF-to-DITA Conversion Pipeline
================================

End-to-end automated conversion of PDF documentation to DITA XML format.

Usage:
    python main.py input.pdf [--output-dir ./output] [--api-key KEY] [--model MODEL]

Environment:
    ANTHROPIC_API_KEY  — Claude API key (or use --api-key flag)

Requirements:
    pip install pdfplumber pypdf lxml

Optional:
    DITA-OT for validation: https://www.dita-ot.org/download
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from parser import group_into_sections, parse_pdf
from pathlib import Path

from classifier import classify_section, classify_section_heuristic
from emitter import (topic_filename, validate_dita_ot,
                     validate_xml_wellformedness, write_output)


def detect_doc_title(pdf_path: str) -> str:
    """Extract document title from PDF metadata or first page."""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    # Try metadata
    meta = reader.metadata
    if meta and meta.title and len(meta.title.strip()) > 3:
        return meta.title.strip()
    # Fallback to filename
    return Path(pdf_path).stem.replace("_", " ").replace("-", " ").title()


def detect_product_name(sections: list[dict]) -> str | None:
    """Try to detect product name from content (for keydef)."""
    # Look for patterns like "ABC's ... solution" or "XYZ platform"
    for section in sections:
        for block in section["blocks"]:
            if block.type in ("paragraph", "list_item"):
                # Pattern: "ABC's <product> solution/platform/system"
                import re
                m = re.search(r"(\b[A-Z]{2,}\b)'s\s+", block.text)
                if m:
                    return m.group(1)
    return None


def run_pipeline(pdf_path: str, output_dir: str, api_key: str = None,
                 model: str = "gemini-3.1-flash-lite",
                 provider: str = None,
                 dita_ot_path: str = None,
                 copy_images: bool = True) -> dict:
    """
    Run the complete PDF-to-DITA conversion pipeline.

    Returns: {
        "files": [filenames],
        "errors": [error_messages],
        "ditamap": ditamap_filename,
        "dita_ot_passed": bool | None,
        "stats": {...}
    }
    """
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"PDF-to-DITA Conversion Pipeline")
    print(f"{'='*60}")
    print(f"Input:  {pdf_path}")
    print(f"Output: {output_dir}")
    if api_key:
        from llm_providers import print_provider_info
        print_provider_info({"provider": provider or "claude", "model": model, "api_key": api_key})
    else:
        print(f"Model:  heuristic (no API key)")
    print()

    # ── Step 1: Parse PDF ────────────────────────────────────────────────
    print("Step 1: Parsing PDF...")
    image_dir = str(Path(output_dir) / "images")
    blocks = parse_pdf(pdf_path, image_dir)
    print(f"  Extracted {len(blocks)} blocks")
    for btype in set(b.type for b in blocks):
        count = sum(1 for b in blocks if b.type == btype)
        print(f"    {btype}: {count}")

    # ── Step 2: Group into sections ──────────────────────────────────────
    print("\nStep 2: Grouping into sections...")
    sections = group_into_sections(blocks)
    print(f"  {len(sections)} sections found:")
    for s in sections:
        block_types = [b.type for b in s["blocks"]]
        print(f"    • {s['title']} ({len(s['blocks'])} blocks: "
              f"{', '.join(set(block_types))})")

    # ── Step 3: Detect metadata ──────────────────────────────────────────
    print("\nStep 3: Detecting document metadata...")
    doc_title = detect_doc_title(pdf_path)
    product_name = detect_product_name(sections)
    print(f"  Document title: {doc_title}")
    print(f"  Product name:   {product_name or '(not detected)'}")

    # ── Step 4: Plan topic boundaries ──────────────────────────────────────
    print("\nStep 4: Planning topic boundaries...")
    from classifier import plan_topics, plan_topics_heuristic

    # Skip the LLM planning call when there is only ONE section. No merging
    # is possible, so heuristic always produces the right plan and we save
    # 5-15s of round-trip latency without any quality cost.
    if len(sections) <= 1:
        plans = plan_topics_heuristic(sections)
        print(f"  Single section detected, heuristic planned {len(plans)} topic (skipped LLM call)")
    elif api_key:
        try:
            plans = plan_topics(sections, api_key, model, provider)
            print(f"  LLM planned {len(plans)} topics:")
        except Exception as e:
            print(f"  ⚠ LLM planning failed ({e}), using heuristic")
            plans = plan_topics_heuristic(sections)
            print(f"  Heuristic planned {len(plans)} topics:")
    else:
        plans = plan_topics_heuristic(sections)
        print(f"  Heuristic planned {len(plans)} topics:")

    for plan in plans:
        indices = plan["section_indices"]
        titles = [sections[i]["title"] for i in indices]
        print(f"    • {plan['topic_title']} ({plan['topic_type']}) "
              f"← sections: {titles}")

    # ── Step 5: Classify sections + generate DITA ────────────────────────
    print("\nStep 5: Classifying and generating DITA XML...")
    all_titles = [p["topic_title"] for p in plans]
    # Pre-compute filename map so the LLM can emit correct <xref href=...> cross-refs.
    topic_filenames = {
        p["topic_title"]: topic_filename(p["topic_title"], p["topic_type"])
        for p in plans
    }
    classified = []

    # Prepare per-topic input lists (block merging is pure Python, fast)
    from parser import Block
    topic_inputs = []
    for plan in plans:
        title = plan["topic_title"]
        topic_type = plan["topic_type"]
        indices = plan["section_indices"]
        merged_blocks = []
        for idx in indices:
            if idx == indices[0]:
                merged_blocks.extend(sections[idx]["blocks"])
            else:
                merged_blocks.append(Block(
                    type="heading", text=sections[idx]["title"],
                    page=sections[idx]["page_start"], level=2
                ))
                merged_blocks.extend(sections[idx]["blocks"])
        topic_inputs.append({"title": title, "type": topic_type, "blocks": merged_blocks})

    # Filter empty topics
    valid_inputs = [t for t in topic_inputs if t["blocks"]]
    skipped = len(topic_inputs) - len(valid_inputs)
    if skipped:
        print(f"  ⚠ Skipping {skipped} empty topic(s)")

    def _classify_one(idx_topic):
        idx, t = idx_topic
        title = t["title"]
        if not api_key:
            return idx, {
                "title": title,
                "topic_type": t["type"],
                "body_xml": _fallback_body(title, t["blocks"], t["type"]),
                "reasoning": "heuristic",
            }
        try:
            result = classify_section(
                title=title,
                blocks=t["blocks"],
                api_key=api_key,
                doc_title=doc_title,
                all_section_titles=all_titles,
                model=model,
                provider=provider,
                product_name=product_name,
                topic_filenames=topic_filenames,
            )
            return idx, {
                "title": title,
                "topic_type": result["topic_type"],
                "body_xml": result["body_xml"],
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            return idx, {
                "title": title,
                "topic_type": t["type"],
                "body_xml": _fallback_body(title, t["blocks"], t["type"]),
                "reasoning": f"LLM failed: {e}; heuristic fallback",
            }

    # Run classifications in parallel. Throttle in _post_json keeps RPM safe.
    from concurrent.futures import ThreadPoolExecutor
    if api_key and len(valid_inputs) > 1:
        print(f"  Classifying {len(valid_inputs)} topics in parallel...")
        results = [None] * len(valid_inputs)
        with ThreadPoolExecutor(max_workers=min(len(valid_inputs), 4)) as ex:
            for idx, res in ex.map(_classify_one, list(enumerate(valid_inputs))):
                results[idx] = res
                tag = "→" if "heuristic" not in res["reasoning"].lower() else "⚠"
                print(f"  [{idx+1}/{len(valid_inputs)}] {tag} {res['title']}: "
                      f"{res['topic_type']} ({res.get('reasoning', '')[:60]})")
    else:
        results = []
        for idx, t in enumerate(valid_inputs):
            print(f"  [{idx+1}/{len(valid_inputs)}] Classifying: {t['title']}...")
            _, res = _classify_one((idx, t))
            tag = "→" if "heuristic" not in res["reasoning"].lower() else "⚠"
            print(f"    {tag} {res['topic_type']} ({res.get('reasoning', '')[:60]})")
            results.append(res)

    for res in results:
        classified.append({
            "title": res["title"],
            "topic_type": res["topic_type"],
            "body_xml": res["body_xml"],
        })

    # ── Step 6: Write output files ───────────────────────────────────────
    print(f"\nStep 6: Writing DITA files to {output_dir}...")
    result = write_output(
        output_dir=output_dir,
        doc_title=doc_title,
        classified_sections=classified,
        product_name=product_name,
        api_key=api_key,
        model=model,
        provider=provider,
    )

    # Copy images to output dir
    if copy_images and Path(image_dir).exists():
        for img in Path(image_dir).glob("*.png"):
            dest = Path(output_dir) / img.name
            if not dest.exists():
                shutil.copy2(img, dest)
                print(f"  ✓ {img.name} (image)")

    # ── Step 7: Quality metrics ──────────────────────────────────────────
    print(f"\nStep 7: Quality metrics...")
    try:
        from collections import Counter

        from lxml import etree
        out_path = Path(output_dir)
        total_elems = 0
        total_class = 0
        domain_counts = Counter()
        for f in out_path.glob("*.dita"):
            content = f.read_text()
            clean = re.sub(r"<!DOCTYPE[^>]+>", "", content)
            root = etree.fromstring(clean.encode())
            for e in root.iter():
                total_elems += 1
                cls = e.get("class", "")
                if cls:
                    total_class += 1
                for d in ["ui-d/", "pr-d/"]:
                    if d in cls:
                        m = re.search(rf"{d}(\w+)", cls)
                        if m:
                            domain_counts[m.group(1)] += 1
        class_pct = total_class / max(total_elems, 1) * 100
        print(f"  Elements: {total_elems} total, {total_class} with @class ({class_pct:.0f}%)")
        if domain_counts:
            parts = [f"{k}={v}" for k, v in domain_counts.most_common()]
            print(f"  Semantic: {', '.join(parts)}")
        else:
            print(f"  Semantic: none (heuristic mode — enable LLM for uicontrol, menucascade, option)")
    except Exception:
        pass

    # ── Step 8: DITA-OT validation ───────────────────────────────────────
    print(f"\nStep 8: DITA-OT validation...")
    dita_ot_passed = None
    dita_ot_log = ""
    passed, log = validate_dita_ot(output_dir, result["ditamap"], dita_ot_path)
    if "not found" in log.lower():
        print(f"  ⚠ {log}")
        print(f"  → Skipping DITA-OT validation. Run manually:")
        print(f"    dita -i {Path(output_dir).resolve() / result['ditamap']} -f html5 --processing-mode=strict")
    else:
        dita_ot_passed = passed
        dita_ot_log = log
        if passed:
            print(f"  ✓ DITA-OT validation PASSED")
        else:
            print(f"  ✗ DITA-OT validation FAILED")
            # Extract error lines
            for line in log.split("\n"):
                if "[DOT" in line and any(s in line for s in ["E]", "F]"]):
                    print(f"    {line.strip()}")

    # ── Summary ──────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    stats = {
        "input_file": str(pdf_path),
        "sections": len(sections),
        "topics_generated": len(classified),
        "files_written": len(result["files"]),
        "errors": len(result["errors"]),
        "dita_ot_passed": dita_ot_passed,
        "elapsed_seconds": round(elapsed, 2),
    }

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Sections processed: {stats['sections']}")
    print(f"  Topics generated:   {stats['topics_generated']}")
    print(f"  Files written:      {stats['files_written']}")
    print(f"  Errors:             {stats['errors']}")
    print(f"  DITA-OT:            {'PASS' if dita_ot_passed else 'N/A' if dita_ot_passed is None else 'FAIL'}")
    print(f"  Time:               {stats['elapsed_seconds']}s")
    print()

    if result["errors"]:
        print("Errors:")
        for e in result["errors"]:
            print(f"  ✗ {e}")
        print()

    print("Output files:")
    for f in result["files"]:
        print(f"  {Path(output_dir) / f}")

    result["dita_ot_passed"] = dita_ot_passed
    result["stats"] = stats
    return result


def _fallback_body(title: str, blocks, topic_type: str) -> str:
    """Generate simple DITA body XML without LLM (heuristic fallback)."""
    import html

    from lxml.builder import E

    def esc(text):
        return html.escape(text, quote=False)

    body_parts = []

    if topic_type == "concept":
        body_parts.append(f'<conbody class="- topic/body  concept/conbody ">')
        in_section = False
        for b in blocks:
            if b.type == "heading" and b.level >= 2:
                # Subsection heading
                if in_section:
                    body_parts.append("</section>")
                body_parts.append(f'<section class="- topic/section ">')
                body_parts.append(f'<title class="- topic/title ">{esc(b.text)}</title>')
                in_section = True
            elif b.type == "paragraph":
                body_parts.append(f'<p class="- topic/p ">{esc(b.text)}</p>')
            elif b.type == "note":
                body_parts.append(f'<note class="- topic/note ">{esc(b.text)}</note>')
            elif b.type == "image":
                body_parts.append(f'<fig class="- topic/fig "><title class="- topic/title ">Figure</title><image href="{b.text}" class="- topic/image "/></fig>')
            elif b.type == "code":
                body_parts.append(f'<codeblock class="+ topic/pre pr-d/codeblock ">{esc(b.text)}</codeblock>')
        if in_section:
            body_parts.append("</section>")
        body_parts.append("</conbody>")

    elif topic_type == "task":
        body_parts.append(f'<taskbody class="- topic/body task/taskbody ">')
        # Collect pre-step paragraphs as context
        pre_steps = []
        steps = []
        post_steps = []
        in_steps = False
        past_steps = False
        for b in blocks:
            if b.type == "list_item":
                in_steps = True
                steps.append(b)
            elif in_steps and b.type not in ("list_item",):
                if b.type == "code" and steps:
                    # Code after a list item belongs to the last step
                    steps.append(b)
                elif b.type == "paragraph" and not past_steps:
                    # Could be continuation of step or post-step
                    # Check if more list items follow
                    past_steps = True
                    post_steps.append(b)
                else:
                    post_steps.append(b)
            else:
                if not in_steps:
                    pre_steps.append(b)
                else:
                    post_steps.append(b)

        if pre_steps:
            body_parts.append(f'<context class="- topic/section task/context ">')
            for b in pre_steps:
                body_parts.append(f'<p class="- topic/p ">{esc(b.text)}</p>')
            body_parts.append("</context>")

        if steps:
            body_parts.append(f'<steps class="- topic/ol task/steps ">')
            for b in steps:
                if b.type == "list_item":
                    cmd_text = b.text
                    # Remove leading number
                    import re as _re
                    cmd_text = _re.sub(r"^\d+\.\s*", "", cmd_text)
                    body_parts.append(f'<step class="- topic/li task/step ">')
                    body_parts.append(f'<cmd class="- topic/ph task/cmd ">{esc(cmd_text)}</cmd>')
                    body_parts.append("</step>")
                elif b.type == "code":
                    # Attach to previous step
                    body_parts.insert(-1, f'<stepxmp class="- topic/itemgroup task/stepxmp "><codeblock class="+ topic/pre pr-d/codeblock ">{esc(b.text)}</codeblock></stepxmp>')
            body_parts.append("</steps>")

        if post_steps:
            body_parts.append(f'<result class="- topic/section task/result ">')
            for b in post_steps:
                body_parts.append(f'<p class="- topic/p ">{esc(b.text)}</p>')
            body_parts.append("</result>")

        body_parts.append("</taskbody>")

    elif topic_type == "reference":
        body_parts.append(f'<refbody class="- topic/body        reference/refbody ">')
        body_parts.append(f'<section class="- topic/section ">')
        for b in blocks:
            if b.type == "table":
                table_data = json.loads(b.text)
                if table_data:
                    cols = len(table_data[0])
                    body_parts.append(f'<table class="- topic/table "><tgroup cols="{cols}" class="- topic/tgroup ">')
                    for ci in range(cols):
                        body_parts.append(f'<colspec colname="c{ci+1}" colnum="{ci+1}" class="- topic/colspec "/>')
                    # Header row
                    body_parts.append(f'<thead class="- topic/thead "><row class="- topic/row ">')
                    for cell in table_data[0]:
                        body_parts.append(f'<entry class="- topic/entry ">{esc(cell or "")}</entry>')
                    body_parts.append("</row></thead>")
                    # Body rows
                    body_parts.append(f'<tbody class="- topic/tbody ">')
                    for row in table_data[1:]:
                        body_parts.append(f'<row class="- topic/row ">')
                        for cell in row:
                            body_parts.append(f'<entry class="- topic/entry ">{esc(cell or "")}</entry>')
                        body_parts.append("</row>")
                    body_parts.append("</tbody></tgroup></table>")
            elif b.type == "paragraph":
                body_parts.append(f'<p class="- topic/p ">{esc(b.text)}</p>')
        body_parts.append("</section>")
        body_parts.append("</refbody>")

    return "\n".join(body_parts)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF documentation to DITA XML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported LLM providers:
  claude   Anthropic Claude (env: ANTHROPIC_API_KEY)
           Models: claude-sonnet-4-20250514, claude-haiku-4-5-20251001
  gemini   Google Gemini   (env: GEMINI_API_KEY)
           Models: gemini-3.1-flash-lite, gemini-3-flash-preview, gemini-2.5-pro, gemini-2.5-flash
  kimi     Moonshot Kimi   (env: KIMI_API_KEY)
           Models: moonshot-v1-auto, moonshot-v1-8k, moonshot-v1-32k,
                   moonshot-v1-128k, kimi-latest

Examples:
  # Auto-detect provider from env var:
  export GEMINI_API_KEY=AIza...
  python main.py input.pdf -o output/

  # Explicit provider + model:
  python main.py input.pdf --provider kimi --model moonshot-v1-128k

  # Explicit key on command line:
  python main.py input.pdf -k sk-ant-... --model claude-sonnet-4-20250514

  # Heuristic mode (no API key needed):
  python main.py input.pdf -o output/
""",
    )
    parser.add_argument("input", help="Path to input PDF file")
    parser.add_argument("--output-dir", "-o", default="./dita_output",
                        help="Output directory (default: ./dita_output)")
    parser.add_argument("--api-key", "-k", default=None,
                        help="API key (or set ANTHROPIC_API_KEY / GEMINI_API_KEY / KIMI_API_KEY)")
    parser.add_argument("--provider", "-p", default=None,
                        choices=["claude", "gemini", "kimi"],
                        help="LLM provider (auto-detected from model name or env var)")
    parser.add_argument("--model", "-m", default=None,
                        help="Model name (default depends on provider)")
    parser.add_argument("--dita-ot", default=None,
                        help="Path to DITA-OT 'dita' binary")
    parser.add_argument("--eval", "-e", default=None,
                        help="Reference output dir — run evaluation after conversion")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable response caching")

    args = parser.parse_args()

    # Resolve provider / model / API key
    from llm_providers import resolve_config
    config = resolve_config(
        api_key=args.api_key,
        model=args.model,
        provider=args.provider,
    )

    if not config["api_key"]:
        print("⚠ No API key found. Using heuristic mode (lower quality).")
        print("  Set one of: ANTHROPIC_API_KEY, GEMINI_API_KEY, KIMI_API_KEY")
        print("  Or use --api-key KEY\n")

    result = run_pipeline(
        pdf_path=args.input,
        output_dir=args.output_dir,
        api_key=config["api_key"],
        model=config["model"],
        provider=config["provider"],
        dita_ot_path=args.dita_ot,
    )

    # Live evaluation
    if args.eval:
        print(f"\n{'='*60}")
        print(f"  EVALUATION vs {args.eval}")
        print(f"{'='*60}")
        from pathlib import Path as P

        from evaluate import (check_class_coverage, check_content_faithfulness,
                              check_ditamap, check_semantic_richness,
                              check_structural_f1, check_topic_classification,
                              check_xml_validity, match_files, print_report)
        expected, actual = match_files(P(args.eval), P(args.output_dir))
        common = set(expected.keys()) & set(actual.keys())
        if not common:
            print("  ⚠ No matching files found for evaluation")
        else:
            exp_sub = {k: expected[k] for k in common}
            act_sub = {k: actual[k] for k in common}
            metrics = [
                check_xml_validity(list(P(args.output_dir).glob("*.dita"))),
                check_class_coverage(list(P(args.output_dir).glob("*.dita"))),
            ]
            if "concept" in common:
                metrics.append(check_topic_classification(exp_sub, act_sub))
                metrics.append(check_structural_f1(exp_sub, act_sub))
                metrics.append(check_semantic_richness(exp_sub, act_sub))
                metrics.append(check_content_faithfulness(exp_sub, act_sub))
            if "ditamap" in common:
                metrics.append(check_ditamap(exp_sub, act_sub))
            print_report(metrics)

    sys.exit(0 if not result["errors"] else 1)


if __name__ == "__main__":
    main()
