"""
Arkham API Client for fetching entity information
"""
import requests
import logging
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)


class ArkhamClient:
    def __init__(self, api_key: str, api_url: str = 'https://api.arkm.com'):
        self.api_key = api_key
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({'API-Key': api_key})

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.05  # 20 requests per second

    def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)

        self.last_request_time = time.time()

    def get_address_info(self, address: str, chain: str = 'ethereum') -> Optional[Dict]:
        """
        Get information about an address from Arkham API

        Args:
            address: The blockchain address to query
            chain: The blockchain name (e.g., 'ethereum', 'arbitrum', 'base')

        Returns:
            Dictionary with address information or None if not found
        """
        self._rate_limit()

        try:
            # Try to get address details with chain parameter
            url = f"{self.api_url}/intelligence/address/{address}"
            params = {'chain': chain} if chain else None
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"[{chain}] Found information for address {address}")
                return data
            elif response.status_code == 404:
                logger.debug(f"[{chain}] No information found for address {address}")
                return None
            else:
                logger.warning(f"[{chain}] Arkham API returned status {response.status_code} for {address}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"[{chain}] Error querying Arkham API for {address}: {e}")
            return None

    def extract_entity_info(self, address_data: Optional[Dict]) -> tuple[Optional[str], Optional[str]]:
        """
        Extract entity name and ID from address data

        Returns:
            Tuple of (entity_name, entity_id) or (None, None)
        """
        if not address_data:
            return None, None

        # Try to extract entity information from the response
        try:
            # Common patterns in Arkham API responses
            if 'arkhamEntity' in address_data:
                entity = address_data['arkhamEntity']
                entity_name = entity.get('name')
                entity_id = entity.get('id')
                return entity_name, entity_id

            if 'entity' in address_data:
                entity = address_data['entity']
                entity_name = entity.get('name')
                entity_id = entity.get('id')
                return entity_name, entity_id

            # If the address itself has a name/label
            if 'arkhamLabel' in address_data:
                label = address_data['arkhamLabel']
                entity_name = label.get('name')
                entity_id = label.get('id')
                return entity_name, entity_id

        except (KeyError, TypeError) as e:
            logger.debug(f"Could not extract entity info: {e}")

        return None, None

