#!/usr/bin/env python3
"""
Strict preflight validator using PyYAML.
Scans .github/workflows/*.yml, extracts job names and compares against branch-protection required contexts.
Usage: tools/pr_preflight_validate.py --repo owner/repo
"""
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except Exception as e:
    print("PyYAML is required for the strict validator. Install with: pip install pyyaml", file=sys.stderr)
    raise


def gh_api(path):
    p = subprocess.run(["gh", "api", path, "-q", "."], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh api failed: {p.stderr}")
    return json.loads(p.stdout)


def get_required_contexts(repo):
    path = f"repos/{repo}/branches/main/protection"
    try:
        res = subprocess.run(["gh", "api", path, "-q", ".required_status_checks.contexts"], capture_output=True, text=True)
        if res.returncode != 0:
            print("Could not fetch branch protection contexts; falling back to empty list", file=sys.stderr)
            return []
        # res.stdout is a JSON array
        return json.loads(res.stdout)
    except Exception:
        return []


def get_allowed_root_files_from_workflow():
    """Try to extract the allowed root-level files list from the block-root-files workflow.

    This is a pragmatic parser: it looks for the literal `allowed=(...)` construct
    inside `.github/workflows/block-root-files.yml` and returns the entries.
    Falls back to a conservative default set if not present.
    """
    wf = Path('.github/workflows/block-root-files.yml')
    defaults = [
        "README.md",
        "Makefile",
        ".gitignore",
        ".github",
        "docs",
        "scripts",
        "dev_tools",
        "start_app.sh",
        "pyrightconfig.json",
        "pytest.ini",
        "Python_Testing_Vibe.code-workspace",
        "archive",
        "tools",
        "ui_tests",
        "LICENSE",
        ".venv-ci",
        ".ruff_cache",
    ]
    if not wf.exists():
        return defaults
    text = wf.read_text()
    import re
    m = re.search(r"allowed=\(([^)]*)\)", text, flags=re.S)
    if not m:
        return defaults
    inner = m.group(1)
    # split by whitespace while trimming quotes and commas
    parts = []
    for tok in inner.split():
        tok = tok.strip().strip('"\'')
        if tok.endswith(')'):
            tok = tok[:-1]
        tok = tok.strip(',')
        if tok:
            parts.append(tok)
    # Merge with defaults to be safe
    merged = list(dict.fromkeys(defaults + parts))
    return merged


def discover_job_names():
    jobnames = []
    expanded = []
    for p in Path('.github/workflows').glob('*.yml'):
        data = yaml.safe_load(p.read_text())
        if not data:
            continue
        jobs = data.get('jobs') or {}
        for job_id, job_def in jobs.items():
            name = job_def.get('name')
            if name:
                jobnames.append(str(name))
                # attempt to expand matrix values if present
                strategy = job_def.get('strategy') or {}
                matrix = strategy.get('matrix') or {}
                if matrix:
                    # build list of keys with list values
                    keys = [k for k, v in matrix.items() if isinstance(v, list)]
                    if keys:
                        # create cartesian product of matrix values
                        from itertools import product
                        lists = [matrix[k] for k in keys]
                        for combo in product(*lists):
                            expanded_name = str(name)
                            for k, val in zip(keys, combo):
                                # replace common placeholder patterns
                                expanded_name = expanded_name.replace('${{ matrix.' + k + ' }}', str(val))
                                expanded_name = expanded_name.replace('${{matrix.' + k + '}}', str(val))
                                expanded_name = expanded_name.replace('${{ matrix.' + k + '}}', str(val))
                                expanded_name = expanded_name.replace('${{matrix.' + k + ' }}', str(val))
                            expanded.append(expanded_name)
            else:
                # fallback: derive a readable name from job_id
                jobnames.append(str(job_id))
    # expose expanded names as attribute on the function
    discover_job_names.expanded = expanded
    return jobnames


def detect_root_level_violations():
    """Detect added root-level files compared to origin/main and report any files not allowed.

    Returns a list of offending filenames (empty if none).
    """
    # Ensure we have an up-to-date origin/main
    try:
        subprocess.run(["git", "fetch", "origin", "main"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = "origin/main"
    except Exception:
        base = "main"

    # List changed files between base and HEAD
    p = subprocess.run(["git", "diff", "--name-only", f"{base}..HEAD"], capture_output=True, text=True)
    if p.returncode != 0:
        # fallback: no diff
        return []
    files = [f.strip() for f in p.stdout.splitlines() if f.strip()]
    # collect root-level added/changed files (no slash)
    root_files = [f for f in files if '/' not in f]
    if not root_files:
        return []

    allowed = get_allowed_root_files_from_workflow()
    bad = [f for f in root_files if f not in allowed]
    return bad


def main(argv):
    repo = None
    if '--repo' in argv:
        i = argv.index('--repo')
        if i+1 < len(argv):
            repo = argv[i+1]
    if not repo:
        # try to detect
        p = subprocess.run(['gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner'], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            repo = p.stdout.strip()

    if not repo:
        print('Repository not specified and could not be detected. Use --repo owner/repo', file=sys.stderr)
        return 2

    required = get_required_contexts(repo)
    print('Required contexts:')
    for r in required:
        print('  -', r)

    jobnames = discover_job_names()
    # collect expanded names if available
    expanded = getattr(discover_job_names, 'expanded', [])
    all_names = list(jobnames) + list(expanded)
    print('\nDiscovered job names:')
    for j in all_names:
        print('  -', j)

    missing = [r for r in required if r not in all_names]
    if missing:
        print('\nMissing required contexts:')
        for m in missing:
            print('  -', m)
        print('\nInstall PyYAML and update workflows (or branch-protection) to match job names.', file=sys.stderr)
        return 3

    print('\nAll required contexts are present.')
    return 0


if __name__ == '__main__':
    try:
        rc = main(sys.argv[1:])
        sys.exit(rc)
    except Exception as e:
        print('Error during validation:', e, file=sys.stderr)
        sys.exit(10)
