"""
Contract type analyzer - identifies contract types by bytecode and ABI
"""
import logging
from typing import Dict, Optional
from web3 import Web3
import json

logger = logging.getLogger(__name__)


class ContractAnalyzer:
    """分析合约类型和提取合约信息"""
    
    # ERC20 标准函数签名
    ERC20_SIGNATURES = {
        '0x18160ddd': 'totalSupply()',
        '0x70a08231': 'balanceOf(address)',
        '0xa9059cbb': 'transfer(address,uint256)',
        '0x23b872dd': 'transferFrom(address,address,uint256)',
        '0x095ea7b3': 'approve(address,uint256)',
        '0xdd62ed3e': 'allowance(address,address)'
    }
    
    # ERC721 (NFT) 标准函数签名
    ERC721_SIGNATURES = {
        '0x70a08231': 'balanceOf(address)',
        '0x6352211e': 'ownerOf(uint256)',
        '0x42842e0e': 'safeTransferFrom(address,address,uint256)',
        '0x23b872dd': 'transferFrom(address,address,uint256)',
        '0x095ea7b3': 'approve(address,uint256)',
        '0x081812fc': 'getApproved(uint256)',
        '0xa22cb465': 'setApprovalForAll(address,bool)'
    }
    
    # ERC1155 (多代币) 标准函数签名
    ERC1155_SIGNATURES = {
        '0x00fdd58e': 'balanceOf(address,uint256)',
        '0x4e1273f4': 'balanceOfBatch(address[],uint256[])',
        '0xf242432a': 'safeTransferFrom(address,address,uint256,uint256,bytes)',
        '0x2eb2c2d6': 'safeBatchTransferFrom(address,address,uint256[],uint256[],bytes)',
        '0xa22cb465': 'setApprovalForAll(address,bool)'
    }
    
    # Uniswap/Sushiswap 路由合约
    ROUTER_SIGNATURES = {
        '0x38ed1739': 'swapExactTokensForTokens',
        '0x8803dbee': 'swapTokensForExactTokens',
        '0x7ff36ab5': 'swapExactETHForTokens',
        '0xfb3bdb41': 'swapETHForExactTokens',
        '0x18cbafe5': 'swapExactTokensForETH',
        '0x4a25d94a': 'swapTokensForExactETH',
        '0x02751cec': 'removeLiquidity',
        '0xe8e33700': 'addLiquidity'
    }
    
    # Uniswap V2/V3 Pool/Pair
    POOL_SIGNATURES = {
        '0x0902f1ac': 'getReserves()',
        '0x6a627842': 'mint(address)',
        '0x89afcb44': 'burn(address)',
        '0x022c0d9f': 'swap(uint256,uint256,address,bytes)',
        '0x128acb08': 'slot0()',
        '0xd21220a7': 'token0()',
        '0x0dfe1681': 'token1()'
    }
    
    # 代理合约 (Proxy)
    PROXY_SIGNATURES = {
        '0x5c60da1b': 'implementation()',
        '0x3659cfe6': 'upgradeTo(address)',
        '0x4f1ef286': 'upgradeToAndCall(address,bytes)',
        '0x8f283970': 'changeAdmin(address)',
        '0xf851a440': 'admin()'
    }
    
    # Staking/Farming 合约
    STAKING_SIGNATURES = {
        '0xa694fc3a': 'stake(uint256)',
        '0x2e1a7d4d': 'withdraw(uint256)',
        '0x3d18b912': 'getReward()',
        '0xe9fad8ee': 'exit()',
        '0x8b876347': 'earned(address)',
        '0x70897b23': 'rewardRate()'
    }
    
    # Multisig 钱包
    MULTISIG_SIGNATURES = {
        '0xc6427474': 'submitTransaction',
        '0xc01a8c84': 'confirmTransaction',
        '0x20ea8d86': 'revokeConfirmation',
        '0xee22610b': 'executeTransaction',
        '0x025e7c27': 'owners(uint256)',
        '0x54741525': 'required()'
    }
    
    # Timelock 时间锁
    TIMELOCK_SIGNATURES = {
        '0x3a66f901': 'queueTransaction',
        '0x591fcdfe': 'executeTransaction',
        '0xc1a287e2': 'cancelTransaction',
        '0x7d645fab': 'setPendingAdmin',
        '0x26782247': 'acceptAdmin'
    }
    
    # Factory 工厂合约
    FACTORY_SIGNATURES = {
        '0xc9c65396': 'createPair(address,address)',
        '0xa1671295': 'createPool(address,address,uint24)',
        '0x13af4035': 'allPairsLength()',
        '0x1e3dd18b': 'allPairs(uint256)',
        '0x5c60da1b': 'implementation()',
        '0x4e1273f4': 'deploy(bytes32,bytes)'
    }
    
    # EIP-1167 最小代理合约模式
    MINIMAL_PROXY_PATTERN = '0x363d3d373d3d3d363d73'
    
    # Clone Factory 克隆工厂模式
    CLONE_FACTORY_PATTERN = '0x3d602d80600a3d3981f3'
    
    # 标准 ERC20 ABI
    ERC20_ABI = [
        {'constant': True, 'inputs': [], 'name': 'name', 'outputs': [{'name': '', 'type': 'string'}], 'type': 'function'},
        {'constant': True, 'inputs': [], 'name': 'symbol', 'outputs': [{'name': '', 'type': 'string'}], 'type': 'function'},
        {'constant': True, 'inputs': [], 'name': 'decimals', 'outputs': [{'name': '', 'type': 'uint8'}], 'type': 'function'},
        {'constant': True, 'inputs': [], 'name': 'totalSupply', 'outputs': [{'name': '', 'type': 'uint256'}], 'type': 'function'}
    ]
    
    # 标准 ERC721 ABI
    ERC721_ABI = [
        {'constant': True, 'inputs': [], 'name': 'name', 'outputs': [{'name': '', 'type': 'string'}], 'type': 'function'},
        {'constant': True, 'inputs': [], 'name': 'symbol', 'outputs': [{'name': '', 'type': 'string'}], 'type': 'function'},
        {'constant': True, 'inputs': [], 'name': 'totalSupply', 'outputs': [{'name': '', 'type': 'uint256'}], 'type': 'function'}
    ]

    def __init__(self, w3: Web3):
        self.w3 = w3
    
    def analyze_bytecode(self, bytecode: str) -> Dict[str, any]:
        """分析合约字节码，识别合约类型"""
        if not bytecode or bytecode == '0x':
            return {
                'type': 'EOA',
                'all_types': ['EOA'],
                'confidence': 1.0,
                'scores': {}
            }
        
        bytecode = bytecode.lower()
        contract_types = []
        scores = {}
        
        # 优先检查最小代理模式（EIP-1167）
        if self.MINIMAL_PROXY_PATTERN.lower() in bytecode:
            contract_types.append('MinimalProxy')
            scores['MinimalProxy'] = 1.0
        
        # 检查克隆工厂模式
        if self.CLONE_FACTORY_PATTERN.lower() in bytecode:
            contract_types.append('CloneFactory')
            scores['CloneFactory'] = 1.0
        
        # 检查各种合约类型
        type_checks = [
            ('ERC20', self.ERC20_SIGNATURES, 4),
            ('ERC721', self.ERC721_SIGNATURES, 4),
            ('ERC1155', self.ERC1155_SIGNATURES, 2),
            ('Router', self.ROUTER_SIGNATURES, 2),
            ('Pool', self.POOL_SIGNATURES, 2),
            ('Factory', self.FACTORY_SIGNATURES, 2),
            ('Proxy', self.PROXY_SIGNATURES, 1),
            ('Staking', self.STAKING_SIGNATURES, 2),
            ('Multisig', self.MULTISIG_SIGNATURES, 3),
            ('Timelock', self.TIMELOCK_SIGNATURES, 2)
        ]
        
        for type_name, signatures, threshold in type_checks:
            matches = sum(1 for sig in signatures.keys() if sig in bytecode)
            if matches >= threshold:
                contract_types.append(type_name)
                scores[type_name] = matches / len(signatures)
        
        # 确定主要类型
        if contract_types:
            primary_type = max(scores, key=scores.get)
            confidence = scores[primary_type]
        else:
            primary_type = 'Unknown'
            confidence = 0.0
            contract_types = ['Unknown']
        
        return {
            'type': primary_type,
            'all_types': contract_types,
            'confidence': confidence,
            'scores': scores
        }
    
    def get_contract_info(self, contract_address: str) -> Dict[str, any]:
        """获取合约完整信息（包括类型识别）"""
        try:
            bytecode = self.w3.eth.get_code(contract_address).hex()
            type_info = self.analyze_bytecode(bytecode)
            
            additional_info = {}
            if 'ERC20' in type_info['all_types']:
                additional_info = self._get_token_info(contract_address)
            elif 'ERC721' in type_info['all_types']:
                additional_info = self._get_nft_info(contract_address)
            elif 'Pool' in type_info['all_types']:
                additional_info = self._get_pool_info(contract_address)
            
            return {
                **type_info,
                **additional_info,
                'bytecode_size': len(bytecode) // 2 - 1
            }
        except Exception as e:
            logger.error(f"Error analyzing contract {contract_address}: {e}")
            return {
                'type': 'Error',
                'all_types': ['Error'],
                'confidence': 0.0,
                'scores': {},
                'error': str(e)
            }
    
    def _get_token_info(self, contract_address: str) -> Dict[str, any]:
        """获取ERC20代币的额外信息"""
        info = {}
        try:
            contract = self.w3.eth.contract(address=contract_address, abi=self.ERC20_ABI)
            
            try:
                info['token_name'] = contract.functions.name().call()
            except:
                pass
            
            try:
                info['token_symbol'] = contract.functions.symbol().call()
            except:
                pass
            
            try:
                info['token_decimals'] = contract.functions.decimals().call()
            except:
                pass
            
            try:
                total_supply = contract.functions.totalSupply().call()
                decimals = info.get('token_decimals', 18)
                info['total_supply'] = total_supply / (10 ** decimals)
                info['total_supply_raw'] = str(total_supply)
            except:
                pass
        except Exception as e:
            logger.debug(f"Error fetching token info for {contract_address}: {e}")
        
        return info
    
    def _get_nft_info(self, contract_address: str) -> Dict[str, any]:
        """获取ERC721 NFT的额外信息"""
        info = {}
        try:
            contract = self.w3.eth.contract(address=contract_address, abi=self.ERC721_ABI)
            
            try:
                info['nft_name'] = contract.functions.name().call()
            except:
                pass
            
            try:
                info['nft_symbol'] = contract.functions.symbol().call()
            except:
                pass
            
            try:
                info['nft_total_supply'] = contract.functions.totalSupply().call()
            except:
                pass
        except Exception as e:
            logger.debug(f"Error fetching NFT info for {contract_address}: {e}")
        
        return info
    
    def _get_pool_info(self, contract_address: str) -> Dict[str, any]:
        """获取流动性池信息"""
        info = {}
        try:
            pool_abi = [
                {'constant': True, 'inputs': [], 'name': 'token0', 'outputs': [{'name': '', 'type': 'address'}], 'type': 'function'},
                {'constant': True, 'inputs': [], 'name': 'token1', 'outputs': [{'name': '', 'type': 'address'}], 'type': 'function'},
                {'constant': True, 'inputs': [], 'name': 'getReserves', 'outputs': [
                    {'name': 'reserve0', 'type': 'uint112'},
                    {'name': 'reserve1', 'type': 'uint112'},
                    {'name': 'blockTimestampLast', 'type': 'uint32'}
                ], 'type': 'function'}
            ]
            
            contract = self.w3.eth.contract(address=contract_address, abi=pool_abi)
            
            try:
                info['pool_token0'] = contract.functions.token0().call()
            except:
                pass
            
            try:
                info['pool_token1'] = contract.functions.token1().call()
            except:
                pass
            
            try:
                reserves = contract.functions.getReserves().call()
                info['pool_reserve0'] = str(reserves[0])
                info['pool_reserve1'] = str(reserves[1])
            except:
                pass
        except Exception as e:
            logger.debug(f"Error fetching pool info for {contract_address}: {e}")
        
        return info
    
    def get_implementation_address(self, contract_address: str) -> Optional[str]:
        """获取代理合约的实现地址"""
        try:
            proxy_abi = [
                {'constant': True, 'inputs': [], 'name': 'implementation', 
                 'outputs': [{'name': '', 'type': 'address'}], 'type': 'function'}
            ]
            contract = self.w3.eth.contract(address=contract_address, abi=proxy_abi)
            impl = contract.functions.implementation().call()
            return impl if impl != '0x0000000000000000000000000000000000000000' else None
        except:
            # 尝试从存储槽读取 (EIP-1967)
            try:
                storage_slot = '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc'
                storage_value = self.w3.eth.get_storage_at(contract_address, storage_slot)
                impl_address = '0x' + storage_value.hex()[-40:]
                if impl_address != '0x0000000000000000000000000000000000000000':
                    return impl_address
            except:
                pass
        return None
    
    def format_contract_info(self, contract_info: Dict) -> str:
        """格式化合约信息为易读字符串"""
        lines = [f"Type: {contract_info.get('type', 'Unknown')}"]
        
        if contract_info.get('confidence'):
            lines.append(f"Confidence: {contract_info['confidence']:.1%}")
        
        if len(contract_info.get('all_types', [])) > 1:
            lines.append(f"All Types: {', '.join(contract_info['all_types'])}")
        
        if 'token_symbol' in contract_info:
            token_info = f"{contract_info.get('token_name', 'N/A')} ({contract_info['token_symbol']})"
            if 'total_supply' in contract_info:
                token_info += f" | Supply: {contract_info['total_supply']:,.2f}"
            lines.append(f"Token: {token_info}")
        
        if 'nft_symbol' in contract_info:
            nft_info = f"{contract_info.get('nft_name', 'N/A')} ({contract_info['nft_symbol']})"
            if 'nft_total_supply' in contract_info:
                nft_info += f" | Total: {contract_info['nft_total_supply']}"
            lines.append(f"NFT: {nft_info}")
        
        if 'pool_token0' in contract_info and 'pool_token1' in contract_info:
            lines.append(f"Pool: {contract_info['pool_token0'][:8]}.../{contract_info['pool_token1'][:8]}...")
        
        return " | ".join(lines)

