#!/usr/bin/env python3
"""claude-archive — query the append-only Claude session archive.

  claude-archive stat                 archive size + record counts by type
  claude-archive sessions [--deleted] list sessions seen (mark deleted ones)
  claude-archive deleted              only sessions that were deleted/moved away
  claude-archive grep <pattern>       search captured content (case-insensitive)
  claude-archive show <sess-substr>   reconstruct one session's raw transcript
  claude-archive tail [n] [--full]    last n prompts you actually typed (default 20)
  claude-archive tail [n] --cron      last n marshal-pr-sweep cron prompts only
  claude-archive tail [n] --all       both human + cron (cron lines tagged [cron])
"""
import os, sys, json, re

ARCHIVE_DIR = os.environ.get("CLAUDE_ARCHIVE_DIR", "/var/log/claude-archive")
ARCHIVE = os.path.join(ARCHIVE_DIR, "stream.ndjson")

def records():
    with open(ARCHIVE, encoding="utf-8", errors="replace") as f:
        for line in f:
            line=line.rstrip("\n")
            if not line: continue
            try: yield json.loads(line)
            except Exception: continue

def cmd_stat():
    from collections import Counter
    ev=Counter(); sess=set()
    for r in records():
        ev[r.get("ev")]+=1
        sess.add((r.get("p"),r.get("s")))
    sz=os.path.getsize(ARCHIVE)
    print(f"archive: {ARCHIVE}  ({sz/1e6:.1f} MB)")
    print(f"distinct sessions: {len(sess)}")
    for k,v in ev.most_common(): print(f"  {v:>8}  {k}")

def cmd_sessions(only_deleted=False):
    CONTROL={"archiver_start","archiver_stop"}
    info={}
    for r in records():
        ev=r.get("ev")
        if ev in CONTROL: continue
        key=(r.get("p"),r.get("s"))
        d=info.setdefault(key,{"first":r["t"],"last":r["t"],"lines":0,"deleted":False})
        d["last"]=r["t"]
        if ev=="line": d["lines"]+=1
        if ev in ("deleted",): d["deleted"]=True
    rows=sorted(info.items(), key=lambda kv: kv[1]["last"])
    for (p,s),d in rows:
        if only_deleted and not d["deleted"]: continue
        flag="  \033[31mDELETED\033[0m" if d["deleted"] else ""
        print(f"{d['last']}  {d['lines']:>5} lines  {p}/{s}{flag}")
    print(f"\n{len(rows)} sessions" + (" (deleted only)" if only_deleted else ""))

def cmd_grep(pat):
    rx=re.compile(pat, re.I)
    n=0
    for r in records():
        raw=r.get("raw","")
        if raw and rx.search(raw):
            n+=1
            snip=raw
            m=rx.search(raw)
            a=max(0,m.start()-40); b=min(len(raw),m.end()+60)
            snip="…"+raw[a:b]+"…"
            print(f"{r['t']}  {r.get('p')}/{r.get('s')}: {snip}")
    print(f"\n{n} matches")

def cmd_show(sub):
    for r in records():
        if sub in (r.get("s") or "") and r.get("ev")=="line":
            print(r.get("raw",""))

NOISE_PREFIX=("<local-command-stdout>","Caveat:","<task-notification>",
    "<system-reminder>","[SYSTEM NOTIFICATION","[Request interrupted")

def _user_text(raw):
    """Return (ts, text) of a genuine human-typed prompt, or None for tool
    results, sub-agent turns, meta, cron, or system-injected lines."""
    try:
        o=json.loads(raw)
    except Exception:
        return None
    if o.get("type")!="user" or o.get("isSidechain") or o.get("isMeta"):
        return None
    msg=o.get("message") or {}
    if msg.get("role")!="user": return None
    c=msg.get("content")
    if isinstance(c,list):
        if any(isinstance(x,dict) and x.get("type")=="tool_result" for x in c):
            return None
        txt=" ".join(x.get("text","") for x in c if isinstance(x,dict) and x.get("type")=="text")
    elif isinstance(c,str):
        txt=c
    else:
        return None
    txt=txt.strip()
    if not txt: return None
    if any(txt.startswith(p) for p in NOISE_PREFIX): return None
    # classify: marshal-sweep hourly cron vs a human-typed prompt
    if txt.startswith("Run the marshal-pr-sweep skill"):
        return (o.get("timestamp"), txt, "cron")
    m=re.search(r"<command-name>\s*([^<]+?)\s*</command-name>", txt)
    if m: return (o.get("timestamp"), m.group(1).strip(), "human")
    if txt.startswith("<") and "command-message" in txt: return None
    return (o.get("timestamp"), txt, "human")

def cmd_tail(n=20, full=False, mode="human"):
    # mode: "human" (default) | "cron" (only marshal-sweep) | "all"
    prompts=[]
    for r in records():
        if r.get("ev")!="line": continue
        res=_user_text(r.get("raw",""))
        if res is None: continue
        ts, t, kind = res
        if mode!="all" and kind!=mode: continue
        prompts.append((ts or r.get("t",""), r.get("s",""), t, kind))
    prompts.sort(key=lambda x: x[0])           # true chronological (raw timestamp)
    if mode=="human":
        dedup=[]
        for p in prompts:
            if dedup and dedup[-1][2]==p[2]: continue   # collapse retries/dupes
            dedup.append(p)
    else:
        dedup=prompts                          # keep every cron run (identical text is expected)
    for ts,sess,t,kind in dedup[-n:]:
        show=ts.replace("T"," ")[:19] if ts else "?"
        t=t if full else " ".join(t.split())
        if not full and len(t)>160: t=t[:157]+"…"
        tag="\033[36m[cron]\033[0m " if (mode=="all" and kind=="cron") else ""
        print(f"\033[2m{show}  {sess[:8]}\033[0m  {tag}{t}")

def main():
    a=sys.argv[1:] or ["stat"]
    c=a[0]
    if c=="stat": cmd_stat()
    elif c=="sessions": cmd_sessions("--deleted" in a)
    elif c=="deleted": cmd_sessions(True)
    elif c=="grep" and len(a)>1: cmd_grep(a[1])
    elif c=="show" and len(a)>1: cmd_show(a[1])
    elif c=="tail":
        nums=[int(x) for x in a[1:] if x.isdigit()]
        mode="cron" if "--cron" in a else ("all" if "--all" in a else "human")
        cmd_tail(nums[0] if nums else 20, "--full" in a, mode)
    else: print(__doc__)

if __name__=="__main__":
    main()
