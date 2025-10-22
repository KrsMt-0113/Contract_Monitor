# 合约类型识别功能使用指南

## 功能概述

系统现在可以自动识别部署的合约类型，包括：

### 支持的合约类型

1. **ERC20** - 代币合约
   - 自动提取：代币名称、符号、小数位、总供应量
   
2. **ERC721** - NFT 合约
   - 自动提取：NFT 名称、符号、总供应量

3. **ERC1155** - 多代币标准

4. **Router** - DEX 路由合约（Uniswap/Sushiswap 等）

5. **Pool** - 流动性池/交易对
   - 自动提取：token0、token1 地址

6. **Proxy** - 代理合约（可升级合约）

7. **Staking** - 质押/挖矿合约

8. **Multisig** - 多签钱包

9. **Timelock** - 时间锁合约

10. **Unknown** - 未识别类型

## 工作原理

系统通过以下方式识别合约类型：

1. **字节码分析**：检测合约字节码中的函数签名
2. **标准接口检测**：匹配 ERC20、ERC721 等标准接口
3. **置信度评分**：根据匹配的函数数量计算可信度
4. **信息提取**：对识别的代币/NFT 合约，自动读取名称、符号等信息

## 使用方法

### 1. 启动监控（自动识别）

```bash
# 监控时会自动分析合约类型
python monitor_multichain.py --networks ethereum base arbitrum
```

日志示例：
```
[ethereum] Processing deployment: 0x1234...
[ethereum] Type: ERC20 | Confidence: 100.0% | Token: Tether USD (USDT) | Supply: 1,000,000.00
[ethereum] ✓ Contract 0x1234... belongs to entity: Tether
```

### 2. 查询特定类型的合约

```bash
# 查看所有 ERC20 代币合约
python query.py type ERC20

# 查看特定网络的 ERC20 合约
python query.py type ERC20 ethereum

# 查看所有 Router 合约
python query.py type Router

# 查看所有 NFT 合约
python query.py type ERC721
```

### 3. 查看实体的合约（包含类型）

```bash
# 查看特定实体部署的合约（显示类型信息）
python query.py entity "Uniswap"

# 查看所有已知实体的合约（包含类型列）
python query.py all
```

### 4. 查看统计信息

```bash
python query.py stats
```

## 数据库结构

新增字段：

- `contract_type` - 合约主要类型（如 ERC20、Router 等）
- `contract_info` - JSON 格式存储详细信息
  - type, all_types, confidence
  - token_name, token_symbol, token_decimals, total_supply（ERC20）
  - nft_name, nft_symbol, nft_total_supply（ERC721）
  - pool_token0, pool_token1（Pool）

## 示例输出

### 监控日志
```
2025-10-22 13:30:45 - [ethereum] Processing deployment: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
2025-10-22 13:30:46 - [ethereum] Type: ERC20 | Confidence: 100.0% | Token: USD Coin (USDC) | Supply: 40,000,000,000.00
2025-10-22 13:30:47 - [ethereum] ✓ Contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 belongs to entity: Circle
```

### 查询结果
```bash
$ python query.py type ERC20 ethereum

=== ERC20 Contracts (123 total) ===
┌──────────┬──────────────────┬─────────────────────┬──────────────┬────────┬─────────────────────┐
│ Network  │ Contract         │ Info                │ Entity       │ Block  │ Timestamp           │
├──────────┼──────────────────┼─────────────────────┼──────────────┼────────┼─────────────────────┤
│ ethereum │ 0xA0b86991c6...  │ USD Coin (USDC)     │ Circle       │ 123456 │ 2025-10-22 13:30:45 │
│ ethereum │ 0xdAC17F958D...  │ Tether USD (USDT)   │ Tether       │ 123455 │ 2025-10-22 13:25:30 │
└──────────┴──────────────────┴─────────────────────┴──────────────┴────────┴─────────────────────┘
```

## 注意事项

1. **首次运行**：需要删除旧数据库，让系统创建新的包含类型字段的数据库
   ```bash
   rm -f contract_monitor.db
   ```

2. **性能**：合约分析会额外调用 RPC，但已优化为在后台异步处理

3. **准确性**：
   - 标准合约（ERC20、ERC721）识别准确率接近 100%
   - 自定义合约可能被识别为 Unknown
   - 置信度低于 50% 的结果建议人工核查

4. **扩展**：可以在 `contract_analyzer.py` 中添加更多合约类型的签名

## 技术细节

合约类型通过检测以下函数签名识别：

**ERC20**:
- `totalSupply()` - 0x18160ddd
- `balanceOf(address)` - 0x70a08231
- `transfer(address,uint256)` - 0xa9059cbb
- 等等...

**Router**:
- `swapExactTokensForTokens` - 0x38ed1739
- `swapETHForExactTokens` - 0xfb3bdb41
- 等等...

每种类型需要匹配最少数量的函数才会被识别。

