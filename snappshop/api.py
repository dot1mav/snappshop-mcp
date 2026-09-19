"""
snappshop/api.py
----------------
Transport layer for interacting with the SnappShop JSON API.
Supports automatic fallback to proxy mode if configured.
"""
import requests
from typing import Any, Dict, Optional

class SnappError(Exception):
    """Custom exception for SnappShop API errors."""
    pass

class SnappAPI:
    def __init__(self, proxy_url: Optional[str] = None):
        self.base_url = "https://apix.snappshop.ir"
        self.geo = "?lat=35.77331&lng=51.418591"
        self.proxy_url = proxy_url

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Internal helper to handle HTTP requests and proxy logic."""
        url = f"{self.base_url}{endpoint}{self.geo}"
        
        if self.proxy_url:
            # Route request through the ArvanCloud/Worker proxy
            proxy_url = f"{self.proxy_url}/api{endpoint}"
            # In a real proxy, we would forward the method and body
            resp = requests.request(method, proxy_url, **kwargs)
        else:
            resp = requests.request(method, url, **kwargs)

        if resp.status_code != 200:
            raise SnappError(f"API Error {resp.status_code}: {resp.text}")
        
        return resp.json()

    def search(self, query: str) -> Dict[str, Any]:
        """Fetch search results from /search/v1."""
        return self._request("POST", "/search/v1", json={
            "query": query,
            "render": 4
        })

    def get_product(self, product_id: str) -> Dict[str, Any]:
        """Fetch product details from /products/v2/{id}."""
        return self._request("GET", f"/products/v2/{product_id}")

    def get_categories(self) -> Dict[str, Any]:
        """Fetch the megamenu from /landing/v1/megamenu."""
        return self._request("GET", "/landing/v1/megamenu")
