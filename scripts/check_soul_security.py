"""Deterministic, stdlib-only guard for staged SOUL.md.

Run from repository root or any directory. Exit 0 for a safe staged SOUL.md;
exit 1 on findings, unreadable index, or a missing staged file.
This is a conservative pattern check, not a comprehensive security audit.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 64 * 1024
ROOT = Path(__file__).resolve().parents[1]
RULES = (
    ("private-key", re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----", re.I)),
    ("cloud-access-key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("slack-token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    ("openai-key", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("bearer-token", re.compile(rb"(?i)\bauthorization\s*:\s*bearer\s+\S+")),
    ("credential-assignment", re.compile(
        rb"(?im)^\s*(?:export\s+|\$env:)?(?:password|passwd|api[_-]?key|secret|access[_-]?token|private[_-]?key)\s*[:=]\s*[^\s`'\"<>][^\r\n]{5,}$")),
    ("dangerous-policy-override", re.compile(
        rb"(?i)\b(?:disable|bypass|skip|turn off)\s+(?:all\s+)?(?:security checks|secret scanning|audit logging|authorization|authentication|pre-commit hooks)\b")),
    ("privilege-escalation-instruction", re.compile(
        rb"(?i)\b(?:ignore|override)\s+(?:all\s+)?(?:system|developer|security)\s+(?:instructions|policies|rules)\b")),
    ("private-path", re.compile(rb"(?i)(?:[A-Z]:\\Users\\[^\\\r\n]+\\(?:\.ssh|AppData\\Roaming\\[^\\]+\\secrets)|/home/[^/\s]+/\.ssh/)")),
)


def staged_soul() -> bytes:
    process = subprocess.run(
        ["git", "-C", str(ROOT), "show", ":SOUL.md"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if process.returncode:
        raise ValueError("SOUL.md missing from Git index or index unreadable")
    return process.stdout


def check(content: bytes) -> list[str]:
    findings = []
    if len(content) > MAX_BYTES:
        findings.append(f"file-size: {len(content)} bytes exceeds {MAX_BYTES}")
    if b"\x00" in content:
        findings.append("binary-content: NUL byte")
    for name, pattern in RULES:
        if pattern.search(content):
            findings.append(name)
    return findings


def main() -> int:
    try:
        findings = check(staged_soul())
    except (OSError, ValueError) as exc:
        print(f"SOUL security check ERROR: {exc}", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"SOUL security check FAIL: {finding}", file=sys.stderr)
        return 1
    print("SOUL security check PASS (staged SOUL.md; deterministic pattern checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
