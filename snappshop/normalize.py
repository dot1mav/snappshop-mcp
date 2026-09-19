"""
normalize.py — pure functions turning raw SnappShop API JSON into the
normalized shapes that both the MCP tools and the Cloudflare Worker emit.

Everything here is a pure function of its input: no I/O, no network. That
makes it trivially unit-testable against the recorded fixtures in `fixtures/`.

Verified live response shapes (2026-09, api build customer_production_ir_csr_ae24f668):

  POST /search/v1  {"query":"...","render":4}
    data.structure[].section_type == "plp"
    data.structure[].items[]        product cards
    data.structure[].pagination     {current_page,total,total_pages,count,per_page}
    data.structure[].sort[]         {id,title,is_selected}
    data.structure[].filter[]       {filter_id,filter_type,title,items[]}

  GET /products/v2/<numeric-id>
    data.content      {title_fa,title_en,description,meta_*}
    data.brand        {title_fa,title_en,logo{src,alt},breadcrumbs[]}
    data.images[]     {id,src,alt}
    data.variants[]   {variation_id,attribute_ids[],vendor[]}
    data.variants[].vendor[]  {price,special_price,stock,warranty_id,...}
    data.default_variant      {variation_id,vendor_product_info_id,vendor_id}
    data.page.json_ld[]       schema.org Product (prices in *Rial*)
    data.warranties[] {id,name,company_title,duration}
    data.attributes[] {id,title,value}

PRICE UNITS: the JSON API speaks **Toman**, the embedded JSON-LD speaks
**Rial** (1 Toman = 10 Rial). See `units.py`.
"""
from __future__ import annotations

from typing import Iterable, Optional
from urllib.parse import urljoin

from .units import price_block, rial_to_toman

WEB_BASE_URL = "https://snappshop.ir"

# How many variants/vendors/specs to inline before truncating. Keeps a tool
# response inside a sane token budget while staying complete for the common
# single-variant, single-vendor case.
_MAX_VARIANTS = 12
_MAX_VENDORS_PER_VARIANT = 8
_MAX_ATTRIBUTES = 60


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _abs_url(href: Optional[str]) -> Optional[str]:
    """'/product/snp-1' -> 'https://snappshop.ir/product/snp-1'."""
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(WEB_BASE_URL + "/", href.lstrip("/"))


def _slug_from_href(href: Optional[str]) -> Optional[str]:
    """'/product/snp-25751584' -> 'snp-25751584'."""
    if not href:
        return None
    tail = href.rstrip("/").rsplit("/", 1)[-1]
    return tail or None


