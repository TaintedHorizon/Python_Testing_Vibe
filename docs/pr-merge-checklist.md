# PR Merge Checklist — CI wheelhouse rollout

Use this checklist to validate and merge the `test/wheelhouse-smoke` changes into `main`.

Pre-merge validation
- [ ] Heavy-deps artifact validated: `wheelhouse-3.11.tgz` exists and contains at least one `.whl`.
- [ ] Confirm presence of critical wheels (numpy, pytesseract, Pillow) OR accept documented PyPI fallback.
- [ ] Smoke PR run (label `run-heavy-deps`, matrix python=3.11) completed successfully and installed heavy deps from wheelhouse.
- [ ] pytest non-E2E tests pass and collect-only step did not trigger heavy native builds during collection.
- [ ] `docs/ci-heavy-deps.md` updated with the final policy and steps to reproduce locally.

Mandatory steps for PRs that touch CI or heavy native deps
- [ ] Add the label `run-heavy-deps` to this PR if it requires binary wheels not broadly available on PyPI for the target runner/Python ABI.
	- Why: this opt-in label tells the smoke workflow to download and consume the latest `wheelhouse-3.11` artifact so tests install from trusted binary wheels instead of attempting local builds during collection.
	- How to validate (recommended):
		1. Run `./scripts/ci/fetch_wheelhouse_poll.sh` locally or ask CI owner to fetch the artifact for the most recent heavy-deps run and confirm `critical_wheels.txt` contains `numpy` and `Pillow` (and `pytesseract` when used).
		2. Add the `run-heavy-deps` label to the PR and watch the smoke job (matrix python=3.11). Confirm logs show `pip --no-index --find-links` and that packages installed from the wheelhouse (look for `.whl` filenames in the pip logs).
		3. If the smoke job still fails to find critical wheels, open the heavy-deps Actions run, inspect the download/pip logs, and either re-trigger heavy-deps with `include_manylinux=true` or follow up to produce manylinux wheels.
	- Post-validation: archive the validated wheelhouse by copying `wheelhouse-3.11.tgz` into `docs/ci-archive/` as `run-<ID>-wheelhouse-3.11.tgz` and add a small `run-<ID>.meta` file containing commit, date, and sha256 checksum.

Review & approvals
- [ ] Two code reviewers sign off on workflow changes and docs.
- [ ] CI owner or maintainer confirms wheelhouse artifact contents (if you are not the CI owner, ask them to verify).

Merge criteria
- [ ] All pre-merge checks passed.
- [ ] No secrets/tokens were committed in this branch.
- [ ] `requirements-ci.txt` contains curated lightweight deps for smoke runs.

Post-merge monitoring & rollback
- Monitor CI on `main` for 48 hours for unexpected failures in smoke or heavy-deps jobs.
- If wheelhouse-based installs fail after merge, revert the merge and run a debug heavy-deps job that logs the wheel list and artifacts; open an incident and notify stakeholders.

Notes
- If a required platform wheel cannot be produced for a critical package, schedule a follow-up `cibuildwheel` manylinux build job (see `docs/ci-heavy-deps.md`).
- If a required platform wheel cannot be produced for a critical package, schedule a follow-up `cibuildwheel` manylinux build job (see `docs/ci-heavy-deps.md`).

How to fetch & validate the wheelhouse locally
----------------------------------------------
Use the included non-interactive script to poll for the latest `heavy-deps` workflow run, download the
`wheelhouse-3.11` artifact, and generate a small manifest of wheels.

From the repo root (requires `gh` authenticated):

```bash
chmod +x scripts/ci/fetch_wheelhouse_poll.sh
# default: waits 10 minutes, polls every 15s, writes to ci_artifacts/run-<N>/list/
./scripts/ci/fetch_wheelhouse_poll.sh

# or increase timeout (20 minutes) and poll interval (30s):
./scripts/ci/fetch_wheelhouse_poll.sh --timeout-min 20 --interval-sec 30
```

What you'll find after a successful run:

- `ci_artifacts/run-<N>/list/tar_contents.txt` — listing of tarball contents
- `ci_artifacts/run-<N>/list/whl_files.txt` — absolute paths to `.whl` files extracted
- `ci_artifacts/run-<N>/list/critical_wheels.txt` — lines matching `numpy`, `pytesseract`, or `Pillow`

If `critical_wheels.txt` is empty, open the heavy-deps run in the Actions UI and inspect the job logs.
If wheels are missing, add a follow-up to produce manylinux builds (see `docs/ci-heavy-deps.md`).

Triggering the smoke PR run that consumes the wheelhouse
------------------------------------------------------
After you confirm the wheelhouse contents or accept the documented PyPI fallback, add the label
`run-heavy-deps` to the PR so the smoke workflow downloads and consumes the artifact during the PR run.

Steps:

1. Add the label `run-heavy-deps` to PR #34 (or your branch PR).
2. Watch the smoke workflow run (matrix python=3.11) and confirm it downloads and installs the wheels into
	`doc_processor/.wheelhouse` before pip install.
3. Confirm the smoke collect-only step completed safely and that subsequent pytest installs used the wheelhouse
	(check step logs for `pip --no-index --find-links` usage).

If you'd like, I can run the fetch script here to download the latest artifact and report the manifests — say
"run here" and I'll attempt it (note: requires `gh` auth in this environment). 
