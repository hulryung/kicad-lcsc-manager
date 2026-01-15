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

    # API Endpoints (reverse-engineered)
    LCSC_SEARCH_URL = "https://lcsc.com/api/products/search"
    EASYEDA_COMPONENT_URL = "https://easyeda.com/api/components/{uid}"
    EASYEDA_SEARCH_URL = "https://easyeda.com/api/components/search"

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 30
    REQUEST_DELAY = 2.0  # seconds between requests

    def __init__(self):
        """Initialize LCSC API client"""
        self.config = get_config()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KiCad-LCSC-Manager/0.1.0',
            'Accept': 'application/json',
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
            raise LCSCAPIError(f"API request failed: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise LCSCAPIError(f"Network error: {e}")
        except ValueError as e:
            logger.error(f"JSON decode error: {e}")
            raise LCSCAPIError(f"Invalid API response: {e}")

    def search_component(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        """
        Search for a component by LCSC part number using EasyEDA API

        Args:
            lcsc_id: LCSC part number (e.g., "C2040")

        Returns:
            Component data dictionary or None if not found

        Raises:
            LCSCAPIError: If search fails
        """
        logger.info(f"Searching for component: {lcsc_id}")

        try:
            # Use EasyEDA API (same as JLC2KiCad_lib)
            url = f"https://easyeda.com/api/products/{lcsc_id}/svgs"

            response = self._make_request(
                method="GET",
                url=url,
                params=None
            )

            # Parse response
            if response.get("success"):
                result = response.get("result", [])
                if result:
                    logger.info(f"Found component: {lcsc_id}")

                    # Get component UUIDs
                    symbol_uuids = [item.get("component_uuid") for item in result[:-1]]
                    footprint_uuid = result[-1].get("component_uuid") if result else None

                    # Create basic component info
                    component_data = {
                        "lcsc_id": lcsc_id,
                        "name": lcsc_id,  # Will be updated from detail API if available
                        "description": f"JLCPCB Component {lcsc_id}",
                        "manufacturer": "Unknown",
                        "package": "Unknown",
                        "price": [],
                        "stock": 0,
                        "datasheet": "",
                        "image": "",
                        "category": "Electronic Component",
                        "subcategory": "",
                        "symbol_uuids": symbol_uuids,
                        "footprint_uuid": footprint_uuid,
                    }

                    # Try to get additional details
                    try:
                        detail_data = self._get_component_details(lcsc_id)
                        if detail_data:
                            component_data.update(detail_data)
                    except Exception as e:
                        logger.warning(f"Could not fetch additional details: {e}")

                    return component_data

            logger.warning(f"Component not found: {lcsc_id}")
            return None

        except Exception as e:
            logger.error(f"Search failed for {lcsc_id}: {e}")
            raise LCSCAPIError(f"Search failed: {e}")

    def _get_component_details(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get additional component details (optional, best effort)

        Args:
            lcsc_id: LCSC part number

        Returns:
            Additional component data or None
        """
        # Try to get more details from JLCPCB API or other sources
        # This is optional and won't fail the main search
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

        # The EasyEDA data is already included in the component
        # The symbol_uuids and footprint_uuid are ready to use
        component["easyeda_data"] = {
            "symbol_uuids": component.get("symbol_uuids", []),
            "footprint_uuid": component.get("footprint_uuid"),
        }

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
