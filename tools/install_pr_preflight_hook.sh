#!/usr/bin/env bash
set -euo pipefail

# install_pr_preflight_hook.sh
# Installs a local git pre-push hook that runs the project's preflight validator.
# Usage: ./tools/install_pr_preflight_hook.sh [--repo owner/repo]

usage(){
  cat <<EOF
Usage: $0 [--repo owner/repo]

This will create or overwrite .git/hooks/pre-push to run the
Python preflight validator (tools/pr_preflight_validate.py) before pushing.
Set SKIP_LOCAL_HOOK=1 in your environment to bypass the hook.
EOF
  exit 1
}

REPO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO=$2; shift 2;;
    -h|--help) usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

HOOK_PATH=.git/hooks/pre-push
mkdir -p .git/hooks
cat > "$HOOK_PATH" <<'HOOK'
#!/usr/bin/env bash
# Local pre-push hook: run project preflight validator.
# Exits non-zero to block push when preflight fails.
set -euo pipefail

if [[ "${SKIP_LOCAL_HOOK-0}" == "1" ]]; then
  echo "SKIP_LOCAL_HOOK=1 set — skipping preflight hook."
  exit 0
fi

REPO_ARG=""
if [[ -n "${REPO_ARG_ENV-}" ]]; then
  REPO_ARG="--repo ${REPO_ARG_ENV}"
fi

if [[ -f tools/pr_preflight_validate.py ]]; then
  echo "Running preflight validator..."
  python3 tools/pr_preflight_validate.py ${REPO_ARG} || {
    echo "Preflight validation failed. Push aborted." >&2
    exit 2
  }
else
  echo "No preflight validator found at tools/pr_preflight_validate.py; allowing push."
fi

exit 0
HOOK

chmod +x "$HOOK_PATH"

echo "Installed pre-push hook at $HOOK_PATH"

echo "Tip: to skip this hook temporarily, run: SKIP_LOCAL_HOOK=1 git push"

exit 0
