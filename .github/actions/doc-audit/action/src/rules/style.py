"""Style-dimension rules: glossary spelling consistency, casing drift.

Design ref: §5.6. Link rot for absolute URLs is intentionally NOT here
(HEAD checks require network and live in a separate optional pass).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from common.schema import Finding, Location
from rules.registry import RuleContext, rule


_DIM = "style"


@rule("W001_term_casing_drift", _DIM)
def term_casing_drift(ctx: RuleContext) -> Iterable[Finding]:
    """同一术语出现多个大小写形式（Actor / actor / ACTOR）。"""
    by_lc: dict[str, set[str]] = defaultdict(set)
    by_lc_locs: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for t in ctx.head_index.get("terms", []) or []:
        term = t["term"]
        lc = term.lower()
        by_lc[lc].add(term)
        by_lc_locs[lc].append((t["definition_file"], t["line"]))
    for lc, variants in by_lc.items():
        if len(variants) <= 1:
            continue
        locs = [Location(file=f, line_start=l) for f, l in by_lc_locs[lc]]
        yield Finding(
            rule_id="W001_term_casing_drift",
            source="rules",
            dimension=_DIM,
            severity="warn",
            title=f"术语 {sorted(variants)!r} 大小写不一致",
            locations=locs,
            message=f"以下变体并存：{sorted(variants)}。",
            suggestion="选定一种写法在术语表中固化。",
        )


# Detects same-anchor format mistakes like "§ 3.1" vs "§3.1".
_BAD_ANCHOR_RE = re.compile(r"§\s+\d")


@rule("W002_anchor_format", _DIM)
def anchor_format(ctx: RuleContext) -> Iterable[Finding]:
    for rel in ctx.head_index.get("files_parsed", []) or []:
        try:
            with open(f"{ctx.repo_root}/{rel}", encoding="utf-8") as fp:
                text = fp.read()
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if _BAD_ANCHOR_RE.search(line):
                yield Finding(
                    rule_id="W002_anchor_format",
                    source="rules",
                    dimension=_DIM,
                    severity="warn",
                    title="锚点 `§` 与编号之间多余空格",
                    locations=[Location(file=rel, line_start=i)],
                    message=f"{rel}:{i} 中 `§` 与数字之间存在空格，与项目惯例不一致。",
                    suggestion="改为 `§N.M` 形式。",
                )
