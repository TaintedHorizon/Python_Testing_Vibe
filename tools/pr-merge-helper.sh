#!/usr/bin/env bash
set -euo pipefail

#!/usr/bin/env bash
set -euo pipefail

OWNER="${OWNER:-TaintedHorizon}"
REPO="${REPO:-Python_Testing_Vibe}"
MAIN="${MAIN:-main}"

# Safety: support a dry-run mode to preview actions without mutating remote state.
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  echo "Running in dry-run mode: destructive remote actions will be simulated only."
fi

# Preflight
[ -d .git ] || { echo "ERROR: not in a git repo root. Abort."; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not found. Install and authenticate."; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq not found. Install jq."; exit 3; }

echo "gh auth status (informational):"
gh auth status || { echo "ERROR: gh auth failed or not authenticated; fix that first."; exit 4; }

# Refresh local main
git fetch origin --prune
git checkout --force "$MAIN"
git reset --hard origin/"$MAIN"

# Get the open PRs (we will operate on the list returned)
gh pr list --repo "$OWNER/$REPO" --state open --json number,title,headRefName,mergeable,mergeStateStatus,updatedAt --jq '.[]' > open_prs.json
if [ ! -s open_prs.json ]; then
  echo "No open PRs found. Exiting."
  exit 0
fi
echo "Saved open PR metadata to open_prs.json"

# Build ordered processing list: 1 = clean/mergeable, 2 = unknown/behind, 3 = dirty/conflicting
jq -r '. | "\(.number)\t\(.headRefName)\t\(.mergeable)\t\(.mergeStateStatus)\t\(.title)"' open_prs.json \
  | awk -F"\t" '{
      m=$3; s=$4;
      if (m=="true" && (s=="CLEAN" || s=="clean" || s=="MERGEABLE" || s=="mergeable")) pri=1;
      else if (m=="true" || s=="UNKNOWN" || s=="null") pri=2;
      else pri=3;
      print pri "\t" $0
    }' | sort -n | cut -f2- > pr_order.txt

echo "Planned processing order:"
cat pr_order.txt
echo ""
read -p "Proceed to process PRs in this order? Type exactly 'yes' to proceed: " PROCEED
[ "$PROCEED" = "yes" ] || { echo "Aborted by user."; exit 0; }

# Helper: safe backup and fetch
backup_pr_branch() {
  local pr_branch="$1"
  echo "Backing up remote branch origin/${pr_branch} to backup/${pr_branch} (if exists)..."
  git fetch origin "refs/heads/${pr_branch}:backup/${pr_branch}" || echo "No remote head to backup (or backup already exists)."
}

post_pr_comment() {
  local pr_num="$1" ; shift
  local body="$*"
  gh pr comment "$pr_num" --repo "$OWNER/$REPO" --body "$body" || echo "Failed to post PR comment #$pr_num"
}

