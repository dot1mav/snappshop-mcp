"""
test_parsers.py — Offline pytest tests using recorded API fixtures.

All tests use the JSON files in ``fixtures/`` (captured live responses from
``apix.snappshop.ir`` on 2026-09-19). No network calls are made.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
sys.path.insert(0, str(FIXTURES.parent))

from snappshop.normalize import (
    normalize_card,
    normalize_categories,
    normalize_product,
    normalize_search,
)
from snappshop.units import (
    IR_TOMAN_PER_RIAL,
    format_toman,
    price_block,
    rial_to_toman,
    toman_to_rial,
)
from snappshop.api import parse_product_ref


# ── fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def search_raw():
    return json.loads((FIXTURES / "search.json").read_text("utf-8"))


@pytest.fixture
def product_raw():
    return json.loads((FIXTURES / "product.json").read_text("utf-8"))


@pytest.fixture
def megamenu_raw():
    return json.loads((FIXTURES / "megamenu.json").read_text("utf-8"))


# ── units ────────────────────────────────────────────────────────────────
class TestUnits:
    def test_rial_to_toman(self):
        assert rial_to_toman(339800000) == 33980000
        assert rial_to_toman(0) == 0
        assert rial_to_toman(None) is None

    def test_toman_to_rial(self):
        assert toman_to_rial(33980000) == 339800000
        assert toman_to_rial(None) is None

    def test_format_toman(self):
        assert format_toman(33980000) == "33,980,000 \u062a\u0648\u0645\u0627\u0646"
        assert format_toman(None) is None

    def test_price_block_full(self):
        p = price_block(33980000, 49000000, 31)
        assert p["toman"] == 33980000
        assert p["rial"] == 339800000
        assert p["display"]
        assert p["original_toman"] == 49000000
        assert p["discount_percent"] == 31
        assert p["currency"] == "IRT"

    def test_price_block_no_discount(self):
        p = price_block(1000000)
        assert p["toman"] == 1000000
        assert p["original_toman"] is None
        assert p["discount_percent"] is None


# ── parse_product_ref ────────────────────────────────────────────────────
class TestParseRef:
    def test_slug(self):
        assert parse_product_ref("snp-25751584") == "25751584"

    def test_numeric(self):
        assert parse_product_ref("25751584") == "25751584"

    def test_url(self):
        assert parse_product_ref("https://snappshop.ir/product/snp-25751584") == "25751584"

    def test_path(self):
        assert parse_product_ref("/product/snp-9999/foo") == "9999"

    def test_bare_digits(self):
        assert parse_product_ref("  42  ") == "42"

    def test_invalid_raises(self):
        from snappshop.api import SnappError
        with pytest.raises(SnappError):
            parse_product_ref("not-a-product")


# ── normalize_search ─────────────────────────────────────────────────────
class TestNormalizeSearch:
    def test_basic_shape(self, search_raw):
        r = normalize_search(search_raw, query="test", limit=5)
        assert r["query"] == "test"
        assert r["count"] == 5
        assert r["total_unique_products"] == 12
        assert len(r["products"]) == 5

    def test_pagination(self, search_raw):
        r = normalize_search(search_raw, limit=10)
        pag = r["pagination"]
        assert pag["current_page"] == 0
        assert pag["per_page"] == 12
        assert pag["total_pages"] > 0

    def test_sort_options(self, search_raw):
        r = normalize_search(search_raw, limit=3)
        assert len(r["sort_options"]) >= 4
        assert r["sort_options"][0]["is_selected"]

    def test_filters_present(self, search_raw):
        r = normalize_search(search_raw, limit=3)
        assert r["filters"]
        assert len(r["filters"]) >= 5

    def test_suggested_keywords(self, search_raw):
        r = normalize_search(search_raw, limit=3)
        assert r["suggested_keywords"]
        assert len(r["suggested_keywords"]) >= 3

    def test_card_shape(self, search_raw):
        r = normalize_search(search_raw, limit=1)
        c = r["products"][0]
        assert c["slug"].startswith("snp-")
        assert c["product_url"].startswith("https://snappshop.ir/")
        assert c["title"]
        assert c["image_url"]
        assert c["price"]["toman"] > 0
        assert c["price"]["rial"] == c["price"]["toman"] * IR_TOMAN_PER_RIAL

    def test_colors_in_card(self, search_raw):
        r = normalize_search(search_raw, limit=3)
        colored = [c for c in r["products"] if c.get("colors")]
        assert colored
        assert colored[0]["colors"][0]["title"]

    def test_badges(self, search_raw):
        r = normalize_search(search_raw, limit=5)
        badged = [c for c in r["products"] if c.get("badges")]
        assert badged


# ── normalize_product ────────────────────────────────────────────────────
class TestNormalizeProduct:
    def test_basic_fields(self, product_raw):
        p = normalize_product(product_raw, slug="snp-25751584")
        assert p["slug"] == "snp-25751584"
        assert p["name"]
        assert p["name_en"]
        assert p["brand"]["name"]
        assert p["brand"]["name_en"]

    def test_price_toman(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert p["price"]["toman"] == 33980000
        assert p["price"]["rial"] == 339800000
        assert "33" in p["price"]["display"]

    def test_images_from_jsonld(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert len(p["images"]) >= 15

    def test_colors(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        titles = [c["title"] for c in p.get("colors", [])]
        assert "\u0645\u0634\u06a9\u06cc" in titles  # مشکی
        assert len(titles) == 3

    def test_variants_and_offers(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert p["variants"]
        assert p["offers"]
        assert len(p["offers"]) >= 3
        first_offer = p["offers"][0]
        assert first_offer["price_toman"]
        assert first_offer["vendor_id"]

    def test_best_offer(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        bo = p["best_offer"]
        assert bo["price_toman"] > 0
        assert bo["vendor_name"]
        assert bo["warranty"]

    def test_availability(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert p["available"] is True

    def test_attributes(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert len(p["attributes"]) >= 10
        assert any("cpu" in a.get("title", "").lower() or "\u062a\u0631\u0627\u0634\u0647" in a.get("title", "")
                    for a in p["attributes"])

    def test_warranties(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert p["warranties"]
        assert p["warranties"][0]["name"]

    def test_sellers(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert p["sellers"]
        assert len(p["sellers"]) >= 2

    def test_categories(self, product_raw):
        p = normalize_product(product_raw, product_id="25751584")
        assert p["categories"]
        assert p["category_url"]


# ── normalize_categories ─────────────────────────────────────────────────
class TestNormalizeCategories:
    def test_flat(self, megamenu_raw):
        r = normalize_categories(megamenu_raw, flat=True)
        assert r["count"] >= 100
        # depth-1 node: top-level category
        top = [c for c in r["categories"] if c.get("depth") == 1]
        assert len(top) >= 10
        assert any(c["title"] == "\u0645\u0648\u0628\u0627\u06cc\u0644" for c in top)

    def test_tree(self, megamenu_raw):
        r = normalize_categories(megamenu_raw, max_depth=2)
        assert r["count"] >= 10
        # top-level nodes have children
        top = r["categories"][0]
        assert "children" in top
        assert len(top["children"]) >= 5

    def test_max_depth_prune(self, megamenu_raw):
        r = normalize_categories(megamenu_raw, max_depth=1)
        top = r["categories"][0]
        assert "children" in top
        assert "child_count" in top["children"][0]

    def test_slugs(self, megamenu_raw):
        r = normalize_categories(megamenu_raw, flat=True)
        slugged = [c for c in r["categories"] if c.get("slug")]
        assert slugged
        assert slugged[0]["url"]
