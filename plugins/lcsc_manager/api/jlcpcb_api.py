"""
JLCPCB API Client

This module provides functions to interact with the official JLCPCB Components API.
API Documentation: https://api.jlcpcb.com/
"""
import requests
import time
from typing import Dict, List, Optional, Any
from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger()


class JLCPCBAPIError(Exception):
    """Exception raised for JLCPCB API errors"""
    pass


class JLCPCBAPIClient:
    """Client for interacting with JLCPCB Components API"""

    # API Base URL (official API)
    BASE_URL = "https://api.jlcpcb.com"
    COMPONENTS_URL = f"{BASE_URL}/components/v1"

    # Rate limiting
    REQUEST_DELAY = 1.0  # seconds between requests

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize JLCPCB API client

        Args:
            api_key: JLCPCB API key (optional for basic queries)
        """
        self.config = get_config()
        self.api_key = api_key or self.config.get("jlcpcb_api_key")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KiCad-LCSC-Manager/0.1.0',
            'Accept': 'application/json',
        })

        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'

        self.last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.REQUEST_DELAY:
            sleep_time = self.REQUEST_DELAY - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict:
        """
        Make HTTP request to JLCPCB API

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            timeout: Request timeout

        Returns:
            Response JSON data

        Raises:
            JLCPCBAPIError: If request fails
        """
        self._rate_limit()

        if timeout is None:
            timeout = self.config.get("api_timeout", 30)

        url = f"{self.COMPONENTS_URL}/{endpoint.lstrip('/')}"

        try:
            logger.debug(f"{method} {url} params={params}")

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=timeout
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            if e.response.status_code == 401:
                raise JLCPCBAPIError("Authentication failed. Check your API key.")
            elif e.response.status_code == 429:
                raise JLCPCBAPIError("Rate limit exceeded. Please wait and try again.")
            raise JLCPCBAPIError(f"API request failed: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise JLCPCBAPIError(f"Network error: {e}")
        except ValueError as e:
            logger.error(f"JSON decode error: {e}")
            raise JLCPCBAPIError(f"Invalid API response: {e}")

    def search_components(
        self,
        keyword: str,
        category: Optional[str] = None,
        in_stock: bool = True,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Search for components

        Args:
            keyword: Search keyword (part number, description, etc.)
            category: Component category filter
            in_stock: Only show in-stock components
            page: Page number
            page_size: Results per page

        Returns:
            Search results with component list and pagination info

        Raises:
            JLCPCBAPIError: If search fails
        """
        logger.info(f"Searching JLCPCB: {keyword}")

        params = {
            "keyword": keyword,
            "page": page,
            "pageSize": page_size,
        }

        if category:
            params["category"] = category

        if in_stock:
            params["inStock"] = "true"

        try:
            response = self._make_request("GET", "search", params=params)
            return response
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def get_component(self, component_code: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed component information

        Args:
            component_code: JLCPCB component code (e.g., "C2040")

        Returns:
            Component details or None if not found

        Raises:
            JLCPCBAPIError: If request fails
        """
        logger.info(f"Fetching component: {component_code}")

        try:
            response = self._make_request("GET", f"component/{component_code}")

            if response.get("success"):
                return response.get("data")

            logger.warning(f"Component not found: {component_code}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch component: {e}")
            raise

    def get_pricing(self, component_code: str) -> List[Dict[str, Any]]:
        """
        Get component pricing tiers

        Args:
            component_code: JLCPCB component code

        Returns:
            List of pricing tiers

        Raises:
            JLCPCBAPIError: If request fails
        """
        logger.info(f"Fetching pricing for: {component_code}")

        try:
            response = self._make_request("GET", f"component/{component_code}/pricing")

            if response.get("success"):
                return response.get("data", [])

            return []

        except Exception as e:
            logger.error(f"Failed to fetch pricing: {e}")
            raise

    def get_inventory(self, component_code: str) -> Optional[int]:
        """
        Get component inventory/stock level

        Args:
            component_code: JLCPCB component code

        Returns:
            Stock quantity or None if unavailable

        Raises:
            JLCPCBAPIError: If request fails
        """
        logger.info(f"Fetching inventory for: {component_code}")

        try:
            response = self._make_request("GET", f"component/{component_code}/inventory")

            if response.get("success"):
                data = response.get("data", {})
                return data.get("stock")

            return None

        except Exception as e:
            logger.error(f"Failed to fetch inventory: {e}")
            raise

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get list of component categories

        Returns:
            List of categories

        Raises:
            JLCPCBAPIError: If request fails
        """
        logger.info("Fetching component categories")

        try:
            response = self._make_request("GET", "categories")

            if response.get("success"):
                return response.get("data", [])

            return []

        except Exception as e:
            logger.error(f"Failed to fetch categories: {e}")
            raise


# Singleton instance
_jlcpcb_client: Optional[JLCPCBAPIClient] = None


def get_jlcpcb_client(api_key: Optional[str] = None) -> JLCPCBAPIClient:
    """
    Get global JLCPCB API client instance

    Args:
        api_key: Optional API key (uses cached client if already initialized)

    Returns:
        JLCPCBAPIClient instance
    """
    global _jlcpcb_client
    if _jlcpcb_client is None:
        _jlcpcb_client = JLCPCBAPIClient(api_key=api_key)
    return _jlcpcb_client
