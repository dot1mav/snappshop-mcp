"""
fetcher.py — HTTP fetcher for snappshop.ir with multiple strategies.

Strategies (tried in order):
  1. curl_cffi with chrome131 TLS impersonation (default; works if you are
     in Iran or have an Iranian proxy).
  2. Playwright headless with stealth patches (fallback; more reliable
     against bot-detection CDNs).

Optional configuration via environment variables:
  • SNAPP_PROXY        — proxy URL like http://user:pass@host:port
  • SNAPP_FETCHER     — force a specific strategy: "curl_cffi" or "playwright"
  • SNAPP_TIMEOUT     — request timeout in seconds (default 30)

Important note about geo-blocking:
  snappshop.ir sits behind Sotoon CDN which blocks non-Iranian IPs with
  HTTP 403. If you are running this MCP from outside Iran, you MUST either
  (a) route traffic through an Iranian proxy (set SNAPP_PROXY), or
  (b) run the MCP server on a machine with an Iranian egress IP.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

# --- Optional dependencies (graceful if not installed) ---------------------
try:
    from curl_cffi import requests as cffi_requests  # type: ignore
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    from playwright.sync_api import sync_playwright  # type: ignore
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


# --- Configuration --------------------------------------------------------
PROXY_URL: Optional[str] = os.environ.get("SNAPP_PROXY") or None
FORCED_FETCHER: Optional[str] = os.environ.get("SNAPP_FETCHER") or None
TIMEOUT: int = int(os.environ.get("SNAPP_TIMEOUT", "30"))


# Realistic Chrome 131 desktop headers (fa-IR locale).
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,application/xml;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}


@dataclass
class FetchResult:
    url: str
    status: int
    html: str
    title: str = ""
    fetcher: str = ""


def _proxy_dict() -> Optional[dict]:
    """Return proxy dict for requests/playwright, or None."""
    if not PROXY_URL:
        return None
    return {"server": PROXY_URL}


# --- Strategy 1: curl_cffi ------------------------------------------------
def _fetch_via_curl_cffi(url: str, timeout: int) -> Optional[FetchResult]:
    if not HAS_CURL_CFFI:
        return None
    try:
        r = cffi_requests.get(
            url,
            impersonate="chrome131",
            headers=BROWSER_HEADERS,
            timeout=timeout,
            proxies=_proxy_dict(),
        )
        if r.status_code != 200:
            return None
        html = r.text
        tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        return FetchResult(
            url=url, status=r.status_code, html=html,
            title=tm.group(1).strip() if tm else "",
            fetcher="curl_cffi(chrome131)",
        )
    except Exception:
        return None


# --- Strategy 2: Playwright with stealth ---------------------------------
_STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['fa-IR', 'fa', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
window.chrome = { runtime: {}, app: { isInstalled: false } };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (p) => (
    p.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(p)
  );
}
"""


def _fetch_via_playwright(url: str, timeout: int) -> Optional[FetchResult]:
    if not HAS_PLAYWRIGHT:
        return None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            # Try system-installed Chrome/Edge first (avoids needing a
            # playwright install; also works when cdn.playwright.dev is
            # geo-blocked), then fall back to the bundled Chromium.
            launched = False
            for channel in ("chrome", "msedge"):
                try:
                    browser = p.chromium.launch(
                        channel=channel, headless=True, args=launch_args)
                    launched = True
                    break
                except Exception:
                    continue
            if not launched:
                browser = p.chromium.launch(headless=True, args=launch_args)
            ctx_opts = dict(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="fa-IR",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={
                    "Accept-Language": BROWSER_HEADERS["Accept-Language"],
                },
            )
            if _proxy_dict():
                ctx_opts["proxy"] = _proxy_dict()
            ctx = browser.new_context(**ctx_opts)
            ctx.add_init_script(_STEALTH_INIT_JS)
            page = ctx.new_page()
            resp = page.goto(url, wait_until="domcontentloaded",
                             timeout=timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            html = page.content()
            title = page.title() or ""
            status = resp.status if resp else 200
            browser.close()
            if status != 200:
                return None
            return FetchResult(
                url=url, status=status, html=html,
                title=title, fetcher="playwright(stealth)",
            )
    except Exception as exc:
        raise RuntimeError(
            f"Playwright fetch failed: {exc}. "
            "Install Chrome or run: python -m playwright install chromium"
        ) from exc


# --- Public entry point ---------------------------------------------------
def fetch(url: str, timeout: Optional[int] = None) -> FetchResult:
    """Fetch a URL. Tries curl_cffi first, then Playwright.

    Set SNAPP_FETCHER=playwright (or curl_cffi) to force a specific strategy.
    Set SNAPP_PROXY to route through a proxy.

    Raises RuntimeError if both strategies fail.
    """
    t = timeout or TIMEOUT
    strategies = []
    if FORCED_FETCHER == "playwright":
        strategies = [_fetch_via_playwright, _fetch_via_curl_cffi]
    elif FORCED_FETCHER == "curl_cffi":
        strategies = [_fetch_via_curl_cffi, _fetch_via_playwright]
    else:
        strategies = [_fetch_via_curl_cffi, _fetch_via_playwright]

    errors = []
    for fn in strategies:
        if fn is None:
            continue
        name = fn.__name__.replace("_fetch_via_", "")
        try:
            res = fn(url, t)
            if res is not None:
                return res
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError(
        f"All fetchers failed for {url}. "
        f"Available: curl_cffi={HAS_CURL_CFFI}, playwright={HAS_PLAYWRIGHT}. "
        f"Proxy: {PROXY_URL or 'none'}. "
        f"Forced: {FORCED_FETCHER or 'auto'}. "
        f"Errors: {errors or 'no exceptions raised, all returned None'}. "
        f"If you are outside Iran, snappshop.ir returns 403 — set SNAPP_PROXY "
        f"to an Iranian proxy."
    )


def fetcher_info() -> dict:
    """Return info about available fetcher strategies (used by health tool)."""
    return {
        "curl_cffi_available": HAS_CURL_CFFI,
        "playwright_available": HAS_PLAYWRIGHT,
        "proxy_configured": bool(PROXY_URL),
        "forced_fetcher": FORCED_FETCHER or "auto",
        "timeout_seconds": TIMEOUT,
    }


if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://snappshop.ir/"
    print(f"Fetching: {test_url}")
    print(f"Strategies: {fetcher_info()}")
    r = fetch(test_url)
    print(f"Fetched via: {r.fetcher}")
    print(f"Status: {r.status}, HTML length: {len(r.html)}")
    print(f"Title: {r.title[:80]}")
