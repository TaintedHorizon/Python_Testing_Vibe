CI manylinux wheel build (opt-in)
================================

Purpose
-------
This document describes the opt-in manylinux wheel builder. Use it only when the
`heavy-deps` workflow cannot produce required binary wheels (for example, numpy) and
PyPI does not provide a suitable wheel for your platform or configuration.

What was added
--------------
- `doc_processor/requirements-manylinux.txt` — list of packages to target for manylinux builds.
- `.github/workflows/manylinux-build.yml` — a dispatch-only GitHub Actions workflow that runs
  `cibuildwheel` to build manylinux wheels and uploads them as `manylinux-wheelhouse-3.11`.

How to run (manual)
-------------------
1. Inspect and update `doc_processor/requirements-manylinux.txt` to include only the packages
   you need to build.
2. From the GitHub Actions UI, open the `Build manylinux wheels (opt-in)` workflow and click
   "Run workflow". This will start a manual run on `ubuntu-latest` using Python 3.11.
3. Wait for the run to complete. The output artifact `manylinux-wheelhouse-3.11` will contain
   a tarball of the produced wheels.

Notes & cautions
----------------
- Building manylinux wheels is resource- and time-intensive. Only run this when necessary.
- The current workflow is conservative and may require further tuning (e.g., multithreaded
  builds, QEMU setup for cross-Python builds) depending on the package.
- If `cibuildwheel` fails for a package (like numpy) consider using the upstream manylinux
  images or a specialized build VM with enough memory and appropriate system libs installed.

Next steps
----------
- If these manylinux builds are successful and produce the missing wheels, update `heavy-deps.yml`
  to optionally merge or include the manylinux wheelhouse contents when producing `wheelhouse-3.11.tgz`.
- If manylinux builds are not feasible for a package, document the accepted PyPI fallback in
  `docs/ci-heavy-deps.md` and proceed with the documented policy.
