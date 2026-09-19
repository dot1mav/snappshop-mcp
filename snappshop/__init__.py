"""
snappshop — shared core for talking to the SnappShop public JSON API.

This package is the single source of truth for the *normalized* shapes
returned by the MCP tools. The Cloudflare Worker under `worker/` mirrors
this exact logic in JavaScript (see `worker/src/snappshop/`), so a client
gets byte-compatible JSON whether it talks to the Python server directly
or through the Worker proxy.

Public surface:
    SnappClient          high-level API client (search/products/categories)
    normalize_*          pure functions: raw API JSON -> normalized dicts
    SnappApiError        raised on non-2xx API responses
    SnappTransportError  raised when the network/transport itself fails
"""
from __future__ import annotations

from .api import (
    DEFAULT_LAT,
    DEFAULT_LNG,
    ORIGIN,
    WEB_BASE_URL,
    SnappApiError,
    SnappError,
    SnappTransportError,
    get_client,
    parse_product_ref,
)
from .normalize import (
    normalize_categories,
    normalize_product,
    normalize_search,
)
from .units import IR_TOMAN_PER_RIAL, format_rial, rial_to_toman, toman_to_rial

__all__ = [
    "get_client",
    "parse_product_ref",
    "normalize_search",
    "normalize_product",
    "normalize_categories",
    "SnappError",
    "SnappApiError",
    "SnappTransportError",
    "rial_to_toman",
    "toman_to_rial",
    "format_rial",
    "IR_TOMAN_PER_RIAL",
    "WEB_BASE_URL",
    "ORIGIN",
    "DEFAULT_LAT",
    "DEFAULT_LNG",
]

__version__ = "2.0.0"