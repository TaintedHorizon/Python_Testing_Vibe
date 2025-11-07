#!/usr/bin/env bash
set -euo pipefail
REPO="TaintedHorizon/Python_Testing_Vibe"
# Fetch recent workflow runs
runs_json=$(gh api -H "Accept: application/vnd.github+json" "/repos/${REPO}/actions/runs?per_page=50")
failed=$(echo "$runs_json" | jq -c '.workflow_runs[] | select(.status=="completed" and .conclusion!="success") | {id: .id, name: .name, run_number: .run_number, conclusion: .conclusion, html_url: .html_url}')
if [ -z "$(echo "$failed" | jq -r . 2>/dev/null)" ] || [ "$(echo "$failed" | jq -r 'length' 2>/dev/null || echo 0)" = "0" ]; then
  echo "No failing workflow runs found in the last 50 runs."
  exit 0
fi
# Build body
body=$(echo "$failed" | jq -r -s 'map("- \(.name) #\(.run_number) — \(.conclusion) — \(.html_url)") | join("\n")')
issue_title="Nightly CI failures"
full_body="Automated run (manual):\n\n${body}\n\n(Reported by local monitor run)"
# Find existing open issue
existing=$(gh issue list --repo ${REPO} --state open --search "${issue_title}" --json number,title -q '.[0]' || true)
if [ -z "$existing" ] || [ "$existing" = "null" ]; then
  echo "Creating issue: ${issue_title}"
  gh issue create --repo ${REPO} --title "${issue_title}" --body "$full_body"
else
  num=$(echo "$existing" | jq -r '.number')
  echo "Posting comment to existing issue #$num"
  gh issue comment --repo ${REPO} $num --body "$full_body"
fi
