Demo scripts moved
==================

Several demonstration scripts that used to live under `doc_processor/dev_tools/` have
been archived to `docs/examples/demos/` to avoid accidental test collection and to
keep developer tooling separate from runnable examples.

Available examples (moved):
- `docs/examples/demos/refactoring_demo.py`
- `docs/examples/demos/demo_rag_classification.py`
- `docs/examples/demos/demo_resilience.py`

If you need to run these demos for manual testing, run them from the `docs/examples/`
directory or reference them directly. They are intentionally kept out of the automated
test suite.