def _num(value) -> Optional[int]:
    """Coerce to int or None; never raises. Treats 0 as 0 (not None)."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pos(value) -> Optional[int]:
    """Coerce to int, mapping 0/negative/None to None.

    SnappShop uses 0 as the sentinel for "no special price" and
    "0001-01-01" for "no date", so 0 must not be reported as a real price.
    """
    n = _num(value)
    return n if n and n > 0 else None


def _clean(d: dict) -> dict:
    """Drop keys whose value is None so tool output stays readable."""
    return {k: v for k, v in d.items() if v is not None}


# --------------------------------------------------------------------------
# search / listing
# --------------------------------------------------------------------------
def normalize_price_block(raw: Optional[dict]) -> Optional[dict]:
    """`item.price` -> canonical price dict (input is in Toman)."""
    if not raw:
        return None
    special = _pos(raw.get("discounted_price"))
    original = _pos(raw.get("price"))
    if special and original and special < original:
        return price_block(special, original, raw.get("discount"))
    # No discount (or a nonsensical one): the plain price is the price.
    return price_block(original or special)


def normalize_card(item: dict) -> dict:
    """One entry of `structure[].items[]` -> normalized product card."""
    if not isinstance(item, dict):
        return {}
    href = item.get("href")
    img = item.get("image") or {}
    state = item.get("state") or {}
    campaign = item.get("in_campaign") or {}

    colors = [
        _clean({"id": c.get("id"), "title": c.get("title"), "hex": c.get("code")})
        for c in (item.get("colors") or [])
        if isinstance(c, dict) and c.get("title")
    ]

    card = {
        "product_id": item.get("id"),
        "slug": _slug_from_href(href),
        "product_url": _abs_url(href),
        "title": (item.get("title") or "").strip() or None,
        "image_url": img.get("src"),
        "image_alt": img.get("alt"),
        "price": normalize_price_block(item.get("price")),
        "colors": colors or None,
        "badges": [item["badge"]] if item.get("badge") else None,
        "rating": _clean({
            "value": state.get("rate"),
            "count": state.get("rate_count"),
            "score": state.get("score"),
        }) or None,
        "flags": _clean({
            "is_fake": item.get("is_fake"),
            "is_ads": item.get("is_ads"),
        }) or None,
        "campaign": campaign.get("campaign_name") or None,
    }
    return _clean(card)


def normalize_search(payload: dict, *, limit: int = 10,
                     query: Optional[str] = None,
                     category: Optional[str] = None,
                     page: int = 1) -> dict:
    """Full `POST /search/v1` response -> normalized search result.

    `pagination.count` is deliberately ignored: the API reports how many cards
    it built, which does not always equal the number of *unique* products
    (a product can appear in more than one section). We report the real
    deduplicated length instead.
    """
    data = (payload or {}).get("data") or {}
    structure = data.get("structure") or []

    products: list[dict] = []
    seen: set[str] = set()
    section_meta: list[dict] = []
    pagination: dict = {}
    sort_options: list[dict] = []
    filters: list[dict] = []
    suggested_categories: list[dict] = []
    suggested_keywords: list[dict] = []

    for sec in structure:
        if not isinstance(sec, dict):
            continue
        items = sec.get("items") or []
        kept = 0
        for item in items:
            card = normalize_card(item)
            slug = card.get("slug")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            products.append(card)
            kept += 1

        section_meta.append(_clean({
            "id": sec.get("id"),
            "section_type": sec.get("section_type"),
            "is_descriptive": sec.get("is_descriptive"),
            "items": len(items),
            "unique_items": kept,
        }))

        if not pagination and sec.get("pagination"):
            pagination = sec["pagination"] or {}
        if not sort_options and sec.get("sort"):
            sort_options = [
                _clean({"id": s.get("id"), "title": s.get("title"),
                        "is_selected": s.get("is_selected")})
                for s in sec["sort"] if isinstance(s, dict)
            ]
        if not filters and sec.get("filter"):
            filters = [
                _clean({
                    "filter_id": f.get("filter_id"),
                    "filter_type": f.get("filter_type"),
                    "title": f.get("title"),
                    "selected": [i.get("title") for i in (f.get("items") or [])
                                 if isinstance(i, dict) and i.get("is_selected")],
                })
                for f in sec["filter"] if isinstance(f, dict)
            ]
        if not suggested_categories and sec.get("suggested_categories"):
            suggested_categories = [
                _clean({"id": c.get("id"), "title": c.get("title"),
                        "category": c.get("category")})
                for c in sec["suggested_categories"] if isinstance(c, dict)
            ]
        if not suggested_keywords and sec.get("suggested_keywords"):
            suggested_keywords = [
                _clean({"title": k.get("title"), "query": k.get("title")})
                for k in sec["suggested_keywords"] if isinstance(k, dict)
            ]

    sliced = products[: max(1, limit)]

    return _clean({
        "query": query,
        "category": category,
        "page": page,
        "count": len(sliced),
        "total_unique_products": len(products),
        "pagination": _clean({
            "current_page": pagination.get("current_page"),
            "per_page": pagination.get("per_page"),
            "total_pages": pagination.get("total_pages"),
            "reported_total": pagination.get("total"),
            "reported_count": pagination.get("count"),
        }) or None,
        "sort_options": sort_options or None,
        "filters": filters or None,
        "suggested_categories": suggested_categories or None,
        "suggested_keywords": suggested_keywords or None,
        "sections": section_meta or None,
        "products": sliced,
    })


# --------------------------------------------------------------------------
# product detail
# --------------------------------------------------------------------------
def _cheapest_vendor(vendors: Iterable[dict]) -> Optional[dict]:
    """Pick the offer a buyer would actually get: lowest effective price.

    Ties are broken toward the larger stock, so a 1-unit and a 50-unit offer
    at the same price resolve deterministically to the one with stock.
    """
    best, best_key = None, None
    for v in vendors or []:
        if not isinstance(v, dict):
            continue
        effective = _pos(v.get("special_price")) or _pos(v.get("price"))
        if effective is None:
            continue
        key = (effective, -(_num(v.get("stock")) or 0))
        if best_key is None or key < best_key:
            best_key, best = key, v
    return best


def normalize_vendor(v: dict, vendor_meta: Optional[dict] = None) -> dict:
    """One `variants[].vendor[]` entry -> normalized offer.

    `special_price: 0` means "no discount" in this API, not "free", so it is
    mapped to None via `_pos` and the plain `price` is used instead.
    """
    special = _pos(v.get("special_price"))
    plain = _pos(v.get("price"))
    if plain or special:
        price = normalize_price_block({
            "price": plain, "discounted_price": special,
            "discount": v.get("special_price_percent_discount"),
        })
    else:
        price = None

    shipment = v.get("shipment") or {}
    methods = [m for m in ("normal", "asap", "ship_by_seller", "heavy")
               if isinstance(shipment.get(m), dict) and shipment[m].get("enabled")]

    meta = vendor_meta or {}
    stock = _num(v.get("stock"))
    return _clean({
        "vendor_id": v.get("vendor_id"),
        "vendor_name": meta.get("title"),
        "vendor_name_en": meta.get("title_en") or None,
        "vendor_url": _abs_url(meta.get("href")) if meta.get("href") else None,
        "offer_id": v.get("vendor_product_info_id"),
        "price_toman": price["toman"] if price else None,
        "price_rial": price["rial"] if price else None,
        "price_display": price["display"] if price else None,
        "original_price_toman": price["original_toman"] if price else None,
        "discount_percent": price["discount_percent"] if price else None,
        "stock": stock,
        "in_stock": bool(stock and stock > 0),
        "vendor_rate": v.get("vendor_rate"),
        "warranty_id": v.get("warranty_id"),
        "shipment_methods": methods or None,
        "available_in_shop": v.get("is_available_in_shop"),
    })


def _pick_json_ld_product(json_ld) -> dict:
    """Find the schema.org Product block inside `data.page.json_ld`."""
    if isinstance(json_ld, dict):
        json_ld = [json_ld]
    for blk in json_ld or []:
        if isinstance(blk, dict) and blk.get("@type") == "Product":
            return blk
        # nested, e.g. {"@graph": [...]}
        if isinstance(blk, dict) and blk.get("@graph"):
            found = _pick_json_ld_product(blk["@graph"])
            if found:
                return found
    return {}


def _product_prelude(payload: dict, product_id, slug):
    """Shared extraction of the scalar/loose values for `normalize_product`.

    Split out so the assembled return value below stays readable.
    """
    data = (payload or {}).get("data") or {}
    content = data.get("content") or {}
    brand = data.get("brand") or {}
    page = data.get("page") or {}
    ld = _pick_json_ld_product(page.get("json_ld") or [])

    if not slug and product_id:
        slug = f"snp-{product_id}"

    # images: prefer the JSON-LD list (ordered, complete, plain URLs)
    images = [i.get("src") for i in (data.get("images") or [])
              if isinstance(i, dict) and i.get("src")]
    ld_images = ld.get("image") or []
    if isinstance(ld_images, str):
        ld_images = [ld_images]
    if ld_images:
        images = list(dict.fromkeys(list(ld_images) + images))

    warranties = {w.get("id"): w for w in (data.get("warranties") or [])
                  if isinstance(w, dict) and w.get("id")}
    vendor_meta = {v.get("id"): v for v in (data.get("vendors") or [])
                   if isinstance(v, dict) and v.get("id")}

    # configurable attributes (colour swatches live here)
    colors, attributes_config = [], []
    for attr in (data.get("configurable_attribute") or []):
        if not isinstance(attr, dict):
            continue
        val = attr.get("value") or {}
        attributes_config.append(_clean({
            "attribute_id": attr.get("id"),
            "type": attr.get("type"),
            "title": attr.get("title"),
            "value_id": val.get("id"),
            "value": val.get("title"),
            "hex": val.get("hex_code"),
            "is_default": val.get("default"),
        }))
        if attr.get("type") == "color" and val.get("title"):
            colors.append(_clean({"id": val.get("id"), "title": val.get("title"),
                                  "hex": val.get("hex_code"),
                                  "is_default": val.get("default")}))

    offers_ld = ld.get("offers") or {}
    if isinstance(offers_ld, list):
        offers_ld = offers_ld[0] if offers_ld else {}

    return {
        "data": data, "content": content, "brand": brand, "page": page,
        "ld": ld, "slug": slug, "images": images, "warranties": warranties,
        "vendor_meta": vendor_meta, "colors": colors,
        "attributes_config": attributes_config, "offers_ld": offers_ld,
        "ld_rial": _pos(offers_ld.get("price")),
        "availability": offers_ld.get("availability") or "",
    }


def normalize_product(payload: dict, *, product_id: Optional[str] = None,
                      slug: Optional[str] = None) -> dict:
    """Full `GET /products/v2/<numeric-id>` response -> normalized detail.

    Prices are reported in **Toman** (`price.toman`, `offers[].price_toman`)
    alongside their Rial equivalent, because the JSON API speaks Toman while
    the embedded schema.org JSON-LD speaks Rial.
    """
    p = _product_prelude(payload, product_id, slug)
    data, content, brand, page, ld = p["data"], p["content"], p["brand"], p["page"], p["ld"]
    state = data.get("state") or {}
    default_variation = (data.get("default_variant") or {}).get("variation_id")

    # --- variants / offers ------------------------------------------------
    variants, all_offers = [], []
    for var in (data.get("variants") or []):
        if not isinstance(var, dict):
            continue
        is_default = var.get("variation_id") == default_variation
        offers = [normalize_vendor(v, p["vendor_meta"].get(v.get("vendor_id")))
                  for v in (var.get("vendor") or []) if isinstance(v, dict)]
        for o in offers:
            w = p["warranties"].get(o.get("warranty_id"))
            if w:
                o["warranty"] = w.get("name")
            o["variation_id"] = var.get("variation_id")
            if is_default:
                o["is_default_variation"] = True

        offers.sort(key=lambda o: (o.get("price_toman") is None,
                                   o.get("price_toman") or 0))
        all_offers.extend(offers)
        variants.append(_clean({
            "variation_id": var.get("variation_id"),
            "attribute_ids": var.get("attribute_ids") or None,
            "is_default": is_default,
            "offer_count": len(offers),
            "offers": offers[:_MAX_VENDORS_PER_VARIANT] or None,
        }))

    # Put the default variation first so `variants[0]` is the canonical one.
    variants.sort(key=lambda v: not v.get("is_default"))
    variants = variants[:_MAX_VARIANTS]

    best = _cheapest_vendor([v for var in (data.get("variants") or [])
                             if isinstance(var, dict)
                             for v in (var.get("vendor") or [])])
    best_offer = (normalize_vendor(best, p["vendor_meta"].get(best.get("vendor_id")))
                  if best else None)
    if best_offer:
        w = p["warranties"].get(best_offer.get("warranty_id"))
        if w:
            best_offer["warranty"] = w.get("name")

    attributes = [
        _clean({"id": a.get("id"), "title": a.get("title"), "value": a.get("value")})
        for a in (data.get("attributes") or []) if isinstance(a, dict)
    ][:_MAX_ATTRIBUTES]
    featured = [_clean({"title": a.get("title"), "value": a.get("value")})
                for a in (data.get("featured_attributes") or []) if isinstance(a, dict)]

    categories = [{"title": c.get("title"), "href": _abs_url(c.get("href"))}
                  for c in (data.get("categories") or []) if isinstance(c, dict)]
    breadcrumbs = [_clean({"title": b.get("title"), "href": _abs_url(b.get("href"))})
                   for b in (brand.get("breadcrumbs") or []) if isinstance(b, dict)]

    price = None
    if best_offer:
        price = {
            "toman": best_offer.get("price_toman"),
            "rial": best_offer.get("price_rial"),
            "display": best_offer.get("price_display"),
            "original_toman": best_offer.get("original_price_toman"),
            "discount_percent": best_offer.get("discount_percent"),
            "currency": "IRT",
        }
    elif p["ld_rial"]:
        # Only the JSON-LD knew a price, and it is expressed in Rial.
        price = price_block(rial_to_toman(p["ld_rial"]))

    available = bool(best_offer and best_offer.get("in_stock"))
    if not best_offer and p["availability"]:
        available = "InStock" in p["availability"]

    _ = (content, page, ld, variants, all_offers, state, categories)
    return _assemble_product(
        p, variants=variants, all_offers=all_offers, best_offer=best_offer,
        price=price, available=available, attributes=attributes,
        featured=featured, categories=categories, breadcrumbs=breadcrumbs,
    )
def _assemble_product(p, *, variants, all_offers, best_offer, price,
                      available, attributes, featured, categories, breadcrumbs):
    data, content, brand, page, ld = p["data"], p["content"], p["brand"], p["page"], p["ld"]
    state = data.get("state") or {}
    slug = p["slug"]
    out = {
        "product_id": data.get("id"),
        "slug": slug,
        "url": f"{WEB_BASE_URL}/product/{slug}" if slug else None,
        "name": (content.get("title_fa") or "").strip() or None,
        "name_en": (content.get("title_en") or "").strip() or None,
        "description": (content.get("description") or "").strip() or None,
        "short_description": (content.get("meta_description") or "").strip() or None,
        "sku": _num(ld.get("sku")),
        "mpn": _num(ld.get("mpn")),
        "brand": _clean({
            "name": brand.get("title_fa"),
            "name_en": brand.get("title_en"),
            "logo": (brand.get("logo") or {}).get("src"),
            "website": brand.get("website"),
            "breadcrumbs": breadcrumbs or None,
        }) or None,
        "categories": categories or None,
        "category_url": ld.get("category") or (categories[-1]["href"] if categories else None),
        "price": price,
        "available": available,
        "availability": p["availability"] or None,
        "condition": p["offers_ld"].get("itemCondition"),
        "price_valid_until": p["offers_ld"].get("priceValidUntil"),
        "rating": _clean({
            "value": state.get("star_rate"),
            "count": state.get("rate_count"),
            "comments": state.get("comments_count"),
            "total_purchasers": state.get("total_purchasers"),
        }) or None,
        "images": p["images"] or None,
        "colors": p["colors"] or None,
        "configurable_attributes": p["attributes_config"] or None,
        "variants": variants or None,
        "offers": sorted(all_offers, key=lambda o: (o.get("price_toman") is None, o.get("price_toman") or 0)) or None,
        "best_offer": best_offer,
        "attributes": attributes or None,
        "featured_attributes": featured or None,
        "warranties": [_clean({"id": w.get("id"), "name": w.get("name"), "company": w.get("company_title"), "duration": w.get("duration")}) for w in (data.get("warranties") or []) if isinstance(w, dict)] or None,
        "sellers": [_clean({"id": v.get("id"), "name": v.get("title"), "name_en": v.get("title_en") or None, "url": _abs_url(v.get("href"))}) for v in (data.get("vendors") or []) if isinstance(v, dict)] or None,
        "installment": data.get("snapp_pay_installment"),
        "warning": data.get("warning_description") or None,
        "is_active": not bool(page.get("is_deactive")),
        "meta": _clean({"title": page.get("title"), "description": page.get("description"), "canonical_url": page.get("canonical_url"), "keywords": page.get("keywords"), "no_index": page.get("no_index"), "status_code": page.get("status_code")}) or None,
    }
    return _clean(out)


def _walk_categories(nodes, depth=0, parent=None, out=None):
    out = out if out is not None else []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        href = node.get("href") or ""
        entry = _clean({
            "id": node.get("id"), "title": node.get("title"),
            "slug": (_slug_from_href(href) if "/category/" in href else None),
            "href": href or None, "url": _abs_url(href),
            "icon": node.get("icon"), "depth": depth, "parent": parent,
            "has_children": bool(node.get("children")),
        })
        out.append(entry)
        children = node.get("children")
        if children:
            _walk_categories(children, depth + 1, node.get("title"), out)
    return out


def _prune_depth(node, max_depth, depth=0):
    out = _clean({
        "id": node.get("id"), "title": node.get("title"),
        "href": node.get("href"), "url": _abs_url(node.get("href")),
        "slug": (_slug_from_href(node.get("href")) if "/category/" in (node.get("href") or "") else None),
        "icon": node.get("icon"),
    })
    children = node.get("children")
    if children and depth < max_depth:
        out["children"] = [_prune_depth(c, max_depth, depth + 1) for c in children if isinstance(c, dict)]
    elif children:
        out["child_count"] = len(children)
    return out


def normalize_categories(payload, *, flat=False, max_depth=3):
    data = (payload or {}).get("data") or {}
    menus = data.get("menus") or []
    tree = []
    for column in menus:
        for root in column or []:
            if isinstance(root, dict):
                tree.append(_prune_depth(root, max_depth))
    if flat:
        flat_list = _walk_categories(tree)
        return {"count": len(flat_list), "categories": flat_list}
    return {"count": len(tree), "columns": len(menus), "categories": tree, "flat": _walk_categories(tree)}
