"""
Configuration file for Contract Monitor
"""
import os

# Public RPC endpoints for all Arkham-supported networks (with fallbacks)
RPC_ENDPOINTS = {
    'ethereum': [
        'https://eth.llamarpc.com',
        'https://rpc.ankr.com/eth',
        'https://ethereum.publicnode.com',
        'https://1rpc.io/eth',
        'https://eth.drpc.org'
    ],
    'arbitrum': [
        'https://arbitrum.llamarpc.com',
        'https://rpc.ankr.com/arbitrum',
        'https://arbitrum.publicnode.com',
        'https://1rpc.io/arb',
        'https://arb1.arbitrum.io/rpc'
    ],
    'base': [
        'https://base.llamarpc.com',
        'https://rpc.ankr.com/base',
        'https://base.publicnode.com',
        'https://1rpc.io/base',
        'https://mainnet.base.org'
    ],
    'optimism': [
        'https://optimism.llamarpc.com',
        'https://rpc.ankr.com/optimism',
        'https://optimism.publicnode.com',
        'https://1rpc.io/op',
        'https://mainnet.optimism.io'
    ],
    'polygon': [
        'https://polygon.llamarpc.com',
        'https://rpc.ankr.com/polygon',
        'https://polygon.publicnode.com',
        'https://1rpc.io/matic',
        'https://polygon-rpc.com'
    ],
    'bsc': [
        'https://bsc.llamarpc.com',
        'https://rpc.ankr.com/bsc',
        'https://bsc.publicnode.com',
        'https://1rpc.io/bnb',
        'https://bsc-dataseed.binance.org'
    ],
    'avalanche': [
        'https://avalanche.publicnode.com',
        'https://rpc.ankr.com/avalanche',
        'https://1rpc.io/avax/c',
        'https://api.avax.network/ext/bc/C/rpc'
    ],
    'blast': [
        'https://rpc.ankr.com/blast',
        'https://blast.publicnode.com',
        'https://rpc.blast.io',
        'https://blast.din.dev/rpc'
    ],
    'linea': [
        'https://rpc.linea.build',
        'https://linea.publicnode.com',
        'https://1rpc.io/linea',
        'https://rpc.ankr.com/linea'
    ],
    'sonic': [
        'https://rpc.soniclabs.com',
        'https://rpc.ankr.com/sonic'
    ],
    'flare': [
        'https://flare-api.flare.network/ext/C/rpc',
        'https://rpc.ankr.com/flare'
    ],
    # Non-EVM chains (special handling required)
    'bitcoin': [],  # Bitcoin uses different API (not Web3)
    'solana': [
        'https://api.mainnet-beta.solana.com',
        'https://rpc.ankr.com/solana'
    ],
    'ton': [],  # TON uses different API
    'tron': [
        'https://api.trongrid.io'
    ]
}

# Default networks to monitor (EVM-compatible chains)
DEFAULT_NETWORKS = [
    'ethereum', 'arbitrum', 'base', 'optimism',
    'polygon', 'bsc', 'avalanche', 'blast', 'linea'
]

# Networks that require special handling (non-EVM)
NON_EVM_NETWORKS = ['bitcoin', 'solana', 'ton', 'tron']

# Arkham API Configuration
ARKHAM_API_URL = 'https://api.arkm.com'
ARKHAM_API_KEY = os.getenv('ARKHAM_API_KEY', '')

# Load API key from file if not in environment
if not ARKHAM_API_KEY:
    try:
        with open('../API-Key', 'r') as f:
            ARKHAM_API_KEY = f.read().strip()
    except FileNotFoundError:
        print("Warning: API-Key file not found")

# Database Configuration
DB_PATH = 'contract_monitor.db'

# Monitoring Configuration
BLOCK_CHECK_INTERVAL = 12  # seconds between block checks
BATCH_SIZE = 10  # number of blocks to process in one batch

# Logging Configuration
LOG_FILE = 'contract_monitor.log'
LOG_LEVEL = 'INFO'
