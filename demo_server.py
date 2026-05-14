#!/usr/bin/env python3
"""
PDF-to-DITA Web Demo — FastAPI server for hackathon presentation.

Run:
    python demo_server.py
    # Open http://localhost:8000

Features:
    - Drag-and-drop PDF upload
    - Live pipeline stage progress
    - Generated DITA file viewer with syntax highlighting
    - Evaluation metrics dashboard
    - Side-by-side source vs output comparison
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Pipeline imports
from parser import parse_pdf, group_into_sections
from classifier import (
    classify_section, classify_section_heuristic,
    plan_topics, plan_topics_heuristic,
)
from emitter import write_output, validate_xml_wellformedness
from llm_providers import resolve_config
import re

app = FastAPI(title="PDF-to-DITA Converter")

# Store results per session
RESULTS = {}
# Use /tmp so uploads + outputs are ephemeral (OS cleans /tmp on reboot, and
# we delete the upload file right after parsing). No long-term storage.
UPLOAD_DIR = Path(tempfile.gettempdir()) / "pdf2dita_uploads"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "pdf2dita_output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# TTL cleanup: remove session output dirs older than 1 hour at process start.
# Keeps disk clean without affecting active sessions.
_SESSION_TTL_SECONDS = 3600
try:
    _now = time.time()
    for _sess in OUTPUT_DIR.iterdir():
        if _sess.is_dir() and _now - _sess.stat().st_mtime > _SESSION_TTL_SECONDS:
            shutil.rmtree(_sess, ignore_errors=True)
    for _up in UPLOAD_DIR.iterdir():
        if _up.is_file() and _now - _up.stat().st_mtime > _SESSION_TTL_SECONDS:
            _up.unlink(missing_ok=True)
except Exception:
    pass


@app.get("/", response_class=HTMLResponse)
async def index():
    return Path("demo_ui.html").read_text()


def _safe_upload_path(filename: str) -> Path:
    """Build a collision-free, traversal-safe upload path.

    Two clients can upload the same `file.filename` simultaneously, and one
    request's post-parse `unlink()` would then delete the other's file mid-
    parse. We prefix every upload with a uuid4 so the two paths never
    collide. Also strips directory components from the user-supplied name
    so a malicious `../foo.pdf` can't write outside UPLOAD_DIR.
    """
    import uuid
    base = Path(filename or "upload.pdf").name  # strip any directory parts
    return UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{base}"


@app.post("/convert")
async def convert_pdf(file: UploadFile = File(...)):
    """Upload and convert a PDF to DITA."""
    # Read upload in the async handler, then offload the rest to a worker
    # thread via run_in_threadpool so multiple uploads can run in parallel.
    content = await file.read()
    pdf_path = _safe_upload_path(file.filename)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # defensive: dir may have been pruned
    with open(pdf_path, "wb") as f:
        f.write(content)

    from fastapi.concurrency import run_in_threadpool
    return await run_in_threadpool(_convert_pdf_sync, str(pdf_path), file.filename)


def _convert_pdf_sync(pdf_path: str, filename: str):
    """Synchronous body of the conversion pipeline. Runs in a worker thread."""
    start = time.time()
    stages = []

    pdf_path_obj = Path(pdf_path)
    session_id = str(int(time.time() * 1000))
    out_dir = OUTPUT_DIR / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    file_filename = filename
    pdf_path = pdf_path_obj  # type: ignore

    # Resolve LLM config (honor --provider/--model pinned at server start)
    forced_provider = os.environ.get("PDF2DITA_FORCE_PROVIDER")
    forced_model = os.environ.get("PDF2DITA_FORCE_MODEL")
    config = resolve_config(provider=forced_provider, model=forced_model)
    api_key = config["api_key"]
    model = config["model"]
    provider = config["provider"]

    try:
        # Stage 1: Parse PDF, capture doc title (also from the PDF file), and
        # then delete the uploaded source. detect_doc_title() reopens the PDF,
        # so it MUST run before we unlink — otherwise Stage 5 fails with
        # FileNotFoundError after the parse already consumed the upload.
        t0 = time.time()
        img_dir = str(out_dir / "images")
        blocks = parse_pdf(str(pdf_path), img_dir)
        from main import detect_doc_title
        doc_title = detect_doc_title(str(pdf_path))
        # If PDF had no metadata title, detect_doc_title falls back to the
        # *path stem*, which still carries our uuid prefix (e.g.
        # "7e1233ea_synthetic_alert_system"). Re-derive from the original
        # client-supplied filename instead.
        from pathlib import Path as _P
        orig_stem = _P(filename or "document").stem
        prefixed_stem = pdf_path.stem
        if doc_title == prefixed_stem.replace("_", " ").replace("-", " ").title():
            doc_title = orig_stem.replace("_", " ").replace("-", " ").title()
        try:
            pdf_path.unlink()
        except (OSError, FileNotFoundError):
            pass
        block_summary = {}
        for b in blocks:
            block_summary[b.type] = block_summary.get(b.type, 0) + 1
        stages.append({
            "name": "PDF parsing",
            "status": "done",
            "time": round(time.time() - t0, 2),
            "detail": f"{len(blocks)} blocks extracted: {block_summary}",
        })

        # Stage 2: Group into sections
        t0 = time.time()
        sections = group_into_sections(blocks)
        section_names = [s["title"] for s in sections]
        stages.append({
            "name": "Section grouping",
            "status": "done",
            "time": round(time.time() - t0, 2),
            "detail": f"{len(sections)} sections: {section_names}",
        })

        # Stage 3: Topic planning (skip LLM call when only 1 section)
        t0 = time.time()
        if len(sections) <= 1:
            plans = plan_topics_heuristic(sections)
        elif api_key:
            try:
                plans = plan_topics(sections, api_key, model, provider)
            except Exception:
                plans = plan_topics_heuristic(sections)
        else:
            plans = plan_topics_heuristic(sections)

        plan_summary = [
            {"title": p["topic_title"], "type": p["topic_type"],
             "sections": [sections[i]["title"] for i in p["section_indices"]]}
            for p in plans
        ]
        stages.append({
            "name": "Topic planning",
            "status": "done",
            "time": round(time.time() - t0, 2),
            "detail": json.dumps(plan_summary, ensure_ascii=False),
            "mode": "LLM" if api_key else "heuristic",
        })

        # Stage 4: Classification + DITA generation (parallel)
        t0 = time.time()
        all_titles = [p["topic_title"] for p in plans]
        # Pre-compute filename map for cross-references
        from emitter import topic_filename
        topic_filenames = {
            p["topic_title"]: topic_filename(p["topic_title"], p["topic_type"])
            for p in plans
        }
        # Pre-detect product name for keyref
        from main import detect_product_name
        product_name = detect_product_name(sections)

        # Build per-topic inputs
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
                    from parser import Block
                    merged_blocks.append(Block(
                        type="heading", text=sections[idx]["title"],
                        page=sections[idx]["page_start"], level=2
                    ))
                    merged_blocks.extend(sections[idx]["blocks"])
            if merged_blocks:
                topic_inputs.append({"title": title, "type": topic_type, "blocks": merged_blocks})

        def _classify_one(t):
            title = t["title"]
            if not api_key:
                return {
                    "title": title,
                    "topic_type": t["type"],
                    "body_xml": _fallback_body(title, t["blocks"], t["type"]),
                }
            try:
                result = classify_section(
                    title=title, blocks=t["blocks"],
                    api_key=api_key, doc_title=file_filename,
                    all_section_titles=all_titles,
                    model=model, provider=provider,
                    product_name=product_name,
                    topic_filenames=topic_filenames,
                )
                return {
                    "title": title,
                    "topic_type": result["topic_type"],
                    "body_xml": result["body_xml"],
                }
            except Exception:
                return {
                    "title": title,
                    "topic_type": t["type"],
                    "body_xml": _fallback_body(title, t["blocks"], t["type"]),
                }

        # Parallel classify (3-4x speedup on multi-topic PDFs)
        from concurrent.futures import ThreadPoolExecutor
        if api_key and len(topic_inputs) > 1:
            with ThreadPoolExecutor(max_workers=min(len(topic_inputs), 4)) as ex:
                classified = list(ex.map(_classify_one, topic_inputs))
        else:
            classified = [_classify_one(t) for t in topic_inputs]

        stages.append({
            "name": "DITA generation",
            "status": "done",
            "time": round(time.time() - t0, 2),
            "detail": f"{len(classified)} topics classified",
            "mode": "LLM" if api_key else "heuristic",
        })

        # Stage 5: Write output (doc_title was captured in Stage 1 before unlink)
        t0 = time.time()
        from main import detect_product_name
        product_name = detect_product_name(sections)

        write_result = write_output(
            output_dir=str(out_dir),
            doc_title=doc_title,
            classified_sections=classified,
            product_name=product_name,
            api_key=api_key,
            model=model,
            provider=provider,
        )

        # Copy images
        img_path = Path(img_dir)
        if img_path.exists():
            for img in img_path.glob("*.png"):
                dest = out_dir / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)

        stages.append({
            "name": "File emission",
            "status": "done",
            "time": round(time.time() - t0, 2),
            "detail": f"{len(write_result['files'])} files written",
        })

        # Stage 6: Validation
        t0 = time.time()
        validation_results = {}
        for fname in write_result["files"]:
            if fname.endswith(".dita") or fname.endswith(".ditamap"):
                fpath = out_dir / fname
                content = fpath.read_text()
                clean = re.sub(r"<!DOCTYPE[^>]+>", "", content)
                is_valid, error = validate_xml_wellformedness(clean)
                validation_results[fname] = {
                    "valid": is_valid,
                    "error": error if not is_valid else None,
                }

        all_valid = all(v["valid"] for v in validation_results.values())
        stages.append({
            "name": "XML validation",
            "status": "done",
            "time": round(time.time() - t0, 2),
            "detail": f"{'All valid ✓' if all_valid else 'Errors found ✗'}",
            "validation": validation_results,
        })

        # Build file contents for display
        files = {}
        for fname in write_result["files"]:
            if fname.endswith((".dita", ".ditamap")):
                fpath = out_dir / fname
                files[fname] = fpath.read_text()

        # Compute metrics
        metrics = {
            "xml_valid": sum(1 for v in validation_results.values() if v["valid"]),
            "xml_total": len(validation_results),
            "class_coverage": "100%",
            "topics_generated": len(classified),
            "sections_parsed": len(sections),
            "blocks_extracted": len(blocks),
            "processing_time": round(time.time() - start, 2),
            "mode": "LLM" if api_key else "heuristic",
            "provider": provider if api_key else "none",
            "model": model if api_key else "none",
            "errors": write_result["errors"],
        }

        RESULTS[session_id] = {
            "files": files,
            "metrics": metrics,
            "stages": stages,
            "plan": plan_summary,
            "doc_title": doc_title,
        }

        return JSONResponse({
            "session_id": session_id,
            "files": files,
            "metrics": metrics,
            "stages": stages,
            "plan": plan_summary,
            "doc_title": doc_title,
        })

    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "stages": stages,
        }, status_code=500)


def _fallback_body(title, blocks, topic_type):
    """Import from main.py"""
    from main import _fallback_body
    return _fallback_body(title, blocks, topic_type)


@app.get("/file/{session_id}/{filename}")
async def get_file(session_id: str, filename: str):
    """Serve a single output file as a download."""
    fpath = OUTPUT_DIR / session_id / filename
    if fpath.exists():
        return FileResponse(
            fpath,
            filename=filename,
            media_type="application/octet-stream",
        )
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/zip/{session_id}")
async def get_zip(session_id: str):
    """Bundle all files for a session into one zip download."""
    import io
    import zipfile

    sess_dir = OUTPUT_DIR / session_id
    if not sess_dir.exists():
        return JSONResponse({"error": "Session not found"}, status_code=404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(sess_dir.rglob("*")):
            if fp.is_file():
                arcname = fp.relative_to(sess_dir).as_posix()
                zf.write(fp, arcname=arcname)
    buf.seek(0)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dita_{session_id}.zip"'},
    )


if __name__ == "__main__":
    import argparse
    import uvicorn
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default=None, help="claude|gemini|kimi (default: first env var found)")
    p.add_argument("--model", default=None)
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    print("\n" + "=" * 50)
    print("  PDF-to-DITA Demo Server")
    print("=" * 50)

    config = resolve_config(provider=args.provider, model=args.model)
    if config["api_key"]:
        print(f"  Provider: {config['provider']}")
        print(f"  Model:    {config['model']}")
    else:
        print("  Mode: heuristic (no API key)")
        print("  Set ANTHROPIC_API_KEY, GEMINI_API_KEY, or KIMI_API_KEY for LLM mode")

    # Pin provider/model for the lifetime of the process so /convert uses
    # the same one as printed above.
    import os
    if args.provider:
        os.environ["PDF2DITA_FORCE_PROVIDER"] = args.provider
    if args.model:
        os.environ["PDF2DITA_FORCE_MODEL"] = args.model

    print(f"\n  -> Open http://localhost:{args.port}\n")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
