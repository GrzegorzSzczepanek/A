"""
LLM Classifier — classifies sections and generates DITA body XML.

Uses Claude API to:
1. Determine topic type (concept / task / reference)
2. Generate semantically rich DITA body content with proper elements
"""

import hashlib
import json
import os
import re
import urllib.request
from parser import Block
from pathlib import Path
from typing import Optional

# ── Cache ────────────────────────────────────────────────────────────────────

CACHE_DIR = Path(__file__).parent / ".cache"


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _cache_get(key: str) -> Optional[dict]:
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _cache_set(key: str, data: dict):
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ── DITA Rules System Prompt ─────────────────────────────────────────────────

SYSTEM_PROMPT = r"""You are an expert technical writer converting PDF content into DITA XML. You produce semantically rich, valid DITA 1.3 content.

## Your Task
Given a section title and its content blocks extracted from a PDF, you must:
1. Classify the section as one of: concept, task, or reference
2. Generate the DITA body XML content (the inner XML, NOT the root element or DOCTYPE)

## Classification Rules
- **concept**: Explanatory/descriptive content. Answers "what is X?" or "how does X work?". Contains paragraphs, definitions, overviews, workflow descriptions.
- **task**: Procedural content with numbered steps. Answers "how do I do X?". Contains imperative verbs ("click", "select", "run", "enter"), numbered procedures. If content has numbered steps with imperative commands, it is a task.
- **reference**: Lookup/tabular content. Settings tables, field descriptions, API references, parameter lists. If the primary content is a table of fields/settings, it is a reference.

## DITA Element Rules

### For ALL topic types, use these elements with EXACT @class attributes:

Paragraphs:
  <p class="- topic/p ">text</p>

Unordered lists:
  <ul class="- topic/ul "><li class="- topic/li "><p class="- topic/p ">item</p></li></ul>

Ordered lists:
  <ol class="- topic/ol "><li class="- topic/li "><p class="- topic/p ">item</p></li></ol>

Notes:
  <note class="- topic/note ">text</note>

Figures with images:
  <fig class="- topic/fig "><title class="- topic/title ">caption</title><image href="FILENAME" class="- topic/image "/></fig>
  If the source PDF has no caption for the image, use the placeholder title "Sample Image" (NOT the filename, NOT "Figure 1").

Cross-references:
  <xref href="URL_OR_FILE" class="- topic/xref ">link text</xref>
  For internal topic refs: <xref href="r_filename.dita" class="- topic/xref ">Topic Title</xref>
  For external links: <xref format="html" href="https://..." scope="external" class="- topic/xref ">link text</xref>

Code blocks:
  <codeblock class="+ topic/pre pr-d/codeblock ">code here</codeblock>

UI elements (USE THESE when text refers to UI controls, buttons, menu items):
  <uicontrol class="+ topic/ph ui-d/uicontrol ">Button Name</uicontrol>
  <wintitle class="+ topic/keyword ui-d/wintitle ">Panel or Window Name</wintitle>
  <menucascade class="+ topic/ph ui-d/menucascade "><uicontrol class="+ topic/ph ui-d/uicontrol ">Menu1</uicontrol><uicontrol class="+ topic/ph ui-d/uicontrol ">Menu2</uicontrol></menucascade>

Options/values:
  <option class="+ topic/keyword pr-d/option ">VALUE</option>

### concept body — wrap in <conbody>
Generate content wrapped in: <conbody class="- topic/body  concept/conbody ">

DO NOT wrap the entire conbody contents in a single <section>. <conbody> takes block children directly. Only use <section> when the source content contains a [SUBSECTION_TITLE] marker.

When the input contains `[SUBSECTION_TITLE level=N] Some Title`, emit a new
<section class="- topic/section "><title class="- topic/title ">Some Title</title>
...all blocks that follow it (until next [SUBSECTION_TITLE] or end) go INSIDE this section...
</section>

Inside conbody, you can use <p>, <section>, <note>, <fig>, <ul>, <ol>, <table>.

Example with subsection (input has [SUBSECTION_TITLE level=2] 2a-7 Workflow):
<conbody class="- topic/body  concept/conbody ">
  <p class="- topic/p ">First paragraph before any subsection.</p>
  <p class="- topic/p ">Second paragraph still before subsection.</p>
  <section class="- topic/section ">
    <title class="- topic/title ">2a-7 Workflow</title>
    <p class="- topic/p ">Paragraph inside subsection.</p>
    <note class="- topic/note ">Important note text.</note>
    <fig class="- topic/fig "><title class="- topic/title ">Sample Image</title><image href="image_1.png" class="- topic/image "/></fig>
  </section>
</conbody>

### task body — wrap in <taskbody>
Generate content wrapped in: <taskbody class="- topic/body task/taskbody ">

CRITICAL task structure (MUST follow this EXACT order):
1. <prereq class="- topic/section task/prereq "> (Optional)
2. <context class="- topic/section task/context "> (Optional)
3. <steps class="- topic/ol task/steps "> OR <steps-unordered> (Optional)
4. <result class="- topic/section task/result "> (Optional)
5. <example class="- topic/section task/example "> (Optional)

Each step MUST have:
  <step class="- topic/li task/step ">
    <cmd class="- topic/ph task/cmd ">Imperative command sentence.</cmd>
    <!-- Optional children: -->
    <info class="- topic/itemgroup task/info ">Additional info</info>
    <stepxmp class="- topic/itemgroup task/stepxmp ">Example content or <codeblock>...</codeblock></stepxmp>
    <stepresult class="- topic/itemgroup task/stepresult ">What you see after this step</stepresult>
  </step>

CRITICAL: <codeblock> CANNOT go directly inside <step>. It MUST be inside <info> or <stepxmp>.
CRITICAL: <p> CANNOT go directly inside <step>. Use <info> for extra paragraphs.
CRITICAL: <info>, <stepxmp>, and <stepresult> are ONLY allowed inside <step>. They CANNOT be used in <result> or <example>.
CRITICAL: Inside <result> and <example>, use standard block elements like <p>, <ul>, <ol>, <codeblock>, <table>.

Example:
<taskbody class="- topic/body task/taskbody ">
  <context class="- topic/section task/context ">Context paragraph.</context>
  <steps class="- topic/ol task/steps ">
    <step class="- topic/li task/step ">
      <cmd class="- topic/ph task/cmd ">Click <uicontrol class="+ topic/ph ui-d/uicontrol ">Submit</uicontrol>.</cmd>
      <info class="- topic/itemgroup task/info ">This is extra info for the step.</info>
    </step>
  </steps>
  <result class="- topic/section task/result ">
    <p class="- topic/p ">Result paragraph.</p>
  </result>
  <example class="- topic/section task/example ">
    <p class="- topic/p ">Example of result:</p>
    <codeblock class="+ topic/pre pr-d/codeblock ">some code</codeblock>
  </example>
</taskbody>

### reference body — wrap in <refbody>
Generate content wrapped in: <refbody class="- topic/body        reference/refbody ">

CRITICAL: <p> CANNOT go directly inside <refbody>. Wrap all content in <section class="- topic/section ">.

Tables use CALS format:
<table class="- topic/table ">
  <tgroup cols="N" class="- topic/tgroup ">
    <colspec colname="c1" colnum="1" class="- topic/colspec "/>
    <thead class="- topic/thead "><row class="- topic/row "><entry class="- topic/entry ">Header</entry></row></thead>
    <tbody class="- topic/tbody "><row class="- topic/row "><entry class="- topic/entry ">Cell</entry></row></tbody>
  </tgroup>
</table>

Use <uicontrol> for field names in settings tables.
Use <option> for enumerated values (like CNAV, VNAV, etc.).

## Content Transformation Rules
- Fix obvious typos (for example "Commisssion" -> "Commission", "prize comparison" -> "price comparison")
- Replace "i.e." with "that is"
- Replace "e.g." with "for example"
- Remove trailing "etc." or ", etc." from sentences (do not replace with anything). Also strip embedded ", etc." inside sentences.
- Preserve all original wording otherwise: do NOT rephrase or summarize
- Preserve all numbers, dates, codes, and identifiers exactly
- Preserve code block contents BYTE-FOR-BYTE: do not change indentation, spacing, quotes, or rewrite f-strings to .format() or vice versa. Copy the [CODE] block character-for-character into <codeblock>.

## STRICT FAITHFULNESS RULES (failing these forfeits the task)
1. DO NOT add introductory or summary sentences that are not in the source. NEVER prepend phrases like "This section provides an overview of...", "This topic describes...", "The following...". Start with the source's first sentence verbatim.
2. DO NOT replace source words with synonyms ("Master Fund" stays "Master Fund", "set up" stays "set up", NOT "Setting Up").
3. DO NOT add or remove technical specifiers. Preserve hyphenated compound terms exactly as written ("multi-step", "cost-to-market", "amortized-cost"). If the source has "cost-to-market value comparisons", emit "cost-to-market value comparisons" (NOT "cost to market value comparisons").
4. The <title> of the topic is the source heading verbatim ("Set Up Master Fund for 2a-7 Processing"), NOT a rephrased version ("Setting Up...").
5. Use ONLY the ASCII hyphen-minus character `-` (U+002D) in body text. DO NOT emit `‑` (U+2011 non-breaking hyphen), `–` (en-dash), `—` (em-dash), or any other dash variant. If the source PDF contained those, normalize them to `-`.
6. DO NOT insert decorative characters (em-dash, double dash `--`, fancy quotes) at the beginning of paragraphs or words. Body text starts with a letter or digit, not punctuation.

## DITA content model: conbody child ordering (CRITICAL for DITA-OT validation)
Inside <conbody>, all block-level children (<p>, <note>, <fig>, <ul>, <ol>, <table>, <codeblock>) MUST appear BEFORE any <section> element. After the first <section>, ONLY <section> or <example> elements are allowed. Layout your output accordingly:
CORRECT:
  <conbody>
    <p>...</p>
    <note>...</note>
    <fig>...</fig>
    <section><title>Sub</title><p>...</p></section>
  </conbody>
INCORRECT (will fail validation):
  <conbody>
    <p>...</p>
    <section>...</section>
    <note>...</note>   <-- note after section is invalid
  </conbody>

## Product Name Abstraction
If the user prompt notes a `product_name` (a company/brand acronym like "ABC"), DO NOT emit it as plain text.
Instead emit a key reference: <ph keyref="product-name" class="- topic/ph "/>
So "ABC's solution" becomes: <ph keyref="product-name" class="- topic/ph "/>'s solution

## Cross-reference detection (CRITICAL for tasks)
When body text says "see X" or "For more information, see X":
- If X matches an "other section in document": emit <xref href="<topic_filename>.dita" class="- topic/xref ">X</xref>
  (use the file naming rule: concept->c_, task->t_, reference->r_; lowercase, words separated by underscore)
- If X looks like a product name / brand reference ("Data and Analytics", a feature name, etc.): emit
  <xref format="html" href="https://www.bny.com/corporate/global/en/solutions/platforms/data-and-analytics.html" scope="external" class="- topic/xref ">X</xref>
  Only invent an external URL when the link is to a well-known product/site mentioned in the source.

## Task topic decomposition rules (CRITICAL)
For task topics, split the source content into these slots:
- **prereq** (before <steps>): sentences starting with "Before you begin", "Prerequisites", "First, ensure..." or any sentence describing what the user must do or have BEFORE the task. CRITICAL: if a paragraph contains both context and a "Before you begin" sentence, you MUST split that paragraph at the boundary so "Before you begin..." (and any sentence that follows it referring to setup that happens before the task starts) goes into <prereq>, while the rest goes into <context>. Both elements get the same hyperlinks (xref) from the original sentence.
- **context** (before <steps>): all other introductory paragraphs that explain *why* or *when* to perform the task. Strip the trailing "To do X:" sentence from context (it is not body content).
- **steps**: each numbered list item becomes a <step>. Any paragraphs between numbered items belong to the PRECEDING step:
  * Plain explanatory paragraph -> <info>
  * Paragraph describing what user sees ("You see the X panel", "The system displays...") -> <stepresult>
  * Code block -> <stepxmp><codeblock>...</codeblock></stepxmp>
  * Cross-reference "For more information, see Y" -> <info><xref ...>Y</xref></info>
- **result**: closing paragraph(s) starting with "After you", "Once you", "The system saves..." or similar outcome description

## UI element detection patterns (task and reference)
- "Click <Word>" or "Select <Word>" where Word is a button label -> <uicontrol>Word</uicontrol>
- "Setup > Portfolio > Mutual Funds > Create Master Fund" (chevron-separated path) -> <menucascade> with one <uicontrol> per segment
- "the Create Master Fund panel/window/dialog" -> <wintitle>Create Master Fund</wintitle> panel
- Enumerated values (CNAV, VNAV, IMMM, etc.) -> <option>VALUE</option>
- Trim whitespace inside <uicontrol>: NO leading/trailing spaces

## COMPLETE WORKED EXAMPLE: task topic

Source content (illustrative, similar to what you may receive):
  Section title: Set Up Master Fund for 2a-7 Processing
  Other sections in document: 2a-7 Processing Settings
  [PARAGRAPH] When you set up 2a-7 processing, you must set up several entity-level fields for each master fund that uses 2a-7 processing. You can use the Create Master Fund panel or the Edit Master Fund/Sector panel to set up master funds for 2a-7 processing. Before you begin, you can set up entity source rules that provide values for these fields. For more information, see Data and Analytics.
  [PARAGRAPH] To set up a master fund for 2a-7 processing:
  [LIST_ITEM] 1. In Accounting Center, in the left navigation pane, select Setup > Portfolio Setup > Mutual Funds > Create Master Fund.
  [PARAGRAPH] You see the Create Master Fund panel where you can add a master fund. Otherwise, you can select the Edit Master Fund/Sector option to change a master fund.
  [LIST_ITEM] 2. Complete the options on the panel, as appropriate.
  [PARAGRAPH] For more information about these options, see 2a-7 Processing Settings.
  [LIST_ITEM] 3. Click Submit.
  [LIST_ITEM] 4. In the command line, run the following code:
  [CODE] import random\nimport string\n...
  [PARAGRAPH] After you set up the master fund for 2a-7 processing and submit your changes, the system saves the updated master fund configuration and applies the 2a-7 processing settings to the selected fund.

Correct body_xml output:
<taskbody class="- topic/body task/taskbody "><prereq class="- topic/section task/prereq ">Before you begin, you can set up entity source rules that provide values for these fields. For more information, see <xref format="html" href="https://www.bny.com/corporate/global/en/solutions/platforms/data-and-analytics.html" scope="external" class="- topic/xref ">Data and Analytics</xref>.</prereq><context class="- topic/section task/context ">When you set up 2a-7 processing, you must set up several entity-level fields for each master fund that uses 2a-7 processing. You can use the <wintitle class="+ topic/keyword ui-d/wintitle ">Create Master Fund</wintitle> panel or the <wintitle class="+ topic/keyword ui-d/wintitle ">Edit Master Fund/Sector</wintitle> panel to set up master funds for 2a-7 processing.</context><steps class="- topic/ol task/steps "><step class="- topic/li task/step "><cmd class="- topic/ph task/cmd ">In Accounting Center, in the left navigation pane, select <menucascade class="+ topic/ph ui-d/menucascade "><uicontrol class="+ topic/ph ui-d/uicontrol ">Setup</uicontrol><uicontrol class="+ topic/ph ui-d/uicontrol ">Portfolio Setup</uicontrol><uicontrol class="+ topic/ph ui-d/uicontrol ">Mutual Funds</uicontrol><uicontrol class="+ topic/ph ui-d/uicontrol ">Create Master Fund</uicontrol></menucascade>.</cmd><stepresult class="- topic/itemgroup task/stepresult ">You see the Create Master Fund panel where you can add a master fund. Otherwise, you can select the <wintitle class="+ topic/keyword ui-d/wintitle ">Edit Master Fund/Sector</wintitle> option to change a master fund.</stepresult></step><step class="- topic/li task/step "><cmd class="- topic/ph task/cmd ">Complete the options on the panel, as appropriate.</cmd><info class="- topic/itemgroup task/info ">For more information about these options, see <xref href="r_2a7_processing_settings_.dita" class="- topic/xref ">2a-7 Processing Settings</xref>.</info></step><step class="- topic/li task/step "><cmd class="- topic/ph task/cmd ">Click <uicontrol class="+ topic/ph ui-d/uicontrol ">Submit</uicontrol>.</cmd></step><step class="- topic/li task/step "><cmd class="- topic/ph task/cmd ">In the command line, run the following code:</cmd><stepxmp class="- topic/itemgroup task/stepxmp "><codeblock class="+ topic/pre pr-d/codeblock ">import random
import string
from datetime import datetime
def generate_random_id(length=10, prefix="ID"):
    chars = string.ascii_uppercase + string.digits
    random_part = "".join(random.choice(chars) for _ in range(length))
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}-{random_part}"
if __name__ == "__main__":
    print(generate_random_id())</codeblock></stepxmp></step></steps><result class="- topic/section task/result ">After you set up the master fund for 2a-7 processing and submit your changes, the system saves the updated master fund configuration and applies the 2a-7 processing settings to the selected fund.</result></taskbody>

Note in the example:
- "Before you begin..." went to <prereq>, NOT <context>
- The trailing "To set up a master fund for 2a-7 processing:" sentence was dropped (it is a hand-off line, not content)
- Step 1's follow-up paragraph "You see the Create Master Fund panel..." became <stepresult> on step 1, NOT <result>
- Step 2's follow-up "For more information..." became <info><xref> on step 2
- "Submit" wrapped in <uicontrol>
- Codeblock indentation reconstructed from original Python (4-space indents inside def block)
- The closing "After you set up..." sentence is the topic-level <result>

## Reference table cell structure (CRITICAL)
Rules for <entry> contents:
- Simple cell with just text or just a number: put the text/number directly inside <entry>, with NO <p> wrapper.
  CORRECT:   <entry class="- topic/entry ">7584</entry>
  INCORRECT: <entry class="- topic/entry "><p class="- topic/p ">7584</p></entry>
- Cell with a UI control / field name (left column of a settings table): wrap in <uicontrol>:
  <entry class="- topic/entry "><uicontrol class="+ topic/ph ui-d/uicontrol ">Master Fund Type</uicontrol></entry>
- Cell with multiple structured elements (paragraphs + lists): use <p> AND <ul> as SIBLINGS inside <entry>, NEVER nest <ul> inside <p>.
  CORRECT:
  <entry class="- topic/entry "><p class="- topic/p ">Specifies the type of money market fund for the master fund.</p><p class="- topic/p ">Options include:</p><ul class="- topic/ul "><li class="- topic/li "><p class="- topic/p "><option class="+ topic/keyword pr-d/option ">CNAV</option> (Constant Net Asset Value Fund)</p></li><li class="- topic/li "><p class="- topic/p "><option class="+ topic/keyword pr-d/option ">VNAV</option> (Variable Net Asset Value Fund)</p></li></ul></entry>
  INCORRECT (do not do this): <p>Specifies... Options include: <ul>...</ul></p>

Header row cells (inside <thead>): plain text only, no <p>, no <uicontrol>.
  CORRECT: <entry class="- topic/entry ">Field Name</entry>

Do NOT flatten lists into inline text.

## Output Format
Return ONLY a JSON object (no markdown fences, no preamble):
{
  "topic_type": "concept" | "task" | "reference",
  "body_xml": "<conbody ...>...</conbody>",
  "reasoning": "brief explanation of classification"
}

The body_xml must be well-formed XML. Use &amp; for &, &lt; for <, &gt; for > in text content.
Do NOT include <?xml?> declaration or <!DOCTYPE> in body_xml.
"""


