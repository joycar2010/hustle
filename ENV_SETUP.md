# 环境配置说明

## 快速开始

1. 复制环境配置模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入实际的配置信息

3. 启动应用：
```bash
python app.py
```

## 配置项说明

### 数据库配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | PostgreSQL 数据库连接 URL | - |
| `DATABASE_HOST` | 数据库主机地址 | localhost |
| `DATABASE_PORT` | 数据库端口 | 5432 |
| `DATABASE_NAME` | 数据库名称 | hustle_db |
| `DATABASE_USER` | 数据库用户名 | - |
| `DATABASE_PASSWORD` | 数据库密码 | - |

### Web 服务器配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `WEBSERVER_HOST` | 服务器监听地址 | 0.0.0.0 |
| `WEBSERVER_PORT` | 服务器监听端口 | 8000 |
| `WEBSERVER_DEBUG` | 调试模式 | True |

### MT5 网关配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MT5_PATH` | MT5 终端路径 | C:\\Program Files\\MetaTrader 5\\terminal64.exe |
| `MT5_LOGIN` | MT5 账号 | - |
| `MT5_PASSWORD` | MT5 密码 | - |
| `MT5_SERVER` | MT5 服务器 | Bybit-Live-2 |
| `MT5_TIMEOUT` | 连接超时时间（秒） | 60 |
| `MT5_SYMBOLS` | 交易对列表 | XAUUSD.s |

### Binance 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BINANCE_API_KEY` | Binance API Key | - |
| `BINANCE_SECRET_KEY` | Binance Secret Key | - |
| `BINANCE_BASE_URL` | Binance API 地址 | https://fapi.binance.com |
| `BINANCE_SYMBOL` | 交易对 | XAUUSDT |
| `BINANCE_CONTRACT_TYPE` | 合约类型 | PERPETUAL |

### 数据更新配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATA_UPDATE_INTERVAL` | 数据更新间隔（秒） | 1 |
| `DATA_MAX_DELAY_SECONDS` | 最大延迟时间（秒） | 3 |

### 备份配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BACKUP_FREQUENCY` | 备份频率 | daily |
| `BACKUP_TIME` | 备份时间 | 02:00 |
| `BACKUP_BRANCH` | 备份分支 | master |
| `BACKUP_AUTO_PUSH` | 自动推送 | True |
| `BACKUP_SEND_NOTIFICATION` | 发送通知 | True |

### 日志配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | INFO |
| `LOG_FILE` | 日志文件路径 | app.log |

### 其他配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MAX_CONNECTIONS` | 最大连接数 | 100 |
| `CONNECTION_TIMEOUT` | 连接超时（秒） | 30 |
| `REQUEST_TIMEOUT` | 请求超时（秒） | 10 |

## 安全注意事项

1. **不要提交 `.env` 文件到 Git 仓库**
   - `.env` 文件已被添加到 `.gitignore`
   - 只提交 `.env.example` 模板文件

2. **保护敏感信息**
   - 不要在代码中硬编码 API 密钥
   - 不要在公开的仓库中包含真实的密码
   - 定期轮换 API 密钥

3. **使用环境变量**
   - 在生产环境中，建议使用系统环境变量
   - 可以使用 `python-dotenv` 库加载 `.env` 文件

## 示例

### 开发环境
```bash
DATABASE_URL=postgresql://dev:dev123@localhost:5432/hustle_dev
WEBSERVER_DEBUG=True
LOG_LEVEL=DEBUG
```

### 生产环境
```bash
DATABASE_URL=postgresql://prod:secure_password@db.example.com:5432/hustle_prod
WEBSERVER_DEBUG=False
LOG_LEVEL=WARNING
```

## 故障排查

### 数据库连接失败
- 检查 `DATABASE_URL` 是否正确
- 确认数据库服务是否运行
- 验证用户名和密码

### MT5 连接失败
- 检查 MT5 终端路径是否正确
- 确认 MT5 终端是否正在运行
- 验证账号和密码

### Binance API 连接失败
- 检查 API Key 和 Secret Key 是否正确
- 确认网络连接
- 验证 API 权限设置

## 相关文件

- `.env.example` - 环境配置模板
- `.gitignore` - Git 忽略文件配置
- `config.py` - Python 配置文件