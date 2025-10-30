#!/usr/bin/env bash
set -euo pipefail
# Optional artifact uploader used by CI when an external store is configured.
# This script is intentionally provider-agnostic and only runs if required
# environment variables are present. It supports S3, GCS, or GitHub Releases
# as opts. No secrets are hard-coded; the CI must provide credentials.

OUT_FILE="${1:-}"
if [[ -z "$OUT_FILE" ]]; then
  echo "Usage: $0 <file-to-upload>" >&2
  exit 2
fi

if [[ ! -f "$OUT_FILE" ]]; then
  echo "File not found: $OUT_FILE" >&2
  exit 3
fi

echo "Preparing to upload: $OUT_FILE"

if [[ -n "${CI_S3_BUCKET:-}" && -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
  # Upload to S3 using aws cli
  if command -v aws >/dev/null 2>&1; then
    echo "Uploading to S3 bucket: $CI_S3_BUCKET"
    aws s3 cp "$OUT_FILE" "s3://$CI_S3_BUCKET/$(basename "$OUT_FILE")"
    echo "Uploaded to s3://$CI_S3_BUCKET/$(basename "$OUT_FILE")"
    exit 0
  else
    echo "aws CLI not found; skipping S3 upload" >&2
  fi
fi

if [[ -n "${CI_GCS_BUCKET:-}" && -n "${GCP_SERVICE_ACCOUNT_KEY:-}" ]]; then
  # Upload to GCS using gsutil
  if command -v gsutil >/dev/null 2>&1; then
    echo "Uploading to GCS bucket: $CI_GCS_BUCKET"
    echo "$GCP_SERVICE_ACCOUNT_KEY" > /tmp/gsa.json
    gcloud auth activate-service-account --key-file=/tmp/gsa.json
    gsutil cp "$OUT_FILE" "gs://$CI_GCS_BUCKET/$(basename "$OUT_FILE")"
    rm -f /tmp/gsa.json
    echo "Uploaded to gs://$CI_GCS_BUCKET/$(basename "$OUT_FILE")"
    exit 0
  else
    echo "gsutil not found; skipping GCS upload" >&2
  fi
fi

if [[ -n "${GITHUB_TOKEN:-}" && -n "${GITHUB_REPOSITORY:-}" ]]; then
  # Create a GitHub release artifact (lightweight). This requires jq and gh or curl.
  if command -v gh >/dev/null 2>&1; then
    echo "Uploading to GitHub Releases for ${GITHUB_REPOSITORY}"
    gh release create "rewrite-preview-$(date -u +%Y%m%dT%H%M%SZ)" "$OUT_FILE" --repo "$GITHUB_REPOSITORY" --title "Rewrite preview"
    echo "Uploaded artifact to GitHub Releases"
    exit 0
  else
    echo "gh CLI not found; skipping GitHub Releases upload" >&2
  fi
fi

echo "No upload method configured or available. Exiting with no-op." >&2
exit 4
