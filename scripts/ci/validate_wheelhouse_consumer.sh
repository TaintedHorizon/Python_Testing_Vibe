#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USG'
Usage: validate_wheelhouse_consumer.sh [--local-tar PATH] [--venv-dir PATH] [--packages "pkg1 pkg2"] [--fetch-opts "--timeout-min 20 --interval-sec 30"] [--pytest-args "..."]

This script creates an isolated venv, fetches a wheelhouse (either by calling
./scripts/ci/fetch_wheelhouse_poll.sh or using a local tarball), installs the
requested packages from the wheelhouse using `pip --no-index --find-links` and
runs smoke tests (pytest -k smoke by default).

Options:
  --local-tar PATH        Use a local wheelhouse tarball instead of polling GitHub Actions.
  --venv-dir PATH         Directory to create the virtualenv in (default: ./.venv-ci)
  --packages "pkg pkg"    Space-separated package names to install (default: "numpy Pillow pytesseract")
  --fetch-opts "..."      Extra args forwarded to fetch script when polling (quoted string)
  --pytest-args "..."     Extra args to pass to pytest
  --python-bin PATH        Python binary to use to create the venv (default: python3)
  -h|--help               Show this help message and exit

Examples:
  # Poll for latest heavy-deps run and run smoke tests
  ./scripts/ci/validate_wheelhouse_consumer.sh

  # Use a local wheelhouse archive
  ./scripts/ci/validate_wheelhouse_consumer.sh --local-tar ci_artifacts/run-18884042880/wheelhouse-3.11.tgz
USG
}

LOCAL_TAR=""
VENV_DIR=".venv-ci"
PACKAGES="numpy Pillow pytesseract"
FETCH_OPTS=""
PYTEST_ARGS=""
PYTHON_BIN="python3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local-tar)
      LOCAL_TAR="$2"; shift 2;;
    --venv-dir)
      VENV_DIR="$2"; shift 2;;
    --packages)
      PACKAGES="$2"; shift 2;;
    --fetch-opts)
      FETCH_OPTS="$2"; shift 2;;
      --python-bin)
        PYTHON_BIN="$2"; shift 2;;
    --pytest-args)
      PYTEST_ARGS="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

echo "[ci/validate] venv: $VENV_DIR"
echo "[ci/validate] python bin: $PYTHON_BIN"
echo "[ci/validate] packages: $PACKAGES"

# Ensure fetch helper exists (if needed)
if [[ -z "$LOCAL_TAR" ]]; then
  if [[ ! -x ./scripts/ci/fetch_wheelhouse_poll.sh && ! -f ./scripts/ci/fetch_wheelhouse_poll.sh ]]; then
    echo "fetch helper script not found at ./scripts/ci/fetch_wheelhouse_poll.sh" >&2
    exit 3
  fi
fi

tmpdir=$(mktemp -d)
cleanup() { rc=$?; rm -rf "$tmpdir" || true; exit $rc; }
trap cleanup EXIT

wheel_extract_dir="$tmpdir/wheelhouse"
mkdir -p "$wheel_extract_dir"

if [[ -n "$LOCAL_TAR" ]]; then
  echo "[ci/validate] Using local tar: $LOCAL_TAR"
  if [[ ! -f "$LOCAL_TAR" ]]; then
    echo "Local tar not found: $LOCAL_TAR" >&2; exit 4
  fi
  tar -xzf "$LOCAL_TAR" -C "$wheel_extract_dir"
else
  echo "[ci/validate] Polling for latest heavy-deps run (this may take a few minutes)..."
  # Forward fetch opts as a quoted string if provided
  if [[ -n "$FETCH_OPTS" ]]; then
    bash ./scripts/ci/fetch_wheelhouse_poll.sh $FETCH_OPTS
  else
    bash ./scripts/ci/fetch_wheelhouse_poll.sh
  fi

  # find latest ci_artifacts/run-* and look for a .tgz
  latest_run_dir=$(ls -td ci_artifacts/run-* 2>/dev/null | head -n1 || true)
  if [[ -z "$latest_run_dir" ]]; then
    echo "No ci_artifacts/run-* directory found after fetch." >&2; exit 5
  fi
  found_tgz=$(find "$latest_run_dir" -maxdepth 2 -type f -name "*.tgz" | head -n1 || true)
  if [[ -z "$found_tgz" ]]; then
    echo "No .tgz artifact found under $latest_run_dir" >&2; exit 6
  fi
  echo "[ci/validate] Found artifact: $found_tgz"
  tar -xzf "$found_tgz" -C "$wheel_extract_dir"
fi

echo "[ci/validate] Extracted wheelhouse to: $wheel_extract_dir"
echo "[ci/validate] wheel files:"
find "$wheel_extract_dir" -type f -name "*.whl" -print || true

# Quick ABI compatibility check: compare system python major/minor to wheel cp tags
sys_py_tag=$($PYTHON_BIN -c 'import sys; print(f"cp{sys.version_info.major}{sys.version_info.minor}")' 2>/dev/null || true)
if [[ -n "$sys_py_tag" ]]; then
  echo "[ci/validate] current python ABI tag: $sys_py_tag"
  wheel_cp_tags=$(find "$wheel_extract_dir" -type f -name "*.whl" -printf "%f\n" | sed -n 's/.*\(cp[0-9]\{3\}\).*/\1/p' | sort -u || true)
  if [[ -n "$wheel_cp_tags" && ! " $wheel_cp_tags " =~ " $sys_py_tag " ]]; then
    echo "[ci/validate] WARNING: wheelhouse contains ABI tags: $wheel_cp_tags which do not include the current python ABI ($sys_py_tag)" >&2
    echo "[ci/validate] Suggestion: run this script on a matching Python (e.g. python3.11) or produce a wheelhouse for your Python version (e.g. manylinux for cp${sys_py_tag#cp})." >&2
    exit 8
  fi
fi

echo "[ci/validate] Creating venv at $VENV_DIR using $PYTHON_BIN"
$PYTHON_BIN -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install -U pip wheel setuptools

echo "[ci/validate] Installing packages from wheelhouse: $PACKAGES"
python -m pip install --no-index --find-links "$wheel_extract_dir" $PACKAGES || {
  echo "[ci/validate] pip install failed; listing wheelhouse contents for debugging:" >&2
  ls -la "$wheel_extract_dir" || true
  exit 7
}

echo "[ci/validate] Running pytest -k smoke"
python -m pytest -k smoke $PYTEST_ARGS
exit $?
