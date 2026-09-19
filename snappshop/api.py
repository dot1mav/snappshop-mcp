"""
api.py — HTTP transport layer for the SnappShop public JSON API.

Supports two transport modes, switched via environment variable:

  * **Direct** (default): talks to ``apix.snappshop.ir`` from wherever the
    Python process runs. Works on Iranian IPs (or with ``SNAPP_PROXY``).
  * **Worker proxy** (``SNAPP_WORKER_URL`` set): all requests are routed
    through the Cloudflare Worker at that URL, so the Python side needs no
    special network access and never sees a geo-block.

In both cases the normalized output is identical — the Worker mirrors the
exact same normalization logic in JavaScript (see ``worker/src/snappshop/``).
"""
from __future__ import annotations

import os
import re
import json as _json
from typing import Any, Optional
from urllib.parse import quote as _q, urlencode as _ue

from .normalize import (
    WEB_BASE_URL,
    normalize_categories as _norm_cat,
    normalize_product as _norm_prod,
    normalize_search as _norm_search,
)

# ── env config ───────────────────────────────────────────────────────────
API_BASE     = os.environ.get("SNAPP_API_BASE",  "https://apix.snappshop.ir")
WORKER_URL   = os.environ.get("SNAPP_WORKER_URL", "").rstrip("/")
WORKER_TOKEN = os.environ.get("SNAPP_WORKER_TOKEN", "")
ORIGIN       = "https://snappshop.ir"
DEFAULT_LAT  = os.environ.get("SNAPP_LAT", "35.77331")
DEFAULT_LNG  = os.environ.get("SNAPP_LNG", "51.418591")
TIMEOUT      = int(os.environ.get("SNAPP_TIMEOUT", "30"))
CACHE_TTL    = int(os.environ.get("SNAPP_CACHE_TTL", "300"))

# ── errors ───────────────────────────────────────────────────────────────
class SnappError(Exception):
    pass

class SnappApiError(SnappError):
    def __init__(self, status: int, body: str, *, method: str = "",
                 path: str = ""):
        self.status = status
        self.body = body
        self.method = method
        self.path = path
        msg = f"Snapp API {status} on {method} {path}: {body[:300]}"
        super().__init__(msg)

class SnappTransportError(SnappError):
    pass

# ── session pool ─────────────────────────────────────────────────────────
_session = None

def _get_session():
    global _session
    if _session is None:
        try:
            from curl_cffi.requests import Session
            _session = Session(impersonate="chrome131")
        except ImportError:
            import urllib.request
            _session = urllib.request
    return _session


# ── helpers ──────────────────────────────────────────────────────────────
_RE_SNIP = re.compile(r"snp-?(\d+)|/(\d+)(?:$|[/?#])")

def parse_product_ref(ref: str) -> str:
    """Extract the numeric product id from any reasonable reference form.

    Accepts: ``snp-25751584``, ``25751584``,
    ``https://snappshop.ir/product/snp-25751584``.
    """
    s = ref.strip()
    if s.startswith("http"):
        s = s.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    m = _RE_SNIP.search(s)
    if m:
        return m.group(1) or m.group(2)
    digits = re.search(r"\d+", s)
    if digits:
        return digits.group(0)
    raise SnappError(f"Cannot extract a numeric product id from: {ref!r}")


