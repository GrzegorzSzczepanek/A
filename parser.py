"""
PDF Parser — extracts structured blocks from a PDF.

Each block has:
  - type: heading | paragraph | list_item | code | table | note | image
  - text: raw text content
  - level: heading level (1-based) for headings
  - page: page number
  - meta: extra info (font, ordinal, table rows, image path, ...)
"""

import re
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import pdfplumber


@dataclass
class Block:
    type: str  # heading, paragraph, list_item, code, table, note, image
    text: str
    page: int
    level: int = 0
    meta: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def _is_monospace(fontname: str) -> bool:
    mono_indicators = ["courier", "mono", "consolas", "sourcecode", "firacode",
                       "menlo", "inconsolata", "dejavu sans mono", "code"]
    fn = fontname.lower()
    return any(m in fn for m in mono_indicators)


def _is_bold(fontname: str) -> bool:
    return "bold" in fontname.lower()


def _detect_heading_sizes(pages) -> dict[float, int]:
    """Analyze font sizes across the document to assign heading levels."""
    size_counts: dict[float, int] = {}
    for page in pages:
        words = page.extract_words(extra_attrs=["fontname", "size"])
        for w in words:
            fn = w.get("fontname", "")
            sz = round(w.get("size", 0), 1)
            if _is_bold(fn) and sz > 12:
                size_counts[sz] = size_counts.get(sz, 0) + 1

    # Sort descending — largest bold font = H1, next = H2, etc.
    sorted_sizes = sorted(size_counts.keys(), reverse=True)
    return {sz: i + 1 for i, sz in enumerate(sorted_sizes)}


def _extract_words_grouped(page) -> list[dict]:
    """Extract words with font info, grouped into text lines by y-position."""
    words = page.extract_words(
        extra_attrs=["fontname", "size"],
        keep_blank_chars=True,
        y_tolerance=3,
        x_tolerance=3,
    )
    if not words:
        return []

    # Group words into lines by y-position (top coordinate)
    lines = []
    current_line = []
    last_top = None
    y_tol = 4

    for w in sorted(words, key=lambda x: (round(x["top"], 1), x["x0"])):
        if last_top is None or abs(w["top"] - last_top) < y_tol:
            current_line.append(w)
        else:
            if current_line:
                lines.append(current_line)
            current_line = [w]
        last_top = w["top"]
    if current_line:
        lines.append(current_line)

    return lines


def _line_text(line_words: list[dict]) -> str:
    """Reconstruct text from a line of words.

    pdfplumber's word extractor treats `‑` (U+2011 non-breaking hyphen) as a
    word boundary, splitting "multi‑step" into ["multi", "‑", "step"]. We
    rejoin these so the source compound stays intact, normalizing to ASCII `-`.
    """
    raw = " ".join(w["text"] for w in line_words).strip()
    # Rejoin compound words split around a non-breaking hyphen or stray ASCII hyphen.
    # Pattern: word, space, hyphen-char, space, word -> word-word.
    # Loop to handle chained compounds like "cost ‑ to ‑ market".
    prev = None
    while raw != prev:
        prev = raw
        raw = re.sub(r"(\w)\s+[‑\-]\s+(\w)", r"\1-\2", raw)
    return raw


def _dominant_font(line_words: list[dict]) -> tuple[str, float]:
    """Get the most common font in a line."""
    font_chars: dict[tuple, int] = {}
    for w in line_words:
        key = (w.get("fontname", ""), round(w.get("size", 0), 1))
        font_chars[key] = font_chars.get(key, 0) + len(w["text"])
    if not font_chars:
        return ("", 0.0)
    return max(font_chars.items(), key=lambda x: x[1])[0]


def _is_footer(text: str, page_num: int) -> bool:
    """Detect page footers."""
    t = text.strip().lower()
    if re.match(r"^page\s+\d+", t):
        return True
    if re.match(r"^sample file:", t):
        return True
    if t.endswith(f"page {page_num}"):
        return True
    return False


def _is_header(text: str) -> bool:
    """Detect running headers (repeated section titles at top of page)."""
    t = text.strip()
    # Very short text at top of page that matches a heading pattern
    return len(t) < 60 and not t.endswith(".")


