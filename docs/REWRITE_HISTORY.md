# Rewriting Git History: removing large files

This document explains how we will rewrite repository history to permanently remove large files (model weights) from git history and how collaborators should re-sync their clones.

Files targeted for removal in this run:

- Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth
- Document_Scanner_Ollama_outdated/model_cache/english_g2.pth

Summary of the approach

1. Create a mirror clone of the repository.
2. Run `git-filter-repo` to remove the specified file paths from all commits.
3. Force-push rewritten refs to `origin` (all branches + tags).
4. Inform collaborators and provide re-sync instructions.

Important notes

- This operation rewrites history; commit SHAs will change. Any open branches or PRs that reference old SHAs will be affected.
- After the force-push, collaborators must re-clone or follow the re-sync steps below. DO NOT try to pull --force; re-cloning is the safest option.

Commands we will run (on maintainer machine with repo access):

```bash
# from a safe directory (not the working copy)
git clone --mirror git@github.com:TaintedHorizon/Python_Testing_Vibe.git repo-mirror.git
cd repo-mirror.git
git filter-repo --invert-paths --paths Document_Scanner_Ollama_outdated/model_cache/craft_mlt_25k.pth --paths Document_Scanner_Ollama_outdated/model_cache/english_g2.pth
git push --force origin --all
git push --force origin --tags
```

Collaborator re-sync instructions

Option A (recommended): fresh clone

```bash
# Move aside any local changes you want to keep, then re-clone
git clone git@github.com:TaintedHorizon/Python_Testing_Vibe.git
```

Option B (advanced): attempt to rebase local branches onto the rewritten history

This is riskier and only for advanced users who cannot re-clone. Steps include fetching the rewritten refs and forcing local branches to reset to the new remote branches. Not recommended for casual contributors.

What I'll do next

- If you confirm, I will run `scripts/purge_large_files.sh` to perform the mirror, filter-repo rewrite, and force-push. I will not run it until you explicitly instruct me to execute it.
- I will then provide a short collaborator notification you can paste into PRs or team chat.

Questions? Ask here and I'll incorporate them into the collaborator note.
