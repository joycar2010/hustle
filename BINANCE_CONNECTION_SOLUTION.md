# Binance API 连接问题解决方案

## 问题诊断结果

根据网络诊断测试，您的系统存在以下网络问题：

❌ **无法访问的网站**：
- `fapi.binance.com` (Binance API)
- `www.google.com` (Google)

✅ **可以访问的网站**：
- `www.baidu.com` (百度)

## 根本原因

您的网络环境限制了访问国外网站，而Binance API需要访问国外服务器。

## 解决方案

### 方案一：配置代理（推荐）

如果您有可用的代理服务器，请按以下步骤配置：

1. **编辑配置文件** `config.py`：

```python
BINANCE_CONFIG = {
    "api_key": "0OYJ2YLAoFNrZCMf5mKDgbm887JD69YXfYt1p5XMnao7PQxXVDxHPXSeQSe7f6Bi",
    "secret_key": "qIvY5MUDcp5ZJtPzyW0DCbTI1dJElyiAfL6KhytTsTvIHIBOKbDEiRVAefniZvC2",
    "base_url": "https://fapi.binance.com",
    "symbol": "XAUUSDT",
    "contract_type": "PERPETUAL",
    "proxies": {
        "http": "http://your_proxy_address:port",
        "https": "http://your_proxy_address:port"
    },
    "timeout": 30
}
```

2. **替换代理地址**：
   - 将 `your_proxy_address:port` 替换为您的实际代理地址
   - 例如：`http://127.0.0.1:7890` 或 `http://username:password@proxy.example.com:8080`

3. **重启服务**：
   - 停止当前运行的服务
   - 重新启动 `app.py`

### 方案二：使用VPN

1. **连接VPN**到可以访问国外网络的服务器
2. **确保VPN代理端口可用**（通常是 127.0.0.1:7890 或类似）
3. **按照方案一的步骤配置代理**

### 方案三：更换网络环境

1. **切换到可以访问国外网络的环境**
2. **重新尝试连接Binance账户**

### 方案四：使用国内交易所

如果以上方案都不可行，可以考虑：

1. **使用国内支持的交易所API**
2. **修改代码以支持其他交易所**

## 测试连接

配置代理后，运行测试脚本验证连接：

```bash
python test_binance_connection.py
```

如果看到以下输出，说明连接成功：
```
✓ 连接成功！状态码: 200
✓ API密钥有效
```

## 常见代理地址格式

### 本地代理
```python
"proxies": {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
}
```

### 带认证的代理
```python
"proxies": {
    "http": "http://username:password@proxy.example.com:8080",
    "https": "http://username:password@proxy.example.com:8080"
}
```

### SOCKS5 代理
```python
"proxies": {
    "http": "socks5://127.0.0.1:1080",
    "https": "socks5://127.0.0.1:1080"
}
```

## 网络诊断脚本

运行以下命令进行网络诊断：

```bash
python test_binance_connection.py
```

该脚本会测试：
1. 基础连接到 Binance API
2. API 密钥有效性
3. 网络连通性

## 注意事项

1. **代理稳定性**：确保代理服务器稳定可靠
2. **API密钥安全**：不要将API密钥泄露给不信任的代理服务器
3. **网络延迟**：使用代理可能会增加网络延迟
4. **防火墙设置**：确保防火墙允许代理连接

## 联系支持

如果问题仍然存在，请检查：
- 代理服务器是否正常运行
- 网络连接是否稳定
- Binance API密钥是否有效
- 防火墙设置是否阻止了连接

## 更新日志

- 2026-02-16: 增加代理支持和网络诊断功能
- 增加超时配置（从10秒增加到30秒）
- 改进错误处理和日志记录
