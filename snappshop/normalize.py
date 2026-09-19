"""
snappshop/normalize.py
----------------------
Pure functions that transform raw API JSON into clean, LLM-friendly shapes.
This is the "Source of Truth" for the Normalization Contract.
"""
from typing import Any, Dict, List, Optional
from .units import price_block

def normalize_card(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms a single product card from search results into a 
    simplified shape for the LLM.
    """
    price_raw = item.get("price", {})
    special = price_raw.get("discounted_price")
    original = price_raw.get("price")
    
    # Handle discount logic: use special price if it's actually lower
    price = price_block(
        special if (special and original and special < original) else (original or special),
        original,
        price_raw.get("discount")
    )

    return {
        "product_id": item.get("id"),
        "slug": item.get("href", "").split("/")[-1] if item.get("href") else None,
        "product_url": item.get("href"),
        "title": item.get("title", "").strip(),
        "image_url": item.get("image", {}).get("src"),
        "price": price,
        "rating": {
            "value": item.get("state", {}).get("rate"),
            "count": item.get("state", {}).get("rate_count"),
        },
    }

def normalize_search(payload: Dict[str, Any], query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Processes a full search API response, deduplicates products, 
    and applies the limit.
    """
    structure = payload.get("data", {}).get("structure", [])
    products = []
    seen_slugs = set()

    for section in structure:
        for item in section.get("items", []):
            card = normalize_card(item)
            slug = card["slug"]
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                products.append(card)

    return {
        "query": query,
        "count": len(products[:limit]),
        "total_unique": len(products),
        "products": products[:limit],
    }

def normalize_product(payload: Dict[str, Any], product_id: str) -> Dict[str, Any]:
    """
    Transforms a full product detail response into a comprehensive 
    specification for the LLM.
    """
    data = payload.get("data", {})
    content = data.get("content", {})
    
    # Extract best offer (lowest price)
    all_offers = []
    for variant in data.get("variants", []):
        for vendor in variant.get("vendor", []):
            all_offers.append(vendor)
    
    best_offer = min(all_offers, key=lambda x: x.get("price", float('inf'))) if all_offers else None
    
    return {
        "product_id": product_id,
        "name": content.get("title_fa", "").strip(),
        "brand": data.get("brand", {}).get("title_fa"),
        "price": price_block(
            best_offer.get("special_price") if best_offer else None,
            best_offer.get("price") if best_offer else None
        ),
        "available": bool(best_offer),
        "attributes": [
            {"title": a.get("title"), "value": a.get("value")} 
            for a in data.get("attributes", [])
        ],
        "images": [img.get("src") for img in data.get("images", [])],
    }
