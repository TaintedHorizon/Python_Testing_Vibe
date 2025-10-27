#!/usr/bin/env python3
"""
Cluster error fingerprints in ci_logs/summary.json and produce a short report.
"""
import json
import re
from collections import Counter, defaultdict

SUMMARY_PATH = "./ci_logs/summary.json"

# Normalize a line to create a fingerprint
def fingerprint(line: str) -> str:
    if not line:
        return "<empty>"
    # remove timestamps like 2025-10-25T21:26:20.8986930Z
    line = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", "", line)
    # strip ANSI escapes
    line = re.sub(r"\x1B\[[0-9;]*[A-Za-z]", "", line)
    # collapse numbers
    line = re.sub(r"\d+", "<num>", line)
    # collapse paths and python filenames
    line = re.sub(r"[\w\-/\\]+\.py", "<pyfile>", line)
    # collapse long hashes
    line = re.sub(r"[0-9a-f]{7,}", "<hash>", line)
    # shorten whitespace
    line = " ".join(line.split())
    # keep first 120 chars
    return line[:120]


def main():
    with open(SUMMARY_PATH) as fh:
        data = json.load(fh)

    counter = Counter()
    examples = defaultdict(list)

    for item in data:
        # if logs are unavailable, use note
        if not item.get("logs_available"):
            key = fingerprint(item.get("note", "<no logs>"))
            counter[key] += 1
            if len(examples[key]) < 5:
                examples[key].append((item.get("id"), item.get("name"), item.get("note")))
            continue
        # otherwise use first error_preview line(s)
        previews = item.get("error_preview") or []
        if not previews:
            key = fingerprint("<no_preview>")
            counter[key] += 1
            if len(examples[key]) < 5:
                examples[key].append((item.get("id"), item.get("name"), "<no_preview>"))
            continue
        # use up to first 3 preview lines to make a combined fingerprint
        text = " ".join(previews[:3])
        key = fingerprint(text)
        counter[key] += 1
        if len(examples[key]) < 5:
            examples[key].append((item.get("id"), item.get("name"), previews[:3]))

    # produce report
    top = counter.most_common(20)
    report = {"total_runs": len(data), "top_fingerprints": []}
    for k, cnt in top:
        report["top_fingerprints"].append({"fingerprint": k, "count": cnt, "examples": examples[k]})

    out_path = "./ci_logs/clusters.json"
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2)

    print("Wrote clusters to", out_path)
    for entry in report["top_fingerprints"][:10]:
        print(f"\nCount: {entry['count']}\nFingerprint: {entry['fingerprint'][:200]}\nExamples: {entry['examples'][:3]}")

if __name__ == '__main__':
    main()
