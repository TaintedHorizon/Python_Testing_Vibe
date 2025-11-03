# PR Merge Checklist — CI wheelhouse rollout

Use this checklist to validate and merge the `test/wheelhouse-smoke` changes into `main`.

Pre-merge validation
- [ ] Heavy-deps artifact validated: `wheelhouse-3.11.tgz` exists and contains at least one `.whl`.
- [ ] Confirm presence of critical wheels (numpy, pytesseract, Pillow) OR accept documented PyPI fallback.
- [ ] Smoke PR run (label `run-heavy-deps`, matrix python=3.11) completed successfully and installed heavy deps from wheelhouse.
- [ ] pytest non-E2E tests pass and collect-only step did not trigger heavy native builds during collection.
- [ ] `docs/ci-heavy-deps.md` updated with the final policy and steps to reproduce locally.

> Quick status: run 18887489644 validated a wheelhouse in CI (python=3.11 smoke job). See `docs/ci-archive/wheelhouse-3.11-run-18884042880.tgz` for the archived artifact and its `.meta` file.

Mandatory steps for PRs that touch CI or heavy native deps
- [ ] Add the label `run-heavy-deps` to this PR if it requires binary wheels not broadly available on PyPI for the target runner/Python ABI.
	- Why: this opt-in label tells the smoke workflow to download and consume the latest `wheelhouse-3.11` artifact so tests install from trusted binary wheels instead of attempting local builds during collection.
	- How to validate (recommended):

	- Required validation steps (MUST be performed for CI or binary-affecting changes):
		1. Use `./scripts/ci/fetch_wheelhouse_poll.sh` or check the `heavy-deps` workflow run to obtain the latest `wheelhouse-3.11.tgz` artifact and its `critical_wheels.txt` manifest.
		2. Add the `run-heavy-deps` label to the PR and wait for the smoke workflow (matrix python=3.11) to run. Inspect the smoke job logs and confirm it:
			- downloads and unpacks a wheelhouse tarball, and
			- installs packages with `pip --no-index --find-links` referencing `doc_processor/.wheelhouse`, and
			- shows `.whl` filenames (manylinux wheels) for critical packages in the pip logs.
		3. If the smoke job did not find critical wheels, re-run or re-dispatch `heavy-deps` with `include_manylinux=true`, or follow the manylinux build instructions in `docs/ci-manylinux.md`.
	- Post-validation: archive the validated wheelhouse by copying `wheelhouse-3.11.tgz` into `docs/ci-archive/` and add a small `.meta` file containing run id, commit, timestamp, and sha256.

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
