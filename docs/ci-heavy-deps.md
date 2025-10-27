# CI strategy for heavy dependencies

Goal
----
Provide a clear plan to handle heavy native Python wheels (torch, triton, CUDA) so CI remains fast and reliable for the common unit-test path while still allowing heavy-integration/E2E jobs to run when needed.

Summary of options
------------------
Option A — Separate cached "heavy-deps" job (recommended)
- Create a dedicated job or workflow that installs heavy dependencies and caches wheel artifacts (or prebuilt wheelhouse) using `actions/cache` or GitHub Packages.
- Keep the regular smoke/non-E2E workflow lightweight. Heavy tests run only when explicitly requested (label, workflow_dispatch, or nightly).
- Pros: minimal impact on fast CI; caches dramatically reduce repeated install time; can be run on-demand.
- Cons: complexity to maintain a separate job or workflow and ensure compatibility across runners.

Option B — Self-hosted runner with preinstalled heavy wheels
- Use a self-hosted runner that already has heavy wheels (and e.g. CUDA) preinstalled.
- Pros: very fast for heavy tests; avoids repeated wheel downloads.
- Cons: operational cost and infrastructure to maintain runner images; less reproducible than ephemeral GitHub runners.

Option C — Mock/skip heavy tests in PR CI and run full tests elsewhere
- Mark tests that require heavy deps with a pytest marker (e.g., `@pytest.mark.heavy`) and skip them in PR smoke runs. Run them in a separate pipeline (nightly or gated merge pipeline).
- Pros: simplest to implement; keeps PR feedback fast.
- Cons: slower feedback on heavy-test regressions; requires discipline to keep heavy tests covered elsewhere.

Recommendation
--------------
I recommend Option A: a separate cached heavy-deps job/workflow. This gives the best balance:

- PRs and daily development get fast feedback from the lightweight smoke job.
- Teams that need heavy tests get them on-demand or on a schedule.
- With a good cache strategy, repeated runs are fast and CI minutes are saved.

Implementation plan (concrete)
----------------------------
1. Add a new workflow `ci/heavy-deps.yml` with `workflow_dispatch` (manual trigger) and optional schedule.

2. In that workflow, add a job `prepare-heavy-deps` that:
   - Sets up Python with the same matrix/versions you need.
   - Runs `python -m pip wheel -r doc_processor/requirements-heavy.txt -w ./.wheelhouse` to build wheels into a wheelhouse directory.
   - Caches the wheelhouse using `actions/cache` keyed by a digest of `requirements-heavy.txt`.
   - Optionally uploads the wheelhouse artifact for download by other jobs/runners.

3. Provide consumers (PR jobs) an optional step to download and `pip install --no-index --find-links ./.wheelhouse -r doc_processor/requirements-heavy.txt` when label `run-heavy-deps` or workflow input is present. Otherwise skip heavy install.

4. Tag heavy tests with `@pytest.mark.heavy` and keep the default smoke job filter `-k "not e2e and not playwright and not heavy"`.

Example `ci/heavy-deps.yml` snippet
----------------------------------
```yaml
name: Prepare heavy deps
on:
  workflow_dispatch: {}
  schedule:
    - cron: '0 3 * * *' # nightly wheel refresh

jobs:
  build-wheelhouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.11
      - name: Cache wheelhouse
        uses: actions/cache@v4
        with:
          path: ./.wheelhouse
          key: wheelhouse-${{ runner.os }}-py-3.11-${{ hashFiles('doc_processor/requirements-heavy.txt') }}
      - name: Build wheelhouse
        run: |
          python -m pip install --upgrade pip
          mkdir -p ./.wheelhouse
          python -m pip wheel -r doc_processor/requirements-heavy.txt -w ./.wheelhouse
      - name: Upload wheelhouse artifact
        uses: actions/upload-artifact@v4
        with:
          name: wheelhouse-3.11
          path: ./.wheelhouse
```

Notes and next steps
--------------------
- Create `doc_processor/requirements-heavy.txt` listing the heavy deps (torch, triton, etc.). Keep `doc_processor/requirements-ci.txt` as the lightweight runtime used by smoke.
- Add a label-based or workflow input gate to PR jobs that need heavy deps. For example, a PR reviewer can add `run-heavy-deps` label to trigger heavy tests.
- Optionally: publish wheelhouse to a release or internal package registry to provide artifacts to external consumers.

Acceptance criteria
-------------------
- This doc exists at `docs/ci-heavy-deps.md`.
- A follow-up PR implements either the `ci/heavy-deps.yml` workflow or a job in the existing pipeline.

If you want, I can create the `ci/heavy-deps.yml` workflow and a `doc_processor/requirements-heavy.txt` starter file next. Say the word and I'll add them and open a PR.
