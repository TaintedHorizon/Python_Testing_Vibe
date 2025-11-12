#!/usr/bin/env bash
set -euo pipefail

# pr_preflight_validate.sh
# Validate branch-protection required status contexts exist as job names in workflows.
# Usage: tools/pr_preflight_validate.sh [--repo owner/repo]

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
if [[ -z "$REPO" ]]; then
  echo "Could not detect repo via 'gh repo view'. Pass --repo owner/repo as first arg if needed." >&2
fi

if [[ ${1-} == "--repo" ]]; then
  REPO=${2:-$REPO}
fi

if [[ -z "$REPO" ]]; then
  echo "Repository not specified. Exiting." >&2
  exit 2
fi

echo "Repository: $REPO"

echo "Fetching branch-protection required status contexts for 'main'..."
mapfile -t required < <(gh api repos/${REPO}/branches/main/protection -q '.required_status_checks.contexts[]' 2>/dev/null || true)

if (( ${#required[@]} == 0 )); then
  echo "No required status contexts found (or could not fetch protection settings)." >&2
else
  echo "Required contexts:"; for r in "${required[@]}"; do echo "  - $r"; done
fi

echo "Gathering job names from workflow files..."
declare -a jobnames
for wf in .github/workflows/*.{yml,yaml}; do
  [[ -f "$wf" ]] || continue
  awk '
    BEGIN{inj=0}
    /^\s*jobs:/{inj=1; next}
    inj==1 {
      if ($0 ~ /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*$/) {
        jobid=$0; sub(/^[[:space:]]+/,"",jobid); sub(/:$/,"",jobid)
        foundname=0
        next
      }
      if ($0 ~ /^[[:space:]]*name:[[:space:]]*/) {
        line=$0; sub(/^[[:space:]]*name:[[:space:]]*/,"",line); gsub(/^"|"$/,"",line); gsub(/^\047|\047$/,"",line)
        print line
        foundname=1
      }
    }
  ' "$wf" < /dev/null > /tmp/.pr_preflight_names.$$ && \
  while IFS= read -r n; do
    [[ -z "$n" ]] && continue
    jobnames+=("$n")
  done < /tmp/.pr_preflight_names.$$ && rm -f /tmp/.pr_preflight_names.$$
done

if (( ${#jobnames[@]} == 0 )); then
  echo "No job names found in workflows." >&2
else
  echo "Discovered job names:"; for j in "${jobnames[@]}"; do echo "  - $j"; done
fi

echo
echo "Checking for missing required contexts..."
missing=()
for req in "${required[@]}"; do
  found=0
  for j in "${jobnames[@]}"; do
    # normalize job name: replace matrix placeholders with '.*' and strip double-quotes/commas
    # then remove single quotes in a separate step to avoid shell quoting issues.
    pattern=$(printf "%s" "$j" | sed -E 's/\$\{\{[^}]+\}\}/.*/g; s/[\",]//g' | sed "s/'//g")

    # exact match
    if [[ "$j" == "$req" ]]; then found=1; break; fi

    # forgiving regex match (handles matrix placeholders like ${{ matrix.python }})
    if printf "%s" "$req" | grep -E -x "$pattern" >/dev/null 2>&1; then
      found=1; break
    fi

    # heuristic: if both mention 'Unit Tests' assume they match (matrix variants)
    if [[ "$pattern" == *"Unit Tests"* ]] && [[ "$req" == Unit\ Tests* ]]; then
      found=1; break
    fi
  done

  if [[ $found -eq 0 ]]; then
    missing+=("$req")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "The following required contexts are missing from workflow job names:" >&2
  for m in "${missing[@]}"; do echo "  - $m"; done
  echo
  echo "Recommendation: add a matching 'name: <context>' to the corresponding job in .github/workflows/*.yml or update branch-protection to match an existing job name." >&2
  exit 3
else
  echo "All required contexts are present as job names in workflows. Good to open PRs from in-repo branches." 
fi

exit 0
