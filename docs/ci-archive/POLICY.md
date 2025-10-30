CI Archive Policy
=================

Purpose
-------
This policy explains how to handle CI-produced binary artifacts (wheelhouse tarballs)
and their lightweight provenance metadata (`.meta`) to keep the git repository compact
while preserving reproducibility and auditability.

Key principles
--------------
- Keep small, verifiable provenance in the repository: `.meta` files are tiny and
  safe to track in git.
- Avoid committing large binary tarballs into repository HEAD. Store them as CI
  workflow artifacts or in an external object store (S3, GCS, GitHub Releases).
- Provide a discoverable pointer/index in `docs/ci-archive/` that references
  archived runs and their `.meta` files or external URLs.

Recommended layout
------------------
- `docs/ci-archive/index.md` (or README) — lightweight index of archived runs.
- `docs/ci-archive/<YYYYMMDD>-<run-id>/` — optional CI staging path (runner-side)
  used during the workflow run; do not commit run tarballs into HEAD.
- Keep `.meta` files (and optional small pointer files) in the repo; do not keep
  large tarballs in repository history.

Provenance + verification
-------------------------
- Each wheelhouse tarball should be accompanied by a `.meta` file with fields
  such as: `name`, `sha256`, `size`, `created_at`, `runner`, `python`, and
  `requirements_hash`.
- Consumers must verify integrity by comparing the tarball's `sha256` with the
  value in its `.meta` file before trusting or installing from it.
- Optional: sign the `.meta` or tarball with a maintainers' GPG key and publish
  the detached signature alongside the `.meta`.

Retention & lifecycle
---------------------
- Short-term: CI keeps full artifacts (tarballs) as workflow artifacts for a
  configurable short retention (as per GitHub Actions retention or external
  object store policy).
- Mid-term: maintain a small curated set of validated wheelhouses (example: 3)
  in an archive bucket or release; keep `.meta` pointers in the repo to these
  canonical archived runs.
- Long-term: keep only `.meta` and pointer records in the repo; prune older
  binary artifacts from long-term storage according to org policy.

Practical maintainer workflow
-----------------------------
1. CI builds wheelhouse and writes `wheelhouse-<pyver>.tgz` + `wheelhouse-<pyver>.tgz.meta`.
2. CI uploads the tarball to external storage (or artifacts) and writes the `.meta`.
3. CI writes a pointer (run id, URL, `.meta` contents) into `docs/ci-archive/` for discoverability.
4. Repo keeps only `.meta` and pointer/index; large blobs live outside HEAD.

If you'd like, I can:
- Add CI steps to push the tarball to a specified S3/GCS bucket or GitHub Release.
- Add a small `docs/ci-archive/index.md` generator step in CI that adds pointers only (no tarballs).
- Add optional GPG signing of `.meta` files.

Contact
-------
Open an issue or request which option (S3/GCS/GitHub Release) you prefer and I will draft the required CI changes.
