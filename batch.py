#!/usr/bin/env python3
"""
Batch runner — process multiple PDFs through the pipeline.

Usage:
    python batch.py input_dir/ --output-dir output/ --api-key KEY
    python batch.py file1.pdf file2.pdf --output-dir output/
"""

import argparse
import os
import sys
import json
import time
from pathlib import Path

from main import run_pipeline


def run_batch(inputs: list[str], output_base: str, api_key: str = None,
              model: str = "claude-sonnet-4-20250514", provider: str = None,
              dita_ot_path: str = None):
    """Process multiple PDF files."""
    # Collect PDF files
    pdf_files = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            pdf_files.extend(sorted(p.glob("**/*.pdf")))
        elif p.is_file() and p.suffix.lower() == ".pdf":
            pdf_files.append(p)
        else:
            print(f"⚠ Skipping: {inp}")

    if not pdf_files:
        print("No PDF files found.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"BATCH PROCESSING: {len(pdf_files)} PDFs")
    print(f"{'='*60}\n")

    results = []
    total_start = time.time()

    for i, pdf in enumerate(pdf_files):
        print(f"\n[{i+1}/{len(pdf_files)}] Processing: {pdf.name}")
        print("-" * 40)

        # Each PDF gets its own output subdirectory
        out_dir = str(Path(output_base) / pdf.stem)

        try:
            result = run_pipeline(
                pdf_path=str(pdf),
                output_dir=out_dir,
                api_key=api_key,
                model=model,
                provider=provider,
                dita_ot_path=dita_ot_path,
            )
            result["input_file"] = str(pdf)
            results.append(result)
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            results.append({
                "input_file": str(pdf),
                "errors": [str(e)],
                "files": [],
                "stats": {"elapsed_seconds": 0},
            })

    total_elapsed = time.time() - total_start

    # Summary
    print(f"\n\n{'='*60}")
    print(f"BATCH SUMMARY")
    print(f"{'='*60}")
    print(f"  Total PDFs:     {len(pdf_files)}")
    print(f"  Successful:     {sum(1 for r in results if not r.get('errors'))}")
    print(f"  With errors:    {sum(1 for r in results if r.get('errors'))}")
    print(f"  Total time:     {total_elapsed:.1f}s")
    print(f"  Avg per PDF:    {total_elapsed/len(pdf_files):.1f}s")

    # Write batch report
    report_path = Path(output_base) / "batch_report.json"
    report = {
        "total_pdfs": len(pdf_files),
        "total_time_seconds": round(total_elapsed, 2),
        "results": [
            {
                "file": r.get("input_file", ""),
                "topics": r.get("stats", {}).get("topics_generated", 0),
                "errors": r.get("errors", []),
                "dita_ot_passed": r.get("dita_ot_passed"),
            }
            for r in results
        ],
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n  Report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch PDF-to-DITA conversion")
    parser.add_argument("inputs", nargs="+", help="PDF files or directories")
    parser.add_argument("--output-dir", "-o", default="./batch_output")
    parser.add_argument("--api-key", "-k", default=None,
                        help="API key (or set ANTHROPIC_API_KEY / GEMINI_API_KEY / KIMI_API_KEY)")
    parser.add_argument("--provider", "-p", default=None,
                        choices=["claude", "gemini", "kimi"])
    parser.add_argument("--model", "-m", default=None)
    parser.add_argument("--dita-ot", default=None)
    args = parser.parse_args()

    from llm_providers import resolve_config
    config = resolve_config(args.api_key, args.model, args.provider)
    run_batch(args.inputs, args.output_dir, config["api_key"],
              config["model"], config["provider"], args.dita_ot)


if __name__ == "__main__":
    main()