# Iterate PRs
while IFS=$'\t' read -r PR_NUMBER PR_HEAD MERGEABLE MERGESTATE TITLE; do
  echo ""
  echo "======== Processing PR #$PR_NUMBER - $TITLE ========"
  echo "branch: $PR_HEAD (mergeable=$MERGEABLE mergeState=$MERGESTATE)"
  read -p "Process this PR now? (yes/skip/stop) " RESP
  if [ "$RESP" = "stop" ]; then echo "Stopped by user."; exit 0; fi
  if [ "$RESP" = "skip" ]; then echo "Skipping PR #$PR_NUMBER"; continue; fi

  # Refresh PR metadata
  gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json number,headRefName,mergeable,mergeStateStatus,changedFiles --jq '.' > pr_meta.json
  MERGEABLE_NOW=$(jq -r '.mergeable' pr_meta.json)
  MERGESTATE_NOW=$(jq -r '.mergeStateStatus // "UNKNOWN"' pr_meta.json)
  echo "Current: mergeable=$MERGEABLE_NOW mergeState=$MERGESTATE_NOW"

  # 1) If mergeable & clean => merge directly
  if [ "$MERGEABLE_NOW" = "true" ] && { [ "$MERGESTATE_NOW" = "CLEAN" ] || [ "$MERGESTATE_NOW" = "clean" ] || [ "$MERGESTATE_NOW" = "MERGEABLE" ]; }; then
    echo "PR appears mergeable — attempting to merge PR #$PR_NUMBER (merge commit) via gh..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[dry-run] would run: gh pr merge $PR_NUMBER --repo $OWNER/$REPO --merge --delete-branch --body 'Merged automatically (clean/mergeable).'"
      echo "[dry-run] skipping actual merge."
      continue
    fi

    if gh pr merge "$PR_NUMBER" --repo "$OWNER/$REPO" --merge --delete-branch --body "Merged automatically (clean/mergeable)." ; then
      echo "Merged PR #$PR_NUMBER successfully."
      continue
    else
      echo "Direct merge failed for PR #$PR_NUMBER; will try update-branch flow."
    fi
  fi

  # 2) Try GitHub Update Branch API (fast, non-destructive)
  echo "Attempting to update branch via GitHub API for PR #$PR_NUMBER..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would request update-branch for PR #$PR_NUMBER via GitHub API"
    UPDATE_EXIT=0
  else
    set +e
    gh api -X PUT repos/"$OWNER"/"$REPO"/pulls/"$PR_NUMBER"/update-branch -H "Accept: application/vnd.github+json" >/dev/null 2>&1
    UPDATE_EXIT=$?
    set -e
  fi

  if [ $UPDATE_EXIT -eq 0 ]; then
    echo "update-branch successful. Re-evaluating mergeability..."
    sleep 3
    MERGEABLE_NOW=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json mergeable --jq '.mergeable')
    if [ "$MERGEABLE_NOW" = "true" ]; then
      echo "Now mergeable — merging..."
      gh pr merge "$PR_NUMBER" --repo "$OWNER/$REPO" --merge --delete-branch --body "Merged after update-branch." && echo "Merged PR #$PR_NUMBER." && continue
    else
      echo "Branch updated but still not mergeable. Will attempt local rebase fallback."
    fi
  else
    echo "update-branch API failed (likely conflicts). Will attempt local rebase fallback if permitted."
  fi

  # 3) Local rebase fallback (will create backup first)
  echo "Preparing local rebase fallback for branch $PR_HEAD..."
  backup_pr_branch "$PR_HEAD"

  # fetch remote PR branch into a local temporary branch
  echo "Fetching origin/${PR_HEAD} into ${PR_HEAD}-local"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would fetch origin/${PR_HEAD} into ${PR_HEAD}-local and rebase onto origin/$MAIN (skipping in dry-run)."
    echo "[dry-run] posting a comment suggesting a manual rebase instead of attempting it."
    post_pr_comment "$PR_NUMBER" "Automated (dry-run): This PR would require a local rebase onto main. In dry-run mode no changes were made. Please rebase locally with:\n\n git fetch origin\n git checkout $PR_HEAD\n git rebase origin/$MAIN\n# Resolve conflicts, then:\n git add <files>\n git rebase --continue\n git push --force-with-lease origin $PR_HEAD"
    continue
  fi

  if ! git fetch origin "${PR_HEAD}:${PR_HEAD}-local"; then
    echo "Failed to fetch origin/${PR_HEAD}. Posting comment and skipping PR."
    post_pr_comment "$PR_NUMBER" "Automated: failed to fetch origin/${PR_HEAD} for local rebase. Please rebase branch onto main or allow a maintainer to update."
    continue
  fi

  git checkout --force "${PR_HEAD}-local"

  echo "Rebasing ${PR_HEAD}-local onto origin/${MAIN}..."
  set +e
  git rebase origin/"$MAIN"
  REBASE_EXIT=$?
  set -e

  if [ $REBASE_EXIT -ne 0 ]; then
    echo "Rebase produced conflicts for PR #$PR_NUMBER — aborting rebase and notifying authors/maintainers."
    git status --porcelain
    post_pr_comment "$PR_NUMBER" $'Automated: I attempted to rebase this branch onto main to resolve merge conflicts but the rebase produced conflicts. Please rebase locally with:\n\n git fetch origin\n git checkout "'$PR_HEAD'"\n git rebase origin/'"$MAIN"'\n# Resolve conflicts, then:\n git add <files>\n git rebase --continue\n git push --force-with-lease origin '"$PR_HEAD"'\n\nIf you prefer a maintainer to resolve conflicts, please assign a reviewer.'
    # cleanup
    git rebase --abort || true
    git checkout "$MAIN"
    git branch -D "${PR_HEAD}-local" || true
    continue
  fi

  # Rebase succeeded locally: run quick checks and push (force-with-lease)
  echo "Local rebase succeeded for $PR_HEAD-local. Running quick syntax check (non-blocking)..."
  python -m py_compile $(find . -name "*.py" -not -path "*/.git/*") >/dev/null 2>&1 || echo "Note: python syntax check reported problems (not blocking)."

  echo "Pushing rebased branch to origin/${PR_HEAD} using --force-with-lease..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would run: git push --force-with-lease origin HEAD:$PR_HEAD"
    echo "[dry-run] skipping push in dry-run mode. Posting a comment to inform the author."
    post_pr_comment "$PR_NUMBER" "Automated (dry-run): rebased branch would be pushed here. In dry-run no push occurred. Please rebase locally and force-push when ready."
    git checkout --force "$MAIN"
    git branch -D "${PR_HEAD}-local" || true
    continue
  fi

  # Ask for confirmation before force-pushing to origin (extra safety)
  read -p "About to force-push rebased branch to origin/$PR_HEAD. Type 'yes' to proceed: " CONFIRM_PUSH
  if [ "$CONFIRM_PUSH" != "yes" ]; then
    echo "User declined to push. Restoring and skipping PR #$PR_NUMBER."
    git checkout "$MAIN"
    git branch -D "${PR_HEAD}-local" || true
    post_pr_comment "$PR_NUMBER" "Automated: attempted a local rebase but push was cancelled by the operator. Please rebase locally and push when ready."
    continue
  fi

  if git push --force-with-lease origin HEAD:"$PR_HEAD"; then
    echo "Pushed rebased branch for PR #$PR_NUMBER."
    post_pr_comment "$PR_NUMBER" "Automated: I rebased this branch onto the updated main and pushed the rebased branch (force-with-lease). Please verify CI and merge when green."
    # back to main and cleanup
    git checkout --force "$MAIN"
    git branch -D "${PR_HEAD}-local" || true
    sleep 4
    # try merging if now mergeable
    MERGEABLE_NOW=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json mergeable --jq '.mergeable')
    if [ "$MERGEABLE_NOW" = "true" ]; then
      echo "PR #$PR_NUMBER now mergeable. Attempting merge..."
      if gh pr merge "$PR_NUMBER" --repo "$OWNER/$REPO" --merge --delete-branch --body "Merged after local rebase." ; then
        echo "Merged PR #$PR_NUMBER."
      else
        echo "Merge attempt failed after rebase; please inspect the PR in the UI."
      fi
    else
      echo "PR not yet mergeable; CI may be running. Inspect the PR URL: https://github.com/$OWNER/$REPO/pull/$PR_NUMBER"
    fi
  else
    echo "Push failed for rebased branch. Restore backup if needed and skip PR."
    git checkout "$MAIN"
    git branch -D "${PR_HEAD}-local" || true
    post_pr_comment "$PR_NUMBER" "Automated: attempted to push rebased branch but push failed. Please investigate or rebase locally and force-push."
  fi

done < pr_order.txt

echo ""
echo "All PRs processed. End of script."