"""Dependency-free bootstrap hygiene checks; not an execution conformance suite."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'README.md', 'LICENSE', 'CONTRIBUTING.md', 'GOVERNANCE.md',
    'CODE_OF_CONDUCT.md', 'SECURITY.md', '.github/CODEOWNERS',
    '.github/PULL_REQUEST_TEMPLATE.md', '.github/dependabot.yml',
    'docs/ARCHITECTURE_HANDOFF.md', 'docs/ROADMAP.md',
    'docs/REPOSITORY_SECURITY.md',
)
errors = []
for name in REQUIRED:
    if not (ROOT / name).is_file():
        errors.append(f'Missing required file: {name}')

result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                        check=True, capture_output=True)
paths = [ROOT / p for p in result.stdout.decode().split('\0') if p]
secret_patterns = [
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
    re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
]
for path in paths:
    rel = path.relative_to(ROOT).as_posix()
    if path.is_symlink():
        errors.append(f'Symlink requires explicit policy review: {rel}')
        continue
    if path.name.startswith('.env') and path.name != '.env.example':
        errors.append(f'Environment file tracked: {rel}')
    if path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.db', '.sqlite', '.sqlite3'}:
        errors.append(f'Sensitive/runtime file tracked: {rel}')
    data = path.read_bytes()
    if len(data) > 1_000_000:
        errors.append(f'Large file requires explicit policy review: {rel}')
    if b'\x00' in data:
        errors.append(f'Binary file requires explicit policy review: {rel}')
        continue
    try:
        content = data.decode('utf-8')
    except UnicodeDecodeError:
        errors.append(f'Non-UTF-8 file requires explicit policy review: {rel}')
        continue
    if any(pattern.search(content) for pattern in secret_patterns):
        errors.append(f'Possible credential in {rel}; inspect locally (value redacted)')
    if rel.startswith('.github/workflows/'):
        for line in content.splitlines():
            match = re.search(r'\buses:\s*(\S+)', line)
            if match and not re.fullmatch(r'[^\s@]+@[0-9a-f]{40}', match[1]):
                errors.append(f'Action must be pinned to full commit SHA: {rel}')
        if re.search(r'\bpull_request_target\s*:', content):
            errors.append(f'Privileged PR trigger requires explicit policy review: {rel}')
        if 'persist-credentials: false' not in content or 'contents: read' not in content:
            errors.append(f'Workflow needs explicit read permissions and no persisted checkout credentials: {rel}')

if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print(f'Repository hygiene passed ({len(paths)} tracked files).')
print('Pattern checks are limited; no runtime or complete secret-scanning guarantee.')
