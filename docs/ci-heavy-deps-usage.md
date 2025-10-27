# How to request heavy dependency installs in CI

This repository supports an opt-in path to install heavy native Python wheels (torch, triton, etc.) in CI without slowing down normal PR feedback.

Quick summary
---------------
- Default PR runs remain fast and use `doc_processor/requirements-ci.txt` (lightweight runtime deps).
- To request a heavy-install run for a PR, add the `run-heavy-deps` label to the pull request. The smoke workflow will then attempt to download a prebuilt wheelhouse artifact named `wheelhouse-3.11` and install packages listed in `doc_processor/requirements-heavy.txt` from that wheelhouse.

Steps for reviewers/maintainers
------------------------------
1. Build the wheelhouse (one-time / periodic):
   - Manually dispatch the `Prepare heavy deps` workflow (.github/workflows/heavy-deps.yml) from the Actions UI (or wait for scheduled run).
   - This produces and uploads an artifact named `wheelhouse-3.11` containing prebuilt wheels in `./.wheelhouse`.

2. Request a heavy install for a PR:
   - Add the label `run-heavy-deps` to the pull request.
   - The smoke workflow will detect this label and download the `wheelhouse-3.11` artifact (if present) using `actions/download-artifact` and install heavy packages from it.

3. Verification:
   - The smoke job will install the wheelhouse packages with:
     python -m pip install --no-index --find-links ./.wheelhouse -r doc_processor/requirements-heavy.txt
   - Check the job logs for install output and any failures. If the wheelhouse artifact is missing the job will skip heavy install and continue.

Notes and caveats
-----------------
- Building the wheelhouse may take significant CI minutes and time; schedule builds during off-hours or run manually when needed.
- The wheelhouse is tied to a Python version and OS (the example workflow builds for Python 3.11 on ubuntu-latest). If you need other platforms, extend the heavy-deps workflow.
- If a package requires an external index or special flags (CUDA variants, extra-index-url), include that in `doc_processor/requirements-heavy.txt` and document needed environment variables or secrets.
- The smoke workflow will still run the lightweight `requirements-ci.txt` path for normal PRs. Heavy installs are opt-in only.

Troubleshooting
---------------
- If the wheelhouse download step can't find `wheelhouse-3.11`, confirm the `heavy-deps` workflow has run recently and uploaded the artifact.
- If pip fails to install from the wheelhouse, download the artifact locally and inspect the wheel filenames for platform tags (cpu vs cu118 vs cu121).

Reference files
---------------
- `.github/workflows/heavy-deps.yml` — builds wheelhouse artifact
- `.github/workflows/smoke.yml` — consumes wheelhouse when PR labeled `run-heavy-deps`
- `doc_processor/requirements-heavy.txt` — list of heavy packages to install from wheelhouse
