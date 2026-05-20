from __future__ import annotations

from common.config import DimensionConfig, TargetConfig
from common.schema import Finding, Location
import report


def _tgt():
    return TargetConfig(
        name="cips",
        paths=["docs/**"],
        dimensions={
            "consistency": DimensionConfig(enabled=True, severity_gate="block"),
            "security": DimensionConfig(enabled=True, severity_gate="warn"),
        },
    )


def test_render_markdown_groups_by_dimension():
    findings = [
        Finding(
            rule_id="R001", source="rules", dimension="consistency", severity="block",
            title="bang", locations=[Location(file="a.md", line_start=1)], message="m"
        ),
        Finding(
            rule_id="S001", source="rules", dimension="security", severity="warn",
            title="leaky", locations=[Location(file="b.md", line_start=2)], message="m"
        ),
    ]
    md = report.render_markdown(
        findings=findings, target=_tgt(), dimension_quality={},
    )
    assert "doc-audit-bot" in md
    assert "一致性" in md
    assert "安全性" in md
    assert "R001" in md and "S001" in md


def test_check_runs_failure_only_when_block_dim_has_block_findings():
    findings = [
        Finding(
            rule_id="R001", source="rules", dimension="consistency", severity="block",
            title="bang", locations=[Location(file="a.md", line_start=1)], message="m"
        ),
        Finding(
            rule_id="S001", source="rules", dimension="security", severity="warn",
            title="leaky", locations=[Location(file="b.md", line_start=2)], message="m"
        ),
    ]
    runs = report.compute_check_runs(findings=findings, target=_tgt())
    by_name = {r["name"]: r for r in runs}
    assert by_name["Doc Audit / 一致性"]["conclusion"] == "failure"
    assert by_name["Doc Audit / 安全性"]["conclusion"] == "success"


def test_sarif_contains_rules_and_results():
    findings = [
        Finding(
            rule_id="R001", source="rules", dimension="consistency", severity="block",
            title="bang", locations=[Location(file="a.md", line_start=1)], message="m"
        ),
    ]
    sarif = report.render_sarif(findings)
    runs = sarif["runs"][0]
    assert runs["tool"]["driver"]["rules"][0]["id"] == "R001"
    assert runs["results"][0]["level"] == "error"
