"""
snappshop/units.py
------------------
Handles currency conversion and formatting for the SnappShop ecosystem.
Crucial for preventing 10x pricing errors between API (Toman) and JSON-LD (Rial).
"""
from typing import Optional

# Constant: 1 Toman = 10 Rial
IR_TOMAN_PER_RIAL = 10

def rial_to_toman(rial: Optional[float]) -> Optional[float]:
    """Convert Rial to Toman by dividing by 10."""
    if rial is None: return None
    return round(rial / IR_TOMAN_PER_RIAL)

def toman_to_rial(toman: Optional[float]) -> Optional[float]:
    """Convert Toman to Rial by multiplying by 10."""
    if toman is None: return None
    return round(toman * IR_TOMAN_PER_RIAL)

def format_toman(toman: Optional[float]) -> Optional[str]:
    """
    Formats a numeric Toman value into a human-readable Persian string.
    Example: 34000000 -> '34,000,000 تومان'
    """
    if toman is None: return None
    return f"{toman:,.0f} تومان"

def price_block(
    toman: Optional[float], 
    original_toman: Optional[float] = None, 
    discount_percent: Optional[float] = None
) -> dict:
    """
    Creates a standardized price dictionary used across the MCP server.
    This ensures that both Python and JS runtimes output the same shape.
    """
    return {
        "toman": toman,
        "rial": toman_to_rial(toman),
        "display": format_toman(toman),
        "original_toman": original_toman,
        "original_rial": toman_to_rial(original_toman),
        "original_display": format_toman(original_toman),
        "discount_percent": discount_percent,
        "currency": "IRT",
    }
