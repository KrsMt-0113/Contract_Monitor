# Contract Monitor

High-performance multi-chain smart contract deployment monitoring system. Real-time detection of new contract deployments across multiple blockchain networks with entity identification via Arkham API.

## Core Features

### Monitoring Capabilities
- Multi-chain support: Monitor 11 EVM-compatible blockchain networks simultaneously
- Real-time detection: Second-level contract deployment event detection
- Smart identification: Automatic detection of direct deployments and factory contract deployments
- Contract analysis: Intelligent contract type identification (ERC20, ERC721, Proxy, DEX, etc.)
- Entity recognition: Deployer entity identification through Arkham API integration

### Performance Optimizations
- Async API calls: Using aiohttp for asynchronous Arkham API calls (3-5x performance improvement)
- Batch database writes: Queue-based batch writes to reduce lock contention (5-10x performance improvement)
- Smart caching: In-memory caching of API query results (1-hour TTL, 50%+ API call reduction)
- Parallel processing: Multi-threaded concurrent contract analysis and deployment processing
- Overall throughput: 5-10x performance increase

### Reliability Features
- RPC node failover: Automatic switching between multiple backup nodes
- Resume capability: Continue from last position after service restart
- Rate limiting: Compliance with Arkham API limits (20 req/s)
- Comprehensive logging: Detailed operation and error logs
- Graceful shutdown: Wait for batch writes to complete before exit

## Supported Blockchain Networks

### EVM-Compatible Chains (Supported)
- Ethereum - Ethereum Mainnet
- Arbitrum - Layer 2 Scaling Solution
- Base - Coinbase Layer 2
- Optimism - Optimistic Rollup
- Polygon - Sidechain Network
- BSC - Binance Smart Chain
- Avalanche - C-Chain
- Blast - Layer 2
- Linea - zkEVM Layer 2
- Sonic - High-Performance Chain
- Flare - Smart Contract Platform

### Non-EVM Chains (Planned)
- Bitcoin
- Solana
- TON - Telegram Open Network
- Tron

## Project Structure

```
Contract Monitor/
├── README.md                    # Project documentation
├── OPTIMIZATION_SUMMARY.md      # Performance optimization details
├── requirements.txt             # Python dependencies
├── config.py                    # Configuration file
├── main.py                      # Main entry point (multi-chain monitoring)
├── blockchain_monitor.py        # Blockchain monitoring core
├── contract_analyzer.py         # Contract type analyzer
├── arkham_client_async.py       # Async Arkham API client (optimized)
├── arkham_client.py             # Sync Arkham API client (legacy)
├── database.py                  # Database operations (batch write support)
├── contract_monitor.db          # SQLite database (generated at runtime)
├── contract_monitor.log         # Log file (generated at runtime)
└── CONTRACT_TYPE_GUIDE.md       # Contract type identification guide
```

## Quick Start

### 1. Install Dependencies

```bash
cd "Contract Monitor"
pip install -r requirements.txt
```

Required packages:
- `web3` - Ethereum interaction
- `aiohttp` - Async HTTP client (performance optimization)
- `requests` - HTTP client (legacy support)

### 2. Configure API Key

Ensure the parent directory has an `API-Key` file containing your Arkham API Key:
```
YOUR_ARKHAM_API_KEY_HERE
```

Alternatively, configure `ARKHAM_API_KEY` directly in `config.py`.

### 3. Start Monitoring

**Monitor all default networks** (recommended):
```bash
python main.py
```
Default networks: Ethereum, Arbitrum, Base, Optimism, Polygon, BSC, Avalanche, Blast, Linea

**Monitor specific networks**:
```bash
python main.py --networks ethereum base arbitrum
```

**Monitor all supported networks**:
```bash
python main.py --all
```

### 4. Service Features

Once started, the service will:
- Start monitoring from the latest block (first run) or resume from last position (subsequent runs)
- Concurrently monitor multiple networks using multi-threading
- Automatically detect both direct and factory contract deployments
- Intelligently analyze contract types (ERC20, NFT, DEX, etc.)
- Asynchronously query Arkham API for entity identification
- Batch write to database for improved performance
- Automatically save progress for resume capability
- Gracefully shutdown on exit (Ctrl+C waits for queue to flush)

### 5. View Logs

Monitor logs in real-time:
```bash
tail -f contract_monitor.log
```

Key log indicators:
- `Queued contract` - Contract added to batch write queue
- `Contract ... belongs to entity` - Known entity contract discovered
- `Cache hit` - Cache hit, API call saved
- `Batch write completed` - Batch write operation completed

## Configuration

Settings in `config.py`:

- `RPC_ENDPOINTS`: RPC node addresses (default: Cloudflare public nodes)
- `BLOCK_CHECK_INTERVAL`: Block check interval in seconds
- `BATCH_SIZE`: Number of blocks to process per batch
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Database Structure

### contracts table
Stores contract deployment information:
- `contract_address`: Contract address
- `network`: Blockchain network name
- `deployer_address`: Deployer address
- `entity_name`: Entity name (if belongs to known entity)
- `entity_id`: Entity ID
- `block_number`: Deployment block number
- `transaction_hash`: Transaction hash
- `contract_type`: Contract type (ERC20, ERC721, Proxy, etc.)
- `contract_info`: Detailed contract information (JSON)
- `factory_address`: Factory contract address (if factory deployment)
- `deployment_type`: Deployment type (direct/factory)
- `timestamp`: Record timestamp

### monitoring_state table
Stores monitoring state:
- `network`: Network name
- `last_processed_block`: Last processed block number
- `updated_at`: Last update timestamp

## Important Notes

1. **API Rate Limiting**: Arkham API standard limit is 20 requests per second, the program implements automatic rate limiting
2. **RPC Access**: Uses Cloudflare public nodes by default, configure private nodes for higher performance if needed
3. **Data Persistence**: All data is saved in SQLite database, historical records can be queried anytime
4. **Logging**: All operations are logged to `contract_monitor.log` file
5. **Performance**: With optimizations enabled, the system achieves 5-10x throughput improvement over baseline

## Troubleshooting

If you encounter connection issues:
1. Check network connectivity
2. Verify API Key is correct
3. Review log file for detailed error information
4. Ensure RPC endpoints are accessible
5. Check if the blockchain network is experiencing issues

## Extension Capabilities

The system can be easily extended to support:
- Additional blockchain networks
- Webhook notifications for real-time alerts
- Advanced entity analysis and relationship mapping
- Data export to CSV/JSON formats
- Custom contract type detection rules
- Integration with other analytics platforms

## Performance Optimizations

The system includes several performance optimizations:
- **Asynchronous API calls**: Non-blocking Arkham API queries using aiohttp
- **Batch database operations**: Queue-based writes to minimize database locks
- **Intelligent caching**: 1-hour TTL cache for API responses
- **Multi-threaded processing**: Parallel contract analysis across networks
- **RPC connection pooling**: Efficient reuse of blockchain connections

For detailed information about optimizations, see `OPTIMIZATION_SUMMARY.md`.

## License

This project is for monitoring and analysis purposes. Please ensure compliance with all applicable terms of service for RPC providers and APIs used.

