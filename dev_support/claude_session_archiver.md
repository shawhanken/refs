# Claude Session Archiver — Usage Guide

Real-time, tamper-resistant, append-only mirror of **all** Claude Code session
transcripts on this host. Because every transcript line is copied the instant it
is written, deleting a session's `.jsonl` afterwards cannot erase what was said —
and the deletion itself is recorded. Built 2026-07-18 on `cowboy-001`.

> Motivation: a deleted `rm-this-session.sh` script surfaced in shell history and
> a full session audit could not rule out a self-erasing session. This closes
> that blind spot going forward.

---

## What is installed

| Component | Path |
|-----------|------|
| inotify daemon (root) | `/usr/local/bin/claude-session-archiver` |
| Query CLI | `/usr/local/bin/claude-archive` |
| systemd unit (enabled, `Restart=always`, starts at boot) | `/etc/systemd/system/claude-session-archiver.service` |
| The archive | `/var/log/claude-archive/stream.ndjson` — `root:root 600`, `chattr +a` (append-only) |
| Source + installer + README | `/home/ubuntu/claude-archiver/` |

It watches `~/.claude/projects/**/*.jsonl` (all projects, including new ones
created at runtime).

---

## Usage

The archive is root-only, so every query needs `sudo`.

```bash
# Archive size + record counts by type
sudo claude-archive stat

# Every session ever seen; deleted/moved-away ones are flagged DELETED
sudo claude-archive sessions

# Only sessions that were deleted or moved away
sudo claude-archive deleted

# Full-text search across all captured content (case-insensitive regex)
sudo claude-archive grep "some phrase"

# Reconstruct one session's raw transcript (accepts a session-id substring)
sudo claude-archive show 385b08cb

# Latest N prompts you actually typed (default 20), like tail — newest last.
# Uses each transcript's own timestamp; filters out tool results, sub-agent
# turns, system-injected lines, and the hourly marshal-pr-sweep cron.
sudo claude-archive tail 20
sudo claude-archive tail 5 --full     # full text, no truncation
sudo claude-archive tail 20 --cron    # only the marshal-pr-sweep cron prompts
sudo claude-archive tail 30 --all     # human + cron interleaved (cron tagged [cron])
```

### Service management

```bash
sudo systemctl status  claude-session-archiver
sudo systemctl restart claude-session-archiver
sudo journalctl -u claude-session-archiver -n 50
```

### Reinstall / update after editing the source

```bash
sudo bash /home/ubuntu/claude-archiver/install.sh
```

---

## How it survives deletion

`inotify` fires on every write to a transcript; the daemon appends each new line
to the archive immediately, tagging it with timestamp, project and session id.
A session that is created and `rm`-ed within the same shell command is still
captured (verified), followed by a `deleted` record. So even an erased session
leaves both its content and a "this was deleted at T" trace.

Record types in `stream.ndjson`: `line` (a captured transcript line),
`created`, `deleted`, `truncated`, `replaced`, `baseline_open` (content already
on disk at install time), `archiver_start` / `archiver_stop`.

---

## Manual rotation

The archive is append-only, so `logrotate` cannot rename it. To rotate by hand:

```bash
sudo chattr -a /var/log/claude-archive/stream.ndjson
sudo mv /var/log/claude-archive/stream.ndjson \
        /var/log/claude-archive/stream-$(date +%F).ndjson
sudo systemctl restart claude-session-archiver   # recreates + re-locks stream.ndjson
```

---

## Known limit (by design — local-only deployment)

A process with root / passwordless `sudo` — including the hourly
`--dangerously-skip-permissions` cron on this host — can `systemctl stop` the
service or `chattr -a` the archive before tampering. Local measures deter casual
deletion, self-erasing sessions, and any non-`sudo` agent, but **cannot stop a
`sudo`-capable adversary**. For that, stream each line off-box (remote syslog or
an S3 bucket with object-lock). Not enabled yet.

## Security note

The archive stores transcripts **verbatim, including any secrets** that appear in
them (the 2026-07-18 audit found real API keys and private keys in transcripts).
That is why it is `root:root 600`. Treat `stream.ndjson` as a sensitive asset,
and rotate any credentials known to have passed through a session.
