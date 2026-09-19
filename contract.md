# SnappShop MCP Normalization Contract

This document defines the shared data structure between the Python MCP Server and the ArvanCloud Edge MCP Server.

## 1. ProductCard (Search Result)
Used in `search_products`.
- `product_id`: (string) Internal ID.
- `slug`: (string) URL slug (e.g., "snp-123").
- `product_url`: (string) Full URL.
- `title`: (string) Trimmed product name.
- `image_url`: (string) CDN URL to main image.
- `price`: {
    - `toman`: (number)- Authoritative price.
    - `rial`: (number) - Toman * 10.
    - `display`: (string) - Formatted "X تومان".
    - `original_toman`: (number|null) - Price before discount.
    - `original_display`: (string|null) - Formatted original.
    - `discount_percent`: (number|null) - Discount percentage.
    - `currency`: "IRT"
}
- `rating`: {
    - `value`: (number) - Star rating.
    - `count`: (number) - Review count.
}

## 2. ProductDetail
Used in `get_product`.
- `product_id`: (string)
- `name`: (string)
- `brand`: (string)
- `price`: (Same as ProductCard.price)
- `available`: (boolean)
- `attributes`: [ { `title`: string, `value`: string } ]
- `images`: [ string ]
