#!/usr/bin/env python3
"""Manual workflow demonstration script.

Formerly test_complete_workflow.py (moved from root of doc_processor).
Use for ad-hoc inspection; not part of automated pytest suite.
"""
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo/doc_processor

def create_test_environment():
    base = Path(tempfile.gettempdir())/ 'pdf_workflow_demo'
    intake = base / 'intake'
    if base.exists(): shutil.rmtree(base)
    intake.mkdir(parents=True, exist_ok=True)
    img1 = intake / 'demo1.png'
    Image.new('RGB', (600,400), 'lightblue').save(img1, 'PNG')
    return base, intake, [img1]

def main():
    print('🚀 Starting manual workflow demo')
    base, intake, files = create_test_environment()
    try:
        from document_detector import DocumentTypeDetector
        detector = DocumentTypeDetector()
        for f in files:
            a = detector.analyze_image_file(str(f))
            print(f'✓ {f.name} -> strategy={a.processing_strategy} pdf={a.pdf_path}')
    finally:
        shutil.rmtree(base, ignore_errors=True)
        print('🧹 Cleaned up demo workspace')

if __name__ == '__main__':
    main()