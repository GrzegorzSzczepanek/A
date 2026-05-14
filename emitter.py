"""
DITA Emitter — generates valid .dita files and .ditamap from classified sections.

Handles:
- Wrapping body XML in proper DOCTYPE and root element
- File naming conventions (c_, t_, r_ prefixes)
- Ditamap generation with topicref hierarchy and keydefs
- XML well-formedness validation via lxml
- DITA-OT validation (if available)
"""

import json
import random
import re
import subprocess
from pathlib import Path
from typing import Optional

from lxml import etree

# ── File naming ──────────────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    """Convert title to a filename-safe slug."""
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9\s_-]", "", s)
    s = re.sub(r"[\s-]+", "_", s)
    s = re.sub(r"_+", "_", s)  # collapse multiple underscores
    s = s.strip("_")
    return s[:60]


def topic_filename(title: str, topic_type: str) -> str:
    """Generate DITA filename with type prefix."""
    prefix = {"concept": "c", "task": "t", "reference": "r"}.get(topic_type, "c")
    slug = _slugify(title)
    return f"{prefix}_{slug}.dita"


def _random_id() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


# ── DITA topic wrappers ─────────────────────────────────────────────────────

TOPIC_TEMPLATES = {
    "concept": {
        "doctype": '<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">',
        "root_open": '<concept id="concept-{id}" xml:lang="en-us" class="- topic/topic concept/concept ">',
        "root_close": "</concept>",
    },
    "task": {
        "doctype": '<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">',
        "root_open": '<task id="task-{id}" xml:lang="en-us" class="- topic/topic task/task ">',
        "root_close": "</task>",
    },
    "reference": {
        "doctype": '<!DOCTYPE reference PUBLIC "-//OASIS//DTD DITA Reference//EN" "reference.dtd">',
        "root_open": '<reference id="reference-{id}" xml:lang="en-us" class="- topic/topic       reference/reference ">',
        "root_close": "</reference>",
    },
}


def wrap_dita_topic(title: str, body_xml: str, topic_type: str,
                    shortdesc: str = "", keywords: list = None) -> str:
    """Wrap body XML in a complete DITA topic document.

    Emits, in spec-mandated order: <title>, <shortdesc> (3.2.1.6),
    <prolog><metadata><keywords> (3.2.2.18), then the body.
    """
    tmpl = TOPIC_TEMPLATES.get(topic_type, TOPIC_TEMPLATES["concept"])
    topic_id = _random_id()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        tmpl["doctype"],
        tmpl["root_open"].format(id=topic_id),
        f'<title class="- topic/title ">{_xml_escape(title)}</title>',
    ]

    if shortdesc and shortdesc.strip():
        lines.append(
            f'<shortdesc class="- topic/shortdesc ">{_xml_escape(shortdesc.strip())}</shortdesc>'
        )

    keywords = [k for k in (keywords or []) if isinstance(k, str) and k.strip()]
    if keywords:
        kw_xml = "".join(
            f'<keyword class="- topic/keyword ">{_xml_escape(k)}</keyword>'
            for k in keywords
        )
        lines.append(
            '<prolog class="- topic/prolog ">'
            '<metadata class="- topic/metadata ">'
            f'<keywords class="- topic/keywords ">{kw_xml}</keywords>'
            '</metadata>'
            '</prolog>'
        )

    lines.extend([body_xml, tmpl["root_close"]])
    return "\n".join(lines)


