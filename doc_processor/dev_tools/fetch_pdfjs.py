"""
Fetch PDF.js distribution files into the app's static directory for offline/local use.

This script downloads the minified core bundle and worker from a CDN and places
them under doc_processor/static/pdfjs/ as:
    - pdf.min.js
    - pdf.worker.min.js

Primary source: jsDelivr (npm: pdfjs-dist)
Fallback: unpkg (npm: pdfjs-dist)

Run from repository root or anywhere; it locates the static folder relative to this file.
You can pin a version via PDFJS_VERSION env var (default: 4.2.67)
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

CDN_VERSION = os.environ.get("PDFJS_VERSION", "3.11.174")

# Candidate URLs (try in order) for each file
URL_CANDIDATES = {
    "pdf.min.js": [
        f"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{CDN_VERSION}/pdf.min.js",
        f"https://cdn.jsdelivr.net/npm/pdfjs-dist@{CDN_VERSION}/build/pdf.min.js",
        f"https://unpkg.com/pdfjs-dist@{CDN_VERSION}/build/pdf.min.js",
    ],
    "pdf.worker.min.js": [
        f"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{CDN_VERSION}/pdf.worker.min.js",
        f"https://cdn.jsdelivr.net/npm/pdfjs-dist@{CDN_VERSION}/build/pdf.worker.min.js",
        f"https://unpkg.com/pdfjs-dist@{CDN_VERSION}/build/pdf.worker.min.js",
    ],
}


def try_download(urls: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for url in urls:
        try:
            print(f"Downloading {url} -> {dest}")
            with urllib.request.urlopen(url) as resp:
                data = resp.read()
            dest.write_bytes(data)
            return
        except Exception as e:
            print(f"  - failed: {e}")
            last_err = e
    raise RuntimeError(f"All sources failed for {dest.name}: {last_err}")


def main() -> int:
    here = Path(__file__).resolve()
    # Allow overriding destination (useful in CI or when static dir is not writable)
    import tempfile
    pdfjs_dest = os.environ.get('PDFJS_DEST')
    if pdfjs_dest:
        static_dir = Path(pdfjs_dest)
    else:
        static_dir = here.parent.parent / "static" / "pdfjs"
    static_dir.mkdir(parents=True, exist_ok=True)
    try:
        for name, urls in URL_CANDIDATES.items():
            try_download(urls, static_dir / name)
        print("\n✅ PDF.js assets fetched successfully.")
        print(f"   Location: {static_dir}")
        print("   Files: pdf.min.js, pdf.worker.min.js")
        return 0
    except Exception as e:
        print(f"\n❌ Failed to fetch PDF.js assets: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
