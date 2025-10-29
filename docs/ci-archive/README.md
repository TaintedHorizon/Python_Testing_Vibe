# CI Archive: wheelhouse artifacts and validation

This document explains the wheelhouse artifact workflow used by CI, the
provenance `.meta` file format produced alongside wheelhouses, and how to use
the included consumer helper scripts to fetch and validate wheelhouses locally.

Purpose
-------
- Provide reproducible wheelhouse artifacts for offline installs and CI.
- Produce lightweight provenance metadata so archived artifacts can be
  independently verified without committing large binary files into the repo.

What CI produces
-----------------
The `heavy-deps` workflow produces an artifact named `wheelhouse-3.11` which
contains at minimum:

- `wheelhouse-3.11.tgz` — a tarball containing `.whl` files (one-per-package)
- `wheelhouse-3.11.tgz.meta` — a small text file with provenance details

Example `.meta` contents
------------------------
The meta file is simple `key=value` lines. Example keys:

- `name` — artifact filename (wheelhouse-3.11.tgz)
- `sha256` — SHA256 checksum of the tarball
- `size` — size in bytes
- `created_at` — UTC timestamp when the meta was generated
- `runner` — output of `uname -a` for the runner
- `python` — python version string on the runner
- `requirements_hash` — sha256 of `doc_processor/requirements-heavy.txt` used to build
- `wheels` — comma-separated list of wheel filenames included

Using the helper scripts
------------------------
There are two convenience scripts under `scripts/ci/` to fetch and validate
wheelhouses locally. Both assume you have the `gh` CLI available and authorized
for the GitHub repo (for polling mode). They also work with a local tarball.

1. `scripts/ci/fetch_wheelhouse_poll.sh`

- Polls the latest `heavy-deps` workflow run and downloads the artifact named
  `wheelhouse-3.11` into `ci_artifacts/run-<run-id>/`.
- Usage (defaults work for this repository):

```bash
./scripts/ci/fetch_wheelhouse_poll.sh
```

You can override repo/workflow/artifact/outdir with flags. The script will
write `tar_contents.txt`, `whl_files.txt` and `critical_wheels.txt` under the
download directory for quick inspection.

2. `scripts/ci/validate_wheelhouse_consumer.sh`

- Creates an isolated virtualenv, extracts a wheelhouse (either from a local
  tarball or a fetched artifact), installs a small set of critical packages
  using `pip --no-index --find-links` against the extracted wheelhouse, and
  runs smoke pytest tests.
- Example (use a local tarball):

```bash
./scripts/ci/validate_wheelhouse_consumer.sh --local-tar ci_artifacts/run-12345/wheelhouse-3.11.tgz \
  --venv-dir ./.venv-ci --packages "numpy Pillow pytesseract" --python-bin python3.11
```

- Example (poll remote run, then validate):

```bash
./scripts/ci/fetch_wheelhouse_poll.sh --outdir ci_artifacts
./scripts/ci/validate_wheelhouse_consumer.sh --local-tar ci_artifacts/run-<runid>/*.tgz
```

Notes & recommendations
-----------------------
- The fetch script relies on the `gh` CLI for listing and downloading workflow
  artifacts. Ensure `gh auth status` is successful and you have repo access.
- The validation script performs a conservative ABI check and will warn/exit
  if the wheelhouse ABI tags don't match the local Python. Use the matching
  Python version (e.g., python3.11) when testing wheelhouses built for 3.11.
- The `.meta` file is the canonical provenance record produced by CI; compare
  the `sha256` in the `.meta` file with a locally computed `sha256sum` after
  download to ensure integrity.

Automating archive layout in CI
------------------------------
The `heavy-deps` workflow was updated to stage the produced wheelhouse and
meta into `docs/ci-archive/<YYYYMMDD>-<run_id>/` inside the uploaded artifact.
This makes it easier to find and download archived wheelhouses for long-term
storage or release packaging.

If you want further automation (upload to an external object store, attach to
a GitHub Release, or sign the tarball), I can add optional steps to the
workflow. Ask me to draft those and I will include safe defaults and retry
logic.

Contact / next steps
--------------------
If you'd like, I can:

- Trigger a manual `heavy-deps` workflow run and fetch the produced artifact to
  demonstrate the pipeline end-to-end.
- Add an optional step to sign the tarball (GPG) and include the signature in
  the artifact.
- Produce a short `validate_wheelhouse_consumer` CI job that runs in a small
  runner to smoke-test the produced wheelhouse before archiving.

Pick one and I'll implement it in the next iteration.
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
