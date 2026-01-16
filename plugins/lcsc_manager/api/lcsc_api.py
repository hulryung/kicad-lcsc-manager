"""
LCSC/EasyEDA API Client

This module provides functions to search and fetch component data from LCSC/EasyEDA.
Note: These APIs are not officially documented and were reverse-engineered.
"""
import requests
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger()


class LCSCAPIError(Exception):
    """Exception raised for LCSC API errors"""
    pass


class LCSCAPIClient:
    """Client for interacting with LCSC/EasyEDA APIs"""

    # API Endpoints
    JLCPCB_SEARCH_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
    EASYEDA_COMPONENT_URL = "https://easyeda.com/api/components/{uid}"
    EASYEDA_SEARCH_URL = "https://easyeda.com/api/components/search"

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 30
    REQUEST_DELAY = 2.0  # seconds between requests

    def __init__(self):
        """Initialize LCSC API client"""
        self.config = get_config()
        self.session = requests.Session()
        # Use realistic browser headers to avoid API blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://jlcpcb.com/',
            'Origin': 'https://jlcpcb.com',
        })
        self.last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting to avoid hitting API limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.REQUEST_DELAY:
            sleep_time = self.REQUEST_DELAY - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict:
        """
        Make HTTP request with error handling and rate limiting

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Query parameters
            json_data: JSON request body
            timeout: Request timeout in seconds

        Returns:
            Response JSON data

        Raises:
            LCSCAPIError: If request fails
        """
        self._rate_limit()

        if timeout is None:
            timeout = self.config.get("api_timeout", 30)

        try:
            logger.debug(f"{method} {url} params={params}")

            # Add Content-Type for POST requests with JSON data
            headers = {}
            if method.upper() == "POST" and json_data:
                headers['Content-Type'] = 'application/json;charset=UTF-8'

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=timeout
            )

            response.raise_for_status()

            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise LCSCAPIError(f"API request failed: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise LCSCAPIError(f"Network error: {e}")
        except ValueError as e:
            logger.error(f"JSON decode error: {e}")
            raise LCSCAPIError(f"Invalid API response: {e}")

    def _get_jlcpcb_info(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get stock and price information from JLCPCB API

        Args:
            lcsc_id: LCSC part number (e.g., "C2040")

        Returns:
            Dictionary with stock, price, and datasheet info or None if not found
        """
        try:
            logger.info(f"Fetching JLCPCB stock/price info for: {lcsc_id}")

            response = self._make_request(
                method="POST",
                url=self.JLCPCB_SEARCH_URL,
                json_data={"keyword": lcsc_id}
            )

            if response.get("code") != 200:
                logger.warning(f"JLCPCB API returned code: {response.get('code')}")
                return None

            # Extract component list
            components = response.get("data", {}).get("componentPageInfo", {}).get("list", [])

            if not components:
                logger.warning(f"No components found in JLCPCB API")
                return None

            # Find exact match
            component = None
            for c in components:
                if c.get("componentCode") == lcsc_id:
                    component = c
                    break

            if not component:
                logger.warning(f"Exact match not found in JLCPCB API")
                return None

            # Extract stock and price info
            stock = component.get("stockCount", 0)
            price_list = component.get("componentPrices", [])

            # Parse prices
            prices = []
            if price_list:
                sorted_prices = sorted(price_list, key=lambda p: p.get("startNumber", 0))
                for price_tier in sorted_prices:
                    start_qty = price_tier.get("startNumber", 0)
                    end_qty = price_tier.get("endNumber", -1)
                    price = price_tier.get("productPrice", 0)

                    prices.append({
                        "qty": start_qty,
                        "qty_max": None if end_qty == -1 else end_qty,
                        "price": price
                    })

            jlcpcb_info = {
                "stock": stock,
                "price": prices,
                "datasheet": component.get("dataManualUrl", ""),
                "image": component.get("minImageAccessId", ""),
                "url": component.get("lcscGoodsUrl", f"https://www.lcsc.com/product-detail/{lcsc_id}.html"),
                # May have better description
                "jlcpcb_description": component.get("describe", ""),
            }

            logger.info(f"JLCPCB info: stock={stock}, prices={len(prices)} tiers")
            return jlcpcb_info

        except Exception as e:
            logger.warning(f"Failed to fetch JLCPCB info: {e}")
            return None

    def search_component(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        """
        Search for a component by LCSC part number using EasyEDA and JLCPCB APIs

        Args:
            lcsc_id: LCSC part number (e.g., "C2040")

        Returns:
            Component data dictionary or None if not found

        Raises:
            LCSCAPIError: If search fails
        """
        logger.info(f"Searching for component: {lcsc_id}")

        try:
            # Step 1: Get EasyEDA data (for symbol/footprint)
            url = f"https://easyeda.com/api/products/{lcsc_id}/components"

            response = self._make_request(
                method="GET",
                url=url,
                params={"version": "6.4.19.5"}
            )

            # Parse response
            if not response.get("success"):
                logger.warning(f"Component not found in EasyEDA: {lcsc_id}")
                return None

            result = response.get("result", {})
            if not result:
                logger.warning(f"Empty result from EasyEDA: {lcsc_id}")
                return None

            logger.info(f"Found component in EasyEDA: {lcsc_id}")

            # Extract symbol and footprint UUIDs
            symbol_uuid = result.get("uuid")
            footprint_uuid = None
            if "packageDetail" in result:
                footprint_uuid = result["packageDetail"].get("uuid")

            # Extract component parameters from dataStr
            c_para = {}
            if "dataStr" in result and "head" in result["dataStr"]:
                c_para = result["dataStr"]["head"].get("c_para", {})

            # Extract LCSC info
            lcsc_info = result.get("lcsc", {})

            # Create component info with EasyEDA data
            component_data = {
                "lcsc_id": lcsc_info.get("number", lcsc_id),
                "name": c_para.get("name", result.get("title", lcsc_id)),
                "description": result.get("description") or c_para.get("name", ""),
                "manufacturer": c_para.get("Manufacturer", "Unknown"),
                "manufacturer_part": c_para.get("Manufacturer Part", ""),
                "package": c_para.get("package", "Unknown"),
                "prefix": c_para.get("pre", "U"),
                "jlcpcb_class": c_para.get("JLCPCB Part Class", ""),
                "price": [],
                "stock": 0,
                "datasheet": "",
                "image": result.get("thumb", ""),
                "url": "",
                "category": "Electronic Component",
                "subcategory": "",
                "symbol_uuid": symbol_uuid,
                "footprint_uuid": footprint_uuid,
                "smt": result.get("SMT", False),
                "easyeda_data": result,
            }

            # Step 2: Get JLCPCB data (for stock/price)
            jlcpcb_info = self._get_jlcpcb_info(lcsc_id)
            if jlcpcb_info:
                # Merge JLCPCB data
                component_data["stock"] = jlcpcb_info.get("stock", 0)
                component_data["price"] = jlcpcb_info.get("price", [])
                component_data["datasheet"] = jlcpcb_info.get("datasheet", "")
                component_data["url"] = jlcpcb_info.get("url", "")

                # Use JLCPCB description if EasyEDA description is empty
                if not component_data["description"] and jlcpcb_info.get("jlcpcb_description"):
                    component_data["description"] = jlcpcb_info["jlcpcb_description"]

                # Update image if JLCPCB has one
                if jlcpcb_info.get("image"):
                    image_id = jlcpcb_info["image"]
                    component_data["image"] = f"https://assets.jlcpcb.com/attachments/{image_id}"

            logger.info(f"Component complete: {component_data['name']} by {component_data['manufacturer']}, stock={component_data['stock']}")
            return component_data

        except Exception as e:
            logger.error(f"Search failed for {lcsc_id}: {e}")
            raise LCSCAPIError(f"Search failed: {e}")

    def _get_component_details_from_uuid(self, component_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed component information from EasyEDA using component UUID

        Args:
            component_uuid: EasyEDA component UUID

        Returns:
            Dictionary with detailed component info or None
        """
        try:
            url = f"https://easyeda.com/api/components/{component_uuid}"

            response = self._make_request(method="GET", url=url, params=None)

            if response.get("success"):
                result = response.get("result", {})

                # Extract component details
                title = result.get("title", "")
                dataStr = result.get("dataStr", {})
                head = dataStr.get("head", {})
                c_para = head.get("c_para", {})

                # Get package info (try multiple fields)
                package = c_para.get("package") or \
                         result.get("packageDetail", {}).get("package") or \
                         c_para.get("pre", {}).get("package", "Unknown")

                manufacturer = c_para.get("Manufacturer", "Unknown")
                datasheet = c_para.get("link", "")

                # Build detailed info
                detail_data = {
                    "name": title or "Unknown",
                    "manufacturer": manufacturer,
                    "package": package,
                    "datasheet": datasheet,
                }

                # Try to extract description
                if c_para.get("Supplier Part"):
                    detail_data["description"] = f"{title} - {c_para.get('Supplier Part')}"
                else:
                    detail_data["description"] = title or "Electronic Component"

                return detail_data

            return None

        except Exception as e:
            logger.error(f"Failed to get component details from UUID {component_uuid}: {e}")
            return None

    def _parse_lcsc_component(self, product: Dict) -> Dict[str, Any]:
        """
        Parse LCSC product data into standardized format

        Args:
            product: Raw product data from LCSC API

        Returns:
            Standardized component data
        """
        return {
            "lcsc_id": product.get("productCode"),
            "name": product.get("productModel"),
            "description": product.get("productIntroEn") or product.get("productDescEn", ""),
            "manufacturer": product.get("brandNameEn"),
            "package": product.get("encapStandard"),
            "price": product.get("productPriceList", []),
            "stock": product.get("stockNumber", 0),
            "datasheet": product.get("pdfUrl"),
            "image": product.get("productImage"),
            "category": product.get("parentCatalogName"),
            "subcategory": product.get("catalogName"),
            # EasyEDA specific fields (if available)
            "easyeda_uuid": product.get("uuid"),
        }

    def get_easyeda_component(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get component data from EasyEDA by UUID

        Args:
            uuid: EasyEDA component UUID

        Returns:
            Component data with symbol, footprint, and 3D model info

        Raises:
            LCSCAPIError: If request fails
        """
        logger.info(f"Fetching EasyEDA component: {uuid}")

        try:
            url = self.EASYEDA_COMPONENT_URL.format(uid=uuid)
            response = self._make_request(method="GET", url=url)

            if response.get("success"):
                return response.get("result")

            logger.warning(f"EasyEDA component not found: {uuid}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch EasyEDA component {uuid}: {e}")
            raise LCSCAPIError(f"EasyEDA fetch failed: {e}")

    def advanced_search(
        self,
        component_name: str = "",
        value: str = "",
        package: str = "",
        manufacturer: str = "",
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Advanced component search with multiple parameters

        Args:
            component_name: Component name or description
            value: Component value (e.g., "10uF", "10k")
            package: Package size (e.g., "0603", "SOT23")
            manufacturer: Manufacturer name
            page: Page number (default: 1)

        Returns:
            List of component data dictionaries

        Raises:
            LCSCAPIError: If search fails
        """
        # Build query string from non-empty parameters
        query_parts = []
        if component_name:
            query_parts.append(component_name)
        if value:
            query_parts.append(value)
        if package:
            query_parts.append(package)
        if manufacturer:
            query_parts.append(manufacturer)

        if not query_parts:
            logger.warning("Advanced search called with no parameters")
            return []

        # Join parts with spaces
        query = " ".join(query_parts)
        logger.info(f"Advanced search query: {query}")

        # Use existing search_easyeda method
        return self.search_easyeda(query, page)

    def search_easyeda(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        Search for components on EasyEDA

        Args:
            query: Search query
            page: Page number (default: 1)

        Returns:
            List of component data dictionaries

        Raises:
            LCSCAPIError: If search fails
        """
        logger.info(f"Searching EasyEDA: {query}, page {page}")

        try:
            response = self._make_request(
                method="GET",
                url=self.EASYEDA_SEARCH_URL,
                params={
                    "keyword": query,
                    "page": page
                }
            )

            if response.get("success"):
                return response.get("result", [])

            return []

        except Exception as e:
            logger.error(f"EasyEDA search failed for '{query}': {e}")
            raise LCSCAPIError(f"EasyEDA search failed: {e}")

    def download_file(self, url: str, output_path: Path) -> bool:
        """
        Download a file from URL to local path

        Args:
            url: File URL
            output_path: Local file path to save to

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Downloading: {url} -> {output_path}")

        try:
            self._rate_limit()

            timeout = self.config.get("download_timeout", 60)
            response = self.session.get(url, timeout=timeout, stream=True)
            response.raise_for_status()

            # Create parent directory if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded successfully: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    def get_component_complete(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete component data including symbol, footprint, and 3D model info

        Args:
            lcsc_id: LCSC part number

        Returns:
            Complete component data or None if not found

        Raises:
            LCSCAPIError: If fetch fails
        """
        logger.info(f"Fetching complete data for: {lcsc_id}")

        # Get basic component info from EasyEDA
        component = self.search_component(lcsc_id)
        if not component:
            return None

        # The EasyEDA data is already included in the component from search_component
        # No need to modify it - it already contains the full API response
        return component


# Singleton instance
_api_client: Optional[LCSCAPIClient] = None


def get_api_client() -> LCSCAPIClient:
    """
    Get global API client instance

    Returns:
        LCSCAPIClient instance
    """
    global _api_client
    if _api_client is None:
        _api_client = LCSCAPIClient()
    return _api_client
