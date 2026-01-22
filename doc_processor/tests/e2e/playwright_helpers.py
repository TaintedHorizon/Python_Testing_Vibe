# Small helper functions for Playwright E2E tests

from typing import Optional
import os
import time
import requests


DEFAULT_ARTIFACTS = os.path.join(os.path.dirname(__file__), "artifacts")


def dump_screenshot_and_html(page, artifacts_dir_or_name: str, name: Optional[str] = None):
    """Save screenshot and page HTML for debugging failures.

    Calling styles supported:
    - dump_screenshot_and_html(page, "failure_name")
    - dump_screenshot_and_html(page, "/abs/path/to/artifacts", "failure_name")
    """
    if name is None:
        # called as (page, name)
        name = artifacts_dir_or_name
        artifacts_dir = DEFAULT_ARTIFACTS
    else:
        artifacts_dir = artifacts_dir_or_name

    os.makedirs(artifacts_dir, exist_ok=True)
    screenshot_path = os.path.join(artifacts_dir, f"{name}.png")
    html_path = os.path.join(artifacts_dir, f"{name}.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass


def wait_for_progress_update(page, selector: str, previous_text: Optional[str], timeout: int = 5000):
    """Wait until the element's text changes from previous_text (or becomes non-empty).
    Returns the new text or None if timed out.
    """
    from playwright.sync_api import TimeoutError
    try:
        if previous_text is None:
            # wait until the element is visible so we don't detect hidden placeholders
            page.wait_for_selector(selector, timeout=timeout, state='visible')
        else:
            page.wait_for_function("(sel, prev) => document.querySelector(sel) && document.querySelector(sel).innerText !== prev", selector, previous_text, timeout=timeout)
        el = page.query_selector(selector)
        return el.inner_text() if el else None
    except TimeoutError:
        return None


def get_rotation_degrees(page, selector: str):
    """Attempt to read rotation degrees from a DOM attribute or CSS transform.
    Returns an int degrees (0/90/180/270) or None if not found.
    """
    try:
        el = page.query_selector(selector)
        if not el:
            return None
        # Common pattern: data-rotation attribute or style transform: rotate(90deg)
        try:
            attr = el.get_attribute('data-rotation')
            if attr:
                return int(attr)
        except Exception:
            pass
        try:
            style = el.evaluate("el => window.getComputedStyle(el).transform", el)
            if style and style != 'none' and 'rotate' in style:
                import re
                m = re.search(r'rotate\(([-0-9.]+)deg\)', style)
                if m:
                    return int(float(m.group(1))) % 360
        except Exception:
            pass
    except Exception:
        pass
    return None


def wait_for_analysis_complete(intake_path: str, timeout: int = 30):
    """Poll the debug endpoint until a processed document referencing intake_path appears.

    This is a best-effort helper used by tests to wait for background analysis.
    It checks `/batch/api/debug/latest_document` for an `original_pdf_path` or filename that
    matches the provided intake_path (basename match).
    """
    deadline = time.time() + timeout
    basename = os.path.basename(intake_path)
    base = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
    url = f"{base}/batch/api/debug/latest_document"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.text:
                js = r.json()
                if isinstance(js, dict) and "data" in js and "latest_document" in js["data"]:
                    doc = js["data"]["latest_document"]
                elif isinstance(js, dict) and "latest_document" in js:
                    doc = js["latest_document"]
                else:
                    doc = js
                if isinstance(doc, dict):
                    path = doc.get("original_pdf_path") or doc.get("file_path") or ""
                    if basename in path:
                        return True
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Analysis did not complete for {intake_path} within {timeout}s")
# Small helper functions for Playwright E2E tests

from typing import Optional
import os
import time
import requests


DEFAULT_ARTIFACTS = os.path.join(os.path.dirname(__file__), "artifacts")


def dump_screenshot_and_html(page, artifacts_dir_or_name: str, name: Optional[str] = None):
    """Save screenshot and page HTML for debugging failures.

    Calling styles supported:
    - dump_screenshot_and_html(page, "failure_name")
    - dump_screenshot_and_html(page, "/abs/path/to/artifacts", "failure_name")
    """
    if name is None:
        # called as (page, name)
        name = artifacts_dir_or_name
        artifacts_dir = DEFAULT_ARTIFACTS
    else:
        artifacts_dir = artifacts_dir_or_name

    os.makedirs(artifacts_dir, exist_ok=True)
    screenshot_path = os.path.join(artifacts_dir, f"{name}.png")
    html_path = os.path.join(artifacts_dir, f"{name}.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass


def wait_for_progress_update(page, selector: str, previous_text: Optional[str], timeout: int = 5000):
    """Wait until the element's text changes from previous_text (or becomes non-empty).
    Returns the new text or None if timed out.
    """
    from playwright.sync_api import TimeoutError
    try:
        if previous_text is None:
            # wait until the element is visible so we don't detect hidden placeholders
            page.wait_for_selector(selector, timeout=timeout, state='visible')
        else:
            page.wait_for_function("(sel, prev) => document.querySelector(sel) && document.querySelector(sel).innerText !== prev", selector, previous_text, timeout=timeout)
        el = page.query_selector(selector)
        return el.inner_text() if el else None
    except TimeoutError:
        return None


def get_rotation_degrees(page, selector: str):
    """Attempt to read rotation degrees from a DOM attribute or CSS transform.
    Returns an int degrees (0/90/180/270) or None if not found.
    """
    try:
        el = page.query_selector(selector)
        if not el:
            return None
        # Common pattern: data-rotation attribute or style transform: rotate(90deg)
        try:
            attr = el.get_attribute('data-rotation')
            if attr:
                return int(attr)
        except Exception:
            pass
        try:
            style = el.evaluate("el => window.getComputedStyle(el).transform", el)
            if style and style != 'none' and 'rotate' in style:
                import re
                m = re.search(r'rotate\(([-0-9.]+)deg\)', style)
                if m:
                    return int(float(m.group(1))) % 360
        except Exception:
            pass
    except Exception:
        pass
    return None


def wait_for_analysis_complete(intake_path: str, timeout: int = 30):
    """Poll the debug endpoint until a processed document referencing intake_path appears.

    This is a best-effort helper used by tests to wait for background analysis.
    It checks `/batch/api/debug/latest_document` for an `original_pdf_path` or filename that
    matches the provided intake_path (basename match).
    """
    deadline = time.time() + timeout
    basename = os.path.basename(intake_path)
    base = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
    url = f"{base}/batch/api/debug/latest_document"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.text:
                js = r.json()
                if isinstance(js, dict) and "data" in js and "latest_document" in js["data"]:
                    doc = js["data"]["latest_document"]
                elif isinstance(js, dict) and "latest_document" in js:
                    doc = js["latest_document"]
                else:
                    doc = js
                if isinstance(doc, dict):
                    path = doc.get("original_pdf_path") or doc.get("file_path") or ""
                    if basename in path:
                        return True
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Analysis did not complete for {intake_path} within {timeout}s")
# Small helper functions for Playwright E2E tests

from typing import Optional
import os
import time
import requests


DEFAULT_ARTIFACTS = os.path.join(os.path.dirname(__file__), "artifacts")


def dump_screenshot_and_html(page, artifacts_dir_or_name: str, name: Optional[str] = None):
    """Save screenshot and page HTML for debugging failures.

    Calling styles supported:
    - dump_screenshot_and_html(page, "failure_name")
    - dump_screenshot_and_html(page, "/abs/path/to/artifacts", "failure_name")
    """
    if name is None:
        # called as (page, name)
        name = artifacts_dir_or_name
        artifacts_dir = DEFAULT_ARTIFACTS
    else:
        artifacts_dir = artifacts_dir_or_name

    os.makedirs(artifacts_dir, exist_ok=True)
    screenshot_path = os.path.join(artifacts_dir, f"{name}.png")
    html_path = os.path.join(artifacts_dir, f"{name}.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass


def wait_for_progress_update(page, selector: str, previous_text: Optional[str], timeout: int = 5000):
    """Wait until the element's text changes from previous_text (or becomes non-empty).
    Returns the new text or None if timed out.
    """
    from playwright.sync_api import TimeoutError
    try:
        if previous_text is None:
            # wait until the element is visible so we don't detect hidden placeholders
            page.wait_for_selector(selector, timeout=timeout, state='visible')
        else:
            page.wait_for_function("(sel, prev) => document.querySelector(sel) && document.querySelector(sel).innerText !== prev", selector, previous_text, timeout=timeout)
        el = page.query_selector(selector)
        return el.inner_text() if el else None
    except TimeoutError:
        return None


def get_rotation_degrees(page, selector: str):
    """Attempt to read rotation degrees from a DOM attribute or CSS transform.
    Returns an int degrees (0/90/180/270) or None if not found.
    """
    try:
        el = page.query_selector(selector)
        if not el:
            return None
        # Common pattern: data-rotation attribute or style transform: rotate(90deg)
        try:
            attr = el.get_attribute('data-rotation')
            if attr:
                return int(attr)
        except Exception:
            pass
        try:
            style = el.evaluate("el => window.getComputedStyle(el).transform", el)
            if style and style != 'none' and 'rotate' in style:
                import re
                m = re.search(r'rotate\(([-0-9.]+)deg\)', style)
                if m:
                    return int(float(m.group(1))) % 360
        except Exception:
            pass
    except Exception:
        pass
    return None


def wait_for_analysis_complete(intake_path: str, timeout: int = 30):
    """Poll the debug endpoint until a processed document referencing intake_path appears.

    This is a best-effort helper used by tests to wait for background analysis.
    It checks `/batch/api/debug/latest_document` for an `original_pdf_path` or filename that
    matches the provided intake_path (basename match).
    """
    deadline = time.time() + timeout
    basename = os.path.basename(intake_path)
    base = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
    url = f"{base}/batch/api/debug/latest_document"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.text:
                js = r.json()
                if isinstance(js, dict) and "data" in js and "latest_document" in js["data"]:
                    doc = js["data"]["latest_document"]
                elif isinstance(js, dict) and "latest_document" in js:
                    doc = js["latest_document"]
                else:
                    doc = js
                if isinstance(doc, dict):
                    path = doc.get("original_pdf_path") or doc.get("file_path") or ""
                    if basename in path:
                        return True
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Analysis did not complete for {intake_path} within {timeout}s")
