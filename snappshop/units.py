"""
units.py — currency helpers.

SnappShop is inconsistent between its two public surfaces, and getting this
wrong is the single easiest way to report a price that is 10x off:

  * Public JSON API (`apix.snappshop.ir`) returns **Toman**.
        /products/v2/25751584  ->  special_price: 33980000
  * The schema.org JSON-LD embedded on the same PDP returns **Rial**.
        page.json_ld[0].offers.price -> 339800000

1 Toman == 10 Rial (the Rial is the official currency, the Toman is what
people and shops actually quote). This module keeps both, explicitly, so no
caller ever has to guess which one it is holding.
"""
from __future__ import annotations

# 1 Toman = 10 Rial
IR_TOMAN_PER_RIAL = 10


def rial_to_toman(rial) -> int | None:
    """39999999... Rial -> Toman. Rounds to the nearest Toman."""
    if rial is None:
        return None
    try:
        return int(round(int(rial) / IR_TOMAN_PER_RIAL))
    except (TypeError, ValueError):
        return None


def toman_to_rial(toman) -> int | None:
    """Toman -> Rial."""
    if toman is None:
        return None
    try:
        return int(toman) * IR_TOMAN_PER_RIAL
    except (TypeError, ValueError):
        return None


def format_rial(rial) -> str | None:
    """Human readable, e.g. 339800000 -> '33,980,000 تومان'."""
    if rial is None:
        return None
    t = rial_to_toman(rial)
    if t is None:
        return None
    return f"{t:,} تومان"


def format_toman(toman) -> str | None:
    """Human readable Toman, e.g. 33980000 -> '33,980,000 تومان'."""
    if toman is None:
        return None
    try:
        return f"{int(toman):,} تومان"
    except (TypeError, ValueError):
        return None


def price_block(toman, original_toman=None, discount_percent=None) -> dict:
    """Build the canonical `price` object used in every normalized payload.

    Always exposes both units plus a display string, so an LLM reading the
    tool output cannot mis-scale the number.
    """
    t = None if toman is None else int(toman)
    o = None if original_toman in (None, 0) else int(original_toman)
    return {
        "toman": t,
        "rial": toman_to_rial(t),
        "display": format_toman(t),
        "original_toman": o,
        "original_rial": toman_to_rial(o),
        "original_display": format_toman(o),
        "discount_percent": discount_percent,
        "currency": "IRT",
        "currency_note": "toman is authoritative; rial = toman * 10",
    }