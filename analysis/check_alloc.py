#!/usr/bin/env python3
"""Reconcile CIP-claimed opcode / system-actor-address numbers against the
on-chain source of truth. Deep-audit §6 recommended this deterministic diff in
place of a verification-agent pass. Wire as CI: exit non-zero on any real
mismatch. Run from the workspace root (dir containing node/, cowboy/,
cowboy-protocol/).

    python3 refs/analysis/check_alloc.py
"""
import re, sys, glob, os

ROOT = os.environ.get("WS", os.getcwd())
CODEC = f"{ROOT}/cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs"
ACTORS = f"{ROOT}/node/runner/src/system_actors.rs"
CIP_DIR = f"{ROOT}/cowboy/docs/cips"

# Known-benign exceptions (host syscalls, correct "does-not-exist" prose, and the
# CIP-10-owner holdout tracked in 2026-07-13_system-actor-address-reconciliation.md).
IGNORE_OPNAMES = {"SYS_FETCH_SECRET_METADATA", "SYS_VALIDATOR_", "SYS_SESSION_"}
IGNORE_DOCS_FOR_CONTAINER_0X11 = {"cip-10-runner-containers.md"}  # owner to fix

def load_opcodes():
    m = {}
    for line in open(CODEC):
        g = re.search(r'pub const (SYS_[A-Z0-9_]+): u8 = (\d+)', line)
        if g:
            m[g.group(1)] = int(g.group(2))
    return m

def load_addrs():
    m = {}
    for line in open(ACTORS):
        g = re.search(r'\b([A-Z][A-Z0-9_]+) = 0x([0-9A-Fa-f]+)', line)
        if g:
            m[g.group(1)] = int(g.group(2), 16)
    return m

op = load_opcodes()
addr = load_addrs()
# collision self-check on the source of truth
assert len(set(op.values())) == len(op), "codec has duplicate opcode values!"
findings = []

for path in sorted(glob.glob(f"{CIP_DIR}/*.md")):
    doc = os.path.basename(path)
    for i, line in enumerate(open(path, errors="replace"), 1):
        for g in re.finditer(r'\b(SYS_[A-Z0-9_]+)\b(?:[^\n]{0,12}?=\s*|[^\n]{0,12}?\bopcode\b[^\n]{0,4}?)(\d{1,3})\b', line):
            name, num = g.group(1), int(g.group(2))
            if name in op and op[name] != num:
                findings.append((doc, i, "OPCODE-VAL", f"{name}={num} but codec={op[name]}"))
        # tight-adjacency address checks in either order: "0xNN NAME" / "NAME 0xNN"
        for g in re.finditer(r'0x([0-9A-Fa-f]{1,2})[`)\s]{1,4}([A-Z][A-Z0-9_]{3,})', line):
            hx, name = int(g.group(1), 16), g.group(2)
            if name in addr and addr[name] != hx:
                if doc in IGNORE_DOCS_FOR_CONTAINER_0X11 and name == "CONTAINER_REGISTRY":
                    continue
                findings.append((doc, i, "ADDR", f"{name}@0x{hx:02X} but code=0x{addr[name]:02X}"))

if findings:
    print(f"{len(findings)} allocation mismatch(es) vs source of truth:")
    for f in findings:
        print(f"  {f[0]}:{f[1]}  [{f[2]}]  {f[3]}")
    sys.exit(1)
print(f"OK — {len(op)} opcodes / {len(addr)} addresses; no unexpected spec mismatches.")
