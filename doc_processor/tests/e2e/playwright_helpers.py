# Small helper functions for Playwright E2E tests

from typing import Optional


def dump_screenshot_and_html(page, artifacts_dir: str, name: str):
    """Save screenshot and page HTML for debugging failures."""
    import os
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
