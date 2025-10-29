#!/usr/bin/env bash
set -euo pipefail

# Generate a list of large blobs and print suggested git-filter-repo commands.
# This script DOES NOT perform any rewrite. It writes a candidates file to docs/HISTORY_REWRITE_CANDIDATES.txt

THRESHOLD_MB=${1:-50}
THRESHOLD_BYTES=$((THRESHOLD_MB * 1024 * 1024))

OUT_FILE=docs/HISTORY_REWRITE_CANDIDATES.txt
mkdir -p docs
echo "History rewrite candidates (threshold=${THRESHOLD_MB}MB)" > "$OUT_FILE"
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT_FILE"
echo >> "$OUT_FILE"

echo "Scanning repository for blobs larger than ${THRESHOLD_MB} MB..."

# produce list of blobs and their paths
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | sed -n 's/^blob //p' \
  | awk -v thresh=$THRESHOLD_BYTES '$2 > thresh {printf "%s %s %s\n", $1, $2, substr($0,index($0,$3))}' \
  | sort -k2 -n -r \
  | tee >(sed -n '1,200p') \
  > /tmp/large_blobs_raw.txt

if [ ! -s /tmp/large_blobs_raw.txt ]; then
  echo "No blobs above ${THRESHOLD_MB}MB found." | tee -a "$OUT_FILE"
  exit 0
fi

echo "Found the following large blobs:" >> "$OUT_FILE"
nl -ba /tmp/large_blobs_raw.txt | tee -a "$OUT_FILE"

echo >> "$OUT_FILE"
echo "Suggested actions:" >> "$OUT_FILE"
echo "1) Remove by size (recommended)" >> "$OUT_FILE"
echo "   git clone --mirror <repo-url> repo-rewrite.git" >> "$OUT_FILE"
echo "   cd repo-rewrite.git" >> "$OUT_FILE"
echo "   git filter-repo --strip-blobs-bigger-than ${THRESHOLD_MB}M" >> "$OUT_FILE"
echo >> "$OUT_FILE"
echo "2) Remove by path (if any specific path is listed below, add one --path line per path)" >> "$OUT_FILE"
echo >> "$OUT_FILE"
echo "Paths that appear in the above blobs (candidate paths will be printed):" >> "$OUT_FILE"

# map blob SHAs back to paths (best-effort)
awk '{print $1}' /tmp/large_blobs_raw.txt | while read -r sha; do
  git rev-list --all --objects | grep "^$sha " | awk '{print $2 "  ->  " $1}' | tee -a "$OUT_FILE"
done

echo >> "$OUT_FILE"
echo "If you want me to prepare a filter-repo command that removes specific paths, re-run this script with the same threshold and then edit the produced $OUT_FILE to include the exact --path lines you want removed. I will not perform any rewrite." >> "$OUT_FILE"

echo "Wrote candidates to $OUT_FILE"

exit 0