IMAGE_TARGET_WIDTH = 1000  # px
IMAGE_MAX_BYTES = 200 * 1024  # 200 KB cap per spec


def _optimize_image(path: Path) -> None:
    """Resize image to <=1000px wide and compress until <=200KB on disk.

    Operates in place. For PNGs that won't shrink below the byte cap even at
    width 1000, we re-encode as JPEG (quality steps 85→60). Alpha channels are
    flattened on a white background before JPEG fallback. Silent no-op on any
    error — image extraction shouldn't break the whole pipeline.
    """
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        with Image.open(path) as im:
            im.load()
            orig_mode = im.mode
            # 1. Width cap
            if im.width > IMAGE_TARGET_WIDTH:
                ratio = IMAGE_TARGET_WIDTH / im.width
                new_size = (IMAGE_TARGET_WIDTH, max(1, int(im.height * ratio)))
                im = im.resize(new_size, Image.LANCZOS)

            ext = path.suffix.lower()

            # 2. Try keeping the original format first (best quality for PNG line-art).
            if ext in (".png", ".gif"):
                im.save(path, optimize=True)
                if path.stat().st_size <= IMAGE_MAX_BYTES:
                    return
                # Fall through to JPEG fallback for photographic content.
                if orig_mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
                    im = bg
                else:
                    im = im.convert("RGB")
                jpg_path = path.with_suffix(".jpg")
                for quality in (85, 75, 65, 60):
                    im.save(jpg_path, "JPEG", quality=quality, optimize=True, progressive=True)
                    if jpg_path.stat().st_size <= IMAGE_MAX_BYTES:
                        break
                path.unlink(missing_ok=True)
                return

            # JPEG path
            if im.mode != "RGB":
                im = im.convert("RGB")
            for quality in (85, 75, 65, 60, 50):
                im.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
                if path.stat().st_size <= IMAGE_MAX_BYTES:
                    return
    except Exception:
        return