def _section_to_prompt(title: str, blocks: list[Block], doc_title: str = "",
                       all_section_titles: list[str] = None,
                       product_name: str = None,
                       topic_filenames: dict = None) -> str:
    """Build the user prompt from section data."""
    parts = [f"Document title: {doc_title}\n" if doc_title else ""]
    parts.append(f"Section title: {title}\n")

    if product_name:
        parts.append(
            f"product_name: {product_name} "
            f"(any literal mention of '{product_name}' in body text MUST be replaced with "
            f"<ph keyref=\"product-name\" class=\"- topic/ph \"/>)\n"
        )

    if all_section_titles:
        other = [t for t in all_section_titles if t != title]
        if other:
            parts.append(f"Other sections in this document (for cross-references): {', '.join(other)}\n")
            if topic_filenames:
                lines = []
                for t, fn in topic_filenames.items():
                    if t != title and fn:
                        lines.append(f'  "{t}" -> {fn}')
                if lines:
                    parts.append("Topic filename map (use for <xref href=>):\n" + "\n".join(lines) + "\n")

    parts.append("\nContent blocks (in document order):\n")
    for b in blocks:
        if b.type == "heading":
            # Subsection heading inside a merged concept - emit as <section><title>
            parts.append(f"[SUBSECTION_TITLE level={b.level}] {b.text}\n")
        elif b.type == "table":
            parts.append(f"[TABLE]\n{b.text}\n")
        elif b.type == "code":
            parts.append(f"[CODE]\n{b.text}\n")
        elif b.type == "image":
            parts.append(f"[IMAGE] filename: {b.text}\n")
        elif b.type == "list_item":
            parts.append(f"[LIST_ITEM] {b.text}\n")
        elif b.type == "note":
            parts.append(f"[NOTE] {b.text}\n")
        else:
            parts.append(f"[PARAGRAPH] {b.text}\n")

    return "".join(parts)


