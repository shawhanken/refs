"""Consistency-dimension rules (R001-R009).

Inherits the rule IDs and severity from the CIP Bot design §4.3 and the
doc-audit-service design §5.2.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Iterable

from common.schema import Finding, Location
from rules.registry import RuleContext, rule


_DIM = "consistency"


@rule("R001_opcode_collision", _DIM)
def opcode_collision(ctx: RuleContext) -> Iterable[Finding]:
    """Detect opcode-id collisions.

    Fires in two cases:
      A) `diff.added` contains an opcode whose id already exists in `base`
         (the classic "new opcode collides with existing" case).
      B) `head` contains the same opcode id in multiple distinct files, AND
         at least one of those files is in `changed_files` (i.e. the PR
         introduced the second occurrence). Case B catches collisions that
         (A) misses because the resource-level diff is keyed on opcode id
         and therefore collapses multi-file occurrences of the same id.
    """
    # --- case A: diff.added vs base -------------------------------------------
    added = ctx.diff["by_kind"].get("opcodes", {}).get("added", [])
    base_by_id: dict[int, list[dict]] = defaultdict(list)
    for o in ctx.base_index.get("opcodes", []) or []:
        base_by_id[o["id"]].append(o)
    yielded: set[tuple[int, str, str]] = set()
    for new in added:
        for other in base_by_id.get(new["id"], []):
            key = (new["id"], new["file"], other["file"])
            if key in yielded:
                continue
            yielded.add(key)
            yield _opcode_collision_finding(new, other)

    # --- case B: within-head, PR-introduced ----------------------------------
    head_by_id: dict[int, list[dict]] = defaultdict(list)
    for o in ctx.head_index.get("opcodes", []) or []:
        head_by_id[o["id"]].append(o)
    changed = set(ctx.changed_files)
    for opcode_id, occs in head_by_id.items():
        files = {o["file"] for o in occs}
        if len(files) < 2:
            continue
        if not (files & changed):
            continue  # the collision was already there before this PR
        # Pair every changed-file occurrence with every existing-file occurrence.
        in_pr = [o for o in occs if o["file"] in changed]
        elsewhere = [o for o in occs if o["file"] not in changed]
        for new in in_pr:
            for other in elsewhere:
                key = (opcode_id, new["file"], other["file"])
                if key in yielded:
                    continue
                yielded.add(key)
                yield _opcode_collision_finding(new, other)


def _opcode_collision_finding(new: dict, other: dict) -> Finding:
    return Finding(
        rule_id="R001_opcode_collision",
        source="rules",
        dimension=_DIM,
        severity="block",
        title=f"Opcode 0x{new['id']:02X} 与已有定义冲突",
        locations=[
            Location(file=new["file"], line_start=new["line"]),
            Location(file=other["file"], line_start=other["line"]),
        ],
        message=(
            f"HEAD 新增 opcode 0x{new['id']:02X}（{new.get('name') or '匿名'}）"
            f"，但 {other['file']}:{other['line']} 已分配该 opcode"
            f"（{other.get('name') or '匿名'}）。"
        ),
        suggestion="按白皮书 §9.2 注释取下一个空闲位。",
    )


@rule("R002_address_collision", _DIM)
def address_collision(ctx: RuleContext) -> Iterable[Finding]:
    added = ctx.diff["by_kind"].get("addresses", {}).get("added", [])
    base_by_id: dict[str, dict] = {
        a["id"]: a for a in ctx.base_index.get("addresses", []) or []
    }
    for new in added:
        other = base_by_id.get(new["id"])
        if other:
            yield Finding(
                rule_id="R002_address_collision",
                source="rules",
                dimension=_DIM,
                severity="block",
                title=f"System actor 地址 {new['id']} 冲突",
                locations=[
                    Location(file=new["file"], line_start=new["line"]),
                    Location(file=other["file"], line_start=other["line"]),
                ],
                message=(
                    f"HEAD 给 {new.get('name')} 分配 {new['id']}，但 "
                    f"{other['file']} 已把它分给 {other.get('name')}。"
                ),
                suggestion="选择未占用的地址。",
            )


@rule("R003_opcode_without_wp_update", _DIM)
def opcode_without_wp_update(ctx: RuleContext) -> Iterable[Finding]:
    """新增/修改 opcode 时必须同步白皮书 §9.2 所在文件。"""
    opcode_change = (
        ctx.diff["by_kind"].get("opcodes", {}).get("added")
        or ctx.diff["by_kind"].get("opcodes", {}).get("modified")
    )
    if not opcode_change:
        return
    # Heuristic: any changed file under a whitepaper-like path counts.
    whitepaper_touched = any(
        "whitepaper" in cf.lower() or "wp" in os.path.basename(cf).lower()
        for cf in ctx.changed_files
    )
    if whitepaper_touched:
        return
    sample = opcode_change[0]
    sample_loc = sample.get("after") or sample
    yield Finding(
        rule_id="R003_opcode_without_wp_update",
        source="rules",
        dimension=_DIM,
        severity="block",
        title="改动 opcode 但未同步白皮书 §9.2",
        locations=[Location(file=sample_loc["file"], line_start=sample_loc["line"])],
        message=(
            "本次 PR 触及 opcode 列表，但 changed_files 中没有白皮书条目。"
            "按白皮书 §9.2 收尾注释要求，opcode 变更必须同 PR 内同步注册表。"
        ),
        suggestion="在同一 PR 修改白皮书 §9.2 的 opcode 表。",
    )


@rule("R004_dangling_xref", _DIM)
def dangling_xref(ctx: RuleContext) -> Iterable[Finding]:
    head_cips = {c["id"]: c for c in ctx.head_index.get("cips", []) or []}
    for x in ctx.head_index.get("xrefs", []) or []:
        target = x.get("to", "")
        if not target.startswith("CIP-"):
            continue
        cip_num_str, *rest = target[4:].split(" ", 1)
        try:
            cip_num = int(cip_num_str)
        except ValueError:
            continue
        cip = head_cips.get(cip_num)
        if cip is None:
            yield Finding(
                rule_id="R004_dangling_xref",
                source="rules",
                dimension=_DIM,
                severity="block",
                title=f"悬空引用：{target}",
                locations=[Location(file=x["file"], line_start=x["line"])],
                message=f"{x['file']}:{x['line']} 引用 {target}，但该 CIP 在 HEAD 中不存在。",
                suggestion="修正引用编号或落地缺失的 CIP。",
            )
            continue
        if rest:
            # xref stores anchors as "§9.7"; the index strips the § and stores
            # bare numbers like "9.7". Normalize both sides before comparing.
            anchor = rest[0].strip().lstrip("§").strip()
            existing = {a.lstrip("§").strip() for a in (cip.get("anchors") or [])}
            if anchor and anchor not in existing:
                yield Finding(
                    rule_id="R004_dangling_xref",
                    source="rules",
                    dimension=_DIM,
                    severity="block",
                    title=f"悬空锚点：{target}",
                    locations=[Location(file=x["file"], line_start=x["line"])],
                    message=f"{target} 中的锚点 §{anchor} 不存在于 CIP-{cip_num}。",
                    suggestion=f"使用 CIP-{cip_num} 中实际存在的章节锚点。",
                )


@rule("R005_cip_number_collision", _DIM)
def cip_number_collision(ctx: RuleContext) -> Iterable[Finding]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for c in ctx.head_index.get("cips", []) or []:
        grouped[c["id"]].append(c)
    for cip_id, items in grouped.items():
        if len(items) <= 1:
            continue
        yield Finding(
            rule_id="R005_cip_number_collision",
            source="rules",
            dimension=_DIM,
            severity="block",
            title=f"CIP-{cip_id} 编号被多个文件使用",
            locations=[Location(file=i["file"], line_start=1) for i in items],
            message=", ".join(i["file"] for i in items) + f" 都自称 CIP-{cip_id}。",
            suggestion="给冲突的 CIP 重新编号。",
        )


@rule("R006_status_regression", _DIM)
def status_regression(ctx: RuleContext) -> Iterable[Finding]:
    rank = {"Draft": 0, "Review": 1, "LastCall": 2, "Final": 3, "Withdrawn": 4}
    base = {c["id"]: c for c in ctx.base_index.get("cips", []) or []}
    for h in ctx.head_index.get("cips", []) or []:
        b = base.get(h["id"])
        if not b:
            continue
        b_rank = rank.get(b.get("status", ""), -1)
        h_rank = rank.get(h.get("status", ""), -1)
        if b_rank > 0 and h_rank >= 0 and h_rank < b_rank and h.get("status") != "Withdrawn":
            yield Finding(
                rule_id="R006_status_regression",
                source="rules",
                dimension=_DIM,
                severity="block",
                title=f"CIP-{h['id']} 状态倒退：{b['status']} → {h['status']}",
                locations=[Location(file=h["file"], line_start=1)],
                message=f"{h['file']} 把 CIP-{h['id']} 从 {b['status']} 改为 {h['status']}。",
                suggestion="只允许向 Withdrawn 倒退；其他变更需要在 PR 描述里说明理由。",
            )


@rule("R007_terminology_drift", _DIM)
def terminology_drift(ctx: RuleContext) -> Iterable[Finding]:
    """术语在不同文档首次定义不一致（同名 term 出现在多个 definition_file）。"""
    by_term: dict[str, list[dict]] = defaultdict(list)
    for t in ctx.head_index.get("terms", []) or []:
        by_term[t["term"].lower()].append(t)
    for term, defs in by_term.items():
        files = {d["definition_file"] for d in defs}
        if len(files) > 1:
            yield Finding(
                rule_id="R007_terminology_drift",
                source="rules",
                dimension=_DIM,
                severity="warn",
                title=f"术语 '{term}' 在多个文档定义",
                locations=[
                    Location(file=d["definition_file"], line_start=d["line"]) for d in defs
                ],
                message=f"术语 {term!r} 在 {len(files)} 个文档中作为首次定义出现。",
                suggestion="在术语表统一定义，其他文档改为引用。",
            )


@rule("R008_link_rot", _DIM)
def link_rot(ctx: RuleContext) -> Iterable[Finding]:
    """检查 HEAD 索引中的相对链接是否能在仓库内解析。

    CIP-N 形式的交叉引用由 R004 处理；这里只看 markdown `[text](path)` 形式的
    相对路径链接。绝对 URL 不在此规则范围（留给 style 维度）。
    """
    head_files = {os.path.normpath(f) for f in ctx.head_index.get("files_parsed", [])}
    for rel in ctx.head_index.get("files_parsed", []) or []:
        full = os.path.join(ctx.repo_root, rel)
        try:
            with open(full, encoding="utf-8") as fp:
                text = fp.read()
        except OSError:
            continue
        from common.markdown import extract_links
        for line, _label, url in extract_links(text):
            if "://" in url or url.startswith("#") or url.startswith("mailto:"):
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(rel), url.split("#", 1)[0]))
            if not target or target in head_files:
                continue
            if os.path.exists(os.path.join(ctx.repo_root, target)):
                continue
            yield Finding(
                rule_id="R008_link_rot",
                source="rules",
                dimension=_DIM,
                severity="warn",
                title=f"相对链接失效：{url}",
                locations=[Location(file=rel, line_start=line)],
                message=f"{rel}:{line} 指向不存在的相对路径 {url}。",
                suggestion="修正链接或移除。",
            )


@rule("R009_constant_value_mismatch", _DIM)
def constant_value_mismatch(ctx: RuleContext) -> Iterable[Finding]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for c in ctx.head_index.get("constants", []) or []:
        by_name[c["name"]].append(c)
    for name, items in by_name.items():
        values = {i["value"] for i in items}
        if len(values) > 1:
            yield Finding(
                rule_id="R009_constant_value_mismatch",
                source="rules",
                dimension=_DIM,
                severity="block",
                title=f"常量 {name} 在文档中出现多个值",
                locations=[Location(file=i["file"], line_start=i["line"]) for i in items],
                message=f"{name} 取值 {sorted(values)} 在多个文档不一致。",
                suggestion="选择权威定义并在其他文档统一。",
            )
