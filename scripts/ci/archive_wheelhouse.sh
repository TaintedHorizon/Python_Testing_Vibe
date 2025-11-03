#!/usr/bin/env bash
set -euo pipefail

usage(){
  cat <<USG
Usage: archive_wheelhouse.sh --src PATH [--dest-dir docs/ci-archive] [--run-id ID]

Copies a wheelhouse tgz into the docs/ci-archive directory and writes a small
metadata file with provenance (run id, commit, date, sha256).

Example:
  ./scripts/ci/archive_wheelhouse.sh --src ci_artifacts/run-18884042880/wheelhouse-3.11.tgz --run-id 18884042880
USG
}

DEST_DIR="docs/ci-archive"
SRC=""
RUN_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src) SRC="$2"; shift 2;;
    --dest-dir) DEST_DIR="$2"; shift 2;;
    --run-id) RUN_ID="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$SRC" ]]; then echo "--src is required" >&2; usage; exit 3; fi
if [[ ! -f "$SRC" ]]; then echo "source not found: $SRC" >&2; exit 4; fi

mkdir -p "$DEST_DIR"

base=$(basename "$SRC")
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
sha256=$(sha256sum "$SRC" | awk '{print $1}')
commit=$(git rev-parse --short HEAD 2>/dev/null || echo "<no-git>")

target="$DEST_DIR/${base%.*}-run-${RUN_ID:-unknown}.tgz"
meta="$DEST_DIR/${base%.*}-run-${RUN_ID:-unknown}.meta"

cp "$SRC" "$target"
cat > "$meta" <<EOF
run_id: ${RUN_ID:-unknown}
source: $SRC
archived_at: $ts
git_commit: $commit
sha256: $sha256
notes: "Archived by scripts/ci/archive_wheelhouse.sh"
EOF

echo "Archived $SRC -> $target"
echo "Metadata: $meta"
echo
ls -lh "$target"
echo
echo "Meta contents:"; cat "$meta"

exit 0
