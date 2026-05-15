"""Lightweight markdown scanning utilities.

We deliberately stay regex-based and tolerant: index extraction must keep
going when individual headings or tables are malformed (design §4.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ANCHOR_RE = re.compile(r"§(\d+(?:\.\d+)*)")
FENCED_RE = re.compile(r"^```([a-zA-Z0-9_+\-]*)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


@dataclass
class CodeBlock:
    file: str
    line_start: int  # line of opening fence
    line_end: int    # line of closing fence
    lang: str
    content: str


def iter_lines(text: str) -> list[str]:
    return text.splitlines()


def extract_code_blocks(file: str, text: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    lines = iter_lines(text)
    i = 0
    while i < len(lines):
        m = FENCED_RE.match(lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1) or ""
        start = i + 1  # 1-based line number for opening fence
        body: list[str] = []
        j = i + 1
        while j < len(lines):
            if FENCED_RE.match(lines[j]):
                break
            body.append(lines[j])
            j += 1
        end = j + 1
        blocks.append(
            CodeBlock(
                file=file,
                line_start=start,
                line_end=end,
                lang=lang.lower(),
                content="\n".join(body),
            )
        )
        i = j + 1
    return blocks


def extract_anchors(text: str) -> list[str]:
    """Return ['3.1', '9.2.3', ...] for §3.1, §9.2.3 references in text."""
    return ANCHOR_RE.findall(text)


def extract_headings(text: str) -> list[tuple[int, int, str]]:
    """Return list of (line_no, level, title) tuples."""
    out: list[tuple[int, int, str]] = []
    for i, line in enumerate(iter_lines(text), start=1):
        m = HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def extract_links(text: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for i, line in enumerate(iter_lines(text), start=1):
        for m in LINK_RE.finditer(line):
            out.append((i, m.group(1), m.group(2)))
    return out
