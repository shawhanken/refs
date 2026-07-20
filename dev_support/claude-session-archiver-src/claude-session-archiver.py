#!/usr/bin/env python3
"""
claude-session-archiver — real-time, append-only mirror of all Claude Code
session transcripts.

Watches ~/.claude/projects/**/*.jsonl via inotify and appends every newly
written line to a root-owned, append-only archive the moment it is written, so
that deleting a session .jsonl afterwards cannot remove what was already
captured. Deletions are themselves recorded, so an erased session still leaves a
trace ("session X existed and was deleted at T").

Zero third-party deps: inotify is driven through ctypes.
Runs as root under systemd. See install.sh.
"""
import os, sys, json, time, ctypes, ctypes.util, struct, errno, glob, signal

WATCH_ROOTS = os.environ.get("CLAUDE_PROJECTS",
    "/home/ubuntu/.claude/projects").split(":")
ARCHIVE_DIR = os.environ.get("CLAUDE_ARCHIVE_DIR", "/var/log/claude-archive")
ARCHIVE = os.path.join(ARCHIVE_DIR, "stream.ndjson")
STATE   = os.path.join(ARCHIVE_DIR, ".offsets.json")   # best-effort resume

# ---- inotify constants ----
IN_MODIFY=0x2; IN_CLOSE_WRITE=0x8; IN_MOVED_FROM=0x40; IN_MOVED_TO=0x80
IN_CREATE=0x100; IN_DELETE=0x200; IN_DELETE_SELF=0x400; IN_MOVE_SELF=0x800
IN_ISDIR=0x40000000
DIR_MASK = IN_CREATE|IN_MOVED_TO|IN_DELETE|IN_MOVED_FROM|IN_DELETE_SELF
EVENT_HDR = struct.calcsize("iIII")

libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)

def _iso(t=None):
    t = time.time() if t is None else t
    lt = time.gmtime(t)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", lt)

