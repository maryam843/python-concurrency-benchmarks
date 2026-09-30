"""PII and secret scan over the full git history (every blob, every commit message, every author/committer).

Usage: python tools/pii_scan.py [--repo PATH] [--worktree]

Two kinds of checks:
1. Hashed denylist: SHA-256 of known personal tokens (a student ID, lab IP addresses and
   hostnames, university identities from the old coursework repo's commit metadata). Only the
   hashes are stored here, so the scanner never contains the values it looks for.
2. Generic patterns: e-mail addresses, IPv4 addresses, home-directory paths and common
   secret formats (cloud keys, tokens, private keys).

Exit code 0 means 0 hits.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

DENY_SHA256 = {
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
}

ALLOWED_EMAILS = {"185722545+maryam843@users.noreply.github.com", "noreply@github.com"}
ALLOWED_IPS = {"127.0.0.1", "0.0.0.0"}

TOKEN_RE = re.compile(r"[A-Za-z0-9_@.+-]+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
PATH_RE = re.compile(
    # (?<![\w.]) skips URL paths such as nyc.gov/home/... ; a real path starts after a space, quote or line start
    r"((?<![\w.])/home/[A-Za-z0-9_.-]+|(?<![\w.])/Users/[A-Za-z0-9_.-]+|[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9_.-]+)"
)
SECRET_RES = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"
    ),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "sk_prefixed_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "password_assignment": re.compile(
        r"(?i)\b(?:password|passwd|secret|api_key)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]"
    ),
}


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def scan_text(text: str, where: str) -> list[str]:
    hits: list[str] = []
    for tok in TOKEN_RE.findall(text):
        t = tok.strip(".-").lower()
        if len(t) >= 4 and hashlib.sha256(t.encode()).hexdigest() in DENY_SHA256:
            hits.append(f"{where}: denylisted token (sha256 {hashlib.sha256(t.encode()).hexdigest()[:12]})")
    for m in EMAIL_RE.findall(text):
        if m.lower() not in ALLOWED_EMAILS:
            hits.append(f"{where}: e-mail address")
    for m in IPV4_RE.findall(text):
        parts = m.split(".")
        if m not in ALLOWED_IPS and all(0 <= int(p) <= 255 for p in parts):
            hits.append(f"{where}: IPv4 address {m}")
    for m in PATH_RE.findall(text):
        hits.append(f"{where}: user path {m!r}")
    for name, rx in SECRET_RES.items():
        if rx.search(text):
            hits.append(f"{where}: possible secret ({name})")
    return hits


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]


def scan_history(repo: Path) -> list[str]:
    hits: list[str] = []
    fmt = "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x01"
    meta = _git(repo, "log", "--all", fmt).decode("utf-8", "replace")
    for rec in meta.split("\x01"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, an, ae, cn, ce, body = rec.split("\x00", 5)
        for email in (ae, ce):
            if email.lower() not in ALLOWED_EMAILS:
                hits.append(f"commit {sha[:8]}: author/committer e-mail not allowed")
        if re.search(r"(?i)co-authored-by|generated with", body):
            hits.append(f"commit {sha[:8]}: attribution trailer in message")
        hits += scan_text(" ".join((an, cn, body)), f"commit {sha[:8]} metadata")
    objs = _git(repo, "rev-list", "--all", "--objects").decode().splitlines()
    seen: set[str] = set()
    for line in objs:
        parts = line.split(" ", 1)
        if len(parts) != 2 or parts[0] in seen:
            continue
        sha, path = parts
        seen.add(sha)
        if _git(repo, "cat-file", "-t", sha).strip() != b"blob":
            continue
        data = _git(repo, "cat-file", "-p", sha)
        if path.endswith("tools/pii_scan.py") or is_binary(data):
            continue
        hits += scan_text(data.decode("utf-8", "replace"), f"{path} ({sha[:8]})")
    return hits


def scan_worktree(repo: Path) -> list[str]:
    hits: list[str] = []
    files = _git(repo, "ls-files", "--cached", "--others", "--exclude-standard").decode().splitlines()
    for f in files:
        p = repo / f
        if not p.is_file() or f.endswith("tools/pii_scan.py"):
            continue
        data = p.read_bytes()
        if not is_binary(data):
            hits += scan_text(data.decode("utf-8", "replace"), f)
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", type=Path)
    ap.add_argument("--worktree", action="store_true", help="also scan uncommitted files")
    args = ap.parse_args(argv)
    hits = scan_history(args.repo)
    if args.worktree:
        hits += scan_worktree(args.repo)
    for h in hits:
        print("HIT", h)
    print(f"pii_scan: {len(hits)} hits")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
