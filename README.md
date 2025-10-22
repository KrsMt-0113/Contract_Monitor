# Contract Monitor

多链智能合约部署监控系统 - 监听多个区块链网络上的新合约部署，并通过 Arkham API 识别部署者所属实体。

## 功能特性

- ✅ **多链支持**：同时监听 15 个区块链网络
- ✅ 实时监听合约部署事件
- ✅ 使用公共 RPC 节点（多个备用节点自动切换）
- ✅ 通过 Arkham API 查询部署者信息
- ✅ 识别并记录属于已知实体的合约
- ✅ SQLite 数据库持久化存储
- ✅ 断点续传功能（服务重启后从上次位置继续）
- ✅ 完整的日志记录
- ✅ 速率限制保护（符合 Arkham API 限制）
- ✅ 多线程并发监听

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

## 项目结构

```
Contract Monitor/
├── README.md                 # 项目说明文档
├── requirements.txt          # Python 依赖
├── .env.example             # 环境变量示例
├── config.py                # 配置文件
├── database.py              # 数据库操作
├── blockchain_monitor.py    # 区块链监听
**监控默认网络**（Ethereum, Arbitrum, Base, Optimism, Polygon, BSC, Avalanche, Blast, Linea）：
```bash
python monitor_multichain.py
```

**监控指定网络**：
```bash
python monitor_multichain.py --networks ethereum arbitrum base
```

**监控所有可用网络**：
```bash
python monitor_multichain.py --all
```

**单链监控**（传统方式）：
├── arkham_client.py         # Arkham API 客户端
├── monitor.py               # 主监控服务
├── query.py                 # 数据查询工具
├── contract_monitor.db      # SQLite 数据库（运行后生成）
服务特性：
- 多线程并发监听多个网络
```

## 安装

- RPC 节点自动故障切换
1. 安装依赖：
```bash
cd "Contract Monitor"
**查看所有网络统计信息**：
```

2. 配置 API Key：
   - 确保项目根目录有 `API-Key` 文件，或
**查看所有已知实体的合约**：

## 使用方法

### 启动监控服务
**查看特定网络的实体合约**：
```bash
python query.py all ethereum
```

**查看特定实体的合约**：
```bash
python monitor.py
```

**查看特定实体在特定网络的合约**：
```bash
python query.py entity "实体名称" arbitrum
```

服务会：
- 从最新区块开始监听（首次运行）
- 或从上次停止的位置继续（再次运行）
- 每 12 秒检查一次新区块
- 自动保存进度

### 查询数据

查看统计信息：
```bash
python query.py stats
```

查看所有已知实体的合约：
```bash
python query.py all
```

查看特定实体的合约：
```bash
python query.py entity "实体名称"
```

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