def extract_images(pdf_path: str, output_dir: str) -> dict[int, list[str]]:
    """Extract images from PDF.

    Primary path: pypdf (pure Python, already in requirements).
    Fallback: pdfimages (poppler-utils) if available.
    Returns {page_num: [image_paths]}.

    After extraction, each image is optimized: width capped at
    IMAGE_TARGET_WIDTH px, byte size capped at IMAGE_MAX_BYTES (PNGs that
    can't compress under the cap are re-encoded as JPEG).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    page_map: dict[int, list[str]] = {}

    # Path 1: pypdf (default) - no external binary needed
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            try:
                images = page.images
            except Exception:
                images = []
            for img_idx, img in enumerate(images):
                # img has .name and .data
                ext = Path(img.name).suffix.lower() or ".png"
                # Normalize extension - some PDFs report .jpg, some .jp2, etc.
                if ext not in (".png", ".jpg", ".jpeg", ".gif"):
                    ext = ".png"
                # Sequential numbering across the whole document (image_1, image_2 ...)
                seq = sum(len(v) for v in page_map.values()) + 1
                out_path = output_dir / f"image_{seq}{ext}"
                try:
                    out_path.write_bytes(img.data)
                    page_map.setdefault(page_num, []).append(str(out_path))
                except Exception:
                    continue
        if page_map:
            _optimize_extracted(page_map)
            return page_map
    except Exception:
        page_map = {}

    # Path 2: pdfimages (poppler-utils) - optional, if installed
    prefix = str(output_dir / "img")
    try:
        subprocess.run(
            ["pdfimages", "-png", pdf_path, prefix],
            capture_output=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    try:
        result = subprocess.run(
            ["pdfimages", "-list", pdf_path],
            capture_output=True, text=True, check=True,
        )
        img_idx = 0
        for line in result.stdout.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) >= 2:
                page_num = int(parts[0])
                img_file = f"{prefix}-{img_idx:03d}.png"
                if Path(img_file).exists():
                    page_map.setdefault(page_num, []).append(img_file)
                    img_idx += 1
    except Exception:
        for f in sorted(output_dir.glob("img-*.png")):
            page_map.setdefault(0, []).append(str(f))

    _optimize_extracted(page_map)
    return page_map


def _optimize_extracted(page_map: dict[int, list[str]]) -> None:
    """Run image optimization on every path recorded in `page_map`. The map
    keys may be reassigned if a file extension changes (PNG→JPEG fallback)."""
    for page_num, paths in list(page_map.items()):
        new_paths = []
        for p in paths:
            pth = Path(p)
            _optimize_image(pth)
            # JPEG fallback may have renamed .png → .jpg
            if not pth.exists():
                jpg = pth.with_suffix(".jpg")
                if jpg.exists():
                    new_paths.append(str(jpg))
                    continue
            new_paths.append(str(pth))
        page_map[page_num] = new_paths


def parse_pdf(pdf_path: str, image_output_dir: str = None) -> list[Block]:
    """
    Parse a PDF into a list of structured Blocks.

    Returns blocks in document order with types:
    heading, paragraph, list_item, code, table, note, image
    """
    blocks: list[Block] = []
    pdf_path = str(pdf_path)

    # Extract images first
    img_dir = image_output_dir or str(Path(pdf_path).parent / "images")
    page_images = extract_images(pdf_path, img_dir)

    with pdfplumber.open(pdf_path) as pdf:
        heading_sizes = _detect_heading_sizes(pdf.pages)

        # Get table bounding boxes to exclude table text from line extraction
        for page_idx, page in enumerate(pdf.pages):
            page_num = page_idx + 1

            # Skip cover pages and TOC pages (detected by content, not page number)
            page_text = page.extract_text() or ""
            lines = page_text.strip().split("\n")

            # TOC detection: page contains "table of contents" with many dotted lines
            if any("table of contents" in l.lower() for l in lines):
                continue

            # Cover page detection: dominant font is very large (title page)
            all_words = page.extract_words(extra_attrs=["size"])
            if all_words:
                sizes = [w.get("size", 0) for w in all_words]
                avg_size = sum(sizes) / len(sizes)
                max_size = max(sizes)
                # Cover page: average font > 20pt or max font > 30pt with few words
                if max_size > 30 and len(all_words) < 40:
                    continue

            # Extract tables
            tables = page.extract_tables()
            table_bboxes = []
            if page.find_tables():
                for t in page.find_tables():
                    table_bboxes.append(t.bbox)

            # Extract lines
            all_lines = _extract_words_grouped(page)

            # Detect body text font size (most common)
            all_page_words = page.extract_words(extra_attrs=["size"])
            size_counts_page: dict[float, int] = {}
            for w in all_page_words:
                sz = round(w.get("size", 0), 1)
                size_counts_page[sz] = size_counts_page.get(sz, 0) + len(w.get("text", ""))
            body_font_size = max(size_counts_page, key=size_counts_page.get) if size_counts_page else 10.0

            # Filter out words inside table bounding boxes
            def in_table_bbox(word):
                for bbox in table_bboxes:
                    x0, top, x1, bottom = bbox
                    if (word["x0"] >= x0 - 2 and word["top"] >= top - 2
                            and word["x1"] <= x1 + 2 and word["bottom"] <= bottom + 2):
                        return True
                return False

            # Process lines (excluding table content)
            filtered_lines = []
            for line_words in all_lines:
                non_table_words = [w for w in line_words if not in_table_bbox(w)]
                if non_table_words:
                    # Skip lines where dominant font is smaller than body text (footers/headers)
                    _, dom_size = _dominant_font(non_table_words)
                    if dom_size > 0 and dom_size < body_font_size - 0.5:
                        # Allow monospace (code) even if smaller
                        dom_font, _ = _dominant_font(non_table_words)
                        if not _is_monospace(dom_font):
                            continue
                    filtered_lines.append(non_table_words)

            # Merge consecutive lines with same font into blocks
            current_block_lines = []
            current_block_type = None
            current_font = None
            current_block_y = 0

            def flush_block():
                nonlocal current_block_lines, current_block_type, current_font
                if not current_block_lines:
                    return
                text = " ".join(current_block_lines).strip()
                if not text:
                    current_block_lines = []
                    return

                # Skip footers/headers
                if _is_footer(text, page_num):
                    current_block_lines = []
                    return

                if current_block_type == "heading":
                    # Clean heading number prefix for level detection
                    clean = re.sub(r"^\d+\.\s*", "", text).strip()
                    font_name, font_size = current_font or ("", 0)
                    level = heading_sizes.get(font_size, 1)
                    # Track y-position from first word in current block's line
                    y_pos = current_block_y if current_block_y else 0
                    blocks.append(Block(
                        type="heading", text=clean, page=page_num,
                        level=level, meta={"original": text, "font_size": font_size, "y_pos": y_pos}
                    ))
                elif current_block_type == "code":
                    blocks.append(Block(type="code", text=text, page=page_num))
                elif current_block_type == "note":
                    blocks.append(Block(type="note", text=text, page=page_num))
                else:
                    blocks.append(Block(type="paragraph", text=text, page=page_num))

                current_block_lines = []
                current_block_type = None

            in_code_block = False
            code_lines = []
            prev_line_bottom = None  # for paragraph-break detection

            for line_words in filtered_lines:
                text = _line_text(line_words)
                font_name, font_size = _dominant_font(line_words)

                if not text.strip():
                    continue

                # Paragraph break detection: vertical gap from previous line in
                # the same body block triggers a flush. Within-paragraph line
                # spacing is typically 0.15-0.3x font height; between-paragraph
                # spacing is 0.7x+ in most layouts. Threshold 0.6x catches it
                # without false-positives on normal line spacing.
                line_top = line_words[0]["top"] if line_words else 0
                line_bottom = max((w["bottom"] for w in line_words), default=line_top)
                if (prev_line_bottom is not None
                        and current_block_type == "paragraph"
                        and current_block_lines
                        and font_size > 0):
                    gap = line_top - prev_line_bottom
                    if gap > 0.6 * font_size:
                        flush_block()
                prev_line_bottom = line_bottom

                # Skip page-level running headers (first short line at top)
                if not blocks and not current_block_lines and len(text) < 60:
                    word_top = line_words[0]["top"]
                    if word_top < 50:  # near top of page
                        # Check if this is a running header (matches heading pattern)
                        if not re.match(r"^\d+\.", text.strip()):
                            continue

                # Detect code blocks (monospace font)
                if _is_monospace(font_name):
                    if not in_code_block:
                        flush_block()
                        in_code_block = True
                        code_lines = []
                    code_lines.append(text)
                    continue
                elif in_code_block:
                    # End of code block
                    blocks.append(Block(
                        type="code",
                        text="\n".join(code_lines),
                        page=page_num
                    ))
                    in_code_block = False
                    code_lines = []

                # Detect headings (bold + large font)
                if _is_bold(font_name) and font_size in heading_sizes:
                    flush_block()
                    current_block_type = "heading"
                    current_font = (font_name, font_size)
                    current_block_y = line_words[0]["top"] if line_words else 0
                    current_block_lines.append(text)
                    flush_block()
                    continue

                # Detect notes
                if text.strip().startswith("Note:") and _is_bold(font_name):
                    flush_block()
                    current_block_type = "note"
                    current_block_lines.append(text)
                    continue

                # Detect numbered list items
                list_match = re.match(r"^(\d+)\.\s+(.+)", text.strip())
                if list_match:
                    flush_block()
                    ordinal = int(list_match.group(1))
                    blocks.append(Block(
                        type="list_item",
                        text=text.strip(),
                        page=page_num,
                        meta={"ordinal": ordinal}
                    ))
                    continue

                # Continuation of current block or new paragraph
                if current_block_type == "note":
                    current_block_lines.append(text)
                else:
                    # Check if this continues the previous block
                    if current_block_type == "paragraph":
                        current_block_lines.append(text)
                    else:
                        flush_block()
                        current_block_type = "paragraph"
                        current_block_lines.append(text)

            # Flush remaining code block
            if in_code_block and code_lines:
                blocks.append(Block(
                    type="code", text="\n".join(code_lines), page=page_num
                ))

            flush_block()

            # Add tables at their correct vertical positions
            # We need to insert them among the existing blocks based on y-coordinate
            table_blocks = []
            found_tables = page.find_tables()
            for ti, table in enumerate(tables):
                if table and len(table) > 0:
                    # Get table y-position
                    table_top = found_tables[ti].bbox[1] if ti < len(found_tables) else 9999
                    clean_table = []
                    for row in table:
                        clean_row = [
                            (cell or "").replace("\n", " ").strip()
                            if isinstance(cell, str) else (cell or "")
                            for cell in row
                        ]
                        clean_table.append(clean_row)
                    table_blocks.append((table_top, Block(
                        type="table",
                        text=json.dumps(clean_table, ensure_ascii=False),
                        page=page_num,
                        meta={"rows": len(clean_table),
                              "cols": len(clean_table[0]) if clean_table else 0}
                    )))

            # Insert table blocks at the right position
            if table_blocks:
                # Find the index range for this page's blocks
                page_start = len(blocks)
                for idx in range(len(blocks) - 1, -1, -1):
                    if blocks[idx].page == page_num:
                        page_start = idx
                    else:
                        break

                # For each table, find where it should go based on y-position
                # We approximate by inserting after the last block that starts
                # before the table's top position
                for table_top, table_block in sorted(table_blocks, key=lambda x: x[0]):
                    inserted = False
                    # Simple heuristic: insert before the first heading that comes
                    # after the table's position on the page
                    for idx in range(page_start, len(blocks)):
                        b = blocks[idx]
                        if b.page == page_num and b.type == "heading":
                            # Check if this heading is after the table
                            if b.meta.get("y_pos", 0) > table_top:
                                blocks.insert(idx, table_block)
                                inserted = True
                                break
                    if not inserted:
                        blocks.append(table_block)

            # Add images for this page
            if page_num in page_images:
                for img_path in page_images[page_num]:
                    img_filename = Path(img_path).name
                    blocks.append(Block(
                        type="image",
                        text=img_filename,
                        page=page_num,
                        meta={"path": img_path, "filename": img_filename}
                    ))

    return blocks


def _clean_blocks(blocks: list[Block]) -> list[Block]:
    """Remove running headers (short paragraphs that duplicate a nearby heading)."""
    cleaned = []
    heading_texts = {b.text.strip().lower() for b in blocks if b.type == "heading"}

    for i, block in enumerate(blocks):
        if block.type == "paragraph":
            txt = block.text.strip().lower()
            # Skip if this paragraph matches a heading exactly (running header)
            if txt in heading_texts and len(txt) < 80:
                continue
            # Skip page footers that slipped through
            if re.match(r"^(page\s+\d+|sample file:)", txt, re.IGNORECASE):
                continue
        cleaned.append(block)

    return cleaned


def group_into_sections(blocks: list[Block]) -> list[dict]:
    """
    Group blocks into sections, each starting with a heading.
    Returns list of sections:
    {
        "title": str,
        "level": int,
        "blocks": [Block, ...],
        "page_start": int
    }
    """
    blocks = _clean_blocks(blocks)
    sections = []
    current_section = None

    for block in blocks:
        if block.type == "heading":
            if current_section:
                sections.append(current_section)
            current_section = {
                "title": block.text,
                "level": block.level,
                "blocks": [],
                "page_start": block.page,
            }
        else:
            if current_section is None:
                current_section = {
                    "title": "Introduction",
                    "level": 1,
                    "blocks": [],
                    "page_start": block.page,
                }
            current_section["blocks"].append(block)

    if current_section:
        sections.append(current_section)

    return sections


if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Sample_File__Manage_2a-7_Processing.pdf"
    blocks = parse_pdf(pdf_path, "/home/claude/pdf2dita/test_output")
    print(f"\nExtracted {len(blocks)} blocks:")
    for b in blocks:
        preview = b.text[:80].replace("\n", "\\n")
        print(f"  [{b.type}] (p{b.page}) {preview}...")

    sections = group_into_sections(blocks)
    print(f"\n{len(sections)} sections:")
    for s in sections:
        btypes = [b.type for b in s["blocks"]]
        print(f"  L{s['level']}: {s['title']} -> {len(s['blocks'])} blocks: {btypes}")
