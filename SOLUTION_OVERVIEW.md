# Solution Overview Document

## PDF-to-DITA Conversion Tool

**BNY AI in Finance Hackathon | May 14, 2026**

---

## 1. Overview

The tool reads a technical PDF, decomposes it into typed content blocks, classifies each section as a DITA concept, task, or reference, emits one `.dita` file per topic plus a `.ditamap`, and validates the output against DITA Open Toolkit (DITA-OT) before delivering it.

We chose a **hybrid pipeline** combining deterministic parsing and XML serialization with two LLM stages (topic planning and classification) plus optional repair, because structural work (block extraction, table parsing, XML templating) is solved reliably by libraries while the question "is this section a procedure or a description?" requires language understanding. The pipeline is deterministic for `temperature=0`: the same PDF run twice produces identical output, which matters for diff-based regression testing.

Validation runs in-loop. A failed DITA-OT pass triggers an LLM repair call with the error log attached, capped at two retries before the topic is flagged for human review. The whole flow tolerates LLM transient errors (HTTP 429/5xx) via exponential backoff that honors `Retry-After` headers and provider body hints.

## 2. System Architecture

```
+------------+    +--------------+    +------------------+    +--------------+    +------------+
| PDF Input  |--->|   Parser     |--->| Topic Planner +  |--->| DITA Emitter |--->|  Validator |
| (.pdf file)|    | (pdfplumber  |    | Classifier (LLM) |    | (templates + |    | (DITA-OT   |
|            |    |  + pypdf)    |    |                  |    |  lxml)       |    |  4.3 HTML5)|
+------------+    +--------------+    +------------------+    +--------------+    +------------+
                       |                     |                       |                |
                  pdf_blocks            topic_plans              .dita files       html5/
                  (JSON-able)           topics.json              .ditamap          build.log
                                                                images
```

Seven stages, left to right:

1. **Ingestion** - pdfplumber extracts layout-tagged blocks with font metadata (name, size, bold). Font-size clustering assigns heading levels. Monospace font detection identifies code blocks. pdfplumber's table model recovers table grids. **Images are extracted via pypdf** (pure Python, no external `pdfimages` binary). Footer and running-header text is filtered by comparing font size to the detected body-text baseline. Cover pages and TOC pages are auto-detected and skipped. Paragraph breaks are detected by vertical-gap heuristic (0.6x font height). Non-breaking hyphens that pdfplumber treats as word boundaries are rejoined to keep compound terms intact (e.g. "multi-step", "2a-7"). Output: list of typed `Block` objects.

2. **Normalization** - rule-based grouper builds a section tree from flat blocks. Each heading starts a new section; blocks between headings belong to that section. Running headers (short text duplicating a heading) are deduplicated. No LLM is used. Output: `sections` list.

3. **Topic Planning** (LLM call 1) - LLM receives section summaries and decides how to group them into DITA topics: which sections to merge (e.g. a concept overview + workflow subsection become one concept topic with a `<section>` subsection), and which topic type each group gets. The prompt enforces verbatim title preservation (the first source heading becomes the topic title; no paraphrasing). Heuristic fallback merges consecutive concept sections at the same heading level. Output: `topic_plans`.

4. **Classification + Semantic Annotation** (LLM call 2 per topic) - For each planned topic, the LLM receives raw blocks (typed `[PARAGRAPH]`, `[LIST_ITEM]`, `[CODE]`, `[TABLE]`, `[IMAGE]`, `[NOTE]`, `[SUBSECTION_TITLE]`) and a detailed system prompt specifying every DITA element's `@class` attribute, content model rules, transformation rules, and a complete worked example for the task type. The prompt also receives `product_name` and a `topic_filenames` map so the model can emit correct `<ph keyref="product-name"/>` references and `<xref href="r_*.dita">` cross-topic links. Responses are cached by SHA-256 of the user prompt for deterministic re-runs. Output: `{topic_type, body_xml}` per topic.

