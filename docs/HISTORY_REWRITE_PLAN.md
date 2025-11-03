# History-rewrite plan (draft)

Purpose
-------
This document captures the findings from a local scan for large objects in the repository and provides a safe, reproducible plan to remove very large historical blobs from git history. DO NOT run the commands below without coordinating with repository maintainers: a history rewrite requires force-pushing and will make existing clones incompatible until contributors rebase or reclone.

Summary of findings (top objects)
--------------------------------
The following list was generated with:

```
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  sed -n 's/^blob //p' | sort -k3 -n -r | head -n 50
```

Top reachable blobs (object-sha size path)

```
15586 ui_tests/node_modules/undici-types/dispatcher.d.ts
19395 doc_processor/static/pdfjs/web/standard_fonts/FoxitSerifBold.pfb
51087 doc_processor/CHANGELOG.md
49911 doc_processor/templates/intake_analysis.html
... (truncated)
```

Interpretation
--------------
- The scan shows the largest reachable objects in the current history. If you previously observed an ~83MB blob, that object may already be unreachable (and removable by GC) or may exist in a pack that was not reachable by the current refs (or it was identified earlier and has since been partially removed).
- This draft plan focuses on two safe, supported options:
  1. Remove very large blobs by size threshold (e.g., >50 MB) using git-filter-repo --strip-blobs-bigger-than.
  2. Remove specific files/paths (for example, historical wheelhouse tarballs) by path using git-filter-repo --path/--invert-paths.

Recommended approach (safe workflow)
-----------------------------------
1. Prepare a mirror clone (do this on a machine with sufficient disk space):

```bash
# clone a mirror to perform the rewrite in isolation
git clone --mirror git@github.com:TaintedHorizon/Python_Testing_Vibe.git repo-rewrite.git
cd repo-rewrite.git
```

2. Install git-filter-repo (preferred):

```bash
# on linux/mac
pip install --user git-filter-repo
# ensure ~/.local/bin is on PATH (or install via distro package if available)
```

3a. Quick remove by size (recommended if you want to simply strip any huge historical blob):

```bash
# remove any blob larger than 50MB
git filter-repo --strip-blobs-bigger-than 50M
```

3b. Or: remove by path (if you know the offending files, e.g., archived wheelhouses):

```bash
# remove all history of docs/ci-archive/*.tgz
git filter-repo --path docs/ci-archive --invert-paths
```

4. Inspect rewritten repo locally and run tests (do not push yet):

```bash
# check branches
git for-each-ref --format='%(refname) %(objectname) %(committerdate:iso8601)' refs/heads refs/tags
# run a local checkout of a branch and run tests (on a separate clone):
git clone file://$PWD ../verify-rewrite
cd ../verify-rewrite
pytest -q || true
```

5. Coordinate with maintainers and force-push (this is the destructive step):

```bash
# after approval by maintainers, push rewritten refs to origin
git push --force --all origin
git push --force --tags origin
```

6. Post-rewrite steps for contributors
------------------------------------
- Each contributor must re-clone or run these steps locally to recover:

```bash
git fetch origin --prune
# Option A: create new clone
git clone git@github.com:TaintedHorizon/Python_Testing_Vibe.git

# Option B: rebase/repair local branches (advanced) - maintainers may prefer re-clone to avoid mistakes
```

Notes and caveats
-----------------
- Backup: keep a copy of the mirror clone before pushing. You can also archive the mirror as a backup.
- Large-file removal might remove legitimate historical artifacts that teams expect; review deleted paths carefully.
- GitHub Actions, releases, PRs referencing old commits will still point to old SHAs; depending on your org policy, communicate the rewrite widely.
- If you want, I can produce a more targeted plan: (A) auto-detect candidate paths above a threshold and create a safe script that runs `git filter-repo --paths` to remove known paths, or (B) produce a PR that documents the exact SHAs/paths to be removed.

Status: draft — do NOT execute any rewrite without an explicit approval and a maintainer coordination plan.
