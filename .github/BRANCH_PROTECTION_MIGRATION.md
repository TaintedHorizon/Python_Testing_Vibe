# Branch Protection Migration Guide

## Problem

After simplifying workflows from 15 to 3, you may see:
- Old checks showing as "Expected — Waiting for status to be reported"
- New workflows not running on existing PRs
- PRs stuck in "pending" state

## Why This Happens

GitHub branch protection rules still reference the old workflow checks that no longer exist. The new workflows won't run on PRs created before the workflows were added.

## Solution

### Step 1: Update Branch Protection Rules

1. Go to your repository Settings
2. Click **Branches** in the left sidebar
3. Find the branch protection rule for `main` and click **Edit**
4. Scroll to **Status checks**
5. **Remove** old checks:
   - `validate-workflows`
   - `smoke tests`
   - `ci-fast-path`
   - `ci-smoke`
   - Any other old workflow names
6. **Add** new required checks:
   - `CI Basic Checks`
   - `Unit Tests (Python 3.11)`
   - `Unit Tests (Python 3.12)`
7. Click **Save changes**

### Step 2: Fix Existing PRs

For PRs created before the workflow changes (like PR #57, #59):

**Option A: Empty Commit (Easiest)**
```bash
git checkout <branch-name>
git commit --allow-empty -m "trigger new workflows"
git push
```

**Option B: Close and Reopen**
1. Close the PR
2. Reopen it immediately
3. New workflows will trigger

**Option C: Rebase**
```bash
git checkout <branch-name>
git pull origin main
git rebase main
git push --force-with-lease
```

### Step 3: Verify

After updating branch protection and triggering workflows:
1. Check the PR's "Checks" tab
2. You should see:
   - ✅ `CI Basic Checks` (running or complete)
   - ✅ `Unit Tests (Python 3.11)` (running or complete)
   - ✅ `Unit Tests (Python 3.12)` (running or complete)
3. Old checks should no longer appear

## Quick Reference

### Old Checks (Remove from Branch Protection)
- validate-workflows
- smoke tests (non-E2E)
- CI Smoke
- CI Fast Path
- CI Rewrite
- Diagnose smoke and upload logs
- E2E Tests
- Playwright E2E
- Push Smoke
- Any other workflow from the old 15

### New Checks (Add to Branch Protection)
- **CI Basic Checks** (from ci-basic.yml)
- **Unit Tests (Python 3.11)** (from test-unit.yml)
- **Unit Tests (Python 3.12)** (from test-unit.yml)

### Not Required
- **E2E Tests (Manual)** - This is manual-trigger only, not required for merge

## Troubleshooting

**Q: Workflows still not running after empty commit**
- A: Make sure you're on the branch with the new workflow files. The workflows must exist in the branch being checked.

**Q: Can't find the new check names in branch protection**
- A: The checks won't appear in the dropdown until they've run at least once. Trigger them first, then add to branch protection.

**Q: Old checks still showing as pending**
- A: This is normal until you remove them from branch protection. They can be ignored - they won't block merge once you update the rules.

**Q: What about PR #59?**
- A: Same process - either empty commit, rebase, or close/reopen to trigger new workflows.

## Summary

This is a **one-time migration issue**. Once you:
1. Update branch protection rules
2. Trigger workflows on existing PRs

All future PRs will work automatically with the new simplified workflow structure.

---

**Need help?** See the main documentation in `.github/WORKFLOWS_CLEANUP.md`
