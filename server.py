"""
server.py
----------
The main MCP Server entry point. 
Compatible with FastMCP (1.x) and standard MCPServer (2.x) patterns.
"""
from textutil import enable_utf8_stdout
enable_utf8_stdout()

from mcp.server.fastmcp import FastMCP
from snappshop.api import SnappAPI
from snappshop.normalize import normalize_search, normalize_product

# Initialize FastMCP server
mcp = FastMCP("SnappShop")
api = SnappAPI()

@mcp.tool()
def search_products(query: str, limit: int = 10) -> str:
    """
    Search for products on SnappShop.ir.
    Returns a list of products with prices, ratings, and URLs.
    """
    try:
        raw_data = api.search(query)
        result = normalize_search(raw_data, query, limit)
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error searching products: {str(e)}"

@mcp.tool()
def get_product(product_id: str) -> str:
    """
    Get detailed specifications for a product using its ID.
    Returns technical attributes, images, and the best available price.
    """
    try:
        raw_data = api.get_product(product_id)
        result = normalize_product(raw_data, product_id)
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching product: {str(e)}"

if __name__ == "__main__":
    mcp.run()
