"""
Multi-chain contract monitoring service with retry mechanism and parallel processing
OPTIMIZED: Async Arkham API calls + Batch DB writes + Caching
"""
import logging
import time
import sys
import threading
import asyncio
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    RPC_ENDPOINTS, ARKHAM_API_KEY, ARKHAM_API_URL,
    DB_PATH, BLOCK_CHECK_INTERVAL, BATCH_SIZE,
    LOG_FILE, LOG_LEVEL, DEFAULT_NETWORKS, NON_EVM_NETWORKS
)
from blockchain_monitor import BlockchainMonitor
from arkham_client_async import ArkhamClientAsync
from database import ContractDatabase
from contract_analyzer import ContractAnalyzer

# Setup logging - only to file, not to console
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger(__name__)


class MultiChainMonitorService:
    def __init__(self, networks: List[str], arkham_api_key: str):
        logger.info("Initializing Multi-Chain Contract Monitor Service (OPTIMIZED)")

        self.networks = networks
        self.arkham_client = ArkhamClientAsync(arkham_api_key, ARKHAM_API_URL)
        self.database = ContractDatabase(DB_PATH, enable_batch_mode=True)  # 启用批量写入
        self.monitors: Dict[str, BlockchainMonitor] = {}
        self.analyzers: Dict[str, ContractAnalyzer] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.is_running = False
        
        # 并行处理线程池 - 最多10个并发
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ContractAnalyzer")
        
        # Event loop for async operations
        self.loop = None
        self.loop_thread = None

        # 统计数据
        self.stats = {
            network: {
                'current_block': 0,
                'latest_block': 0,
                'total_deployments': 0,
                'saved_deployments': 0,  # 成功保存到数据库的数量
                'entity_deployments': 0,
                'last_deployment_time': None,
                'status': 'Initializing',
                'errors': 0
            } for network in networks if network not in NON_EVM_NETWORKS and network in RPC_ENDPOINTS
        }
        self.stats_lock = threading.Lock()

        # Initialize blockchain monitors for each network
        for network in networks:
            if network in NON_EVM_NETWORKS:
                logger.warning(f"Skipping {network} - non-EVM chains not yet supported")
                continue

            if network not in RPC_ENDPOINTS or not RPC_ENDPOINTS[network]:
                logger.warning(f"Skipping {network} - no RPC endpoints configured")
                continue

            try:
                monitor = BlockchainMonitor(RPC_ENDPOINTS[network], network)
                self.monitors[network] = monitor
                analyzer = ContractAnalyzer(monitor.w3)
                self.analyzers[network] = analyzer
                logger.info(f"✓ {network} monitor initialized")
            except Exception as e:
                logger.error(f"✗ Failed to initialize {network} monitor: {e}")

    def process_deployment(self, deployment: dict, network: str):
        """Process a single contract deployment with async API calls"""
        contract_address = deployment['contract_address']
        deployer_address = deployment['deployer_address']
        logger.info(f"[{network}] Processing deployment: {contract_address}")

        analyzer = self.analyzers.get(network)
        contract_info = None
        contract_type = None
        contract_info_json = None

        # Step 1: 合约分析 (同步)
        if analyzer:
            try:
                contract_info = analyzer.get_contract_info(contract_address)
                contract_type = contract_info.get('type', 'Unknown')
                info_str = analyzer.format_contract_info(contract_info)
                logger.info(f"[{network}] {info_str}")

                import json
                contract_info_json = json.dumps({
                    'type': contract_type,
                    'all_types': contract_info.get('all_types', []),
                    'confidence': contract_info.get('confidence', 0),
                    'bytecode_size': contract_info.get('bytecode_size', 0),
                    'token_name': contract_info.get('token_name'),
                    'token_symbol': contract_info.get('token_symbol'),
                    'token_decimals': contract_info.get('token_decimals'),
                    'total_supply': contract_info.get('total_supply_raw'),
                    'nft_name': contract_info.get('nft_name'),
                    'nft_symbol': contract_info.get('nft_symbol'),
                    'nft_total_supply': contract_info.get('nft_total_supply'),
                    'pool_token0': contract_info.get('pool_token0'),
                    'pool_token1': contract_info.get('pool_token1'),
                })
            except Exception as e:
                logger.error(f"[{network}] Error analyzing contract: {e}")
                contract_type = 'Error'

        # Step 2: Arkham API 调用 (异步) - 在新的 event loop 中运行
        entity_name, entity_id = self._get_entity_info_sync(deployer_address, network)

        # Step 3: 保存到数据库 (批量队列)
        saved = self.database.save_contract(
            contract_address=contract_address,
            network=network,
            deployer_address=deployer_address,
            entity_name=entity_name,
            entity_id=entity_id,
            block_number=deployment['block_number'],
            transaction_hash=deployment['transaction_hash'],
            contract_type=contract_type,
            contract_info=contract_info_json,
            factory_address=deployment.get('factory_address'),
            deployment_type=deployment.get('deployment_type', 'direct')
        )

        with self.stats_lock:
            if network in self.stats:
                self.stats[network]['total_deployments'] += 1
                if saved:
                    self.stats[network]['saved_deployments'] += 1
                if entity_name:
                    self.stats[network]['entity_deployments'] += 1
                self.stats[network]['last_deployment_time'] = int(time.time())

        if entity_name:
            logger.info(f"[{network}] ✓ Contract {contract_address} belongs to entity: {entity_name}")
        else:
            logger.info(f"[{network}] ○ Contract {contract_address} - no entity found")

    def _get_entity_info_sync(self, address: str, network: str) -> tuple:
        """同步包装器，用于在线程池中调用异步 API"""
        try:
            # 在新的 event loop 中运行异步操作
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                address_info = loop.run_until_complete(
                    self.arkham_client.get_address_info(address, chain=network)
                )
                return self.arkham_client.extract_entity_info(address_info)
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"[{network}] Error getting entity info: {e}")
            return None, None

    def process_deployments_parallel(self, deployments: List[dict], network: str):
        """并行处理多个合约部署"""
        if not deployments:
            return
        
        logger.info(f"[{network}] Starting parallel processing of {len(deployments)} deployments")
        
        futures = {}
        for deployment in deployments:
            future = self.executor.submit(self.process_deployment, deployment, network)
            futures[future] = deployment
        
        completed_count = 0
        error_count = 0
        
        for future in as_completed(futures):
            deployment = futures[future]
            try:
                future.result()
                completed_count += 1
            except Exception as e:
                error_count += 1
                contract_address = deployment.get('contract_address', 'unknown')
                logger.error(f"[{network}] Error processing deployment {contract_address}: {e}", exc_info=True)
        
        logger.info(f"[{network}] Parallel processing completed: {completed_count}/{len(deployments)} successful (errors: {error_count})")

    def initialize_start_block(self, network: str) -> int:
        """Initialize the starting block for monitoring a network"""
        last_processed = self.database.get_last_processed_block(network)
        if last_processed:
            logger.info(f"[{network}] Resuming from block {last_processed + 1}")
            return last_processed + 1
        else:
            current_block = self.monitors[network].get_latest_block_number()
            logger.info(f"[{network}] Starting fresh from current block {current_block}")
            return current_block

    def monitor_network(self, network: str):
        """Monitor a single network with retry mechanism"""
        monitor = self.monitors[network]
        current_block = self.initialize_start_block(network)
        consecutive_errors = 0
        max_consecutive_errors = 5

        logger.info(f"[{network}] Monitoring started")

        with self.stats_lock:
            if network in self.stats:
                self.stats[network]['status'] = 'Running'

        while self.is_running:
            try:
                latest_block = monitor.get_latest_block_number()
                
                with self.stats_lock:
                    if network in self.stats:
                        self.stats[network]['latest_block'] = latest_block

                if latest_block > current_block:
                    end_block = min(current_block + BATCH_SIZE - 1, latest_block)
                    start_time = time.time()
                    logger.info(f"[{network}][{time.strftime('%H:%M:%S')}] Processing blocks {current_block} to {end_block}")

                    deployments = monitor.get_contract_deployments(current_block, end_block)

                    if deployments:
                        logger.info(f"[{network}][{time.strftime('%H:%M:%S')}] Found {len(deployments)} contract deployment(s)")
                        self.process_deployments_parallel(deployments, network)
                        elapsed = time.time() - start_time
                        logger.info(f"[{network}] Batch completed in {elapsed:.2f}s")

                    self.database.update_last_processed_block(network, end_block)
                    current_block = end_block + 1
                    
                    with self.stats_lock:
                        if network in self.stats:
                            self.stats[network]['current_block'] = current_block
                    consecutive_errors = 0

                time.sleep(BLOCK_CHECK_INTERVAL)

            except ConnectionError as e:
                consecutive_errors += 1
                logger.error(f"[{network}] Connection error (#{consecutive_errors}): {e}")
                with self.stats_lock:
                    if network in self.stats:
                        self.stats[network]['errors'] += 1
                        self.stats[network]['status'] = f'Error (#{consecutive_errors})'
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"[{network}] Too many consecutive connection errors. Attempting reinitialization...")
                    try:
                        monitor = BlockchainMonitor(RPC_ENDPOINTS[network], network)
                        self.monitors[network] = monitor
                        analyzer = ContractAnalyzer(monitor.w3)
                        self.analyzers[network] = analyzer
                        consecutive_errors = 0
                        logger.info(f"[{network}] Monitor reinitialized successfully")
                        with self.stats_lock:
                            if network in self.stats:
                                self.stats[network]['status'] = 'Running'
                    except Exception as reinit_error:
                        logger.critical(f"[{network}] Failed to reinitialize monitor: {reinit_error}")
                        sleep_time = min(300, BLOCK_CHECK_INTERVAL * (2 ** min(consecutive_errors, 8)))
                        time.sleep(sleep_time)
                else:
                    sleep_time = BLOCK_CHECK_INTERVAL * (2 ** min(consecutive_errors - 1, 5))
                    time.sleep(sleep_time)
                    
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[{network}] Unexpected error (#{consecutive_errors}): {e}", exc_info=True)
                with self.stats_lock:
                    if network in self.stats:
                        self.stats[network]['errors'] += 1
                        self.stats[network]['status'] = f'Error (#{consecutive_errors})'
                sleep_time = min(300, BLOCK_CHECK_INTERVAL * (2 ** min(consecutive_errors - 1, 5)))
                time.sleep(sleep_time)

        logger.info(f"[{network}] Monitoring stopped")

    def display_status(self):
        """Display real-time monitoring status in terminal"""
        import os
        while self.is_running:
            time.sleep(5)
            os.system('clear' if os.name == 'posix' else 'cls')
            print("=" * 100)
            print(f"{'Multi-Chain Contract Monitor (Parallel Processing Enabled)'.center(120)}")
            print(f"{'Updated: ' + time.strftime('%Y-%m-%d %H:%M:%S').center(120)}")
            print("=" * 120)
            print()
            print(f"{'Network':<15} {'Status':<20} {'Current':<12} {'Latest':<12} {'Behind':<10} {'Found':<10} {'Saved':<10} {'Entity':<10} {'Errors':<10}")
            print("-" * 120)

            with self.stats_lock:
                for network in sorted(self.stats.keys()):
                    stat = self.stats[network]
                    current = stat['current_block']
                    latest = stat['latest_block']
                    behind = latest - current if latest > 0 and current > 0 else 0
                    status = stat['status']
                    if 'Running' in status:
                        status_colored = f"\033[92m{status}\033[0m"
                    elif 'Error' in status:
                        status_colored = f"\033[91m{status}\033[0m"
                    else:
                        status_colored = f"\033[93m{status}\033[0m"

                    # 计算保存率
                    saved = stat['saved_deployments']
                    total = stat['total_deployments']
                    saved_str = f"{saved}" if total == 0 else f"{saved}"

                    print(f"{network:<15} {status_colored:<29} {current:<12,} {latest:<12,} {behind:<10,} {total:<10} {saved_str:<10} {stat['entity_deployments']:<10} {stat['errors']:<10}")

            print("-" * 120)
            with self.stats_lock:
                total_deployments = sum(s['total_deployments'] for s in self.stats.values())
                total_saved = sum(s['saved_deployments'] for s in self.stats.values())
                total_entities = sum(s['entity_deployments'] for s in self.stats.values())
                total_errors = sum(s['errors'] for s in self.stats.values())
                active_chains = sum(1 for s in self.stats.values() if 'Running' in s['status'])

            # 显示活跃线程
            active_threads = sum(1 for t in self.threads.values() if t and t.is_alive())

            save_rate = f"{total_saved*100//total_deployments}%" if total_deployments > 0 else "0%"
            print(f"\n{'Total:':<15} Active Chains: {active_chains}/{len(self.stats)}  |  Found: {total_deployments}  |  Saved: {total_saved} ({save_rate})  |  With Entity: {total_entities}  |  Errors: {total_errors}")
            print()
            print("🔄 Multi-chain parallel monitoring: Each chain runs in independent thread")
            print("⚡ Contract analysis: Up to 10 concurrent per chain")
            print(f"📊 Active monitoring threads: {active_threads}/{len(self.threads)}")
            print(f"💾 Note: 'Saved' shows unique contracts written to DB, 'Found' includes duplicates")
            print("\nPress Ctrl+C to stop monitoring...")
            print(f"Log file: {LOG_FILE}")
    
    def monitor_thread_health(self):
        """Monitor health of all monitoring threads and restart if needed"""
        logger.info("Thread health monitor started")
        while self.is_running:
            time.sleep(30)
            for network in list(self.monitors.keys()):
                thread = self.threads.get(network)
                if thread and not thread.is_alive():
                    logger.warning(f"[{network}] Thread died unexpectedly, restarting...")
                    try:
                        new_thread = threading.Thread(target=self.monitor_network, args=(network,), daemon=True, name=f"Monitor-{network}")
                        new_thread.start()
                        self.threads[network] = new_thread
                        logger.info(f"[{network}] Thread restarted successfully")
                    except Exception as e:
                        logger.error(f"[{network}] Failed to restart thread: {e}")

    def run(self):
        """Run the multi-chain monitoring service"""
        if not self.monitors:
            logger.error("No monitors initialized. Exiting.")
            return

        self.is_running = True

        logger.info("="*80)
        logger.info(f"🚀 MULTI-CHAIN PARALLEL MONITORING")
        logger.info(f"📡 Monitoring {len(self.monitors)} networks: {', '.join(self.monitors.keys())}")
        logger.info(f"⏱️  Check interval: {BLOCK_CHECK_INTERVAL} seconds per chain")
        logger.info(f"⚡ Contract analysis: Up to 10 concurrent per chain")
        logger.info(f"🔄 Each chain runs in INDEPENDENT THREAD - TRUE PARALLELISM")
        logger.info("="*80)

        for network in self.monitors.keys():
            thread = threading.Thread(target=self.monitor_network, args=(network,), daemon=True, name=f"Monitor-{network}")
            thread.start()
            self.threads[network] = thread
            logger.info(f"✓ [{network}] Independent monitoring thread started")

        logger.info(f"\n🎯 All {len(self.monitors)} chains are now running in PARALLEL!")

        health_thread = threading.Thread(target=self.monitor_thread_health, daemon=True, name="HealthMonitor")
        health_thread.start()
        logger.info("Health monitor thread started")
        
        display_thread = threading.Thread(target=self.display_status, daemon=True, name="StatusDisplay")
        display_thread.start()
        logger.info("Status display thread started")

        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()

    def stop(self):
        """Stop the monitoring service"""
        logger.info("Stopping all monitors...")
        self.is_running = False
        for network, thread in self.threads.items():
            logger.info(f"[{network}] Waiting for thread to stop...")
            thread.join(timeout=5)
        logger.info("Shutting down thread pool executor...")
        self.executor.shutdown(wait=True, cancel_futures=False)

        # 关闭异步 Arkham 客户端
        logger.info("Closing Arkham API client...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.arkham_client.close())
        finally:
            loop.close()

        # 关闭数据库（会等待批量写入完成）
        logger.info("Closing database...")
        self.database.close()

        # 显示缓存统计
        cache_stats = self.arkham_client.get_cache_stats()
        logger.info(f"Arkham API cache stats: {cache_stats}")

        logger.info("Multi-Chain Contract Monitor Service stopped")


def main():
    """Main entry point"""
    if not ARKHAM_API_KEY:
        logger.error("ARKHAM_API_KEY not configured. Please set it in config.py or API-Key file")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description='Multi-Chain Contract Monitor with Parallel Processing')
    parser.add_argument('--networks', nargs='+', default=DEFAULT_NETWORKS, help='Networks to monitor')
    parser.add_argument('--all', action='store_true', help='Monitor all available networks')
    args = parser.parse_args()

    if args.all:
        networks = [n for n in RPC_ENDPOINTS.keys() if n not in NON_EVM_NETWORKS and RPC_ENDPOINTS[n]]
    else:
        networks = args.networks

    logger.info(f"Selected networks: {', '.join(networks)}")

    try:
        service = MultiChainMonitorService(networks, ARKHAM_API_KEY)
        service.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

