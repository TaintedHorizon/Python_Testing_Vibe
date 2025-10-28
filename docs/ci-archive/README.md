# CI Wheelhouse Archive

This directory contains archived, validated wheelhouse artifacts produced by the `heavy-deps` CI workflow.

Purpose
- Keep a small, git-tracked provenance record for wheelhouses validated by CI.
- Make it simple to re-run smoke consumer tests against a known-good wheelhouse.

Contents
- `wheelhouse-3.11-run-<ID>.tgz` — tarball of `.whl` files created by the heavy-deps run.
- `wheelhouse-3.11-run-<ID>.meta` — small metadata file containing the source run id, commit SHA, timestamp, and sha256 checksum.

Retention & policy
- Prefer storing large binary artifacts in an external artifact store (GitHub releases, S3, or an internal artifact server) for long-term retention.
- The repo may keep a small number of recent validated wheelhouses for reproducibility; consider pruning older items and keeping metadata-only entries (or pointers) for older runs.

How to validate locally
1. Copy `wheelhouse-3.11-run-<ID>.tgz` to a runner with matching Python ABI (e.g. Python 3.11 for cp311 wheels) or use a matching container image:

```bash
# Example: run validation using a python:3.11 container
docker run --rm -v "$PWD":/src -w /src python:3.11 bash -lc '
  python -m venv venv && . venv/bin/activate && \
  pip install --upgrade pip && \
  tar -xzf docs/ci-archive/wheelhouse-3.11-run-<ID>.tgz -C /tmp/wheelhouse && \
  pip install --no-index --find-links /tmp/wheelhouse -r requirements-heavy.txt && \
  pytest -k smoke
'
```

If you need help moving large artifacts to an external store, open an issue and tag the CI owner.
