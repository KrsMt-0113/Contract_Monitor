"""
Blockchain monitor for detecting contract deployments with retry mechanism
"""
import logging
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from typing import List, Dict, Union
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Networks that use Proof of Authority (POA) consensus
POA_NETWORKS = ['polygon', 'bsc', 'linea', 'flare', 'avalanche']


class BlockchainMonitor:
    def __init__(self, rpc_urls: Union[str, List[str]], network_name: str = 'ethereum'):
        # Support both single URL and list of URLs
        if isinstance(rpc_urls, str):
            self.rpc_urls = [rpc_urls]
        else:
            self.rpc_urls = rpc_urls

        self.network_name = network_name
        self.w3 = None
        self.current_rpc_url = None

        # Try to connect to any available RPC endpoint
        self._connect_to_rpc()

        if not self.w3 or not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to any RPC endpoint for {network_name}")

        logger.info(f"Connected to {network_name} blockchain at {self.current_rpc_url}")
        try:
            current_block = self.w3.eth.block_number
            logger.info(f"[{network_name}] Current block number: {current_block}")
        except Exception as e:
            logger.warning(f"Could not fetch current block number: {e}")

    def _connect_to_rpc(self):
        """Try to connect to RPC endpoints in order"""
        for rpc_url in self.rpc_urls:
            try:
                logger.info(f"[{self.network_name}] Trying to connect to {rpc_url}...")
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))

                # Inject POA middleware for networks that use Proof of Authority
                if self.network_name in POA_NETWORKS:
                    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
                    logger.debug(f"[{self.network_name}] Injected POA middleware")

                # Test the connection with a simple call
                if w3.is_connected():
                    try:
                        _ = w3.eth.block_number
                        self.w3 = w3
                        self.current_rpc_url = rpc_url
                        logger.info(f"[{self.network_name}] Successfully connected to {rpc_url}")
                        return
                    except Exception as e:
                        logger.warning(f"[{self.network_name}] Connection test failed for {rpc_url}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"[{self.network_name}] Failed to connect to {rpc_url}: {e}")
                continue

        logger.error(f"[{self.network_name}] Could not connect to any RPC endpoint")

    def _ensure_connection(self, max_retries=3, retry_delay=5):
        """Ensure we have a valid connection, reconnect if needed"""
        if not self.w3 or not self.w3.is_connected():
            logger.warning(f"[{self.network_name}] Connection lost, attempting to reconnect...")

            for retry in range(max_retries):
                self._connect_to_rpc()
                if self.w3 and self.w3.is_connected():
                    logger.info(f"[{self.network_name}] Reconnection successful")
                    return

                if retry < max_retries - 1:
                    wait_time = retry_delay * (2 ** retry)  # 指数退避
                    logger.warning(f"[{self.network_name}] Reconnection failed, retrying in {wait_time}s... (attempt {retry + 1}/{max_retries})")
                    time.sleep(wait_time)

            raise ConnectionError(f"[{self.network_name}] Failed to reconnect after {max_retries} attempts")

    def get_latest_block_number(self, max_retries=3) -> int:
        """Get the latest block number with retry logic"""
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                return self.w3.eth.block_number
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[{self.network_name}] Failed to get block number (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"[{self.network_name}] Failed to get block number after {max_retries} attempts: {e}")
                    raise

    def get_contract_deployments(self, block_number: int, max_retries=3) -> List[Dict]:
        """
        Get all contract deployments in a specific block with retry logic
        使用批量 trace_block 和并行处理提升性能

        Returns:
            List of dictionaries containing deployment information
        """
        deployments = []

        # 重试获取区块数据
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                block = self.w3.eth.get_block(block_number, full_transactions=True)
                break  # 成功获取区块，退出重试循环
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[{self.network_name}] Failed to get block {block_number} (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"[{self.network_name}] Failed to get block {block_number} after {max_retries} attempts: {e}")
                    raise

        if not block.transactions:
            return deployments

        # **优化1: 批量获取整个区块的 trace (一次 RPC 调用)**
        block_traces = self._get_block_traces(block_number)

        # **优化2: 并行获取所有交易的 receipts**
        receipts_map = self._get_receipts_parallel(block.transactions)

        # **优化3: 并行处理所有交易**
        try:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for tx in block.transactions:
                    receipt = receipts_map.get(tx['hash'].hex())
                    if not receipt:
                        continue

                    # 提交任务到线程池
                    future = executor.submit(
                        self._process_single_transaction,
                        tx, receipt, block_number, block_traces
                    )
                    futures.append(future)

                # 收集结果
                for future in as_completed(futures):
                    try:
                        tx_deployments = future.result()
                        deployments.extend(tx_deployments)
                    except Exception as e:
                        logger.error(f"[{self.network_name}] Error processing transaction: {e}")

        except Exception as e:
            logger.error(f"[{self.network_name}] Error in parallel processing for block {block_number}: {e}")

        return deployments

    def _get_receipts_parallel(self, transactions: List[Dict], max_workers=10) -> Dict[str, Dict]:
        """并行获取所有交易的 receipts"""
        receipts_map = {}

        def get_receipt(tx_hash):
            try:
                return tx_hash.hex(), self.w3.eth.get_transaction_receipt(tx_hash)
            except Exception as e:
                logger.debug(f"[{self.network_name}] Failed to get receipt for {tx_hash.hex()}: {e}")
                return tx_hash.hex(), None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(get_receipt, tx['hash']) for tx in transactions]

            for future in as_completed(futures):
                try:
                    tx_hash, receipt = future.result()
                    if receipt:
                        receipts_map[tx_hash] = receipt
                except Exception as e:
                    logger.debug(f"[{self.network_name}] Error getting receipt: {e}")

        return receipts_map

    def _process_single_transaction(self, tx: Dict, receipt: Dict, block_number: int,
                                    block_traces: Dict) -> List[Dict]:
        """处理单个交易，返回该交易中的所有部署"""
        deployments = []

        # 方法1: 直接部署检测 (tx.to is None)
        if tx['to'] is None and receipt.get('contractAddress'):
            deployment = {
                'contract_address': receipt['contractAddress'],
                'deployer_address': tx['from'],
                'transaction_hash': tx['hash'].hex(),
                'block_number': block_number,
                'network': self.network_name,
                'deployment_type': 'direct',
                'factory_address': None,
                'gas_used': receipt['gasUsed'],
                'status': receipt['status']
            }
            deployments.append(deployment)
            logger.info(f"[{self.network_name}] Found direct deployment: {receipt['contractAddress']} "
                      f"by {tx['from'][:10]}... in block {block_number}")

        # 方法2: 工厂合约部署检测 - 使用预先获取的 traces
        elif tx['to'] is not None:
            tx_hash = tx['hash'].hex()

            # 优先使用批量获取的 traces
            if block_traces and tx_hash in block_traces:
                factory_deployments = self._parse_traces_for_deployments(
                    block_traces[tx_hash], tx, receipt, block_number
                )
                deployments.extend(factory_deployments)
            else:
                # 如果批量 trace 失败，使用回退方案
                factory_deployments = self._fallback_detect_factory_deployments(tx, receipt, block_number)
                deployments.extend(factory_deployments)

        return deployments

    def _get_block_traces(self, block_number: int) -> Dict:
        """
        批量获取整个区块的所有 trace (一次 RPC 调用)
        相比逐个交易调用 trace_transaction，这能大幅提升性能

        Returns:
            Dict[tx_hash, List[trace]]: 按交易哈希组织的 trace 数据
        """
        try:
            # 使用 trace_block 一次性获取整个区块的 trace
            result = self.w3.provider.make_request('trace_block', [hex(block_number)])
            traces = result.get('result', [])

            # 按交易哈希组织 trace
            traces_by_tx = {}
            for trace in traces:
                tx_hash = trace.get('transactionHash')
                if tx_hash:
                    if tx_hash not in traces_by_tx:
                        traces_by_tx[tx_hash] = []
                    traces_by_tx[tx_hash].append(trace)

            logger.debug(f"[{self.network_name}] Got traces for {len(traces_by_tx)} transactions in block {block_number}")
            return traces_by_tx

        except Exception as e:
            logger.debug(f"[{self.network_name}] trace_block not available for block {block_number}: {e}")
            return {}

    def _parse_traces_for_deployments(self, traces: List[Dict], tx: Dict, receipt: Dict,
                                     block_number: int) -> List[Dict]:
        """从 trace 列表中提取合约部署（使用 trace_block 格式）"""
        deployments = []

        for trace in traces:
            if trace.get('type') == 'create':
                action = trace.get('action', {})
                result = trace.get('result', {})

                contract_address = result.get('address')
                if not contract_address:
                    continue

                deployment = {
                    'contract_address': contract_address,
                    'deployer_address': action.get('from'),
                    'factory_address': tx['to'],
                    'transaction_hash': tx['hash'].hex(),
                    'block_number': block_number,
                    'network': self.network_name,
                    'deployment_type': 'factory',
                    'gas_used': result.get('gasUsed', 0),
                    'status': receipt['status']
                }
                deployments.append(deployment)

                logger.info(f"[{self.network_name}] Found factory deployment: {contract_address} "
                          f"created by {action.get('from')[:10]}... via factory {tx['to'][:10]}...")

        return deployments

    def _detect_factory_deployments(self, tx: Dict, receipt: Dict, block_number: int) -> List[Dict]:
        """通过内部交易检测工厂合约创建的子合约"""
        deployments = []

        try:
            # 使用 debug_traceTransaction 或 trace_transaction 获取内部交易
            # 注意：需要 RPC 节点支持 trace 或 debug API
            try:
                # 方法1: Parity/OpenEthereum trace API (推荐)
                traces = self.w3.provider.make_request('trace_transaction', [tx['hash'].hex()])

                for trace in traces.get('result', []):
                    # 检查是否为 CREATE 或 CREATE2 操作
                    if trace.get('type') == 'create':
                        action = trace.get('action', {})
                        result = trace.get('result', {})

                        contract_address = result.get('address')
                        if not contract_address:
                            continue

                        deployment = {
                            'contract_address': contract_address,
                            'deployer_address': action.get('from'),  # 实际创建者
                            'factory_address': tx['to'],  # 工厂合约
                            'transaction_hash': tx['hash'].hex(),
                            'block_number': block_number,
                            'network': self.network_name,
                            'deployment_type': 'factory',
                            'gas_used': result.get('gasUsed', 0),
                            'status': receipt['status'],
                            'init_code': action.get('init', '')[:20] + '...'  # 记录部分初始化代码
                        }
                        deployments.append(deployment)

                        logger.info(f"[{self.network_name}] Found factory deployment via trace: {contract_address} "
                                  f"created by {action.get('from')[:10]}... via factory {tx['to'][:10]}...")

            except Exception as e:
                # 如果 trace API 不可用，尝试使用 debug API
                logger.debug(f"[{self.network_name}] trace_transaction not available, trying debug_traceTransaction: {e}")

                try:
                    # 方法2: Geth debug API (较慢但更通用)
                    trace = self.w3.provider.make_request('debug_traceTransaction',
                                                          [tx['hash'].hex(),
                                                           {'tracer': 'callTracer'}])

                    deployments.extend(self._parse_call_trace(trace.get('result', {}), tx, receipt, block_number))

                except Exception as e2:
                    logger.debug(f"[{self.network_name}] debug_traceTransaction also failed: {e2}")
                    # 如果两种方法都不可用，回退到原来的方法
                    return self._fallback_detect_factory_deployments(tx, receipt, block_number)

        except Exception as e:
            logger.error(f"[{self.network_name}] Error in trace-based factory detection: {e}")

        return deployments

    def _parse_call_trace(self, call_trace: Dict, tx: Dict, receipt: Dict, block_number: int) -> List[Dict]:
        """解析 callTracer 格式的追踪数据"""
        deployments = []

        def extract_creates(trace: Dict, parent_address: str = None):
            """递归提取 CREATE 操作"""
            call_type = trace.get('type', '').upper()

            if call_type in ['CREATE', 'CREATE2']:
                contract_address = trace.get('to')
                if contract_address:
                    deployment = {
                        'contract_address': contract_address,
                        'deployer_address': trace.get('from'),
                        'factory_address': parent_address or tx['to'],
                        'transaction_hash': tx['hash'].hex(),
                        'block_number': block_number,
                        'network': self.network_name,
                        'deployment_type': 'factory',
                        'gas_used': int(trace.get('gasUsed', '0x0'), 16) if isinstance(trace.get('gasUsed'), str) else trace.get('gasUsed', 0),
                        'status': receipt['status']
                    }
                    deployments.append(deployment)

                    logger.info(f"[{self.network_name}] Found {call_type} deployment: {contract_address} "
                              f"by {trace.get('from')[:10]}...")

            # 递归处理子调用
            for call in trace.get('calls', []):
                extract_creates(call, trace.get('to'))

        extract_creates(call_trace)
        return deployments

    def _fallback_detect_factory_deployments(self, tx: Dict, receipt: Dict, block_number: int) -> List[Dict]:
        """回退方案：当 trace API 不可用时使用"""
        # 这里放你原来的基于 logs 和字节码检查的实现
        deployments = []
        seen_addresses = set()

        SKIP_ADDRESSES = {
            '0x0000000000000000000000000000000000000000',
            *[f'0x000000000000000000000000000000000000000{i}' for i in range(1, 20)]
        }

        try:
            for log in receipt.get('logs', []):
                address = log['address']

                if (address in seen_addresses or
                    address == tx['to'] or
                    address in SKIP_ADDRESSES):
                    continue

                seen_addresses.add(address)

                try:
                    code = self.w3.eth.get_code(address)
                    if not code or code == b'\x00' or len(code) <= 2:
                        continue

                    try:
                        previous_code = self.w3.eth.get_code(address, block_identifier=block_number - 1)
                        if previous_code and len(previous_code) > 2:
                            continue
                    except Exception:
                        pass

                    deployment = {
                        'contract_address': address,
                        'deployer_address': tx['from'],
                        'factory_address': tx['to'],
                        'transaction_hash': tx['hash'].hex(),
                        'block_number': block_number,
                        'network': self.network_name,
                        'deployment_type': 'factory',
                        'gas_used': receipt['gasUsed'],
                        'status': receipt['status']
                    }
                    deployments.append(deployment)

                except Exception as e:
                    logger.debug(f"[{self.network_name}] Error checking address {address}: {e}")
                    continue

        except Exception as e:
            logger.debug(f"[{self.network_name}] Error in fallback factory detection: {e}")

        return deployments

    def get_deployments_in_range(self, start_block: int, end_block: int, max_workers=5) -> List[Dict]:
        """
        Get all contract deployments in a range of blocks (并行处理)

        Args:
            start_block: Starting block number (inclusive)
            end_block: Ending block number (inclusive)
            max_workers: 并行处理的最大线程数

        Returns:
            List of all deployments found
        """
        all_deployments = []
        failed_blocks = []

        # **并行处理多个区块**
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有区块的处理任务
            future_to_block = {
                executor.submit(self.get_contract_deployments, block_num): block_num
                for block_num in range(start_block, end_block + 1)
            }

            # 收集结果
            for future in as_completed(future_to_block):
                block_num = future_to_block[future]
                try:
                    deployments = future.result()
                    all_deployments.extend(deployments)
                except Exception as e:
                    logger.error(f"[{self.network_name}] Error processing block {block_num}: {e}")
                    failed_blocks.append(block_num)

        if failed_blocks:
            logger.warning(f"[{self.network_name}] Failed to process {len(failed_blocks)} block(s): {failed_blocks}")

        # 按区块号排序结果
        all_deployments.sort(key=lambda x: x['block_number'])

        return all_deployments

