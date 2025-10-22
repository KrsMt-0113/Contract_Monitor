"""
Multi-chain contract monitoring service
"""
import logging
import time
import sys
import threading
from typing import Optional, Dict, List

from config import (
    RPC_ENDPOINTS, ARKHAM_API_KEY, ARKHAM_API_URL,
    DB_PATH, BLOCK_CHECK_INTERVAL, BATCH_SIZE,
    LOG_FILE, LOG_LEVEL, DEFAULT_NETWORKS, NON_EVM_NETWORKS
)
from blockchain_monitor import BlockchainMonitor
from arkham_client import ArkhamClient
from database import ContractDatabase
from contract_analyzer import ContractAnalyzer

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MultiChainMonitorService:
    def __init__(self, networks: List[str], arkham_api_key: str):
        logger.info("Initializing Multi-Chain Contract Monitor Service")

        self.networks = networks
        self.arkham_client = ArkhamClient(arkham_api_key, ARKHAM_API_URL)
        self.database = ContractDatabase(DB_PATH)
        self.monitors: Dict[str, BlockchainMonitor] = {}
        self.analyzers: Dict[str, ContractAnalyzer] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.is_running = False

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

                # Initialize contract analyzer for this network
                analyzer = ContractAnalyzer(monitor.w3)
                self.analyzers[network] = analyzer

                logger.info(f"✓ {network} monitor initialized")
            except Exception as e:
                logger.error(f"✗ Failed to initialize {network} monitor: {e}")

    def process_deployment(self, deployment: dict, network: str):
        """Process a single contract deployment"""
        contract_address = deployment['contract_address']
        deployer_address = deployment['deployer_address']

        logger.info(f"[{network}] Processing deployment: {contract_address}")

        # Analyze contract type
        analyzer = self.analyzers.get(network)
        contract_info = None
        contract_type = None
        contract_info_json = None

        if analyzer:
            try:
                contract_info = analyzer.get_contract_info(contract_address)
                contract_type = contract_info.get('type', 'Unknown')

                # Format and log contract info
                info_str = analyzer.format_contract_info(contract_info)
                logger.info(f"[{network}] {info_str}")

                # Prepare JSON for database storage
                import json
                contract_info_json = json.dumps({
                    'type': contract_type,
                    'all_types': contract_info.get('all_types', []),
                    'confidence': contract_info.get('confidence', 0),
                    'bytecode_size': contract_info.get('bytecode_size', 0),
                    # Token info
                    'token_name': contract_info.get('token_name'),
                    'token_symbol': contract_info.get('token_symbol'),
                    'token_decimals': contract_info.get('token_decimals'),
                    'total_supply': contract_info.get('total_supply_raw'),
                    # NFT info
                    'nft_name': contract_info.get('nft_name'),
                    'nft_symbol': contract_info.get('nft_symbol'),
                    'nft_total_supply': contract_info.get('nft_total_supply'),
                    # Pool info
                    'pool_token0': contract_info.get('pool_token0'),
                    'pool_token1': contract_info.get('pool_token1'),
                })
            except Exception as e:
                logger.error(f"[{network}] Error analyzing contract: {e}")
                contract_type = 'Error'

        # Query Arkham API for deployer information
        address_info = self.arkham_client.get_address_info(deployer_address, chain=network)
        entity_name, entity_id = self.arkham_client.extract_entity_info(address_info)

        # Save to database with contract type
        self.database.save_contract(
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

        if entity_name:
            logger.info(f"[{network}] ✓ Contract {contract_address} belongs to entity: {entity_name}")
        else:
            logger.info(f"[{network}] ○ Contract {contract_address} - no entity found")

    def initialize_start_block(self, network: str) -> int:
        """Initialize the starting block for monitoring a network"""
        last_processed = self.database.get_last_processed_block(network)

        if last_processed:
            logger.info(f"[{network}] Resuming from block {last_processed + 1}")
            return last_processed + 1
        else:
            # Start from current block if no previous state
            current_block = self.monitors[network].get_latest_block_number()
            logger.info(f"[{network}] Starting fresh from current block {current_block}")
            return current_block

    def monitor_network(self, network: str):
        """Monitor a single network (runs in separate thread)"""
        monitor = self.monitors[network]
        current_block = self.initialize_start_block(network)
        consecutive_errors = 0
        max_consecutive_errors = 5

        logger.info(f"[{network}] Monitoring started")

        while self.is_running:
            try:
                latest_block = monitor.get_latest_block_number()

                if latest_block > current_block:
                    # Process blocks in batches
                    end_block = min(current_block + BATCH_SIZE - 1, latest_block)

                    logger.info(f"[{network}] Processing blocks {current_block} to {end_block}")

                    deployments = monitor.get_deployments_in_range(current_block, end_block)

                    if deployments:
                        logger.info(f"[{network}] Found {len(deployments)} contract deployment(s)")

                        for deployment in deployments:
                            try:
                                self.process_deployment(deployment, network)
                            except Exception as e:
                                logger.error(f"[{network}] Error processing deployment {deployment.get('contract_address')}: {e}", exc_info=True)
                                continue

                    # Update last processed block
                    self.database.update_last_processed_block(network, end_block)
                    current_block = end_block + 1

                    # 重置错误计数器
                    consecutive_errors = 0

                # Wait before checking again
                time.sleep(BLOCK_CHECK_INTERVAL)

            except ConnectionError as e:
                consecutive_errors += 1
                logger.error(f"[{network}] Connection error (#{consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"[{network}] Too many consecutive connection errors ({consecutive_errors}). Attempting full reinitialization...")
                    try:
                        # 尝试重新初始化监控器
                        monitor = BlockchainMonitor(RPC_ENDPOINTS[network], network)
                        self.monitors[network] = monitor

                        # 重新初始化分析器
                        analyzer = ContractAnalyzer(monitor.w3)
                        self.analyzers[network] = analyzer

                        consecutive_errors = 0
                        logger.info(f"[{network}] Monitor reinitialized successfully")
                    except Exception as reinit_error:
                        logger.critical(f"[{network}] Failed to reinitialize monitor: {reinit_error}")
                        # 使用指数退避
                        sleep_time = min(300, BLOCK_CHECK_INTERVAL * (2 ** min(consecutive_errors, 8)))
                        logger.info(f"[{network}] Waiting {sleep_time}s before retry...")
                        time.sleep(sleep_time)
                else:
                    # 指数退避
                    sleep_time = BLOCK_CHECK_INTERVAL * (2 ** min(consecutive_errors - 1, 5))
                    logger.info(f"[{network}] Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[{network}] Unexpected error in monitoring loop (#{consecutive_errors}): {e}", exc_info=True)

                # 指数退避，但最多等待5分钟
                sleep_time = min(300, BLOCK_CHECK_INTERVAL * (2 ** min(consecutive_errors - 1, 5)))
                logger.info(f"[{network}] Waiting {sleep_time}s before retry...")
                time.sleep(sleep_time)

        logger.info(f"[{network}] Monitoring stopped")

    def monitor_thread_health(self):
        """Monitor health of all monitoring threads and restart if needed"""
        logger.info("Thread health monitor started")

        while self.is_running:
            time.sleep(30)  # 每30秒检查一次

            for network in list(self.monitors.keys()):
                thread = self.threads.get(network)

                if thread and not thread.is_alive():
                    logger.warning(f"[{network}] Thread died unexpectedly, restarting...")

                    try:
                        # 重启线程
                        new_thread = threading.Thread(
                            target=self.monitor_network,
                            args=(network,),
                            daemon=True,
                            name=f"Monitor-{network}"
                        )
                        new_thread.start()
                        self.threads[network] = new_thread
                        logger.info(f"[{network}] Thread restarted successfully")

                    except Exception as e:
                        logger.error(f"[{network}] Failed to restart thread: {e}")

        logger.info("Thread health monitor stopped")

    def run(self):
        """Run the multi-chain monitoring service"""
        if not self.monitors:
            logger.error("No monitors initialized. Exiting.")
            return

        self.is_running = True

        logger.info(f"Starting monitoring for {len(self.monitors)} network(s): {', '.join(self.monitors.keys())}")
        logger.info(f"Check interval: {BLOCK_CHECK_INTERVAL} seconds")

        # Start a thread for each network
        for network in self.monitors.keys():
            thread = threading.Thread(
                target=self.monitor_network,
                args=(network,),
                daemon=True,
                name=f"Monitor-{network}"
            )
            thread.start()
            self.threads[network] = thread
            logger.info(f"[{network}] Thread started")

        # Start health monitor thread
        health_thread = threading.Thread(
            target=self.monitor_thread_health,
            daemon=True,
            name="HealthMonitor"
        )
        health_thread.start()
        logger.info("Health monitor thread started")

        try:
            # Keep main thread alive and wait for KeyboardInterrupt
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

        # Wait for all threads to finish
        for network, thread in self.threads.items():
            logger.info(f"[{network}] Waiting for thread to stop...")
            thread.join(timeout=5)

        logger.info("Multi-Chain Contract Monitor Service stopped")


def main():
    """Main entry point"""
    if not ARKHAM_API_KEY:
        logger.error("ARKHAM_API_KEY not configured. Please set it in config.py or API-Key file")
        sys.exit(1)

    # Parse command line arguments for network selection
    import argparse
    parser = argparse.ArgumentParser(description='Multi-Chain Contract Monitor')
    parser.add_argument('--networks', nargs='+', default=DEFAULT_NETWORKS,
                       help='Networks to monitor (space-separated)')
    parser.add_argument('--all', action='store_true',
                       help='Monitor all available networks')
    args = parser.parse_args()

    # Determine which networks to monitor
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


if __name__ == "__main__":
    main()