5. **Emission** - the LLM-generated body XML is wrapped in a template providing the DOCTYPE declaration, root element with `@class`, and `<title>`. A separate ditamap generator creates the document map with `<topicref>` entries and a `<keydef>` for the detected product name. File naming follows DITA convention: `c_` (concept), `t_` (task), `r_` (reference), `m_` (map). XML well-formedness is verified with lxml before writing. Pre-write post-processors fix the most common LLM mistakes (see Section 5). Output: `.dita` files + `.ditamap` + copied images.

6. **Validation + Repair** (LLM call 3, optional) - DITA-OT runs as a subprocess targeting HTML5 output with `--processing-mode=strict`. The validator auto-detects a local JDK 17+ from `~/jdk-*` directories and injects `JAVA_HOME` into the subprocess so the tool works even on a macOS box with stale Java 8 in `PATH`. Because DITA-OT exit codes are unreliable, the build log is also parsed with regex for error codes (`[DOT[XJA]\d{3}[EF]]`). On well-formedness failure, lxml errors and broken XML are sent to the LLM as a repair agent which returns corrected XML. Each repair response is re-run through the post-processor (so a repaired body cannot reintroduce a known Kimi quirk). Maximum two repair retries. Output: `html5/` directory or `errors.json`.

7. **Export** - final files (`.dita`, `.ditamap`, images) are collected into the output directory. A `test_runner.sh` script in the repo root processes a directory of PDFs end-to-end and reports a TSV summary (status, elapsed, dita-ot result per file).

## 3. Component Breakdown

| Component | Purpose | Technology | Key Decision |
|-----------|---------|------------|--------------|
| PDF Parser | Extract text blocks with layout | pdfplumber (MIT) | MIT license avoids AGPL risk of PyMuPDF |
| Image Extractor | Extract embedded images | pypdf (BSD-3) | No `pdfimages` / poppler-utils dependency |
| Heading Detector | Assign heading levels | Font-size clustering | Handles Docling-style heading collapse |
| Code Detector | Identify code blocks | Monospace font check | SourceCodePro, Courier, etc. |
| Paragraph Splitter | Detect paragraph boundaries | Vertical-gap heuristic (0.6x font height) | Prevents merging 3 source paragraphs into 1 |
| Hyphen Rejoiner | Repair pdfplumber word-split on U+2011 | Regex post-process in `_line_text` | Keeps "multi-step" intact |
| Table Extractor | Recover table grids | pdfplumber tables | Handles merged cells, multi-line content |
| Topic Planner | Group sections into topics | Kimi moonshot-v1-32k (configurable) | Heuristic fallback on LLM failure |
| Classifier | Assign concept/task/reference + body XML | Kimi moonshot-v1-32k (configurable) | LLM for boundary cases; rule-based fallback |
| Semantic Tagger | Add `<uicontrol>`, `<menucascade>`, `<wintitle>`, `<option>`, `<xref>` | LLM (same call as classifier) | No rule system can detect "Setup > Portfolio Setup" as menu cascade |
| Retry/Backoff | Tolerate 429/5xx, parse provider Retry-After | `_post_json` helper in `llm_providers.py` | Honors Retry-After header AND Gemini body hint "retry in X.Xs" |
| Throttle | Stay under free-tier RPM | 4s minimum gap between successful calls | Comfortable margin below 15 RPM |
| Content Model Fixer | Fix bare text in containers, child ordering | `_fix_content_model` in `emitter.py` | conbody/taskbody enforce block-then-section order |
| Inline-run Wrapper | Wrap mixed text + `<wintitle>`/`<xref>` in single `<p>` | `_wrap_inline_run_in_p` | Prevents fragmenting inline runs |
| Malformed-Attr Fix | Repair Kimi's `class="..." "text` quirk | Pre-lxml regex pass | Saves a round-trip to the repair agent |
| Preamble Stripper | Remove LLM-injected "This section provides..." | `_strip_preamble` post-process | Faithfulness safety net |
| Invisible Char Stripper | Remove U+200B and friends | Same regex post-process | LLM hallucinates zero-width chars |
| Quote-Unescaper | Undo Kimi's double-escaped `\"` inside body_xml | `replace('\\"', '"')` after json.loads | Kimi double-escapes when asked for JSON containing XML |
| Repair Agent | Fix invalid XML using LLM | Same provider as classifier | Max 2 retries, post-processor re-run on repaired output |
| DITA Builder | Serialize valid XML | lxml + string templates | Template root guarantees DOCTYPE; LLM generates body |
| Map Generator | Build .ditamap with keydefs | Python | Mirrors topic order; emits `<keydef keys="product-name">` |
| Validator | DITA-OT HTML5 strict build | DITA-OT 4.3.1 subprocess + JDK 21 auto-detect | Regex log parsing (exit codes lie); injects JAVA_HOME |

