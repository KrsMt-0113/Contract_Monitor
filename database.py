"""
Database module for storing contract deployment information
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ContractDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create contracts table with network field and contract type
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_address TEXT NOT NULL,
                network TEXT NOT NULL,
                deployer_address TEXT NOT NULL,
                entity_name TEXT,
                entity_id TEXT,
                block_number INTEGER NOT NULL,
                transaction_hash TEXT NOT NULL,
                contract_type TEXT,
                contract_info TEXT,
                factory_address TEXT,
                deployment_type TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(contract_address, network)
            )
        ''')

        # Create monitoring state table with network field
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_state (
                network TEXT PRIMARY KEY,
                last_processed_block INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_deployer 
            ON contracts(deployer_address)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_entity 
            ON contracts(entity_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_network 
            ON contracts(network)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_contract_type 
            ON contracts(contract_type)
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def save_contract(self, contract_address: str, network: str, deployer_address: str,
                     entity_name: Optional[str], entity_id: Optional[str],
                     block_number: int, transaction_hash: str,
                     contract_type: Optional[str] = None,
                     contract_info: Optional[str] = None,
                     factory_address: Optional[str] = None,
                     deployment_type: Optional[str] = None) -> bool:
        """
        Save contract deployment information
        Returns True if saved successfully, False if already exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO contracts 
                (contract_address, network, deployer_address, entity_name, entity_id, 
                 block_number, transaction_hash, contract_type, contract_info, factory_address, deployment_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (contract_address, network, deployer_address, entity_name, entity_id,
                  block_number, transaction_hash, contract_type, contract_info, factory_address, deployment_type))
            conn.commit()

            # Enhanced logging with contract type
            log_msg = f"[{network}] ✓ Saved contract {contract_address}"
            if contract_type:
                log_msg += f" (Type: {contract_type})"
            if deployment_type and deployment_type != 'direct':
                log_msg += f" (Deployment: {deployment_type})"
            if factory_address:
                log_msg += f" (Factory: {factory_address[:10]}...)"
            if entity_name:
                log_msg += f" (Entity: {entity_name})"
            logger.info(log_msg)
            return True
        except sqlite3.IntegrityError:
            logger.debug(f"[{network}] ⊗ Contract {contract_address} already exists in database (skipped)")
            return False
        finally:
            conn.close()

    def get_last_processed_block(self, network: str) -> Optional[int]:
        """Get the last processed block number for a specific network"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT last_processed_block FROM monitoring_state WHERE network = ?', (network,))
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def update_last_processed_block(self, network: str, block_number: int):
        """Update the last processed block number for a specific network"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO monitoring_state (network, last_processed_block, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(network) DO UPDATE SET 
                last_processed_block = excluded.last_processed_block,
                updated_at = CURRENT_TIMESTAMP
        ''', (network, block_number))

        conn.commit()
        conn.close()

    def get_contracts_by_entity(self, entity_name: str, network: Optional[str] = None) -> List[Dict]:
        """Get all contracts deployed by a specific entity"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if network:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE entity_name = ? AND network = ?
                ORDER BY block_number DESC
            ''', (entity_name, network))
        else:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE entity_name = ? 
                ORDER BY block_number DESC
            ''', (entity_name,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_all_entity_contracts(self, network: Optional[str] = None) -> List[Dict]:
        """Get all contracts that belong to known entities"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if network:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE entity_name IS NOT NULL AND network = ?
                ORDER BY block_number DESC
            ''', (network,))
        else:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE entity_name IS NOT NULL 
                ORDER BY block_number DESC
            ''')

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_stats_by_network(self) -> Dict[str, Dict]:
        """Get statistics for each network"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                network,
                COUNT(*) as total_contracts,
                COUNT(CASE WHEN entity_name IS NOT NULL THEN 1 END) as entity_contracts,
                MAX(block_number) as latest_block
            FROM contracts
            GROUP BY network
        ''')

        results = {row['network']: dict(row) for row in cursor.fetchall()}
        conn.close()

        return results

    def get_contracts_by_factory(self, factory_address: str, network: Optional[str] = None) -> List[Dict]:
        """Get all contracts deployed by a specific factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if network:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE factory_address = ? AND network = ?
                ORDER BY block_number DESC
            ''', (factory_address, network))
        else:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE factory_address = ?
                ORDER BY block_number DESC
            ''', (factory_address,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_contracts_by_deployment_type(self, deployment_type: str, network: Optional[str] = None) -> List[Dict]:
        """Get all contracts by deployment type (direct/factory)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if network:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE deployment_type = ? AND network = ?
                ORDER BY block_number DESC
            ''', (deployment_type, network))
        else:
            cursor.execute('''
                SELECT * FROM contracts 
                WHERE deployment_type = ?
                ORDER BY block_number DESC
            ''', (deployment_type,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

