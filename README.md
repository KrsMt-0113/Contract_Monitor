# Contract Monitor

🚀 **高性能多链智能合约部署监控系统** - 实时监听多个区块链网络上的新合约部署，并通过 Arkham API 识别部署者所属实体。

## ✨ 核心功能

### 🎯 监控能力
- ✅ **多链支持**：同时监听 11 个 EVM 区块链网络
- ✅ **实时监听**：秒级检测合约部署事件
- ✅ **智能识别**：自动识别直接部署和工厂合约部署
- ✅ **合约分析**：智能识别合约类型（ERC20、ERC721、Proxy、DEX 等）
- ✅ **实体识别**：通过 Arkham API 识别部署者所属实体

### ⚡ 性能优化（已实施）
- 🚀 **异步 API 调用**：使用 aiohttp 异步调用 Arkham API，性能提升 3-5 倍
- 💾 **批量数据库写入**：队列批量写入，减少锁竞争，性能提升 5-10 倍
- 🗄️ **智能缓存**：内存缓存 API 查询结果（1小时 TTL），减少 50%+ API 调用
- 🔄 **并行处理**：多线程并发分析合约和处理部署
- 📊 **总体性能提升**：5-10 倍吞吐量提升

### 🛡️ 稳定性保障
- ✅ **RPC 节点故障切换**：多个备用节点自动切换
- ✅ **断点续传**：服务重启后从上次位置继续
- ✅ **速率限制保护**：符合 Arkham API 限制（20 req/s）
- ✅ **完整日志记录**：详细的操作和错误日志
- ✅ **优雅关闭**：等待批量写入完成后安全退出

## 支持的区块链网络

### EVM 兼容链（已支持）
- **Ethereum** - 以太坊主网
- **Arbitrum** - Layer 2 扩容方案
- **Base** - Coinbase Layer 2
- **Optimism** - Optimistic Rollup
- **Polygon** - 侧链网络
- **BSC** - Binance Smart Chain
- **Avalanche** - C-Chain
- **Blast** - Layer 2
- **Linea** - zkEVM Layer 2
- **Sonic** - 高性能链
- **Flare** - 智能合约平台

### 非 EVM 链（计划支持）
- Bitcoin - 比特币
- Solana - 高性能区块链
- TON - Telegram Open Network
- Tron - 波场

## 📁 项目结构

```
Contract Monitor/
├── README.md                    # 项目说明文档
├── OPTIMIZATION_SUMMARY.md      # 性能优化详细说明
├── requirements.txt             # Python 依赖
├── config.py                    # 配置文件
├── main.py                      # 主程序入口（多链监控）
├── blockchain_monitor.py        # 区块链监听核心
├── contract_analyzer.py         # 合约类型分析器
├── arkham_client_async.py       # 异步 Arkham API 客户端（优化版）
├── arkham_client.py             # 同步 Arkham API 客户端（兼容）
├── database.py                  # 数据库操作（支持批量写入）
├── contract_monitor.db          # SQLite 数据库（运行后生成）
├── contract_monitor.log         # 日志文件（运行后生成）
└── CONTRACT_TYPE_GUIDE.md       # 合约类型识别指南
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd "Contract Monitor"
pip install -r requirements.txt
```

依赖包括：
- `web3` - 以太坊交互
- `aiohttp` - 异步 HTTP 客户端（性能优化）
- `requests` - HTTP 客户端（兼容）

### 2. 配置 API Key

确保项目根目录（上级目录）有 `API-Key` 文件，内容为你的 Arkham API Key：
```
YOUR_ARKHAM_API_KEY_HERE
```

或在 `config.py` 中直接配置 `ARKHAM_API_KEY`。

### 3. 启动监控

**监控所有默认网络**（推荐）：
```bash
python main.py
```
默认监控：Ethereum, Arbitrum, Base, Optimism, Polygon, BSC, Avalanche, Blast, Linea

**监控指定网络**：
```bash
python main.py --networks ethereum base arbitrum
```

**监控所有支持的网络**：
```bash
python main.py --all
```

### 4. 服务特性

启动后服务会：
- ✅ 从最新区块开始监听（首次运行）或从上次位置继续（再次运行）
- ✅ 多线程并发监听多个网络
- ✅ 自动识别直接部署和工厂合约部署
- ✅ 智能分析合约类型（ERC20、NFT、DEX 等）
- ✅ 异步查询 Arkham API 识别实体
- ✅ 批量写入数据库，提升性能
- ✅ 自动保存进度，支持断点续传
- ✅ 优雅关闭（Ctrl+C 等待队列清空）

### 5. 查看日志

实时日志：
```bash
tail -f contract_monitor.log
```

日志会显示：
- `⊕ Queued contract` - 合约已加入批量写入队列
- `✓ Contract ... belongs to entity` - 发现已知实体的合约
- `Cache hit` - 缓存命中，节省 API 调用
- `Batch write completed` - 批量写入完成

## 配置说明

在 `config.py` 中可以修改：

- `RPC_ENDPOINTS`: RPC 节点地址（默认使用 Cloudflare）
- `BLOCK_CHECK_INTERVAL`: 区块检查间隔（秒）
- `BATCH_SIZE`: 每次处理的区块数量
- `LOG_LEVEL`: 日志级别

## 数据库结构

### contracts 表
存储合约部署信息：
- `contract_address`: 合约地址
- `deployer_address`: 部署者地址
- `entity_name`: 实体名称（如果属于已知实体）
- `entity_id`: 实体 ID
- `block_number`: 部署区块号
- `transaction_hash`: 交易哈希
- `timestamp`: 记录时间

### monitoring_state 表
存储监控状态：
- `last_processed_block`: 最后处理的区块号

## 注意事项

1. **API 速率限制**：Arkham API 标准限制为每秒 20 次请求，程序已实现自动限速
2. **RPC 访问**：使用 Cloudflare 公共节点，如果需要更高性能可以配置私有节点
3. **数据持久化**：所有数据保存在 SQLite 数据库中，可以随时查询历史记录
4. **日志记录**：所有操作都会记录到 `contract_monitor.log` 文件

## 故障排查

如果遇到连接问题：
1. 检查网络连接
2. 验证 API Key 是否正确
3. 查看日志文件了解详细错误信息

## 扩展功能

可以轻松扩展以支持：
- 多条区块链监听
- Webhook 通知
- 更复杂的实体分析
- 导出数据为 CSV/JSON