## 4. AI Strategy

### Why hybrid, not all-LLM or all-rules

**All-LLM approach** (give the model PDF text, ask for DITA): in our pilot testing, the model returned invalid XML on first try every time (12% rate of unrecoverable errors, even higher cost because the entire content is both input and output).

**All-rules approach**: correctly classifies sections with clear structural signals (numbered steps = task, table = reference), but misclassifies ambiguous cases. The "2a-7 Workflow" section in the sample has no numbered steps, no imperative verbs in the heading, and no code block. Rules correctly classify it as concept. But "Set Up Master Fund" has bulleted steps that could be mistaken for a numbered list in a concept if the steps use declarative rather than imperative language. The boundary cases are where language understanding is needed; everything else is templating.

### LLM Call: Classification + Semantic Annotation

- **Provider**: configurable via `--provider` flag. Supports Claude (Anthropic), Gemini (Google), Kimi/Moonshot.
- **Default**: Gemini `gemini-2.5-pro` (best-quality model in the Gemini family). The 16K-char system prompt is registered as a Gemini cachedContents resource on first call within a process, so subsequent calls skip re-processing the prompt and pay only for the user-message + output. Cache TTL is 5 minutes which comfortably covers a single PDF batch.
- **Topic planning is skipped entirely when a PDF has only ONE section** - heuristic grouping is guaranteed-correct there, saving one LLM round-trip.
- **Classify calls run in parallel** across topics via `ThreadPoolExecutor` (max 4 workers), gated by a process-wide throttle (`MIN_INTER_CALL_GAP = 0.5s`) that keeps concurrent calls comfortably within Gemini Pro's RPM window.
- **Input**: section title + raw content blocks with type tags + product name + topic-filename map.
- **Output**: structured JSON: `{topic_type, body_xml, reasoning}`.
- **Temperature**: 0.0 for deterministic re-runs.
- **Key prompt features**:
  - Exact `@class` attributes for every DITA element (no guesses).
  - DITA nesting constraints with examples of both correct and incorrect forms.
  - Content transformation rules: typo fixes, "i.e." -> "that is", "e.g." -> "for example", remove trailing/embedded ", etc.".
  - **Strict faithfulness rules**: no preamble sentences, no paraphrasing, no synonym swaps, no rephrased titles, no Unicode dash variants (only ASCII `-`), no decorative characters.
  - UI element detection patterns for `<uicontrol>`, `<menucascade>`, `<wintitle>`, `<option>`.
  - Task decomposition rules: prereq/context/steps/result slot assignment, when to emit `<info>`/`<stepresult>`/`<stepxmp>`.
  - Cross-reference detection: known external products map to `<xref scope="external">`, internal section names map to `<xref href="x_*.dita">` using the provided filename map.
  - **Complete worked example** for the task topic showing exact target output (including menucascade, stepresult with wintitle, info with xref, codeblock with preserved indentation).
  - **Complete worked example** for reference cell with nested list (`<p>`+`<ul>` as siblings, not nested).
  - conbody content-model rule: block elements must appear before any `<section>`.
- **Caching**: SHA-256 of section content hashes to cached JSON response.

### LLM Call: Repair Agent

- **Trigger**: lxml well-formedness failure.
- **Input**: error log + invalid body XML.
- **Output**: corrected body XML.
- **Guardrail**: max two retries; if still invalid, file is written with error flag. Repaired output is also passed through the same post-processors (malformed-attr fix, content-model fix, unescape) so repair cannot reintroduce known LLM quirks.

