"""Stdlib-only Markdown→HTML mini-renderer.

Supports: ATX headings (#-######), paragraphs, fenced code blocks (```lang),
unordered + ordered lists (single-level), blockquotes, horizontal rules,
inline code (`x`), bold (**x**), italic (*x*), links ([x](y)), and images.

Tables: pipe-style GFM tables with header separator (---|---) — we use them
heavily in ISAs.

NOT a full GFM impl — no nested lists, no task lists, no autolinks beyond
explicit [text](url). Good enough for ISA / memory / daily content.
"""

from __future__ import annotations

import html as html_escape
import re


def render(md: str) -> str:
    """Convert markdown text to an HTML body fragment.

    Strips YAML frontmatter (--- … ---) if present at the very start; the
    dashboard's ISA renderer surfaces frontmatter as a separate metadata
    panel rather than inlining it as paragraphs.
    """
    md = _strip_frontmatter(md)
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.lstrip().startswith("```"):
            lang = line.lstrip()[3:].strip()
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # consume closing fence
            code = "\n".join(buf)
            lang_class = f' class="lang-{html_escape.escape(lang)}"' if lang else ""
            out.append(f'<pre><code{lang_class}>{html_escape.escape(code)}</code></pre>')
            continue

        # Horizontal rule (---, ***, ___). Match on its own line, regardless
        # of context — handles YAML frontmatter fences too.
        if re.fullmatch(r"\s*[-*_]{3,}\s*", line):
            out.append("<hr>")
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m:
            level = len(m.group(1))
            text = _inline(m.group(2))
            anchor = _slug(m.group(2))
            out.append(f'<h{level} id="{anchor}">{text}</h{level}>')
            i += 1
            continue

        # Blockquote (collapse contiguous > lines)
        if line.lstrip().startswith(">"):
            buf2: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf2.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            inner = render("\n".join(buf2))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # Tables — header row with pipes + separator row
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[-:\s|]+\|[-:\s|]+\s*$", lines[i+1]):
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            out.append(_render_table(table_lines))
            continue

        # Unordered list
        if re.match(r"^\s*[-*+]\s+", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(_inline(re.sub(r"^\s*[-*+]\s+", "", lines[i])))
                i += 1
            out.append("<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            items_ol: list[str] = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items_ol.append(_inline(re.sub(r"^\s*\d+\.\s+", "", lines[i])))
                i += 1
            out.append("<ol>" + "".join(f"<li>{it}</li>" for it in items_ol) + "</ol>")
            continue

        # Blank line — paragraph separator
        if not line.strip():
            i += 1
            continue

        # Paragraph: collect contiguous non-empty, non-block lines
        para: list[str] = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para.append(lines[i])
            i += 1
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")

    return "\n".join(out)


def parse_frontmatter(md: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) for a markdown doc.

    Frontmatter is a leading `---\\n<yaml>\\n---\\n` block. Keys are parsed
    naively as `key: value` lines — no nested mappings, no lists. Good
    enough for the simple frontmatter our ISAs use.
    """
    if not md.startswith("---\n") and not md.startswith("---\r\n"):
        return {}, md
    lines = md.splitlines(keepends=True)
    end_idx = None
    for j in range(1, len(lines)):
        if lines[j].rstrip("\r\n") == "---":
            end_idx = j
            break
    if end_idx is None:
        return {}, md
    fm = {}
    for raw in lines[1:end_idx]:
        ln = raw.rstrip("\r\n")
        if ":" not in ln:
            continue
        key, _, value = ln.partition(":")
        fm[key.strip()] = value.strip()
    body = "".join(lines[end_idx + 1:])
    return fm, body


def _strip_frontmatter(md: str) -> str:
    _, body = parse_frontmatter(md)
    return body


def _is_block_start(line: str) -> bool:
    """True if this line begins a new block-level element."""
    stripped = line.lstrip()
    return (
        stripped.startswith("#")
        or stripped.startswith("```")
        or stripped.startswith(">")
        or re.match(r"^\s*[-*+]\s+", line) is not None
        or re.match(r"^\s*\d+\.\s+", line) is not None
        or re.fullmatch(r"\s*-{3,}\s*", line) is not None
    )


def _render_table(lines: list[str]) -> str:
    """Render a GFM-style pipe table."""
    rows = [_split_table_row(ln) for ln in lines]
    if len(rows) < 2:
        return "<p>" + _inline(" ".join(lines)) + "</p>"
    header, _sep, *body = rows
    out = ["<table>", "<thead><tr>"]
    out.extend(f"<th>{_inline(c)}</th>" for c in header)
    out.append("</tr></thead>")
    if body:
        out.append("<tbody>")
        for row in body:
            out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
        out.append("</tbody>")
    out.append("</table>")
    return "".join(out)


def _split_table_row(line: str) -> list[str]:
    # Strip leading/trailing pipes, then split. Preserve internal whitespace per cell.
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _slug(text: str) -> str:
    """URL-safe heading anchor."""
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "section"


# ---- Inline rendering ----

_INLINE_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\s)([^*]+?)\*(?!\*)")


def _inline(text: str) -> str:
    """Render inline markdown elements (code, links, bold, italic).

    Order matters: code first (so its contents aren't HTML-escaped twice or
    parsed for *bold*); then escape; then images/links; then emphasis.
    """
    # Pull out inline-code spans first, replace with sentinels
    code_spans: list[str] = []
    def _stash_code(m: re.Match) -> str:
        code_spans.append(m.group(1))
        return f"\x00CODE{len(code_spans)-1}\x00"
    text = _INLINE_CODE.sub(_stash_code, text)

    # Escape HTML in everything else
    text = html_escape.escape(text, quote=False)

    # Images
    text = _IMAGE.sub(
        lambda m: f'<img src="{html_escape.escape(m.group(2))}" alt="{html_escape.escape(m.group(1))}">',
        text,
    )
    # Links
    text = _LINK.sub(
        lambda m: f'<a href="{html_escape.escape(m.group(2))}">{m.group(1)}</a>',
        text,
    )

    # Bold + italic
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)

    # Restore inline code spans (escape their contents)
    def _restore_code(m: re.Match) -> str:
        idx = int(m.group(1))
        return f"<code>{html_escape.escape(code_spans[idx])}</code>"
    text = re.sub(r"\x00CODE(\d+)\x00", _restore_code, text)

    return text
