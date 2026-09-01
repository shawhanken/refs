#!/usr/bin/env python3
"""Recompute the CIP-39 v1-vs-v2 metrics table in
2026-08-24_cip39_v2_simplification_plan.md.

Every number in that table comes from here, so the table can be re-derived
rather than trusted. Run from a `cowboy` checkout on `spec/cip-39-v2`:

    git show origin/main:docs/cips/cip-39-cowboy-queue-system.md > /tmp/v1.md
    python3 cip39_metrics.py /tmp/v1.md docs/cips/cip-39-cowboy-queue-system.md
"""
import json
import os
import re
import sys

IO_ROW = re.compile(r"^\| `(\w+)` \| (\d+) \| (\d+) \|", re.M)
PARAM_ROW = re.compile(r"^\| `cbqs\.[a-z0-9_.]+` \|", re.M)
CODE_ROW = re.compile(r"^\|\s*(39\d\d)\s*\|", re.M)


def struct_fields(text, name):
    """Count declared fields in a ```text struct block."""
    m = re.search(re.escape(name) + r" \{\n(.*?)\n\}", text, re.S)
    if not m:
        return 0
    return len([l for l in m.group(1).split("\n") if re.match(r"\s+\w+:", l)])


def required_cips(text):
    m = re.search(r"\*\*Requires:\*\*(.*)", text)
    return len(set(re.findall(r"CIP-\d+", m.group(1)))) if m else 0


def metrics(text, version):
    io = IO_ROW.findall(text)
    suffix = "V1" if version == 1 else "V2"
    return {
        "Specification lines": text.count("\n"),
        "MUST occurrences": text.count("MUST"),
        "  of which MUST NOT": text.count("MUST NOT"),
        "Chain instructions": len(io),
        "StreamRecord fields": struct_fields(text, "StreamRecord" + suffix),
        "RecordHeader fields": struct_fields(text, "RecordHeader" + suffix),
        "StreamConfig fields on chain": struct_fields(text, "StreamConfig" + suffix),
        "Signed object types": len(set(re.findall(r"`(cbqs/[a-z-]+/v%d)`" % version, text))),
        "Governance parameters": len(PARAM_ROW.findall(text)),
        "Typed error codes": len(set(CODE_ROW.findall(text))),
        "State reads reserved": sum(int(r[1]) for r in io),
        "State writes reserved": sum(int(r[2]) for r in io),
        "Required CIPs": required_cips(text),
    }


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    v1 = open(sys.argv[1], encoding="utf-8").read()
    v2 = open(sys.argv[2], encoding="utf-8").read()
    a, b = metrics(v1, 1), metrics(v2, 2)
    width = max(len(k) for k in a)
    for key in a:
        x, y = a[key], b[key]
        delta = f"{(y - x) / x * 100:+.0f}%" if x else ""
        print(f"{key:<{width}}  {x:>6}  {y:>6}  {delta:>6}")

    create = {r[0]: (r[1], r[2]) for r in IO_ROW.findall(v1)}.get("CreateStream")
    create2 = {r[0]: (r[1], r[2]) for r in IO_ROW.findall(v2)}.get("CreateStream")
    print(f"\nCreateStream reads/writes  {create}  ->  {create2}")

    # The gas artifact lives beside the v2 document; check its pin while we are here.
    artifact = os.path.join(os.path.dirname(sys.argv[2]), "cip-39-gas-vectors-v2.json")
    if os.path.exists(artifact):
        import hashlib
        raw = open(artifact, "rb").read()
        digest = hashlib.sha256(raw).hexdigest()
        vectors = json.loads(raw)["vectors"]
        rejected = sum(1 for v in vectors if v.get("rejected"))
        print(f"gas vectors: {len(vectors)} ({rejected} rejection paths)")
        print(f"artifact sha256 pinned in the spec: {digest in v2}  {digest}")


if __name__ == "__main__":
    main()
