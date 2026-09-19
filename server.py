"""
server.py — MCP server exposing snappshop.ir product data as tools.

Compatible with both MCP 1.x (FastMCP) and MCP 2.x (MCPServer).
Auto-detects installed version at import time.

Supports two transport modes (controlled by SNAPP_WORKER_URL env var):
  - Direct: talks to apix.snappshop.ir (requires Iranian IP or SNAPP_PROXY)
  - Worker proxy: routes through a Cloudflare Worker (works from anywhere)

Tools exposed:
  * search_products(query, limit=10)         -> search snappshop.ir
  * get_product(slug)                        -> full product detail
  * list_categories()                        -> top-level categories
  * get_category_products(category, limit=10) -> products in a category
  * health()                                 -> connectivity check
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# UTF-8 fix for Windows (prevents UnicodeEncodeError on Persian text)
from textutil import enable_utf8_stdout
enable_utf8_stdout()

# --- MCP SDK: support both v1 (FastMCP) and v2 (MCPServer) ---
try:
    from mcp.server.mcpserver import MCPServer as _Server  # MCP 2.x
    _MCP_VERSION = "2.x"
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as _Server   # MCP 1.x
        _MCP_VERSION = "1.x"
    except ImportError as e:
        raise ImportError(
            "Neither mcp.server.mcpserver (MCP 2.x) nor "
            "mcp.server.fastmcp (MCP 1.x) is available. "
            "Install with: pip install mcp"
        ) from e

from snappshop.api import get_client, parse_product_ref, SnappApiError, SnappError

WORKER_URL = os.environ.get("SNAPP_WORKER_URL", "")

mcp = _Server(
    "snappshop",
    instructions=(
        "SnappShop MCP server - exposes tools to search products, fetch "
        "product details, list categories, and list products in a category "
        "from snappshop.ir (Iranian e-commerce marketplace). All prices "
        "are reported in Toman (IRR * 10)."
    ),
)


def _json(obj, **kw) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, **kw)


@mcp.tool()
def search_products(query: str, limit: int = 10) -> str:
    """Search snappshop.ir for products matching the given query.

    Args:
        query: Search term in Persian or English (e.g. "گوشی", "headphones").
        limit: Max number of results to return (1..50). Default 10.

    Returns:
        JSON with: count, total_unique_products, pagination, filters,
        sort_options, suggested_categories, suggested_keywords,
        products[] (each with slug, title, price.toman, image_url, colors, badges).
    """
    limit = max(1, min(int(limit or 10), 50))
    try:
        result = get_client().search(query=query, limit=limit)
    except SnappError as e:
        return _json({"error": str(e)})
    return _json(result)


@mcp.tool()
def get_product(slug: str) -> str:
    """Fetch full product detail from snappshop.ir.

    Args:
        slug: Product identifier. Accepts any of:
          - "snp-25751584"
          - "25751584"
          - "https://snappshop.ir/product/snp-25751584"

    Returns:
        JSON with full product information including:
          name, name_en, description, brand, sku, mpn
          price.toman, price.rial, price.display
          images, colors, attributes, variants, offers, best_offer
          availability, rating, categories, sellers, warranties
    """
    try:
        result = get_client().product(slug)
    except SnappError as e:
        return _json({"error": str(e), "ref": slug})
    return _json(result)


@mcp.tool()
def list_categories() -> str:
    """List the product categories available on snappshop.ir.

    Returns:
        JSON array of category objects with: title, href, url, icon, depth, parent.
        Hierarchically structured via the nested category tree from the megamenu.
    """
    try:
        result = get_client().categories(flat=True)
    except SnappError as e:
        return _json({"error": str(e)})
    return _json(result)


@mcp.tool()
def get_category_products(category: str, limit: int = 10) -> str:
    """List products in a top-level category on snappshop.ir.

    Args:
        category: Category identifier. Use the 'title' from list_categories()
                  (e.g. "موبایل"), or a slug like "mobile".
        limit: Max number of results (1..50). Default 10.

    Returns:
        JSON with: category, count, products[] (same shape as search_products).
    """
    limit = max(1, min(int(limit or 10), 50))
    try:
        result = get_client().search(category=category, limit=limit)
    except SnappError as e:
        return _json({"error": str(e), "category": category})
    return _json(result)


@mcp.tool()
def health() -> str:
    """Connectivity check: test that the SnappShop API is reachable.

    Returns:
        JSON with: status, mcp_version, transport mode, sample search result.
    """
    info = {
        "status": "unknown",
        "mcp_version": _MCP_VERSION,
        "transport": "worker" if WORKER_URL else "direct",
        "worker_url": WORKER_URL or None,
    }
    try:
        client = get_client()
        result = client.search("گوشی", limit=1)
        info["status"] = "ok"
        info["test_search"] = {
            "count": result.get("count", 0),
            "first_product": (result.get("products") or [{}])[0].get("title", ""),
        }
    except Exception as e:
        info["status"] = "error"
        info["error"] = str(e)
    return _json(info)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
