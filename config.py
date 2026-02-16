MT5_GATEWAY_CONFIG = {
    "gateway_name": "MT5",
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
    "login": 5229471,
    "password": "Lk106504!",
    "server": "Bybit-Live-2",
    "timeout": 60,
    "symbols": ["XAUUSD.s"],
}

WEBSERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": True,
}

DATA_CONFIG = {
    "update_interval": 1,
    "max_delay_seconds": 3,
}

BINANCE_CONFIG = {
    "api_key": "0OYJ2YLAoFNrZCMf5mKDgbm887JD69YXfYt1p5XMnao7PQxXVDxHPXSeQSe7f6Bi",
    "secret_key": "qIvY5MUDcp5ZJtPzyW0DCbTI1dJElyiAfL6KhytTsTvIHIBOKbDEiRVAefniZvC2",
    "base_url": "https://fapi.binance.com",
    "symbol": "XAUUSDT",
    "contract_type": "PERPETUAL",
    "proxies": {
        "http": None,
        "https": None
    },
    "timeout": 30
}
