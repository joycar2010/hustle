# 实时价格监控系统 - MT5 & Binance

这是一个基于 vnpy 的实时价格监控系统，支持同时获取 Bybit TradFi MT5 Gateway 和币安期货 API 的黄金价格数据。

## 功能特性

- MT5 Gateway: 实时获取 XAUUSD.s 价格数据
- Binance Futures: 实时获取 XAUUSDT 永续合约价格数据
- WebSocket 实时推送价格更新
- 双平台连接状态监控和错误提示
- 数据延迟监控（不超过 3 秒）
- 美观的 Web 界面展示

## 配置参数

### MT5 Gateway
- **MT5 ID**: 5229471
- **MT5 Server**: Bybit-Live-2
- **主密码**: Lk106504!
- **交易品种**: XAUUSD.s

### Binance Futures
- **API Key**: 0OYJ2YLAoFNrZCMf5mKDgbm887JD69YXfYt1p5XMnao7PQxXVDxHPXSeQSe7f6Bi
- **Secret Key**: qIvY5MUDcp5ZJtPzyW0DCbTI1dJElyiAfL6KhytTsTvIHIBOKbDEiRVAefniZvC2
- **Base URL**: https://fapi.binance.com
- **交易品种**: XAUUSDT
- **合约类型**: PERPETUAL（永续合约）

## 安装依赖

```bash
py -3.9 -m pip install -r requirements.txt
```

## 运行服务

```bash
py -3.9 app.py
```

服务将在 `http://localhost:8000` 启动。

## 使用说明

1. 在浏览器中打开 `http://localhost:8000`
2. 点击"连接 MT5"按钮连接到 MT5 Gateway
3. 点击"连接 Binance"按钮连接到币安期货 API
4. 实时查看 XAUUSD.s 和 XAUUSDT 价格数据
5. 点击"断开"按钮断开相应连接

## 注意事项

- 确保 MetaTrader 5 已正确安装并运行（用于 MT5 连接）
- 确保 MT5 账户信息正确
- 确保 MT5 服务器可访问
- 确保币安 API Key 和 Secret Key 正确
- 确保网络可访问币安期货 API
- 数据更新延迟不超过 3 秒

## API 接口

### MT5 Gateway
- `GET /` - Web 页面
- `GET /api/status` - 获取所有连接状态
- `POST /api/connect` - 连接 MT5 Gateway
- `POST /api/disconnect` - 断开 MT5 Gateway

### Binance Gateway
- `GET /` - Web 页面
- `GET /api/status` - 获取所有连接状态
- `POST /api/binance/connect` - 连接币安期货 API
- `POST /api/binance/disconnect` - 断开币安期货 API

## WebSocket 事件

- `mt5_price_update` - MT5 价格更新事件
- `binance_price_update` - 币安价格更新事件

## 项目结构

```
d:\git\hustle-s\
├── app.py                  # Flask Web 服务器主程序
├── mt5_gateway.py          # MT5 Gateway 连接管理
├── binance_gateway.py      # 币安期货 API 连接管理
├── config.py               # 配置文件
├── requirements.txt        # 依赖包列表
├── README.md              # 项目说明文档
└── templates\
    └── index.html         # Web 前端页面
```
