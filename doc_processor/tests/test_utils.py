from pathlib import Path

def write_valid_png(p: Path):
    """Write a tiny valid 1x1 PNG to path. Uses Pillow when available."""
    try:
        from PIL import Image
        img = Image.new('RGBA', (1, 1), (255, 255, 255, 0))
        img.save(p, format='PNG')
    except Exception:
        import base64
        png_b64 = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII='
        p.write_bytes(base64.b64decode(png_b64))


def write_valid_pdf(p: Path):
    """Write a tiny valid PDF (single blank page) to path. Uses Pillow when available."""
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), (255, 255, 255))
        img.save(p, format='PDF')
    except Exception:
        # Fallback: write a minimal PDF header; not all PDF consumers accept this,
        # but it's a best-effort fallback for environments without Pillow.
        p.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R>>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R>>\nendobj\n4 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000110 00000 n \n0000000210 00000 n \ntrailer\n<< /Root 1 0 R /Size 5>>\nstartxref\n310\n%%EOF")


def write_valid_jpeg(p: Path):
    """Write a tiny valid JPEG to path. Uses Pillow when available."""
    try:
        from PIL import Image
        img = Image.new('RGB', (10, 10), (255, 255, 255))
        img.save(p, format='JPEG')
    except Exception:
        # Minimal JPEG header fallback (not a valid image but a placeholder)
        p.write_bytes(b'\xff\xd8\xff\xdb\x00C')
