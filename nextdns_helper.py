#!/usr/bin/python3
"""Privileged, argument-validated configuration helper."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CONFIG = Path("/etc/systemd/resolved.conf.d/90-nextdns-manager.conf")


def restart():
    subprocess.run(["systemctl", "restart", "systemd-resolved.service"], check=True)


def enable(profile, device):
    if not re.fullmatch(r"[0-9a-f]{6}", profile):
        raise ValueError("Invalid NextDNS profile ID")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", device):
        raise ValueError("Invalid device name")
    content = (
        "# Managed by NextDNS Manager. Edit through the application.\n"
        f"# Device: {device}\n"
        "[Resolve]\n"
        "DNSOverTLS=yes\n"
        f"DNS=45.90.28.0#{device}-{profile}.dns.nextdns.io 45.90.30.0#{device}-{profile}.dns.nextdns.io\n"
        "Domains=~.\n"
    )
    CONFIG.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".nextdns-manager-", dir=CONFIG.parent)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, CONFIG)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    restart()


def disable():
    CONFIG.unlink(missing_ok=True)
    restart()


def main():
    if os.geteuid() != 0:
        raise PermissionError("Administrative privileges required")
    if len(sys.argv) == 4 and sys.argv[1] == "enable":
        enable(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == "disable":
        disable()
    else:
        raise ValueError("Usage: nextdns-manager-helper enable PROFILE DEVICE | disable")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
