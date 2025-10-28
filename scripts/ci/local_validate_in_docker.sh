#!/usr/bin/env bash
set -euo pipefail

WHEEL_TGZ_DEFAULT="docs/ci-archive/wheelhouse-3.11-run-18884042880.tgz"
PY_IMG_DEFAULT="python:3.11"

usage() {
  cat <<EOF
Usage: $0 [--tar PATH] [--image IMAGE]

Runs a local validation of an archived wheelhouse inside a ${PY_IMG_DEFAULT} container.

Options:
  --tar PATH     Path to wheelhouse tarball (default: ${WHEEL_TGZ_DEFAULT})
  --image IMAGE  Docker image to use (default: ${PY_IMG_DEFAULT})
  -h|--help      Show this help

Example:
  ./scripts/ci/local_validate_in_docker.sh --tar docs/ci-archive/wheelhouse-3.11-run-18884042880.tgz

EOF
}

WHEEL_TGZ="${WHEEL_TGZ_DEFAULT}"
PY_IMG="${PY_IMG_DEFAULT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tar)
      WHEEL_TGZ="$2"; shift 2;;
    --image)
      PY_IMG="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH. This script requires Docker." >&2
  exit 3
fi

if [ ! -f "$WHEEL_TGZ" ]; then
  echo "Error: wheelhouse tarball not found at: $WHEEL_TGZ" >&2
  exit 4
fi

echo "Running local wheelhouse validation in Docker image: $PY_IMG"
echo "Using wheelhouse: $WHEEL_TGZ"

docker run --rm -v "$PWD":/src -w /src "$PY_IMG" bash -lc "set -euo pipefail
mkdir -p /tmp/wheelhouse
tar -xzf \"/src/${WHEEL_TGZ}\" -C /tmp/wheelhouse || true
python -m venv /tmp/venv
. /tmp/venv/bin/activate
pip install --upgrade pip setuptools wheel
# Try to install critical packages from wheelhouse first
pip install --no-index --find-links /tmp/wheelhouse -U numpy Pillow pytesseract || true
# If a requirements-heavy.txt exists, attempt to install it from the wheelhouse
if [ -f requirements-heavy.txt ]; then
  pip install --no-index --find-links /tmp/wheelhouse -r requirements-heavy.txt || true
fi
echo 'Running pytest -k smoke'
pytest -k smoke -q
"

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "Local validation succeeded (pytest -k smoke passed)."
else
  echo "Local validation failed. Exit code: $EXIT_CODE" >&2
fi

exit $EXIT_CODE
