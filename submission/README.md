# Submission package

Everything BNY asks for in one folder. Drop this directory onto the
portable drive.

| File | What it is |
|---|---|
| **`SUBMISSION.pdf`** | The deliverable — the presentation-ready document covering items (a)–(d) from the task description with diagrams, charts, code excerpts, and a one-page exec summary. |
| `SUBMISSION.html` | Same content as the PDF, viewable in a browser. Embedded images, no external dependencies. |
| `SUBMISSION.md` | Source markdown that produced the PDF/HTML. Lets jury verify nothing is hidden. |
| `build_assets.py` | Reproducible asset pipeline. Re-runs Mermaid → PNG via mermaid.ink + matplotlib charts. |
| `images/*.png` | All 16 diagrams and charts that the document embeds. |

## To rebuild the PDF

```bash
python3 submission/build_assets.py        # regenerates images/*.png
pandoc submission/SUBMISSION.md \
    -o submission/SUBMISSION.html \
    --standalone --embed-resources \
    --css submission/style.css
# then headless Chrome / Brave to convert HTML → PDF
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
    --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
    --print-to-pdf=submission/SUBMISSION.pdf \
    "file://$PWD/submission/SUBMISSION.html"
```

## Cross-references (jury convenience)

| Task-description requirement | Where in the deliverable |
|---|---|
| (a) Solution Overview Document | `SUBMISSION.pdf` §(a), plus richer detail in `../SOLUTION_OVERVIEW.md` |
| (b) Code used | `SUBMISSION.pdf` §(b), plus the full repo at <https://github.com/GrzegorzSzczepanek/AI-Finance> |
| (c) Automated Workflows | `SUBMISSION.pdf` §(c), plus `../Makefile`, `../run_demo.sh`, `../.github/workflows/ci.yml` |
| (d) AI Assets | `SUBMISSION.pdf` §(d), plus the system prompts inside `../classifier.py` and `../emitter.py` |
| Cost / ROI / scaling | `SUBMISSION.pdf` §(c.6) and §(d.8), plus `../BUSINESS_CASE.md` |
