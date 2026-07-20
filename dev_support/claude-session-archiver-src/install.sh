#!/usr/bin/env bash
# install.sh — install the Claude session archiver as a root systemd service
# writing to a root-only, append-only archive. Run with sudo.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECTS="${CLAUDE_PROJECTS:-/home/ubuntu/.claude/projects}"
ARCHIVE_DIR="${CLAUDE_ARCHIVE_DIR:-/var/log/claude-archive}"

echo "== installing binaries =="
install -m 0755 -o root -g root "$SRC/claude-session-archiver.py" /usr/local/bin/claude-session-archiver
install -m 0755 -o root -g root "$SRC/claude-archive.py"           /usr/local/bin/claude-archive

echo "== archive dir (root-only) =="
mkdir -p "$ARCHIVE_DIR"
chown root:root "$ARCHIVE_DIR"
chmod 0700 "$ARCHIVE_DIR"
touch "$ARCHIVE_DIR/stream.ndjson"
chown root:root "$ARCHIVE_DIR/stream.ndjson"
chmod 0600 "$ARCHIVE_DIR/stream.ndjson"

echo "== systemd unit =="
cat > /etc/systemd/system/claude-session-archiver.service <<UNIT
[Unit]
Description=Claude Code session transcript archiver (real-time, append-only)
Documentation=man:inotify(7)
After=local-fs.target

[Service]
Type=simple
ExecStart=/usr/local/bin/claude-session-archiver
Environment=CLAUDE_PROJECTS=$PROJECTS
Environment=CLAUDE_ARCHIVE_DIR=$ARCHIVE_DIR
Restart=always
RestartSec=2
Nice=5
# Must be able to read /home; do NOT set ProtectHome. Least-privilege elsewhere:
NoNewPrivileges=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now claude-session-archiver.service
sleep 1.5

echo "== make archive append-only (chattr +a) =="
# baseline pass has started; +a still allows the daemon's O_APPEND writes,
# but blocks truncation / deletion / in-place rewrite by anything short of
# a process with CAP_LINUX_IMMUTABLE (root removing +a first).
chattr +a "$ARCHIVE_DIR/stream.ndjson" 2>/dev/null && echo "  +a set" || echo "  (chattr +a not supported here)"

echo "== status =="
systemctl --no-pager -l status claude-session-archiver.service | head -12
echo
echo "Done. Query with:  sudo claude-archive stat | sessions | deleted | grep <x> | show <sess>"