def _call_llm_api(system: str, user: str, api_key: str,
                  model: str = "gemini-2.5-pro",
                  provider: str = None) -> str:
    """Call LLM API via provider abstraction. Returns text response."""
    from llm_providers import call_llm
    return call_llm(system, user, api_key, model, provider)


def classify_section(title: str, blocks: list[Block], api_key: str,
                     doc_title: str = "", all_section_titles: list[str] = None,
                     model: str = "gemini-2.5-pro",
                     provider: str = None,
                     use_cache: bool = True,
                     product_name: str = None,
                     topic_filenames: dict = None) -> dict:
    """
    Classify a section and generate its DITA body XML.

    Returns: {
        "topic_type": "concept" | "task" | "reference",
        "body_xml": "<conbody>...</conbody>",
        "reasoning": "..."
    }
    """
    user_prompt = _section_to_prompt(
        title, blocks, doc_title, all_section_titles,
        product_name=product_name, topic_filenames=topic_filenames,
    )

    # Check cache
    if use_cache:
        key = _cache_key(user_prompt)
        cached = _cache_get(key)
        if cached:
            return cached

    # Call API
    response_text = _call_llm_api(SYSTEM_PROMPT, user_prompt, api_key, model, provider)

    # Parse JSON response — LLMs often break JSON when XML is inside string values
    clean = response_text.strip()

    # Strip markdown fences (Gemini wraps in ```json ... ```)
    clean = re.sub(r"^```\w*\s*\n?", "", clean)
    clean = re.sub(r"\n?\s*```\s*$", "", clean)
    clean = clean.strip()

    result = None

    # Attempt 1: direct parse
    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract JSON object with greedy match
    if result is None:
        try:
            match = re.search(r"\{[\s\S]*\}", clean)
            if match:
                result = json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Attempt 3: Gemini often breaks JSON by not escaping XML quotes in body_xml.
    # Extract fields individually with regex.
    if result is None:
        topic_match = re.search(r'"topic_type"\s*:\s*"(concept|task|reference)"', clean)
        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', clean)

        # body_xml: find the XML between body tags
        body_match = re.search(
            r'(<(?:conbody|taskbody|refbody)[\s\S]*?</(?:conbody|taskbody|refbody)>)',
            clean
        )

        if topic_match and body_match:
            result = {
                "topic_type": topic_match.group(1),
                "body_xml": body_match.group(1),
                "reasoning": reasoning_match.group(1) if reasoning_match else "regex extraction",
            }

    # Attempt 4: fallback (do NOT cache - we want a fresh attempt next run)
    if result is None:
        return {
            "topic_type": "concept",
            "body_xml": f'<conbody class="- topic/body  concept/conbody "><p class="- topic/p ">Content extraction failed.</p></conbody>',
            "reasoning": "Failed to parse LLM response"
        }

    # Post-process body_xml: clean up LLM faithfulness violations + Kimi quirks.
    if isinstance(result.get("body_xml"), str):
        # Kimi double-escapes quotes inside body_xml (turning `class="..."` into
        # `class=\"...\"` in the JSON string, which decodes to literal `\"` in
        # our parsed value). Undo the extra escape before any other processing.
        result["body_xml"] = result["body_xml"].replace('\\"', '"')
        result["body_xml"] = _strip_preamble(result["body_xml"])

    # Cache result
    if use_cache:
        _cache_set(key, result)

    return result


