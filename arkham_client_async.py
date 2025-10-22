"""
Async Arkham API Client with caching for better performance
"""
import aiohttp
import asyncio
import logging
from typing import Optional, Dict
import time
import hashlib
import threading

logger = logging.getLogger(__name__)


class ArkhamClientAsync:
    def __init__(self, api_key: str, api_url: str = 'https://api.arkm.com'):
        self.api_key = api_key
        self.api_url = api_url

        # Rate limiting - 使用线程锁而不是 asyncio.Lock
        self.last_request_time = 0
        self.min_request_interval = 0.05  # 20 requests per second
        self.rate_limit_lock = threading.Lock()  # 改为线程锁，避免事件循环绑定

        # 内存缓存 - 缓存地址查询结果
        self._cache = {}
        self._cache_ttl = 3600  # 缓存1小时
        self._cache_lock = threading.Lock()  # 缓存访问锁

    async def _create_session(self):
        """创建新的 aiohttp session（每次调用创建，避免跨线程共享）"""
        return aiohttp.ClientSession(
            headers={'API-Key': self.api_key},
            timeout=aiohttp.ClientTimeout(total=10)
        )

    async def _rate_limit(self):
        """Enforce rate limiting (使用线程锁)"""
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                self.last_request_time = time.time() + sleep_time
            else:
                self.last_request_time = time.time()

        # 在锁外执行 sleep
        if time_since_last_request < self.min_request_interval:
            await asyncio.sleep(sleep_time)

    def _get_cache_key(self, address: str, chain: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{address.lower()}:{chain.lower()}".encode()).hexdigest()

    def _get_from_cache(self, address: str, chain: str) -> Optional[Dict]:
        """从缓存获取数据（线程安全）"""
        cache_key = self._get_cache_key(address, chain)
        with self._cache_lock:
            if cache_key in self._cache:
                cached_data, cached_time = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl:
                    logger.debug(f"[{chain}] Cache hit for address {address[:10]}...")
                    return cached_data
                else:
                    # 缓存过期，删除
                    del self._cache[cache_key]
        return None

    def _save_to_cache(self, address: str, chain: str, data: Optional[Dict]):
        """保存到缓存（线程安全）"""
        cache_key = self._get_cache_key(address, chain)
        with self._cache_lock:
            self._cache[cache_key] = (data, time.time())

    async def get_address_info(self, address: str, chain: str = 'ethereum') -> Optional[Dict]:
        """
        异步获取地址信息，带缓存

        Args:
            address: The blockchain address to query
            chain: The blockchain name (e.g., 'ethereum', 'arbitrum', 'base')

        Returns:
            Dictionary with address information or None if not found
        """
        # 先检查缓存
        cached = self._get_from_cache(address, chain)
        if cached is not None:
            return cached

        await self._rate_limit()

        # 每次调用创建新的 session，避免跨线程共享
        session = await self._create_session()
        try:
            url = f"{self.api_url}/intelligence/address/{address}"
            params = {'chain': chain} if chain else None

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"[{chain}] Found information for address {address[:10]}...")
                    self._save_to_cache(address, chain, data)
                    return data
                elif response.status == 404:
                    logger.debug(f"[{chain}] No information found for address {address[:10]}...")
                    self._save_to_cache(address, chain, None)
                    return None
                else:
                    logger.warning(f"[{chain}] Arkham API returned status {response.status} for {address[:10]}...")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"[{chain}] Timeout querying Arkham API for {address[:10]}...")
            return None
        except Exception as e:
            logger.error(f"[{chain}] Error querying Arkham API for {address[:10]}...: {e}")
            return None
        finally:
            # 确保 session 被关闭
            await session.close()

    async def get_address_info_batch(self, addresses: list[tuple[str, str]]) -> list[Optional[Dict]]:
        """
        批量异步获取多个地址信息

        Args:
            addresses: List of (address, chain) tuples

        Returns:
            List of address info dicts in the same order
        """
        tasks = [self.get_address_info(addr, chain) for addr, chain in addresses]
        return await asyncio.gather(*tasks, return_exceptions=False)

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

    async def close(self):
        """关闭 aiohttp session（已废弃，每次调用自动创建和关闭 session）"""
        pass  # 不再需要，因为每次调用都会自动关闭 session

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("Arkham API cache cleared")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            'cache_size': len(self._cache),
            'cache_ttl': self._cache_ttl
        }

