## HISTORY REWRITE — next steps and owner checklist

This file summarizes the safe, maintainer-led next steps to finalize the rewrite that removes the large historical file documented in
`docs/HISTORY_REWRITE_CANDIDATES.txt`.

Key facts
- Target path: Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth
- Blob SHA: 7461d59d6e457f2502bf015395334e3808bb1a0f
- Rewritten mirror tarball (local run): `ci_artifacts/repo-rewrite-20251029.tar.gz`
- Tarball SHA256: `467f6b938231ddf6bb763eee51afd47dacae9a03ac048c99e2b06c7196542102`

Preconditions (maintainers)
- Have a canonical, offline backup of the repository (mirror) prior to any force-push.
- Coordinate a short force-push window and notify contributors (provide instructions for rebase).
- Install `git-filter-repo` on the machine that will perform the rewrite.

Recommended safe procedure (maintainer-run)
1. Clone a mirror (on maintainer host):

```bash
git clone --mirror https://github.com/TaintedHorizon/Python_Testing_Vibe.git python-testing-vibe-mirror.git
cd python-testing-vibe-mirror.git
```

2. Run the rewrite inside the mirror (local-only):

```bash
# targeted removal of the offending path
git filter-repo --path 'Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth' --invert-paths
```

3. Cleanup and sanity checks:

```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# verify the blob is gone (should print "blob not found")
git rev-list --objects --all | grep 7461d59d6e457f2502bf015395334e3808bb1a0f || echo "blob not found"
git rev-list --objects --all | cut -f2 -d' ' | grep -F "Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth" || echo "path not found"
```

4. Inspect the mirror locally and run CI tests against it (recommended): clone the rewritten mirror via `git clone file://$(pwd)` into a verification workspace and run the full test matrix.

5. If verified, coordinate push (MAINTAINER ACTION):

```bash
# optional: push to a backup remote first
git remote add backup https://github.com/TaintedHorizon/Python_Testing_Vibe-backup.git
# push rewritten refs to origin (destructive) -- DO NOT do this without coordination
# git push --force origin main
# git push --force origin --tags
```

Verification checklist (before pushing)
- [ ] Backup mirror created and stored offline.
- [ ] Confirmation from core maintainers with agreed force-push window and communication plan.
- [ ] Rewritten mirror passes the local test matrix (smoke + selected integrations).
- [ ] Packfile size and repo size checked (du -sh) and compared vs backup mirror.

Post-push actions
- Notify contributors and provide one-line instructions to rebase or re-clone. Example:

```text
# after force-push, instruct contributors to:
git fetch origin
git checkout <branch>
git rebase --onto origin/main <old-base> <branch>
# or, simpler, re-clone repository
```

Questions / support
- If you want me to (A) upload the local tarball as a release asset, (B) upload to an S3 bucket you control, or (C) leave the tarball in this workspace, tell me which option and I will proceed.

Thanks — this document is intentionally short and prescriptive to speed maintainer review. If you prefer, I can also produce a checklist PR or a one-click shell script that pushes only `main` and tags the backup remote; I will only do that after explicit approval.