_PREAMBLE_RE = re.compile(
    r"(<p[^>]*>)\s*This\s+(?:section|topic|document|chapter|page)\s+"
    r"(?:provides|describes|outlines|explains|covers|presents|introduces|gives)\b"
    r"[^.]*\.\s*",
    flags=re.IGNORECASE,
)

# Invisible Unicode noise that LLMs sometimes hallucinate:
# U+200B zero-width space, U+200C ZWNJ, U+200D ZWJ, U+FEFF BOM,
# U+2060 word joiner, also &#x200b; entity form.
_INVISIBLE_RE = re.compile(r"[​-‍⁠﻿]|&#x?200[bBcCdD];")

# Trailing "etc." patterns: ", etc." or " etc." anywhere
_ETC_RE = re.compile(r",?\s+etc\.\s*", flags=re.IGNORECASE)


def _strip_preamble(body_xml: str) -> str:
    """Clean up LLM-injected faithfulness violations.

    Removes:
    - Preamble sentences like "This section provides an overview..."
    - Invisible Unicode characters hallucinated by the model
    - Embedded ", etc." sequences that the prompt says to drop
    """
    body_xml = _PREAMBLE_RE.sub(r"\1", body_xml, count=1)
    body_xml = _INVISIBLE_RE.sub("", body_xml)
    # Replace ", etc." inside sentences with nothing; preserve final period if any.
    # "X, etc. The next..." -> "X. The next..."
    # "X, etc." (sentence end) -> "X."
    body_xml = re.sub(r",\s+etc\.\s+", ". ", body_xml)
    body_xml = re.sub(r",\s+etc\.(?=[<\s]|$)", ".", body_xml)
    return body_xml