# ── direct transport ─────────────────────────────────────────────────────
class _DirectClient:
    """Talks directly to ``apix.snappshop.ir`` via curl_cffi."""
    def __init__(self, base: str = API_BASE, lat: str = DEFAULT_LAT,
                 lng: str = DEFAULT_LNG):
        self._base = base.rstrip("/")
        self._lat = lat
        self._lng = lng
        self._token: Optional[str] = None
        self._headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            "Origin": ORIGIN,
            "Referer": ORIGIN + "/",
        }

    def _geo(self) -> str:
        return f"?lat={self._lat}&lng={self._lng}"

    def _ensure_token(self) -> None:
        if self._token:
            return
        try:
            data = self._req("GET", "/guest/v2/token", want_json=True)
            self._token = (data or {}).get("data", {}).get("token")
        except Exception:
            self._token = None

    def _req(self, method: str, path: str, *, params: dict = None,
             json_body: dict = None, want_json: bool = False) -> Any:
        import time as _t
        s = _get_session()
        url = self._base + path
        if params:
            url += ("&" if "?" in url else "?") + _ue(params)
        h = dict(self._headers)
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if json_body:
            h["Content-Type"] = "application/json"
        try:
            if hasattr(s, "request"):
                resp = s.request(method, url, headers=h,
                                 json=json_body, timeout=TIMEOUT)
            else:
                import urllib.request as _ur
                req = _ur.Request(url, method=method,
                                  data=_json.dumps(json_body).encode() if json_body else None,
                                  headers=h)
                with _ur.urlopen(req, timeout=TIMEOUT) as r:
                    body = r.read().decode()
                    class _R: status_code = r.status; text = body
                    resp = _R()
            status = resp.status_code
            body = resp.text
        except Exception as exc:
            raise SnappTransportError(f"{method} {path}: {exc}") from exc

        if status == 401 and not json_body and not params:
            self._token = None
            self._ensure_token()
            return self._req(method, path, json_body=json_body, want_json=want_json)

        if status >= 400:
            raise SnappApiError(status, body, method=method, path=path)
        if want_json:
            return _json.loads(body)
        return body

    # ── public surface ───────────────────────────────────────────────
    def search_raw(self, query: str = None, category: str = None, *,
                   limit: int = 12, page: int = 1,
                   sort: str = None, extra: dict = None) -> dict:
        body = {"render": 4}
        if query:
            body["query"] = query
        if category:
            body["categories"] = [category]
        if sort:
            body["sort"] = sort
        if page and page > 1:
            body["skip"] = page - 1
        if extra:
            body.update(extra)
        return self._req("POST", "/search/v1" + self._geo(),
                         json_body=body, want_json=True)

    def product_raw(self, product_id: str) -> dict:
        return self._req("GET", f"/products/v2/{product_id}" + self._geo(),
                         want_json=True)

    def megamenu_raw(self) -> dict:
        return self._req("GET", "/landing/v1/megamenu" + self._geo(),
                         want_json=True)

    def categories_raw(self) -> dict:
        return self.megamenu_raw()

    def search(self, query: str = None, category: str = None, **kw) -> dict:
        raw = self.search_raw(query, category, **kw)
        return _norm_search(raw, limit=kw.get("limit", 12),
                            query=query, category=category,
                            page=kw.get("page", 1))

    def product(self, ref: str, **kw) -> dict:
        pid = parse_product_ref(ref)
        raw = self.product_raw(pid)
        slug = f"snp-{pid}"
        return _norm_prod(raw, product_id=pid, slug=slug)

    def categories(self, **kw) -> dict:
        raw = self.megamenu_raw()
        return _norm_cat(raw, **kw)


# ── worker proxy transport ───────────────────────────────────────────────
class _WorkerClient:
    """Routes all requests through a Cloudflare Worker."""
    def __init__(self, worker_url: str, token: str = ""):
        self._base = worker_url.rstrip("/")
        self._token = token

    def _req(self, method: str, path: str, *, json_body=None) -> Any:
        s = _get_session()
        url = self._base + "/api" + path
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": ORIGIN,
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        try:
            if hasattr(s, "request"):
                resp = s.request(method, url, headers=h,
                                 json=json_body, timeout=TIMEOUT)
            else:
                import urllib.request as _ur
                req = _ur.Request(url, method=method,
                                  data=_json.dumps(json_body).encode() if json_body else None,
                                  headers=h)
                with _ur.urlopen(req, timeout=TIMEOUT) as r:
                    body = r.read().decode()
                    class _R: status_code = r.status; text = body
                    resp = _R()
        except Exception as exc:
            raise SnappTransportError(f"{method} {path}: {exc}") from exc
        if resp.status_code >= 400:
            raise SnappApiError(resp.status_code, resp.text,
                                method=method, path=path)
        return _json.loads(resp.text)

    def search(self, query=None, category=None, **kw) -> dict:
        return self._req("POST", "/search",
                         json_body={"query": query, "category": category,
                                    "limit": kw.get("limit", 12),
                                    "page": kw.get("page", 1),
                                    "sort": kw.get("sort")})

    def product(self, ref: str, **kw) -> dict:
        return self._req("GET", f"/product/{parse_product_ref(ref)}")

    def categories(self, **kw) -> dict:
        return self._req("GET", "/categories")


# ── public entry point ───────────────────────────────────────────────────
_client: Optional[object] = None

def get_client():
    """Return a singleton client (Direct or Worker, per env)."""
    global _client
    if _client is None:
        if WORKER_URL:
            _client = _WorkerClient(WORKER_URL, WORKER_TOKEN)
        else:
            _client = _DirectClient()
    return _client