def _xml_escape(text: str) -> str:
    """Escape special XML characters in text content."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── Ditamap generation ───────────────────────────────────────────────────────

def generate_ditamap(doc_title: str, topics: list[dict],
                     product_name: str = None) -> str:
    """
    Generate a DITA map file.

    topics: list of {"filename": str, "title": str, "topic_type": str}
    """
    map_id = f"ditamap-{_random_id()}"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE map PUBLIC "-//OASIS//DTD DITA Map//EN" "map.dtd">',
        f'<map id="{map_id}" class="- map/map ">',
        f'<title class="- topic/title ">{_xml_escape(doc_title)}</title>',
    ]

    for topic in topics:
        lines.append(f'<topicref href="{topic["filename"]}" class="- map/topicref "/>')

    # Add keydef for product name if detected
    if product_name:
        lines.append(f'<keydef keys="product-name" class="+ map/topicref mapgroup-d/keydef ">')
        lines.append(f'<topicmeta class="- map/topicmeta ">')
        lines.append(f'<keywords class="- topic/keywords ">')
        lines.append(f'<keyword class="- topic/keyword ">{_xml_escape(product_name)}</keyword>')
        lines.append(f'</keywords>')
        lines.append(f'</topicmeta>')
        lines.append(f'</keydef>')

    lines.append("</map>")
    return "\n".join(lines)


def ditamap_filename(doc_title: str) -> str:
    slug = _slugify(doc_title)
    return f"m_{slug}.ditamap"


# ── XML Validation ───────────────────────────────────────────────────────────

def validate_xml_wellformedness(xml_string: str) -> tuple[bool, str]:
    """Check if XML is well-formed using lxml. Returns (is_valid, error_message)."""
    try:
        etree.fromstring(xml_string.encode("utf-8"))
        return True, ""
    except etree.XMLSyntaxError as e:
        return False, str(e)


def _detect_local_jdk17_home() -> Optional[str]:
    """Find a JDK 17+ on disk (DITA-OT 4.x needs it). Returns path to JAVA_HOME or None."""
    import os
    # If JAVA_HOME is already set and points to >= JDK 17, trust it.
    jh = os.environ.get("JAVA_HOME")
    if jh and Path(jh).joinpath("bin/java").exists():
        try:
            out = subprocess.run([str(Path(jh) / "bin" / "java"), "-version"],
                                 capture_output=True, text=True, timeout=5).stderr
            # JDK 17/21/etc all start with the major version. JDK 8 is "1.8.x".
            if "1.8." not in out and 'version "1.' not in out:
                return jh
        except Exception:
            pass
    # Otherwise scan ~/jdk-* directories (Temurin tarball layout).
    candidates = sorted(Path.home().glob("jdk-*"), reverse=True)
    for c in candidates:
        java_home = c / "Contents" / "Home"
        if not java_home.exists():
            java_home = c  # Linux layout
        if (java_home / "bin" / "java").exists():
            return str(java_home)
    return None


def validate_dita_ot(output_dir: str, ditamap_file: str,
                     dita_ot_path: str = None) -> tuple[bool, str]:
    """
    Run DITA-OT validation on the output.
    Returns (passed, log_output).
    """
    import os
    # Find DITA-OT
    if dita_ot_path is None:
        # Search for DITA-OT using glob (handles any version)
        search_dirs = [Path.home(), Path("/opt")]
        for search_dir in search_dirs:
            matches = sorted(search_dir.glob("dita-ot*/bin/dita"), reverse=True)
            if matches:
                dita_ot_path = str(matches[0])  # newest version first
                break

    if dita_ot_path is None:
        # Try PATH
        try:
            result = subprocess.run(["which", "dita"], capture_output=True, text=True)
            if result.returncode == 0:
                dita_ot_path = result.stdout.strip()
        except FileNotFoundError:
            pass

    if dita_ot_path is None:
        return False, "DITA-OT not found. Install from https://www.dita-ot.org/"

    ditamap_path = Path(output_dir).resolve() / ditamap_file
    html_output = Path(output_dir).resolve() / "html5_output"
    html_output.mkdir(exist_ok=True)

    # DITA-OT 4.x needs Java 17+. If the inherited env has Java 8 (macOS default),
    # subprocess will fail with UnsupportedClassVersionError. Detect a local JDK
    # and inject it into the subprocess env so the tool works out of the box.
    env = os.environ.copy()
    jdk_home = _detect_local_jdk17_home()
    if jdk_home:
        env["JAVA_HOME"] = jdk_home
        env["PATH"] = f"{jdk_home}/bin:" + env.get("PATH", "")

    try:
        result = subprocess.run(
            [dita_ot_path, "-i", str(ditamap_path), "-f", "html5",
             "-o", str(html_output), "--processing-mode=strict"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        log = result.stdout + "\n" + result.stderr

        # Check for errors in log (exit codes are unreliable)
        error_pattern = re.compile(r"\[DOT[XJA]\d{3}[EF]\]")
        errors = error_pattern.findall(log)

        # Also catch general build failures
        if not errors and "Build failed" in log:
            errors = ["Build failed"]

        if errors:
            return False, log
        if result.returncode != 0:
            return False, log
        return True, log

    except subprocess.TimeoutExpired:
        return False, "DITA-OT validation timed out"
    except FileNotFoundError:
        return False, f"DITA-OT binary not found at {dita_ot_path}"


# ── Repair agent ─────────────────────────────────────────────────────────────

REPAIR_PROMPT = """You are a DITA XML repair agent. The following DITA XML failed validation.
Fix the XML to be valid DITA 1.3. Common issues:
- <p> directly inside <refbody> (must be wrapped in <section>)
- <codeblock> directly inside <step> (must be inside <info> or <stepxmp>)
- <p> directly inside <step> (must be inside <info>)
- Block elements inside <shortdesc> (only phrase-level allowed)
- <section> nested inside <section> in concept (forbidden)
- Missing @class attributes