# ── Heuristic classifier (fallback / no-API mode) ────────────────────────────

def classify_section_heuristic(title: str, blocks: list[Block]) -> str:
    """
    Rule-based topic type classification (rule-based features).
    Returns: "concept" | "task" | "reference"
    """
    all_text = " ".join(b.text for b in blocks).lower()
    block_types = [b.type for b in blocks]

    # Reference indicators
    has_table = "table" in block_types
    table_ratio = block_types.count("table") / max(len(block_types), 1)
    if has_table and table_ratio > 0.3:
        return "reference"
    if any(kw in title.lower() for kw in ["settings", "parameters", "fields", "properties",
                                           "reference", "specifications", "configuration"]):
        return "reference"

    # Task indicators
    has_steps = "list_item" in block_types
    imperative_verbs = ["click", "select", "enter", "choose", "set up", "configure",
                        "create", "run", "open", "navigate", "submit", "complete",
                        "specify", "verify", "check", "type", "press"]
    imperative_count = sum(1 for v in imperative_verbs if v in all_text)
    step_heading_patterns = ["to set up", "to create", "to configure", "how to",
                             "procedure", "steps to"]
    has_step_heading = any(p in title.lower() for p in step_heading_patterns)

    if has_steps and imperative_count >= 2:
        return "task"
    if has_step_heading:
        return "task"

    # Default to concept
    return "concept"


