# claude-session-archiver

Real-time, append-only mirror of ALL Claude Code session transcripts, so that
deleting a session `.jsonl` cannot erase what was said — the content is copied
the instant it is written, and deletions are themselves recorded.

## Installed
- `/usr/local/bin/claude-session-archiver`  — the inotify daemon (root)
- `/usr/local/bin/claude-archive`           — query CLI
- `/etc/systemd/system/claude-session-archiver.service` — enabled, Restart=always
- `/var/log/claude-archive/stream.ndjson`   — the archive (root:root 600, `chattr +a` append-only)

## Query (needs sudo — archive is root-only)
    sudo claude-archive stat              # size + record counts
    sudo claude-archive sessions          # every session ever seen (DELETED ones flagged)
    sudo claude-archive deleted           # only sessions that were deleted/moved away
    sudo claude-archive grep <regex>      # search captured content
    sudo claude-archive show <sess-id>    # reconstruct one session's raw transcript
    sudo claude-archive tail [n]          # last n prompts YOU typed (default 20), newest last
    sudo claude-archive tail [n] --cron   # only the hourly marshal-pr-sweep cron prompts
    sudo claude-archive tail [n] --all    # human + cron interleaved (cron lines tagged [cron])
    sudo claude-archive tail [n] --full   # don't truncate long prompts

## How it survives deletion
inotify fires on every write; the daemon appends each new line to the archive
immediately. Even a session that is created and `rm`-ed within the same shell
command is captured (verified), plus a `deleted` record with a timestamp.

## Reinstall / update
    sudo bash /home/ubuntu/claude-archiver/install.sh

## Manual rotation (archive is append-only, so logrotate can't rename it)
    sudo chattr -a /var/log/claude-archive/stream.ndjson
    sudo mv .../stream.ndjson .../stream-$(date +%F).ndjson
    sudo systemctl restart claude-session-archiver   # recreates + re-+a's stream.ndjson

## KNOWN LIMIT (by design, you chose local-only)
A process with root / passwordless-sudo (e.g. the hourly `--dangerously-skip-permissions`
cron) can `systemctl stop` this service or `chattr -a` the archive. Local measures
deter casual/automated deletion and self-erasing sessions, but cannot stop a
sudo-capable adversary. For that, ship each line off-box (remote syslog / S3
object-lock). Ask to add shipping if the threat model needs it.

## SECURITY NOTE
The archive captures transcripts VERBATIM, including any secrets that appear in
them (API keys, private keys were found during the 2026-07-18 audit). It is
root-only 600 for that reason. Treat it as a sensitive asset.