Return ONLY the corrected XML body (the conbody/taskbody/refbody element), no explanation."""


def repair_xml(body_xml: str, error_msg: str, api_key: str,
               model: str = "claude-sonnet-4-20250514",
               provider: str = None) -> Optional[str]:
    """Attempt to repair invalid DITA XML using LLM."""
    from llm_providers import call_llm

    user_prompt = f"Error: {error_msg}\n\nXML to fix:\n{body_xml}"
    try:
        response = call_llm(REPAIR_PROMPT, user_prompt, api_key, model, provider)
        # Strip markdown fences
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        return clean
    except Exception as e:
        print(f"  Repair failed: {e}")
        return None


# ── Write output ─────────────────────────────────────────────────────────────

# ── Content model post-processor ─────────────────────────────────────────────

# DITA elements that require block children (no bare text)
_BLOCK_REQUIRED = {
    "result", "context", "prereq", "section", "conbody",
    "refbody", "taskbody", "steps", "info", "stepxmp", "stepresult",
}

# DITA inline (phrase-level) tags. When a block-required container holds only
# these (plus text), the whole content needs to be wrapped in a SINGLE <p>,
# not split across multiple <p> elements.
_INLINE_TAGS = {
    "uicontrol", "menucascade", "wintitle", "option", "ph", "b", "i", "u",
    "sub", "sup", "term", "q", "image", "xref", "cite", "fn", "keyword",
    "codeph", "varname", "parmname", "filepath", "userinput", "systemoutput",
    "cmdname", "msgnum", "msgph", "synph", "tm", "abbreviated-form",
}


def _wrap_inline_run_in_p(elem) -> bool:
    """If a block-required container has only inline children + text,
    wrap the whole inner content in a single <p>. Returns True if modified.
    """
    children = list(elem)
    has_text = bool(elem.text and elem.text.strip())
    if not children and not has_text:
        return False

    # Check if all children are inline tags
    inline_only = all(
        etree.QName(c.tag).localname in _INLINE_TAGS for c in children
    )
    if not (has_text or inline_only):
        return False
    # If there are children but some have non-inline tails, we can't easily wrap
    if children and any(c.tail and c.tail.strip() and not inline_only for c in children):
        return False

    p = etree.Element("p")
    p.set("class", "- topic/p ")
    p.text = elem.text
    elem.text = None
    for c in children:
        # Move child to p, preserving tail
        elem.remove(c)
        p.append(c)
    elem.append(p)
    return True

_MALFORMED_ATTR_RE = re.compile(r'(\bclass="[^"]*")\s*"([^<>"]*?)(?=<|$)')

# Detect `<word` patterns that look like nested DITA tags accidentally placed
# inside an attribute value (LLMs do this when describing DITA syntax in body).
# E.g. `class="..." href="see <topic>"` is invalid - we escape the inner `<`.
_TAG_IN_ATTR_RE = re.compile(r'(="[^"]*?)<([a-zA-Z][\w-]*[\s/>])')


def _fix_malformed_attrs(body_xml: str) -> str:
    """Fix LLM-emitted XML quirks before lxml parsing.

    Patches:
    - `<p class="..." "text...` -> `<p class="...">text...` (stray `"` instead of `>`)
    - Literal `\"` from Kimi double-escape -> `"`
    - Unescaped `<` inside attribute values (e.g. when LLM writes `href="<topic>"`)
      -> `&lt;` (escaped). lxml fails parsing otherwise.
    """
    # Strip literal backslash before quote (Kimi double-escape leftover).
    body_xml = body_xml.replace('\\"', '"')
    body_xml = _MALFORMED_ATTR_RE.sub(r"\1>\2", body_xml)
    # Escape `<` inside attribute values. Loop in case multiple per attribute.
    prev = None
    while body_xml != prev:
        prev = body_xml
        body_xml = _TAG_IN_ATTR_RE.sub(r"\1&lt;\2", body_xml)
    return body_xml


def _fix_empty_tgroup(body_xml: str) -> str:
    """Ensure every <tgroup> contains a <tbody>.

    DITA's CALS table spec requires `(colspec*, thead?, tbody)`. LLMs sometimes
    emit a <tgroup> with only <thead> (no <tbody>), which fails DITA-OT with
    [DOTJ013E]. We inject an empty <tbody> immediately before </tgroup> when
    one is missing.
    """
    def fix_one(m):
        block = m.group(0)
        if "<tbody" in block:
            return block
        # Insert empty tbody before </tgroup>
        return block.replace(
            "</tgroup>",
            '<tbody class="- topic/tbody "><row class="- topic/row "><entry class="- topic/entry "/></row></tbody></tgroup>',
        )
    return re.sub(r"<tgroup[\s\S]*?</tgroup>", fix_one, body_xml)


import textwrap

def _wrap_text(text: Optional[str], width: int = 80, indent: str = "") -> Optional[str]:
    if not text or len(text) <= width:
        return text
    # Wrap text while preserving existing newlines if they look intentional,
    # but for LLM output they are usually just one long run.
    wrapped = textwrap.fill(text, width=width, initial_indent=indent,
                            subsequent_indent=indent, break_long_words=False,
                            replace_whitespace=False)
    return wrapped

def _fix_content_model(body_xml: str) -> str:
    """
    Fix common DITA content model violations in LLM-generated XML.

    Repairs:
    - Bare text in container elements → wrapped in <p>
    - <p> directly in <refbody> → wrapped in <section>
    - <codeblock>/<p> directly in <step> → wrapped in <info>
    - Line wrapping for text nodes > 80 chars
    """
    body_xml = _fix_malformed_attrs(body_xml)
    # Collapse duplicate close tags that LLMs emit on table cells, e.g.
    # `<entry>foo</entry></entry>`. Cheap regex sweep before lxml sees it,
    # so recovery mode doesn't reorganize rows in surprising ways.
    body_xml = re.sub(r"</entry>\s*</entry>", "</entry>", body_xml)
    body_xml = re.sub(r"</row>\s*</row>", "</row>", body_xml)
    body_xml = _fix_empty_tgroup(body_xml)
    try:
        root = etree.fromstring(f"<_root>{body_xml}</_root>".encode("utf-8"))
    except etree.XMLSyntaxError:
        # Last-resort: parse with libxml2 recovery (drops unbalanced tags).
        # Better a slightly-truncated table than the entire topic failing.
        try:
            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(
                f"<_root>{body_xml}</_root>".encode("utf-8"), parser=parser
            )
            if root is None:
                return body_xml
            # Re-serialize to get balanced XML back.
            body_xml = "".join(
                etree.tostring(c, encoding="unicode") for c in root
            ) + (root.text or "")
            # Re-parse the recovered form to continue with content-model fixes.
            root = etree.fromstring(f"<_root>{body_xml}</_root>".encode("utf-8"))
        except etree.XMLSyntaxError:
            return body_xml  # genuinely unrecoverable

    modified = False

    for elem in root.iter():
        tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""

        # Wrap long text nodes (except in codeblock)
        if tag != "codeblock":
            if elem.text and len(elem.text.strip()) > 80:
                elem.text = _wrap_text(elem.text.strip())
                modified = True
            if elem.tail and len(elem.tail.strip()) > 80:
                elem.tail = _wrap_text(elem.tail.strip())
                modified = True

        # Fix 1: when a block-required container holds only inline content
        # (plus text), wrap everything in a single <p>. This preserves the
        # inline run (text + <uicontrol> + text + <xref> + ...) intact instead
        # of fragmenting it into multiple <p> stubs.
        if tag in _BLOCK_REQUIRED:
            if _wrap_inline_run_in_p(elem):
                modified = True
            else:
                # Mixed block + inline: wrap bare leading text in <p>, and
                # wrap each tail-text run after a block child in its own <p>.
                if elem.text and elem.text.strip():
                    p = etree.Element("p")
                    p.set("class", "- topic/p ")
                    p.text = elem.text
                    elem.text = None
                    elem.insert(0, p)
                    modified = True

                for child in list(elem):
                    if child.tail and child.tail.strip():
                        p = etree.Element("p")
                        p.set("class", "- topic/p ")
                        p.text = child.tail
                        child.tail = None
                        idx = list(elem).index(child) + 1
                        elem.insert(idx, p)
                        modified = True

        # Fix 2: <p> directly in <refbody> → wrap in <section>
        if tag == "refbody":
            p_children = [c for c in elem if c.tag == "p"]
            if p_children:
                section = etree.Element("section")
                section.set("class", "- topic/section ")
                for p in p_children:
                    elem.remove(p)
                    section.append(p)
                elem.insert(0, section)
                modified = True

        # Fix 3: <codeblock> or <p> directly in <step> → wrap in <info>
        if tag == "step":
            # Ensure cmd is present. If missing, turn first p into cmd or invent one.
            children = list(elem)
            has_cmd = any(etree.QName(c.tag).localname == "cmd" for c in children)
            if not has_cmd:
                # Find first child that could be a cmd (text or p)
                if elem.text and elem.text.strip():
                    cmd = etree.Element("cmd")
                    cmd.set("class", "- topic/ph task/cmd ")
                    cmd.text = elem.text
                    elem.text = None
                    elem.insert(0, cmd)
                    modified = True
                elif children and etree.QName(children[0].tag).localname == "p":
                    p = children[0]
                    p.tag = "cmd"
                    p.set("class", "- topic/ph task/cmd ")
                    modified = True
                else:
                    cmd = etree.Element("cmd")
                    cmd.set("class", "- topic/ph task/cmd ")
                    cmd.text = "Complete this step."
                    elem.insert(0, cmd)
                    modified = True

            # Fix order: cmd must be first (after notes).
            # Then wrap other block elements in info.
            bad_children = [c for c in elem if etree.QName(c.tag).localname in ("codeblock", "p")]
            if bad_children:
                info = etree.Element("info")
                info.set("class", "- topic/itemgroup task/info ")
                for c in bad_children:
                    elem.remove(c)
                    info.append(c)
                elem.append(info)
                modified = True

        # Fix 4: conbody content model: all block-level children MUST come
        # before any <section>/<example>. DITA-OT rejects p/note/fig/table
        # appearing after a section. We stable-sort to enforce this.
        if tag == "conbody":
            children = list(elem)
            tail_tags = {"section", "example", "conbodydiv"}
            def conbody_order(c):
                t = etree.QName(c.tag).localname if isinstance(c.tag, str) else ""
                return 1 if t in tail_tags else 0
            new_children = sorted(children, key=conbody_order)
            if new_children != children:
                for c in children:
                    elem.remove(c)
                for c in new_children:
                    elem.append(c)
                modified = True

        # Fix 5: taskbody element order and forbidden children
        if tag == "taskbody":
            # 1. Unwrap forbidden <section> children
            sections = [c for c in elem if etree.QName(c.tag).localname == "section"]
            for s in sections:
                # Change section to example if it has a title "Example"
                s_title = s.find("title")
                if s_title is not None and s_title.text and "example" in s_title.text.lower():
                    s.tag = "example"
                    s.set("class", "- topic/section task/example ")
                else:
                    # Unwrap: move children to parent, remove section
                    idx = list(elem).index(s)
                    for child in reversed(list(s)):
                        s.remove(child)
                        elem.insert(idx, child)
                    elem.remove(s)
                modified = True

            # 2. Move direct <p> or <note> or <fig> or <table> children into context or result
            # DITA Taskbody only allows specific section-like elements.
            bad_task_children = [c for c in elem if etree.QName(c.tag).localname in ("p", "note", "fig", "table", "ul", "ol", "codeblock")]
            if bad_task_children:
                # Find if we have steps
                steps_idx = -1
                for i, c in enumerate(elem):
                    if etree.QName(c.tag).localname in ("steps", "steps-unordered", "steps-informal"):
                        steps_idx = i
                        break

                for c in bad_task_children:
                    idx = list(elem).index(c)
                    elem.remove(c)
                    if steps_idx == -1 or idx < steps_idx:
                        # Move to context
                        context = elem.find("context")
                        if context is None:
                            context = etree.Element("context")
                            context.set("class", "- topic/section task/context ")
                            elem.insert(0, context)
                            # Update steps_idx because we inserted an element
                            if steps_idx != -1: steps_idx += 1
                        context.append(c)
                    else:
                        # Move to result
                        result = elem.find("result")
                        if result is None:
                            result = etree.Element("result")
                            result.set("class", "- topic/section task/result ")
                            elem.append(result)
                        result.append(c)
                modified = True

            # 3. Define desired order
            order = ["prereq", "context", "steps", "steps-unordered", "result", "tasktroubleshooting", "example", "postreq"]
            children = list(elem)
            def get_order(c):
                t = etree.QName(c.tag).localname if isinstance(c.tag, str) else ""
                try: return order.index(t)
                except ValueError: return 99
            new_children = sorted(children, key=get_order)
            if new_children != children:
                for c in children: elem.remove(c)
                for c in new_children: elem.append(c)
                modified = True

        # Fix 6: No nested sections. DITA forbids <section> inside <section>.
        if tag == "section":
            nested = [c for c in elem if etree.QName(c.tag).localname == "section"]
            if nested:
                parent = elem.getparent()
                if parent is not None:
                    # Move nested sections to be siblings of the current section
                    idx = list(parent).index(elem) + 1
                    for n in reversed(nested):
                        elem.remove(n)
                        parent.insert(idx, n)
                    modified = True

        # Fix 7: Image href extensions. LLMs sometimes guess .png when it's .jpg
        if tag == "image":
            href = elem.get("href")
            if href and "." in href:
                base = href.rsplit(".", 1)[0]
                # We don't have easy access to output_dir here, but we can
                # normalize extensions if the LLM used a likely wrong one.
                # Actually, a better place for this is in write_output where
                # we know the output directory.
                pass

    if not modified:
        return body_xml

    # Serialize back, stripping wrapper
    result = etree.tostring(root, encoding="unicode", pretty_print=True)
    result = re.sub(r"^<_root>", "", result)
    result = re.sub(r"</_root>\s*$", "", result)
    return result


def write_output(output_dir: str, doc_title: str,
                 classified_sections: list[dict],
                 product_name: str = None,
                 api_key: str = None,
                 model: str = "gemini-3.1-flash-lite",
                 provider: str = None) -> dict:
    """
    Write all DITA files and ditamap to output_dir.

    classified_sections: list of {
        "title": str,
        "topic_type": str,
        "body_xml": str,
    }

    Returns: {"files": [filenames], "errors": [error_messages], "ditamap": filename}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = []
    errors = []
    topic_list = []

    for section in classified_sections:
        title = section["title"]
        topic_type = section["topic_type"]
        body_xml = section["body_xml"]
        shortdesc = section.get("shortdesc", "")
        keywords = section.get("keywords", [])
        fname = topic_filename(title, topic_type)

        # Post-process: fix common DITA content model violations
        body_xml = _fix_content_model(body_xml)

        # Fix image extensions based on what's actually on disk (or in image_dir)
        # This prevents DOTX008E when LLM guesses .png but it's .jpg
        image_dir = out / "images"
        if image_dir.exists():
            def fix_img_href(m):
                href = m.group(2)
                if not (image_dir / href).exists():
                    base = href.rsplit(".", 1)[0]
                    for ext in [".jpg", ".jpeg", ".png", ".gif"]:
                        if (image_dir / (base + ext)).exists():
                            return f'{m.group(1)}href="{base + ext}"'
                return m.group(0)
            body_xml = re.sub(r'(<image[^>]+)href="([^"]+)"', fix_img_href, body_xml)

        # Build full topic XML
        full_xml = wrap_dita_topic(title, body_xml, topic_type,
                                   shortdesc=shortdesc, keywords=keywords)

        # Final pretty-print of the entire document
        try:
            # Strip DOCTYPE for parsing, then re-add it
            clean_xml = re.sub(r"<!DOCTYPE[^>]+>", "", full_xml)
            root = etree.fromstring(clean_xml.encode("utf-8"))
            pretty_xml = etree.tostring(root, encoding="unicode", pretty_print=True)
            
            # Find DOCTYPE from templates
            tmpl = TOPIC_TEMPLATES.get(topic_type, TOPIC_TEMPLATES["concept"])
            doctype = tmpl["doctype"]
            full_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n{doctype}\n{pretty_xml}'
        except Exception as e:
            print(f"  ⚠ Final pretty-print failed: {e}")

        # Validate well-formedness
        # Need to strip DOCTYPE for lxml parsing (no DTD available locally)
        xml_for_validation = re.sub(r"<!DOCTYPE[^>]+>", "", full_xml)
        is_valid, error = validate_xml_wellformedness(xml_for_validation)

        if not is_valid and api_key:
            print(f"  ⚠ XML validation failed for {fname}: {error}")
            for attempt in range(2):
                print(f"  → Repair attempt {attempt + 1}/2...")
                repaired = repair_xml(body_xml, error, api_key, model, provider)
                if repaired:
                    # Run the same malformed-attribute and content-model fixes on
                    # the repaired XML before validating, so we don't waste retries
                    # on the same Kimi quirks that the original output had.
                    repaired = _fix_content_model(repaired)
                    full_xml = wrap_dita_topic(title, repaired, topic_type,
                                               shortdesc=shortdesc, keywords=keywords)
                    xml_check = re.sub(r"<!DOCTYPE[^>]+>", "", full_xml)
                    is_valid, error = validate_xml_wellformedness(xml_check)
                    if is_valid:
                        print(f"  ✓ Repair successful on attempt {attempt + 1}")
                        body_xml = repaired
                        break
                    else:
                        print(f"  ✗ Attempt {attempt + 1} still invalid: {error}")
                        body_xml = repaired  # use latest attempt for next retry
                else:
                    print(f"  ✗ Repair returned nothing on attempt {attempt + 1}")
                    break
            if not is_valid:
                errors.append(f"{fname}: repair failed after 2 attempts - {error}")

        elif not is_valid:
            errors.append(f"{fname}: {error}")

        # Write file
        filepath = out / fname
        filepath.write_text(full_xml, encoding="utf-8")
        files.append(fname)
        topic_list.append({
            "filename": fname,
            "title": title,
            "topic_type": topic_type,
        })
        print(f"  ✓ {fname} ({topic_type})")

    # Generate and write ditamap
    map_fname = ditamap_filename(doc_title)
    map_xml = generate_ditamap(doc_title, topic_list, product_name)
    (out / map_fname).write_text(map_xml, encoding="utf-8")
    files.append(map_fname)
    print(f"  ✓ {map_fname} (ditamap)")

    return {"files": files, "errors": errors, "ditamap": map_fname}
