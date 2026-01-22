def selector_for(testid_name: str) -> str:
    """Return CSS selector that targets a data-testid."""
    return f"[data-testid='{testid_name}']"

def click_with_fallback(page, testid_name: str, fallback: str = None, timeout: int = 2000):
    """Try clicking the data-testid selector first, then a fallback selector.

    `page` should be a Playwright Page-like object with `click`.
    """
    sel = selector_for(testid_name)
    try:
        page.click(sel, timeout=timeout)
        return True
    except Exception:
        if fallback:
            try:
                page.click(fallback, timeout=timeout)
                return True
            except Exception:
                return False
        return False

def wait_for_any(page, testid_name: str, fallback: str = None, timeout: int = 10000):
    """Wait for the data-testid or fallback selector to appear.
    Returns the selector that was found (data-testid preferred) or None.
    """
    sel = selector_for(testid_name)
    try:
        page.wait_for_selector(sel, timeout=timeout)
        return sel
    except Exception:
        if fallback:
            try:
                page.wait_for_selector(fallback, timeout=timeout)
                return fallback
            except Exception:
                return None
        return None
