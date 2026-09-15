"""Check staged bytes before publishing; report paths/rules, never matched secrets."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'GitHub token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b',
    'AWS access key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'API token': rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b',
    'URL credentials': rb'https?://[^\s/"\x27:]+:[^\s/"\x27@]+@',
}


def main():
    names = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMR'], cwd=ROOT).decode('utf-8').split('\0')
    failures = []
    for name in filter(None, names):
        path = Path(name)
        if any(p in {'.local', 'output', 'workspaces', '.venv', 'node_modules', '__pycache__'} for p in path.parts) or path.name.startswith('.env') and path.name != '.env.example':
            failures.append((name, 'private/generated path'))
        data = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
        if len(data) > 2_000_000 or b'\0' in data:
            failures.append((name, 'unexpected binary/large file'))
        for label, pattern in PATTERNS.items():
            if re.search(pattern, data):
                failures.append((name, label))
    for name, label in failures:
        print(f'BLOCKED: {name} ({label})')
    print(f'Staged scan: {len(list(filter(None, names)))} files; {len(failures)} findings')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
