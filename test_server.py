"""
test_server.py — Direct functional test of the MCP server tools
without needing a real MCP client.
"""
from textutil import enable_utf8_stdout
enable_utf8_stdout()

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from server import (  # noqa
    mcp, search_products, get_product, list_categories,
    get_category_products, health, _MCP_VERSION,
)


def call(fn, *args, **kwargs):
    """Call a tool function and parse its JSON output."""
    raw = fn(*args, **kwargs)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


def main():
    print(f"\n[Detected MCP SDK version: {_MCP_VERSION}]")

    print("\n========== 1) health() ==========")
    h = call(health)
    print(json.dumps(h, ensure_ascii=False, indent=2))

    print("\n========== 2) list_categories() ==========")
    cats = call(list_categories)
    count = cats.get("count", 0)
    print(f"Found {count} categories")
    for c in (cats.get("categories") or [])[:5]:
        print(f"  * {c.get('title', '?'):25s} -> {c.get('href', '?')}")

    print("\n========== 3) search_products('گوشی اپل', limit=5) ==========")
    res = call(search_products, "گوشی اپل", 5)
    if "error" in res:
        print(f"ERROR: {res['error']}")
    else:
        print(f"Found {res.get('count', 0)} products ({res.get('total_unique_products', 0)} total):")
        for p in res.get("products", []):
            price = (p.get("price") or {}).get("display", "?")
            print(f"  * {p.get('slug', '?'):20s} | {p.get('title', '?')[:60]}")
            print(f"    price: {price} | Image: {'Y' if p.get('image_url') else 'N'}")

    print("\n========== 4) get_product('snp-25751584') ==========")
    prod = call(get_product, "snp-25751584")
    if "error" in prod:
        print(f"ERROR: {prod['error']}")
    else:
        price = prod.get("price") or {}
        print(f"Name: {prod.get('name')}")
        print(f"Brand: {(prod.get('brand') or {}).get('name')}")
        print(f"Price: {price.get('display')} ({price.get('rial', 0):,} Rial)")
        print(f"Available: {prod.get('available')}")
        print(f"Images: {len(prod.get('images') or [])}")
        print(f"Offers: {len(prod.get('offers') or [])}")

    print("\n========== 5) get_category_products('mobile', limit=3) ==========")
    catres = call(get_category_products, "mobile", 3)
    if "error" in catres:
        print(f"ERROR: {catres['error']}")
    else:
        print(f"Found {catres.get('count', 0)} products in mobile category:")
        for p in catres.get("products", []):
            print(f"  * {p.get('slug', '?'):20s} | {p.get('title', '?')[:60]}")

    print("\n========== ALL TESTS DONE ==========")


if __name__ == "__main__":
    main()