# ── Topic planning (section merging) ─────────────────────────────────────────

PLANNING_PROMPT = """You are a DITA documentation architect. Given a list of PDF sections with their content summaries, decide how to group them into DITA topics.

Rules:
- Each DITA topic is one of: concept, task, or reference.
- Conceptual sections that logically belong together (overview + subsection) should be MERGED into one concept topic, with the subsection becoming a <section> within the concept's <conbody>.
- Task sections (procedures with steps) should be their own topic.
- Reference sections (settings tables, field descriptions) should be their own topic.
- A concept section followed by a related descriptive/workflow section at the same heading level should be merged.

CRITICAL: `topic_title` MUST be the FIRST source section's heading text VERBATIM. Do NOT rename, paraphrase, or "improve" titles. NEVER use phrases like "Understanding X", "Setting Up X", "X Reference", "X Overview" if the source did not. If sections "Manage 2a-7 Processing" and "2a-7 Workflow" are merged, the topic_title is "Manage 2a-7 Processing" (the first one's exact text).

Return ONLY a JSON array (no markdown fences):
[
  {
    "topic_title": "EXACT text of the first source section's heading",
    "topic_type": "concept" | "task" | "reference",
    "section_indices": [0, 1],  // which source sections to include
    "reasoning": "brief explanation"
  },
  ...
]
"""


