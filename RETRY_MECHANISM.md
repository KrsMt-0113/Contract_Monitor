# 重试机制实现说明

## 概述
已为监听程序添加了完整的连接断开重试机制，包括多层防护和自动恢复功能。

## 新增功能

### 1. **RPC 连接重试机制** (`blockchain_monitor.py`)

#### 特性：
- **指数退避策略**：重试间隔按 2^n 递增（5s, 10s, 20s...）
- **多 RPC 端点支持**：自动切换到备用 RPC 节点
- **连接健康检查**：`_ensure_connection()` 自动检测并恢复断开的连接
- **最大重试次数限制**：默认 3 次重试，避免无限循环

#### 关键方法改进：

```python
# 1. _ensure_connection() - 增强的连接保持
- 检测连接断开
- 指数退避重连（5s, 10s, 20s）
- 遍历所有可用 RPC 端点

# 2. get_latest_block_number() - 带重试的区块获取
- 3 次重试机制
- 失败时自动重连
- 详细的错误日志

# 3. get_contract_deployments() - 带重试的部署检测
- 区块数据获取重试
- 事务处理异常隔离
- 记录失败的区块号

# 4. get_deployments_in_range() - 批量处理优化
- 跟踪失败的区块
- 不会因单个区块失败而中断整个批次
```

### 2. **监控线程重试机制** (`monitor_multichain.py`)

#### 特性：
- **连续错误计数器**：跟踪连续失败次数
- **分级重试策略**：根据错误类型采取不同措施
- **完全重新初始化**：5次连续错误后重建监控器
- **线程健康检查**：每30秒检查线程状态，自动重启死亡线程

#### 错误处理策略：

```python
# 1. 连接错误 (ConnectionError)
- 1-4次错误：指数退避重试
- 5+次错误：完全重新初始化 Monitor 和 Analyzer
- 重新初始化失败：最多等待5分钟后重试

# 2. 一般异常 (Exception)
- 记录详细错误堆栈
- 指数退避（最多5分钟）
- 不中断监控循环

# 3. 单个部署处理失败
- 跳过失败的部署
- 记录错误但继续处理其他部署
- 不影响整体监控
```

### 3. **线程健康监控**

#### 自动守护进程：
```python
monitor_thread_health()
- 每 30 秒检查所有监控线程
- 自动重启死亡的线程
- 命名线程便于调试（Monitor-ethereum, Monitor-polygon 等）
- 独立的健康监控线程
```

## 重试时间策略

### 指数退避计算：
```
第1次失败: 等待 5s  (2^0 * 5s)
第2次失败: 等待 10s (2^1 * 5s)
第3次失败: 等待 20s (2^2 * 5s)
第4次失败: 等待 40s (2^3 * 5s)
第5次失败: 等待 80s (2^4 * 5s)
...
最大等待: 300s (5分钟)
```

## 日志改进

### 新增日志信息：
- `[network] Reconnection failed, retrying in Xs... (attempt N/M)`
- `[network] Connection error (#N)`
- `[network] Too many consecutive connection errors (N). Attempting full reinitialization...`
- `[network] Monitor reinitialized successfully`
- `[network] Thread died unexpectedly, restarting...`
- `[network] Thread restarted successfully`
- `[network] Failed to process N block(s): [block_numbers]`

## 测试建议

### 1. 测试 RPC 断开恢复
```bash
# 运行监听程序
python monitor_multichain.py --networks ethereum

# 模拟网络中断（断开 WiFi 或禁用 RPC）
# 观察日志中的重连尝试

# 恢复网络
# 验证自动恢复
```

### 2. 测试线程崩溃恢复
```bash
# 查看线程状态
ps aux | grep monitor_multichain

# 监控日志
tail -f contract_monitor.log

# 线程会在30秒内自动重启
```

### 3. 压力测试
```bash
# 监控多条链
python monitor_multichain.py --all

# 观察各链的独立重试
# 一条链失败不影响其他链
```

## 配置参数

可在代码中调整的参数：
- `max_retries`: RPC 操作最大重试次数（默认 3）
- `retry_delay`: 基础重试延迟（默认 5 秒）
- `max_consecutive_errors`: 触发完全重新初始化的错误次数（默认 5）
- `health_check_interval`: 线程健康检查间隔（默认 30 秒）
- `max_wait_time`: 最大等待时间（默认 300 秒）

## 优势

✅ **高可用性**: 自动从网络中断中恢复
✅ **独立运行**: 多链监控相互独立，单链故障不影响其他链
✅ **智能重试**: 指数退避避免 API 限流
✅ **完整日志**: 详细记录所有重试和恢复过程
✅ **资源优化**: 失败时减少请求频率
✅ **长期稳定**: 适合7x24小时运行

## 文件变更

- ✅ `blockchain_monitor.py` - 已添加完整重试机制
- ✅ `monitor_multichain.py` - 已添加线程监控和错误恢复
- 📦 `blockchain_monitor_broken.py` - 损坏文件备份
- 📦 `monitor_multichain_broken.py` - 损坏文件备份

## 启动监听程序

```bash
cd "/Users/wuqifeng/IdeaProjects/Arkham_KrsMt/Contract Monitor"

# 监听单条链
python monitor_multichain.py --networks ethereum

# 监听多条链
python monitor_multichain.py --networks ethereum polygon bsc

# 监听所有可用链
python monitor_multichain.py --all
```

## 监控日志

```bash
# 实时查看日志
tail -f contract_monitor.log

# 搜索重试记录
grep "retrying" contract_monitor.log

# 查看连接错误
grep "Connection error" contract_monitor.log

# 查看线程重启
grep "Thread restarted" contract_monitor.log
```

