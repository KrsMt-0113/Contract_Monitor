"""
Database module for storing contract deployment information
"""
import sqlite3
from typing import Optional, List, Dict
import logging
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class ContractDatabase:
    def __init__(self, db_path: str, enable_batch_mode: bool = True):
        self.db_path = db_path
        self.enable_batch_mode = enable_batch_mode

        # 批量写入队列和线程
        self.write_queue = Queue() if enable_batch_mode else None
        self.batch_writer_thread = None
        self.is_running = False
        self._stats_lock = threading.Lock()
        self._batch_stats = {'queued': 0, 'written': 0, 'failed': 0}

        self.init_database()

        if enable_batch_mode:
            self._start_batch_writer()

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

    def _start_batch_writer(self):
        """启动批量写入线程"""
        self.is_running = True
        self.batch_writer_thread = threading.Thread(
            target=self._batch_write_worker,
            daemon=True,
            name="DBBatchWriter"
        )
        self.batch_writer_thread.start()
        logger.info("Batch write worker started")

    def _batch_write_worker(self):
        """批量写入工作线程 - 每0.5秒或累积10条记录时写入一次"""
        batch = []
        batch_size = 10
        timeout = 0.5  # 500ms

        while self.is_running:
            try:
                # 尝试从队列获取数据
                try:
                    item = self.write_queue.get(timeout=timeout)
                    if item is None:  # 停止信号
                        break
                    batch.append(item)
                except Empty:
                    pass

                # 如果达到批量大小或超时，执行写入
                if len(batch) >= batch_size or (len(batch) > 0 and self.write_queue.empty()):
                    self._flush_batch(batch)
                    batch = []

            except Exception as e:
                logger.error(f"Error in batch write worker: {e}", exc_info=True)
                batch = []

        # 停止前写入剩余数据
        if batch:
            self._flush_batch(batch)
        logger.info("Batch write worker stopped")

    def _flush_batch(self, batch: List[tuple]):
        """批量写入数据库"""
        if not batch:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        success_count = 0
        failed_count = 0

        try:
            # 使用 executemany 批量插入
            cursor.executemany('''
                INSERT OR IGNORE INTO contracts 
                (contract_address, network, deployer_address, entity_name, entity_id, 
                 block_number, transaction_hash, contract_type, contract_info, factory_address, deployment_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)

            success_count = cursor.rowcount
            conn.commit()

            with self._stats_lock:
                self._batch_stats['written'] += success_count

            logger.debug(f"Batch write completed: {success_count}/{len(batch)} records written")

        except Exception as e:
            logger.error(f"Error in batch write: {e}")
            failed_count = len(batch)
            with self._stats_lock:
                self._batch_stats['failed'] += failed_count
        finally:
            conn.close()

    def save_contract(self, contract_address: str, network: str, deployer_address: str,
                     entity_name: Optional[str], entity_id: Optional[str],
                     block_number: int, transaction_hash: str,
                     contract_type: Optional[str] = None,
                     contract_info: Optional[str] = None,
                     factory_address: Optional[str] = None,
                     deployment_type: Optional[str] = None) -> bool:
        """
        Save contract deployment information
        如果启用批量模式，将数据加入队列；否则立即写入
        Returns True if queued/saved successfully, False if already exists
        """
        data = (contract_address, network, deployer_address, entity_name, entity_id,
                block_number, transaction_hash, contract_type, contract_info, factory_address, deployment_type)

        if self.enable_batch_mode:
            # 批量模式：加入队列
            self.write_queue.put(data)
            with self._stats_lock:
                self._batch_stats['queued'] += 1

            log_msg = f"[{network}] ⊕ Queued contract {contract_address}"
            if contract_type:
                log_msg += f" (Type: {contract_type})"
            if entity_name:
                log_msg += f" (Entity: {entity_name})"
            logger.debug(log_msg)
            return True
        else:
            # 立即写入模式（原有逻辑）
            return self._save_contract_immediate(contract_address, network, deployer_address,
                                                 entity_name, entity_id, block_number,
                                                 transaction_hash, contract_type, contract_info,
                                                 factory_address, deployment_type)

    def _save_contract_immediate(self, contract_address: str, network: str, deployer_address: str,
                                 entity_name: Optional[str], entity_id: Optional[str],
                                 block_number: int, transaction_hash: str,
                                 contract_type: Optional[str] = None,
                                 contract_info: Optional[str] = None,
                                 factory_address: Optional[str] = None,
                                 deployment_type: Optional[str] = None) -> bool:
        """立即写入单条记录（原有逻辑）"""
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

    def get_batch_stats(self) -> Dict:
        """获取批量写入统计信息"""
        if not self.enable_batch_mode:
            return {'batch_mode': False}
        with self._stats_lock:
            return self._batch_stats.copy()

    def close(self):
        """关闭数据库和批量写入线程"""
        if self.enable_batch_mode and self.is_running:
            logger.info("Stopping batch write worker...")
            self.is_running = False
            self.write_queue.put(None)  # 发送停止信号
            if self.batch_writer_thread:
                self.batch_writer_thread.join(timeout=5)
            logger.info(f"Database closed. Final stats: {self.get_batch_stats()}")