class Archiver:
    def __init__(self):
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        os.chmod(ARCHIVE_DIR, 0o700)
        # open archive in append mode (works even when the file is chattr +a)
        self.afd = os.open(ARCHIVE, os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o600)
        self.fd = libc.inotify_init1(0o2000000)  # IN_CLOEXEC (blocking reads)
        if self.fd < 0: raise OSError(ctypes.get_errno(), "inotify_init1")
        self.wd2path = {}
        self.path2wd = {}
        self.offsets = {}      # realpath -> byte offset consumed
        self.partial = {}      # realpath -> bytes not yet terminated by \n
        self.inodes  = {}      # realpath -> (st_dev, st_ino)
        self._load_state()

    # ---------- archive record ----------
    def emit(self, ev, path, raw=None, extra=None):
        proj, sess = self._split(path)
        rec = {"t": _iso(), "ev": ev, "p": proj, "s": sess}
        if extra: rec.update(extra)
        if raw is not None: rec["raw"] = raw
        os.write(self.afd, (json.dumps(rec, ensure_ascii=False)+"\n").encode("utf-8","replace"))

    @staticmethod
    def _split(path):
        # .../projects/<proj>/<session>.jsonl  -> (proj, session)
        proj = os.path.basename(os.path.dirname(path)) or "?"
        fn = os.path.basename(path)
        sess = fn[:-6] if fn.endswith(".jsonl") else fn
        return proj, sess

    # ---------- state (best effort; archive is source of truth) ----------
    def _load_state(self):
        try:
            d = json.load(open(STATE))
            self.offsets = d.get("offsets", {})
            self.inodes  = {k: tuple(v) for k,v in d.get("inodes", {}).items()}
        except Exception:
            pass
    def _save_state(self):
        try:
            tmp = STATE+".tmp"
            json.dump({"offsets": self.offsets,
                       "inodes": {k:list(v) for k,v in self.inodes.items()}},
                      open(tmp,"w"))
            os.replace(tmp, STATE)
        except Exception:
            pass

    # ---------- watches ----------
    def add_watch(self, path, mask):
        wd = libc.inotify_add_watch(self.fd, path.encode(), mask)
        if wd >= 0:
            self.wd2path[wd] = path
            self.path2wd[path] = wd
        return wd

    def watch_tree(self):
        for root in WATCH_ROOTS:
            if not os.path.isdir(root): continue
            self.add_watch(root, DIR_MASK|IN_MODIFY)
            for sub in glob.glob(root+"/*"):
                if os.path.isdir(sub):
                    self.add_watch(sub, DIR_MASK|IN_MODIFY)

    # ---------- tailing ----------
    def tail(self, path, reason="modify"):
        if not path.endswith(".jsonl"): return
        try:
            st = os.stat(path)
        except FileNotFoundError:
            return
        key = os.path.realpath(path)
        ident = (st.st_dev, st.st_ino)
        off = self.offsets.get(key, 0)
        if self.inodes.get(key) != ident:
            # new file or replaced-in-place (inode changed) -> restart from 0
            if key in self.inodes:
                self.emit("replaced", path, extra={"old_ino": self.inodes[key][1]})
            off = 0; self.partial.pop(key, None)
            self.inodes[key] = ident
        if st.st_size < off:                       # truncated
            self.emit("truncated", path, extra={"from": off, "to": st.st_size})
            off = 0; self.partial.pop(key, None)
        if st.st_size == off:
            return
        try:
            rfd = os.open(path, os.O_RDONLY)
        except FileNotFoundError:
            return
        try:
            os.lseek(rfd, off, os.SEEK_SET)
            data = b""
            while True:
                chunk = os.read(rfd, 1<<20)
                if not chunk: break
                data += chunk
        finally:
            os.close(rfd)
        self.offsets[key] = off + len(data)
        buf = self.partial.pop(key, b"") + data
        *lines, tail = buf.split(b"\n")
        if tail:                                   # incomplete final line
            self.partial[key] = tail
        for ln in lines:
            if ln == b"": continue
            self.emit("line", path, raw=ln.decode("utf-8","replace"))

    def baseline(self):
        """Mirror content already on disk that we have not seen before."""
        for root in WATCH_ROOTS:
            for path in glob.glob(root+"/**/*.jsonl", recursive=True):
                key = os.path.realpath(path)
                if key not in self.offsets:
                    self.emit("baseline_open", path)
                self.tail(path, reason="baseline")
        self._save_state()

    # ---------- event loop ----------
    def run(self):
        self.watch_tree()
        self.baseline()
        self.emit("archiver_start", ARCHIVE, extra={"roots": WATCH_ROOTS, "pid": os.getpid()})
        buf = b""
        last_save = time.time()
        while True:
            try:
                data = os.read(self.fd, 1<<16)
            except BlockingIOError:
                time.sleep(0.2); continue
            except OSError as e:
                if e.errno == errno.EINTR: continue
                raise
            buf += data
            while len(buf) >= EVENT_HDR:
                wd, mask, cookie, nlen = struct.unpack("iIII", buf[:EVENT_HDR])
                if len(buf) < EVENT_HDR+nlen: break
                name = buf[EVENT_HDR:EVENT_HDR+nlen].split(b"\0",1)[0].decode("utf-8","replace")
                buf = buf[EVENT_HDR+nlen:]
                self.handle(wd, mask, name)
            if time.time()-last_save > 5:
                self._save_state(); last_save = time.time()

    def handle(self, wd, mask, name):
        base = self.wd2path.get(wd)
        if base is None: return
        path = os.path.join(base, name) if name else base
        isdir = bool(mask & IN_ISDIR)
        if isdir:
            if mask & (IN_CREATE|IN_MOVED_TO):
                self.add_watch(path, DIR_MASK|IN_MODIFY)   # new project dir
            return
        if mask & IN_MODIFY:
            self.tail(path)
        elif mask & (IN_CREATE|IN_MOVED_TO):
            if path.endswith(".jsonl"):
                self.emit("created", path); self.tail(path)
        elif mask & (IN_DELETE|IN_MOVED_FROM):
            if path.endswith(".jsonl"):
                self.tail(path, reason="pre-delete")       # grab any last bytes
                self.emit("deleted", path,
                          extra={"reason": "unlink" if (mask&IN_DELETE) else "moved_away"})
        elif mask & (IN_DELETE_SELF|IN_MOVE_SELF):
            self.emit("watchdir_gone", path)

def main():
    a = Archiver()
    def _term(*_):
        a.emit("archiver_stop", ARCHIVE); a._save_state(); sys.exit(0)
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    a.run()

if __name__ == "__main__":
    main()