def plan_topics(sections: list[dict], api_key: str,
                model: str = "gemini-2.5-pro",
                provider: str = None) -> list[dict]:
    """
    Plan how sections should be grouped into DITA topics.
    Returns a list of topic plans with section_indices.
    """
    # Build summary of sections
    summaries = []
    for i, sec in enumerate(sections):
        block_types = [b.type for b in sec["blocks"]]
        text_preview = " ".join(b.text[:100] for b in sec["blocks"][:3])
        summaries.append(
            f"Section {i}: \"{sec['title']}\" (level {sec['level']})\n"
            f"  Block types: {block_types}\n"
            f"  Content preview: {text_preview[:200]}"
        )

    user_prompt = "Sections to organize:\n\n" + "\n\n".join(summaries)

    # Check cache
    key = _cache_key(user_prompt)
    cached = _cache_get(key)
    if cached:
        return cached

    response_text = _call_llm_api(PLANNING_PROMPT, user_prompt, api_key, model, provider)

    # Parse response
    clean = response_text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```\w*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)

    try:
        plans = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", clean)
        if match:
            plans = json.loads(match.group())
        else:
            # Fallback: one topic per section
            plans = [
                {
                    "topic_title": sec["title"],
                    "topic_type": classify_section_heuristic(sec["title"], sec["blocks"]),
                    "section_indices": [i],
                    "reasoning": "fallback"
                }
                for i, sec in enumerate(sections)
            ]

    _cache_set(key, plans)
    return plans


def plan_topics_heuristic(sections: list[dict]) -> list[dict]:
    """
    Heuristic topic planning: merge consecutive concept sections.
    """
    plans = []
    i = 0
    while i < len(sections):
        sec = sections[i]
        topic_type = classify_section_heuristic(sec["title"], sec["blocks"])

        if topic_type == "concept":
            # Check if next sections are also concept at same level — merge
            merge_indices = [i]
            j = i + 1
            while j < len(sections):
                next_sec = sections[j]
                next_type = classify_section_heuristic(next_sec["title"], next_sec["blocks"])
                if next_type == "concept" and next_sec["level"] >= sec["level"]:
                    merge_indices.append(j)
                    j += 1
                else:
                    break

            plans.append({
                "topic_title": sec["title"],
                "topic_type": "concept",
                "section_indices": merge_indices,
                "reasoning": f"merged {len(merge_indices)} concept sections"
            })
            i = j
        else:
            plans.append({
                "topic_title": sec["title"],
                "topic_type": topic_type,
                "section_indices": [i],
                "reasoning": "standalone"
            })
            i += 1

    return plans
