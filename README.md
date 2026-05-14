# PDF-to-DITA Conversion Pipeline

**BNY AI in Finance Hackathon - May 14, 2026**

Automated conversion of PDF documentation to valid DITA 1.3 XML using a hybrid deterministic + LLM pipeline. Output passes DITA Open Toolkit (DITA-OT) HTML5 strict validation.

## Architecture

```
PDF -> [Parser] -> [Normalizer] -> [LLM Planner] -> [LLM Classifier] -> [Emitter] -> [DITA-OT Validator] -> .dita + .ditamap
```

**Seven-stage pipeline:**

1. **Ingestion** (`parser.py`): pdfplumber extracts layout-tagged blocks (headings by font-size, code by monospace font, tables, images). Images extracted via pypdf (no `pdfimages` dependency). Non-breaking hyphens rejoined to keep compound terms intact ("multi-step", "2a-7"). Paragraph breaks detected by vertical-gap heuristic.

2. **Normalization** (`parser.py:group_into_sections`): groups blocks into hierarchical sections under headings.

3. **Topic Planning** (`classifier.py:plan_topics`): LLM groups sections into DITA topics (concept/task/reference), preserving source titles verbatim.

4. **Classification + Semantic Annotation** (`classifier.py:classify_section`): LLM emits DITA body XML with `<uicontrol>`, `<menucascade>`, `<wintitle>`, `<option>`, `<xref>`, `<stepxmp>`, `<stepresult>`, etc. Includes a complete worked example in the system prompt.

5. **Emission** (`emitter.py`): wraps LLM body in DOCTYPE/root template. Post-processors fix common LLM quirks (Kimi double-escape, malformed attrs, preamble injection, content model order, inline-run fragmentation).

6. **Validation + Repair** (`emitter.py:validate_dita_ot`): DITA-OT 4.3 strict HTML5 build. Auto-detects local JDK 17+ and injects `JAVA_HOME` for the subprocess. On failure, repair agent runs (max 2 retries).

7. **Export**: collects `.dita` + `.ditamap` + images.

## Quick Start

```bash
# 1. One-time setup (Python deps + JDK 21 + DITA-OT 4.3.1 into ~/, no sudo)
./setup.sh
source ~/.zshrc

# 2. Add API key to .env (any one of these is enough)
echo 'KIMI_API_KEY=sk-...'        >> .env
echo 'GEMINI_API_KEY=AIza...'     >> .env
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env

# 3. Convert a PDF
python3 main.py "Sample File.pdf" -o output/sample --provider kimi --model moonshot-v1-32k

# 4. Validate with DITA-OT (use absolute path; DITA-OT resolves relative paths from its plugin dir, not CWD)
dita -i "$PWD/output/sample/m_*.ditamap" -f html5 -o /tmp/html5 --processing-mode=strict
```

## LLM Providers

The pipeline supports three LLM backends. Provider is auto-detected from the model name or environment variable, override with `--provider`.

| Provider | Env variable | Default model | Notes |
|----------|-------------|---------------|-------|
| Kimi | `KIMI_API_KEY` | `moonshot-v1-32k` | Default for this project. Reliable, ~16K-char system prompt fits comfortably. |
| Gemini | `GEMINI_API_KEY` | `gemini-2.5-flash` | Free tier 20 RPM (easy to exhaust during testing). |
| Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` | Premium quality. |

Retries on 429/5xx are automatic. Provider Retry-After headers are honored. Gemini's "retry in X.Xs" body hint is also parsed.

### Explicit provider selection

```bash
python3 main.py input.pdf --provider gemini --model gemini-2.5-flash
python3 main.py input.pdf --provider kimi   --model moonshot-v1-128k
python3 main.py input.pdf --provider claude --model claude-sonnet-4-20250514
python3 main.py input.pdf -k AIzaSy... --provider gemini
```

## Batch Processing

```bash
# Built-in batch script (Python)
python3 batch.py docs/*.pdf -o batch_output/

# Shell-level test runner (clearer per-file logs + TSV summary)
./test_runner.sh path/to/pdfs/ output/batch/
```

`test_runner.sh` emits a per-PDF log and a final TSV with `status, name, elapsed, dita-ot, rc, errors` per file.

## Heuristic Mode (no API key)

```bash
python3 main.py input.pdf -o output/
```

Pipeline works without an API key using rule-based classification (imperative verbs, list structure, table density, heading keywords). Output quality is much lower without semantic elements like `<uicontrol>`. Use only as a fallback.

## Project Structure

```
pdf2dita/
  main.py            - Entry point + 7-stage orchestration
  parser.py          - PDF -> structured blocks (pdfplumber + pypdf)
  classifier.py      - LLM classification + DITA body generation + post-processors
  emitter.py         - DITA XML emission + ditamap + DITA-OT validation + repair
  llm_providers.py   - Multi-provider LLM abstraction with retry/backoff/throttle
  batch.py           - Multi-PDF batch processing (Python)
  test_runner.sh     - Multi-PDF runner with TSV summary
  evaluate.py        - Metrics against a reference output
  demo_server.py     - FastAPI demo
  demo_ui.html       - Browser UI
  setup.sh           - Environment setup (JDK + DITA-OT)
  requirements.txt   - Python dependencies
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PDF parser | pdfplumber (MIT) | Layout-aware, no AGPL risk (vs PyMuPDF) |
| Image extractor | pypdf (BSD-3) | Avoids poppler-utils binary dependency |
| LLM role | Topic planning + classification + body XML | Rules handle structure; LLM handles semantics |
| Multi-provider | Kimi / Gemini / Claude | Cost flexibility; same prompt works across all |
| XML emission | LLM body + template wrapper | LLM-generated XML fails ~12% without guardrails; template root ensures DOCTYPE/class correctness |
| Validation | DITA-OT 4.3 + lxml + JDK auto-detect | DITA-OT exit codes unreliable; regex log parsing is the standard |
| Caching | SHA-256 content hash | Same section -> same output; cheap re-runs |
| Determinism | `temperature=0` everywhere | Diff-based regression testing |
| License | All MIT/Apache-2.0/BSD-3 | No AGPL/GPL/cloud-only deps |

## Evaluation Metrics

- **DITA-OT pass rate**: binary, must be 100% (it is, on the organizer's sample).
- **Element-type distribution**: count of `<uicontrol>`, `<menucascade>`, `<option>`, `<wintitle>`, `<codeblock>`, etc.
- **Structural F1**: topic/section tree match against reference.
- **Content faithfulness**: source-text coverage + hallucination rate; preamble injection blocked by post-processor.
- **Numerical exact-match**: regex verification of numbers, dates, codes.

## Sample Validation Result

On `Sample File: Manage 2a-7 Processing.pdf` (4 pages, 4 sections):

- **DITA-OT HTML5 strict: PASS** (rc=0, zero warnings or errors).
- 3 topics emitted: concept + task + reference, plus ditamap with `<keydef keys="product-name">`.
- 114 total elements, **100% with `@class` attribute**.
- Semantic richness: `uicontrol`=10, `option`=5, `wintitle`=3, `menucascade`=1, `codeblock`=1.
- Image extracted and referenced as `<fig><title>Sample Image</title><image href="image_1.png"/></fig>`.

See `SOLUTION_OVERVIEW.md` for the full architecture write-up, including the 14 LLM-quirk patches embedded in the pipeline.
