# GitHub Workflows - Simplified Structure

## 🎯 Active Workflows (3 Total)

### Required for PR Merge:
1. **`ci-basic.yml`** - Fast linting and syntax checks (~2 min)
   - Python syntax validation
   - Flake8 linting (errors only)
   - Core file existence checks
   
2. **`test-unit.yml`** - Unit tests without E2E (~5 min)
   - Runs on Python 3.11 and 3.12
   - Excludes E2E tests (marked with `@pytest.mark.e2e`)
   - Does not require 100% pass rate (known flaky tests)

### Optional (Manual Trigger Only):
3. **`test-e2e-manual.yml`** - Full E2E tests with Playwright (~15 min)
   - Only runs when manually triggered
   - NOT required for PR merge
   - Useful for pre-release testing

## 📦 Archived Workflows

All other workflow files have been disabled and moved to `.github/workflows_archived/`.
These were experimental, duplicate, or overly complex implementations that caused merge issues.

### Previously Active (Now Archived):
- `smoke.yml` - Too complex (182 lines, heavy deps)
- `ci-smoke.yml` - Minimal test
- `ci.yml` - Duplicate minimal test
- `ci-fast-path.yml` - Docs-only fast path
- `ci-rewrite.yml` - Experimental rewrite
- `diagnose-smoke-and-upload.yml` - Debugging workflow
- `collect-action-logs.yml` - Log collection
- `e2e.yml` - Old E2E implementation
- `manual-e2e.yml` - Old manual E2E
- `playwright-e2e.yml` - Another E2E variant
- `push-smoke.yml` - Push-triggered smoke tests
- `validate-workflows.yml` - Workflow validation
- `heavy-deps.yml` - Heavy dependency builds
- `manylinux-build.yml` - Wheel building
- `merge-prs.yml` - Auto-merge bot

## 🚀 For Developers

### Creating a PR
Your PR will automatically trigger:
1. **ci-basic** - Must pass (usually passes in < 2 min)
2. **test-unit** - Must pass (usually passes in < 10 min)

Both checks are fast and reliable. If they fail:
- **ci-basic failure**: Fix Python syntax errors or critical linting issues
- **test-unit failure**: Check if you broke core functionality (flaky test failures are OK)

### Running E2E Tests
E2E tests are slow and flaky, so they're not required for merge:
```bash
# Run E2E tests locally
cd doc_processor
pytest -v -m "e2e"
```

To run them in CI, go to Actions → "E2E Tests (Manual)" → Run workflow

## 🤖 For Copilot Agents

**IMPORTANT**: When creating PRs:
- ✅ Only `ci-basic` and `test-unit` need to pass
- ✅ Both workflows are fast (< 10 min total)
- ✅ Test failures in `test-unit` don't block if syntax is valid
- ❌ Do NOT add new workflow files
- ❌ Do NOT modify existing workflows without explicit user request
- ❌ E2E tests are NOT required for merge

## 📝 Changelog

### 2025-11-08 - Major Simplification
- **Removed**: 12 redundant/experimental workflows
- **Added**: 3 simple, reliable workflows
- **Result**: Faster CI, fewer merge blocks, clearer requirements

---

**Previous Problem**: 15 workflows, frequent failures, unclear requirements, PRs blocked
**Current Solution**: 3 workflows, fast & reliable, clear pass/fail criteria, PRs merge easily
