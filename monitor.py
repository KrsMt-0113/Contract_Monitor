"""
Main contract monitoring service
"""
import logging
import time
import sys
from typing import Optional

from config import (
    RPC_ENDPOINTS, ARKHAM_API_KEY, ARKHAM_API_URL,
    DB_PATH, BLOCK_CHECK_INTERVAL, BATCH_SIZE,
    LOG_FILE, LOG_LEVEL
)
from blockchain_monitor import BlockchainMonitor
from arkham_client import ArkhamClient
from database import ContractDatabase

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


class ContractMonitorService:
    def __init__(self, rpc_url: str, arkham_api_key: str):
        logger.info("Initializing Contract Monitor Service")

        self.blockchain_monitor = BlockchainMonitor(rpc_url)
        self.arkham_client = ArkhamClient(arkham_api_key, ARKHAM_API_URL)
        self.database = ContractDatabase(DB_PATH)

        self.is_running = False

    def process_deployment(self, deployment: dict):
        """Process a single contract deployment"""
        contract_address = deployment['contract_address']
        deployer_address = deployment['deployer_address']

        logger.info(f"Processing deployment: {contract_address}")

        # Query Arkham API for deployer information
        address_info = self.arkham_client.get_address_info(deployer_address)
        entity_name, entity_id = self.arkham_client.extract_entity_info(address_info)

        # Save to database
        self.database.save_contract(
            contract_address=contract_address,
            deployer_address=deployer_address,
            entity_name=entity_name,
            entity_id=entity_id,
            block_number=deployment['block_number'],
            transaction_hash=deployment['transaction_hash']
        )

        if entity_name:
            logger.info(f"✓ Contract {contract_address} belongs to entity: {entity_name}")
        else:
            logger.info(f"○ Contract {contract_address} - no entity found")

    def initialize_start_block(self) -> int:
        """Initialize the starting block for monitoring"""
        last_processed = self.database.get_last_processed_block()

        if last_processed:
            logger.info(f"Resuming from block {last_processed + 1}")
            return last_processed + 1
        else:
            # Start from current block if no previous state
            current_block = self.blockchain_monitor.get_latest_block_number()
            logger.info(f"Starting fresh from current block {current_block}")
            return current_block

    def run(self, start_block: Optional[int] = None):
        """Run the monitoring service"""
        self.is_running = True

        if start_block is None:
            current_block = self.initialize_start_block()
        else:
            current_block = start_block
            logger.info(f"Starting from specified block {start_block}")

        logger.info("Contract Monitor Service started")
        logger.info(f"Monitoring for new contract deployments every {BLOCK_CHECK_INTERVAL} seconds")

        try:
            while self.is_running:
                try:
                    latest_block = self.blockchain_monitor.get_latest_block_number()

                    if latest_block > current_block:
                        # Process blocks in batches
                        end_block = min(current_block + BATCH_SIZE - 1, latest_block)

                        logger.info(f"Processing blocks {current_block} to {end_block}")

                        deployments = self.blockchain_monitor.get_deployments_in_range(
                            current_block, end_block
                        )

                        logger.info(f"Found {len(deployments)} contract deployment(s)")

                        for deployment in deployments:
                            self.process_deployment(deployment)

                        # Update last processed block
                        self.database.update_last_processed_block(end_block)
                        current_block = end_block + 1

                    else:
                        logger.debug(f"No new blocks. Current: {current_block}, Latest: {latest_block}")

                    # Wait before checking again
                    time.sleep(BLOCK_CHECK_INTERVAL)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                    time.sleep(BLOCK_CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()

    def stop(self):
        """Stop the monitoring service"""
        self.is_running = False
        logger.info("Contract Monitor Service stopped")


def main():
    """Main entry point"""
    if not ARKHAM_API_KEY:
        logger.error("ARKHAM_API_KEY not configured. Please set it in config.py or API-Key file")
        sys.exit(1)

    rpc_urls = RPC_ENDPOINTS['ethereum']

    try:
        service = ContractMonitorService(rpc_urls, ARKHAM_API_KEY)
        service.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
