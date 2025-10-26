#!/usr/bin/env bash
set -euo pipefail

# Lightweight smoke script for local verification of test-safety.
# - Exports TEST_TMPDIR
# - Sources doc_processor/.env.test if present
# - Creates/uses venv at doc_processor/venv
# - Installs minimal deps and runs pytest subset

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

echo "[smoke] ROOT_DIR=$ROOT_DIR"
echo "[smoke] TEST_TMPDIR=$TEST_TMPDIR"

if [ -f "$ROOT_DIR/doc_processor/.env.test" ]; then
  echo "[smoke] sourcing doc_processor/.env.test"
  # export variables from .env.test into the environment
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/doc_processor/.env.test"
  set +a
fi

VENV_DIR="$ROOT_DIR/doc_processor/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

if [ ! -x "$PYTHON" ]; then
  echo "[smoke] creating venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

echo "[smoke] activating venv"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Ensure pytest is available; install minimal requirements if provided
if [ -f "$ROOT_DIR/doc_processor/requirements.txt" ]; then
  echo "[smoke] installing requirements from doc_processor/requirements.txt"
  "$PIP" install --upgrade pip
  "$PIP" install -r "$ROOT_DIR/doc_processor/requirements.txt"
else
  echo "[smoke] requirements.txt not found, ensuring pytest is installed"
  "$PIP" install --upgrade pip
  "$PIP" install pytest
fi

echo "[smoke] running pytest (non-E2E subset)"
pytest -q -k "not e2e and not playwright"

echo "[smoke] done"
#!/usr/bin/env bash
set -euo pipefail

# Lightweight smoke script for local verification of test-safety.
# - Exports TEST_TMPDIR
# - Sources doc_processor/.env.test if present
# - Creates/uses venv at doc_processor/venv
# - Installs minimal deps and runs pytest subset

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"
export TEST_TMPDIR

echo "[smoke] ROOT_DIR=$ROOT_DIR"
echo "[smoke] TEST_TMPDIR=$TEST_TMPDIR"

if [ -f "$ROOT_DIR/doc_processor/.env.test" ]; then
  echo "[smoke] sourcing doc_processor/.env.test"
  # export variables from .env.test into the environment
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/doc_processor/.env.test"
  set +a
fi

VENV_DIR="$ROOT_DIR/doc_processor/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

if [ ! -x "$PYTHON" ]; then
  echo "[smoke] creating venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

echo "[smoke] activating venv"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Ensure pytest is available; install minimal requirements if provided
if [ -f "$ROOT_DIR/doc_processor/requirements.txt" ]; then
  echo "[smoke] installing requirements from doc_processor/requirements.txt"
  "$PIP" install --upgrade pip
  "$PIP" install -r "$ROOT_DIR/doc_processor/requirements.txt"
else
  echo "[smoke] requirements.txt not found, ensuring pytest is installed"
  "$PIP" install --upgrade pip
  #!/usr/bin/env bash
  set -euo pipefail

  # Lightweight smoke script for local verification of test-safety.
  # - Exports TEST_TMPDIR
  # - Sources doc_processor/.env.test if present
  # - Creates/uses venv at doc_processor/venv
  # - Installs minimal deps and runs pytest subset

  ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
  TEST_TMPDIR="${TEST_TMPDIR:-/tmp/python_testing_vibe_tests}"
  export TEST_TMPDIR

  echo "[smoke] ROOT_DIR=$ROOT_DIR"
  echo "[smoke] TEST_TMPDIR=$TEST_TMPDIR"

  if [ -f "$ROOT_DIR/doc_processor/.env.test" ]; then
    echo "[smoke] sourcing doc_processor/.env.test"
    # export variables from .env.test into the environment
    set -a
    # shellcheck disable=SC1090
    source "$ROOT_DIR/doc_processor/.env.test"
    set +a
  fi

  VENV_DIR="$ROOT_DIR/doc_processor/venv"
  PYTHON="$VENV_DIR/bin/python"
  PIP="$VENV_DIR/bin/pip"

  if [ ! -x "$PYTHON" ]; then
    echo "[smoke] creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  echo "[smoke] activating venv"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  # Ensure pytest is available; install minimal requirements if provided
  if [ -f "$ROOT_DIR/doc_processor/requirements.txt" ]; then
    echo "[smoke] installing requirements from doc_processor/requirements.txt"
    "$PIP" install --upgrade pip
    "$PIP" install -r "$ROOT_DIR/doc_processor/requirements.txt"
  else
    echo "[smoke] requirements.txt not found, ensuring pytest is installed"
    "$PIP" install --upgrade pip
    "$PIP" install pytest
  fi

  echo "[smoke] running pytest (non-E2E subset)"
  pytest -q -k "not e2e and not playwright"

  echo "[smoke] done"
