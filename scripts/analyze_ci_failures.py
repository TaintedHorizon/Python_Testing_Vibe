#!/usr/bin/env python3
"""
analyze_ci_failures.py

Usage:
    # Set your GitHub personal access token in the environment (do NOT commit it):
    export GITHUB_TOKEN="<your_token_here>"
    python scripts/analyze_ci_failures.py --owner TaintedHorizon --repo Python_Testing_Vibe --outdir ./ci_logs

This script:
 - pages through all workflow runs with status=failure
 - downloads each run's logs ZIP
 - extracts job log files into outdir/{run_id}/
 - creates a summary JSON with run metadata and top error lines
"""
import os
import sys
import requests
import argparse
import time
import zipfile
import io
import json

GITHUB_API = "https://api.github.com"

def paged_get(url, headers, params=None):
    items = []
    page = 1
    per_page = 100
    while True:
        p = params.copy() if params else {}
        p.update({"page": page, "per_page": per_page})
        r = requests.get(url, headers=headers, params=p)
        r.raise_for_status()
        data = r.json()
        # Try common wrappers
        if isinstance(data, dict) and data.get("workflow_runs") is not None:
            batch = data.get("workflow_runs", [])
        elif isinstance(data, list):
            batch = data
        else:
            # unknown shape
            batch = []
        if not batch:
            break
        items.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(0.1)
    return items


def download_and_extract_logs(owner, repo, run_id, headers, outdir):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    r = requests.get(url, headers=headers, stream=True)
    if r.status_code == 404:
        return False, "logs not available"
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    run_dir = os.path.join(outdir, str(run_id))
    os.makedirs(run_dir, exist_ok=True)
    z.extractall(run_dir)
    return True, run_dir


def top_error_lines_from_dir(run_dir, max_lines=5):
    error_lines = []
    for root, dirs, files in os.walk(run_dir):
        for f in files:
            path = os.path.join(root, f)
            try:
                with open(path, errors="ignore") as fh:
                    for line in fh:
                        if ("ERROR" in line) or ("Traceback" in line) or ("failed" in line.lower()) or ("Exception" in line):
                            error_lines.append(line.strip())
                            if len(error_lines) >= max_lines:
                                return error_lines
            except Exception:
                continue
    return error_lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--owner", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--outdir", default="./ci_logs")
    p.add_argument("--token", default=os.getenv("GITHUB_TOKEN"))
    args = p.parse_args()
    if not args.token:
        print("Set GITHUB_TOKEN environment variable or pass --token", file=sys.stderr)
        sys.exit(1)
    headers = {"Authorization": f"token {args.token}", "Accept": "application/vnd.github.v3+json"}
    # 1) list failing runs
    url = f"{GITHUB_API}/repos/{args.owner}/{args.repo}/actions/runs"
    print("Listing failing workflow runs...")
    runs = paged_get(url, headers, params={"status":"failure"})
    print(f"Found {len(runs)} failing runs (local fetch).")
    os.makedirs(args.outdir, exist_ok=True)
    summary = []
    for r in runs:
        run_id = r.get("id")
        workflow_name = r.get("name") or r.get("workflow_id")
        print(f"Processing run {run_id} => {workflow_name}")
        try:
            ok, info = download_and_extract_logs(args.owner, args.repo, run_id, headers, args.outdir)
        except Exception as e:
            summary.append({"id": run_id, "name": workflow_name, "logs_available": False, "note": str(e)})
            continue
        if not ok:
            summary.append({"id": run_id, "name": workflow_name, "logs_available": False, "note": info})
            continue
        run_dir = info
        errors = top_error_lines_from_dir(run_dir)
        summary.append({"id": run_id, "name": workflow_name, "logs_available": True, "error_preview": errors})
    with open(os.path.join(args.outdir, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print("Done. Summary written to", os.path.join(args.outdir, "summary.json"))

if __name__ == "__main__":
    main()
