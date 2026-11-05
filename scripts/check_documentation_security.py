"""Scan staged or committed documentation without printing matched secrets."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

MAX_BYTES = 1024 * 1024
EXTENSIONS = {'.md', '.mdx', '.rst', '.adoc', '.txt'}
RULES = (
    ('private-key', rb'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----'),
    ('cloud-access-key', rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    ('github-token', rb'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    ('slack-token', rb'\bxox[baprs]-[A-Za-z0-9-]{16,}\b'),
    ('openai-key', rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),
    ('bearer-token', rb'\bauthorization\s*:\s*bearer\s+\S+'),
    ('credential-assignment', rb'(?m)^\s*(?:export\s+|\$env:)?(?:password|passwd|api[_-]?key|secret|access[_-]?token|private[_-]?key)\s*[:=]\s*[^\s'+String.raw`'"<>][^\r\n]{5,}$'),
    ('dangerous-policy-override', rb'\b(?:disable|bypass|skip|turn off)\s+(?:all\s+)?(?:security checks|secret scanning|audit logging|authorization|authentication|pre-commit hooks)\b'),
    ('privilege-escalation-instruction', rb'\b(?:ignore|override)\s+(?:all\s+)?(?:system|developer|security)\s+(?:instructions|policies|rules)\b'),
    ('private-path', rb'(?:[A-Z]:\\Users\\[^\\\r\n]+\\(?:\.ssh|AppData\\Roaming\\[^\\]+\\secrets)|/home/[^/\s]+/\.ssh/)'),
)
COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in RULES]


def git(*args: str) -> bytes:
    p = subprocess.run(['git', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError('Git index or revision unavailable')
    return p.stdout


def is_doc(path: str) -> bool:
    return path == 'AGENTS.md' or PurePosixPath(path).suffix.lower() in EXTENSIONS


def check(content: bytes) -> list[str]:
    findings = []
    if len(content) > MAX_BYTES:
        findings.append('file-size')
    if b'\x00' in content:
        findings.append('binary-content')
    findings.extend(name for name, pattern in COMPILED if pattern.search(content))
    return findings


def changed_paths(revision: str | None) -> list[str]:
    if revision:
        data = git('diff', '--name-only', '--diff-filter=ACMR', '-z', revision)
    else:
        data = git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z')
    return [p.decode('utf-8', 'surrogateescape') for p in data.split(b'\x00') if p]


def run(revision: str | None) -> int:
    try:
        paths = sorted(set(changed_paths(revision)) | {'AGENTS.md'})
        failures = 0
        for path in paths:
            if not is_doc(path):
                continue
            content = git('show', f'{revision.split("..")[-1]}:{path}' if revision else f':{path}')
            for finding in check(content):
                print(f'documentation security FAIL: {path}: {finding}', file=sys.stderr)
                failures += 1
        if failures:
            return 1
        print('documentation security PASS')
        return 0
    except (RuntimeError, UnicodeError, ValueError) as exc:
        print(f'documentation security ERROR: {exc}', file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--range', dest='revision', help='Git revision range, e.g. BASE..HEAD (CI)')
    return run(parser.parse_args().revision)


if __name__ == '__main__':
    raise SystemExit(main())