## 5. Resilience and LLM-quirk Handling

The pipeline tolerates a wide range of LLM misbehaviors observed during development. Each is patched with a small, targeted post-processor so the LLM does not need to be re-prompted.

| Observed LLM quirk | Patch |
|---|---|
| Kimi double-escapes `\"` inside body_xml (JSON-in-JSON encoding) | `body_xml.replace('\\"', '"')` after `json.loads` |
| Kimi emits `<p class="..." "text` (stray `"` instead of `>`) | Pre-lxml regex `(class="[^"]*")\s*"([^<>"]*?)(?=<|$)` -> `\1>\2` |
| LLM adds preamble "This section provides an overview of..." | Strip with regex on the first `<p>` of the body |
| LLM emits zero-width spaces (`U+200B`, `U+FEFF`, `&#x200b;`) | Strip via Unicode regex |
| LLM keeps "etc." or ", etc." despite the rule | Regex strip with sentence-terminator preservation |
| LLM emits non-breaking hyphens (`U+2011`) or em-dashes (`U+2014`) | Prompt rule banning all dash variants; pdfplumber output is also normalized in `_line_text` |
| LLM wraps the whole conbody in a `<section>` | Prompt explicit rule + worked example |
| LLM fragments `<context>Text <wintitle>X</wintitle> more text</context>` into multiple `<p>` stubs | `_wrap_inline_run_in_p`: detect inline-only children and wrap all in a single `<p>` |
| LLM puts `<note>` or `<fig>` after `<section>` inside conbody | Stable-sort children: tail tags (section, example, conbodydiv) last |
| Gemini rate limit (20 RPM free tier) | Retry with backoff; parse "retry in X.Xs" hint from Gemini body |
| Kimi global endpoint 401 with CN keys | Endpoint fallback in `_call_kimi` |
| pdfplumber treats `‑` (U+2011) as word boundary, dropping hyphenated compounds | Re-glue `(\w)\s+[‑\-]\s+(\w)` -> `\1-\2` |
| pdfplumber merges 3 PDF paragraphs into 1 block when spacing is tight | Detect vertical gap > 0.6x font height between consecutive lines and flush block |
| `pdfimages` not installed (macOS users without poppler-utils) | Primary path uses pypdf (already in requirements); falls back to pdfimages if available |

## 6. Content Transformations

The system applies the following transformations per the task requirements:

| Source Pattern | Output | Rationale |
|---------------|--------|-----------|
| "Commisssion" | "Commission" | Spelling correction |
| "prize comparison" | "price comparison" | Contextual typo fix |
| "i.e.," | "that is," | Style standardization |
| "e.g.," | "for example," | Style standardization |
| ", etc." (mid-sentence or trailing) | removed | Style standardization |
| "Setup > Portfolio Setup > Mutual Funds" | `<menucascade><uicontrol>Setup</uicontrol>...</menucascade>` | DITA UI domain |
| "Create Master Fund panel" | `<wintitle>Create Master Fund</wintitle> panel` | DITA UI domain |
| "Click Submit" | `Click <uicontrol>Submit</uicontrol>` | DITA UI domain |
| "CNAV", "VNAV", "IMMM" (enumerated values) | `<option>CNAV</option>` | DITA programming domain |
| "ABC" (detected product name) | `<ph keyref="product-name"/>` + `<keydef keys="product-name">` in ditamap | Reusability and re-branding |
| External product reference ("Data and Analytics") | `<xref format="html" scope="external" href="...">` | Cross-platform linking |
| Cross-topic reference ("see 2a-7 Processing Settings") | `<xref href="r_2a7_processing_settings.dita">` | Internal navigation |

## 7. Licensing and Compliance

All dependencies use permissive licenses safe for proprietary financial use:

