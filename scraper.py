"""
scraper.py — Extract structured product data from snappshop.ir HTML.

Two parsers:
  1) parse_search_results(html) → list of product cards (slug, title, image, ...)
  2) parse_product_detail(html, source_url) → full product schema from JSON-LD

The site is a Next.js SPA. The SSR HTML contains:
  - On /search and /category/<slug> pages: a list of
    <a href="/product/snp-XXX"> cards with title attribute, image, colors,
    badges. Prices are loaded async (not in the SSR), so card-level results
    do NOT include price.
  - On /product/snp-XXX pages: full JSON-LD `Product` schema in
    <script type="application/ld+json"> with name, description, image,
    brand, offers (price, currency, availability), aggregateRating, sku.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import urljoin

BASE_URL = "https://snappshop.ir"


@dataclass
class ProductCard:
    """Minimal info shown on a search/category listing page."""
    slug: str                 # e.g. "snp-1327041642"
    product_url: str          # absolute URL
    title: str
    image_url: Optional[str] = None
    colors: list[str] = None
    badges: list[str] = None


@dataclass
class ProductDetail:
    """Full product info extracted from JSON-LD `Product` schema."""
    slug: str
    product_url: str
    name: str
    description: Optional[str] = None
    brand: Optional[str] = None
    brand_url: Optional[str] = None
    sku: Optional[str] = None
    mpn: Optional[str] = None
    category_url: Optional[str] = None
    images: list[str] = None
    price: Optional[float] = None           # in IRR (Iranian Rial)
    price_currency: Optional[str] = None    # usually "IRR"
    availability: Optional[str] = None      # schema.org URL
    condition: Optional[str] = None
    rating_value: Optional[float] = None
    review_count: Optional[int] = None


# Color words commonly used on snappshop.ir color swatches.
_COLOR_WORDS = (
    "صورتی", "مشکی", "سرمه‌ای", "سرمه اي", "سفید", "قرمز", "قرمزی",
    "آبی", "سبز", "زرد", "نارنجی", "بنفش", "طوسی", "خاکستری",
    "قهوه‌ای", "قهوه ای", "طلایی", "نقره‌ای", "نقره اي", "بژ",
    "یشمی", "مرمری", "کرم", "یشم",
)


def parse_search_results(html: str) -> list[ProductCard]:
    """Extract product cards from a search/category listing page."""
    cards: list[ProductCard] = []
    seen_slugs: set[str] = set()

    # Each card is wrapped in <a href="/product/snp-XXX" title="...">...</a>
    # Use a tolerant regex that handles attribute order variations.
    card_re = re.compile(
        r'<a[^>]*?'
        r'(?:href="(/product/(?P<slug>snp-[\w-]+))"[^>]*?'
        r'title="(?P<title>[^"]+)"'
        r'|title="(?P<title2>[^"]+)"[^>]*?'
        r'href="(/product/(?P<slug2>snp-[\w-]+))")'
        r'[^>]*>(?P<body>.*?)</a>',
        re.S
    )

    for m in card_re.finditer(html):
        slug = m.group("slug") or m.group("slug2")
        title = m.group("title") or m.group("title2")
        body = m.group("body") or ""
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Image (first cdn product image in the card body)
        img_m = re.search(
            r'src="(https://cdn\.snappshop\.ir/products/[^"]+)"', body
        )
        image_url = img_m.group(1) if img_m else None

        # Colors — <span title="X" ...> swatches
        colors = re.findall(r'title="([^"]+)"', body)
        colors = [c for c in colors if c in _COLOR_WORDS]
        # dedupe preserving order
        seen = set()
        colors = [c for c in colors if not (c in seen or seen.add(c))]

        # Badges — text inside product-badge spans
        badges = re.findall(
            r'product-badge[^>]*>([^<]{2,40})<', body
        )
        badges = [b.strip() for b in badges if b.strip()]

        cards.append(ProductCard(
            slug=slug,
            product_url=urljoin(BASE_URL, f"/product/{slug}"),
            title=title.strip(),
            image_url=image_url,
            colors=colors or None,
            badges=badges or None,
        ))

    return cards


def parse_product_detail(html: str, source_url: str = "") -> Optional[ProductDetail]:
    """Extract full product detail from a /product/snp-XXX page.

    Returns None if no Product JSON-LD block is found.
    """
    ldjson_blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.S
    )

    product_block: dict | None = None
    for blk in ldjson_blocks:
        try:
            parsed = json.loads(blk.strip())
        except json.JSONDecodeError:
            continue
        # A block can be a list of objects or a single object
        candidates = parsed if isinstance(parsed, list) else [parsed]
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            t = cand.get("@type", "")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                product_block = cand
                break
        if product_block:
            break

    if not product_block:
        return None

    slug = source_url.rsplit("/", 1)[-1] if source_url else ""
    images = product_block.get("image") or []
    if isinstance(images, str):
        images = [images]

    offers = product_block.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}

    brand = product_block.get("brand") or {}
    agg = product_block.get("aggregateRating") or {}

    return ProductDetail(
        slug=slug,
        product_url=source_url,
        name=product_block.get("name", "").strip(),
        description=(product_block.get("description") or "").strip() or None,
        brand=(brand.get("name") if isinstance(brand, dict) else None),
        brand_url=(brand.get("url") if isinstance(brand, dict) else None),
        sku=str(product_block.get("sku") or "") or None,
        mpn=str(product_block.get("mpn") or "") or None,
        category_url=product_block.get("category"),
        images=images or None,
        price=offers.get("price"),
        price_currency=offers.get("priceCurrency"),
        availability=offers.get("availability"),
        condition=offers.get("itemCondition"),
        rating_value=agg.get("ratingValue"),
        review_count=agg.get("reviewCount"),
    )


def to_dict(obj) -> dict:
    """Convert a dataclass instance to a JSON-serializable dict."""
    return asdict(obj)
