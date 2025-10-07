# Legacy Code & Naming Standardization

This document defines conventions for identifying, isolating, and eventually removing deprecated or transitional code artifacts in the project.

## Goals
- Make it obvious which modules are authoritative vs. legacy.
- Prevent accidental edits to deprecated implementations.
- Provide a migration path and checklist for retiring old code safely.

## Classification
| Category | Meaning | Action | Example |
|----------|---------|--------|---------|
| Active | Current, maintained implementation | Normal development | `doc_processor/app.py` |
| Transitional | Coexists temporarily while new feature stabilizes | Mark clearly; schedule removal date | `intake_analysis_new.html` (now merged) |
| Legacy | Superseded; retained only for reference/manual testing | Mark read-only; skip in pytest | `dev_tools/test_batch_logic.py` |
| Deprecated Directory | Fully replaced older architecture | Archive or delete after final audit | `Document_Scanner_Gemini_outdated/` |

## Naming Conventions
- Suffix `_legacy` for Python modules or templates retained only for reference (e.g., `manipulate_old.html` could become `manipulate_legacy.html`).
- Avoid using `_new` once the implementation is adopted—rename to canonical name and remove the old version.
- Do **not** introduce mixed suffixes like `_v2`, `_updated` unless performing short-lived (<2 weeks) experimental branches.

## Template Standardization
All active templates must:
1. Load shared rotation logic via `static/js/rotation_utils.js`.
2. Avoid inline duplicate implementations of `rotateDocument` logic.
3. Use unified button set: Rotate Left/Right, Reset, Fit Mode Cycle.

Checklist (✓ = enforced now):
- ✓ `manipulate.html`
- ✓ `intake_analysis.html`
- ✓ `intake_analysis_new.html` (merged; should be RENAMED or removed soon)
- ✓ `verify.html`
- ✓ `revisit.html`
- ✓ `manipulate_old.html` (candidate for `_legacy` rename)

## Test Handling
Legacy diagnostic scripts under `doc_processor/dev_tools/` are skipped automatically using `pytest.skip(..., allow_module_level=True)`.
If converting one into a proper test:
1. Move or copy into `doc_processor/tests/`.
2. Remove the skip marker.
3. Replace direct path hacks (`sys.path.insert`) with proper package imports.

## Rotation Logic Unification
- Source of truth: `doc_processor/static/js/rotation_utils.js`.
- Any new view requiring rotation must call `RotationUtils.applyScaledRotation(iframe, angle)`.
- Do not reimplement scaling math inline.

## Migration Playbook
1. Identify duplication (search for `rotateDocument(`).
2. Replace inline logic with calls to shared utilities.
3. Add presence assertion or extend existing tests.
4. Remove stale functions & re-run tests.
5. Update this document and CHANGELOG if removal is user-visible.

## Directory Status
| Directory | Status | Notes |
|-----------|--------|-------|
| `doc_processor/` | Active | Authoritative codebase |
| `Document_Scanner_Gemini_outdated/` | Deprecated | Keep until final audit; no edits |
| `Document_Scanner_Ollama_outdated/` | Deprecated | Same as above |
| `tools/` | Mixed | Some utilities; audit for potential extraction |

## Removal Criteria for Legacy Files
A legacy file may be deleted when ALL apply:
- Feature parity confirmed in replacement.
- No imports reference the legacy file.
- No active docs or READMEs instruct usage.
- CI / test suite green without it.

## Future Cleanup Targets
- Rename `manipulate_old.html` → `manipulate_legacy.html` or remove after verification step completed.
- Remove `intake_analysis_new.html` if its improvements are fully merged (they are now—candidate for deletion).
- Consolidate dev tools into a `scripts/` or `maintenance/` namespace with clear execution docs.

## Change Control
When deprecating a module:
1. Add header comment: `# DEPRECATED: Replaced by <newpath>. Scheduled for removal YYYY-MM-DD.`
2. Update this file under sections above.
3. Optionally add a runtime warning if still imported.

---
Maintained: October 2025