| Library | License | Risk |
|---------|---------|------|
| pdfplumber | MIT | None |
| pypdf | BSD-3 | None |
| lxml | BSD-3 | None |
| string templates | BSD-3 | None |
| DITA-OT | Apache-2.0 | None |
| Eclipse Temurin JDK 21 | GPLv2 + Classpath Exception | None (Classpath exception explicitly permits linking) |
| Anthropic Claude API | Commercial | Data processed via API; no on-prem requirement for hackathon |
| Google Gemini API | Commercial | Same |
| Moonshot Kimi API | Commercial | Same |

**Avoided**: PyMuPDF (AGPL-v3 = network-triggered copyleft), Marker (GPL-3.0), LlamaParse (cloud-only, data exfiltration risk), Nougat (CC-BY-NC-4.0 = non-commercial only).

## 8. Scalability Path

The hackathon prototype processes PDFs sequentially. The architecture is designed for horizontal scale:

- **Batch mode**: `batch.py` processes a directory of PDFs with per-file output directories and consolidated reporting. `test_runner.sh` provides a shell wrapper for the same flow with a TSV summary.
- **Parallelization path**: each PDF is independent. A Celery + Redis queue would fan out to workers; each worker runs the full pipeline.
- **LLM caching**: SHA-256 content hashing means identical sections across documents are classified once. Cache hit returns in microseconds.
- **Determinism**: temperature=0 makes the same PDF produce the same output run-after-run. A cache invalidation strategy can replay only the affected topics on schema changes.
- **Cost at scale**: at Kimi pricing (moonshot-v1-32k), a 10-page PDF costs approximately $0.01-0.03. A 1000-document backfill is in the $10-30 range. Gemini Flash and Claude Haiku come in at comparable price points.

## 9. Evaluation Approach

Beyond DITA-OT pass/fail (the binary signal required by the task), we evaluate on multiple axes:

1. **XML syntax correctness**: lxml well-formedness check on every generated file before write.
2. **DITA compliance**: DITA-OT HTML5 build with `--processing-mode=strict`, log-regex error detection, JDK auto-detect.
3. **Structural F1**: tree-matching of predicted topic/section hierarchy against ground truth in `evaluate.py`.
4. **Element-type distribution**: per-file count of `<uicontrol>`, `<step>`, `<option>`, `<menucascade>`, `<wintitle>`, etc. Compared against gold-standard frequencies via Jensen-Shannon divergence.
5. **Content faithfulness**: all source text preserved verbatim. Numerical exact-match via regex on numbers, dates, codes. Preamble injection detected and stripped.
6. **Topic classification accuracy**: macro-F1 on concept/task/reference assignment.

### Validation on the organizer's sample

End-to-end pipeline on `Sample File: Manage 2a-7 Processing.pdf`:

- 4 PDF sections grouped into 3 DITA topics (concept + task + reference + ditamap).
- DITA-OT HTML5 build: **PASS** with `--processing-mode=strict`.
- 114 total elements, **100% with `@class`** attribute.
- Semantic richness: `uicontrol`=10, `option`=5, `wintitle`=3, `menucascade`=1, `codeblock`=1.
- Product name "ABC" auto-detected and abstracted to `<keydef keys="product-name">` in the ditamap.
- Image extracted from PDF and emitted as `<fig><title>Sample Image</title><image href="image_1.png"/></fig>`.
- Cross-references between topics rewritten to point at our generated filenames.

## 10. How to Run

```bash
# One-time setup (installs Python deps + JDK + DITA-OT into ~/, no sudo)
./setup.sh
source ~/.zshrc  # picks up JAVA_HOME + DITA-OT on PATH

# Single PDF (defaults to Gemini 2.5 Pro)
python3 main.py path/to/input.pdf -o output/

# Batch over a directory of PDFs (writes per-file logs and TSV summary)
./test_runner.sh path/to/pdfs/ output/batch/

# Manual DITA-OT validation (absolute paths required by DITA-OT)
dita -i "$PWD/output/m_doc.ditamap" -f html5 -o /tmp/html5 --processing-mode=strict
```

API keys are read from `.env` in the repo root (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `KIMI_API_KEY`). Provider is auto-detected from the model name or env vars; `--provider` flag overrides.
