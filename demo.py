"""
End-to-end demo: simulate a real user query that an MCP client (Claude/Cursor)
would call. No MCP wire protocol needed - just direct function calls.
"""
from textutil import enable_utf8_stdout
enable_utf8_stdout()

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from server import search_products, get_product, list_categories, get_category_products, health  # noqa


def call(fn, *a, **kw):
    return json.loads(fn(*a, **kw))


def main():
    print("=" * 70)
    print("USER SCENARIO: Find a Samsung phone on snappshop.ir")
    print("              and tell me its rating + price + image URL.")
    print("=" * 70)

    # Step 1: search
    print("\n[1] Search 'گوشی سامسونگ'...")
    res = call(search_products, "گوشی سامسونگ", limit=5)
    if "error" in res:
        print(f"  ERROR: {res['error']}")
        return
    print(f"  -> {res['count']} products returned ({res['total_unique_products']} total unique)")
    for i, p in enumerate(res["products"][:3], 1):
        price = (p.get("price") or {}).get("display", "?")
        print(f"  [{i}] {p['title'][:70]}")
        print(f"      price: {price} | slug: {p.get('slug')}")

    # Step 2: pick first card, fetch full product detail
    if not res["products"]:
        print("  No products found.")
        return
    top = res["products"][0]
    print(f"\n[2] Top result: {top['title']}")
    print(f"    slug: {top['slug']}")
    print(f"    image: {top.get('image_url')}")
    print(f"    colors: {[c['title'] for c in (top.get('colors') or [])]}")

    print(f"\n[3] Fetching full detail for {top['slug']}...")
    prod = call(get_product, top["slug"])
    if "error" in prod:
        print(f"  ERROR: {prod['error']}")
        return
    print(f"  name: {prod['name']}")
    brand = prod.get("brand") or {}
    print(f"  brand: {brand.get('name')} ({brand.get('name_en')})")
    price = prod.get("price") or {}
    if price.get("toman"):
        print(f"  price: {price['display']} ({price.get('rial', 0):,} Rial)")
        if price.get("original_toman"):
            print(f"  original: {price.get('original_display')} | discount: {price.get('discount_percent')}%")
    print(f"  available: {prod.get('available')}")
    rating = prod.get("rating") or {}
    print(f"  rating: {rating.get('value', '?')} ({rating.get('count', '?')} ratings, {rating.get('comments', '?')} comments)")
    print(f"  images: {len(prod.get('images') or [])}")
    for img in (prod.get("images") or [])[:3]:
        print(f"    - {img}")

    print("\n[4] Categories available:")
    cats = call(list_categories)
    for c in (cats.get("categories") or [])[:10]:
        print(f"  * {c.get('title', '?'):30s} depth={c.get('depth', '?')} -> {c.get('href', '?')}")

    print("\n" + "=" * 70)
    print("All scenarios passed. MCP server is ready.")
    print("=" * 70)


if __name__ == "__main__":
    main()
