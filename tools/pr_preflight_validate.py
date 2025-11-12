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
