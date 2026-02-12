import requests
import threading
import time
import hmac
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BinanceGateway:
    def __init__(self, api_key: str, secret_key: str, base_url: str, symbol: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.symbol = symbol
        self.connected = False
        self.last_price = None
        self.last_update_time = None
        self.callbacks = []
        self.running = False
        self.thread = None

    def _generate_signature(self, params: dict) -> str:
        query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_request(self, endpoint: str, params: dict = None, signed: bool = False, method: str = "GET") -> Optional[dict]:
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                'Content-Type': 'application/json',
                'X-MBX-APIKEY': self.api_key
            }

            if params is None:
                params = {}

            if signed:
                params['timestamp'] = int(time.time() * 1000)
                params['signature'] = self._generate_signature(params)

            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=params, timeout=10)
            else:
                response = requests.get(url, headers=headers, params=params, timeout=10)
            
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    def connect(self) -> bool:
        try:
            server_time = self._make_request('/fapi/v1/time')
            if server_time and 'serverTime' in server_time:
                logger.info(f"Connected to Binance Futures API. Server time: {server_time['serverTime']}")
                self.connected = True
                return True
            else:
                logger.error("Failed to connect to Binance API")
                return False

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.connected = False
        logger.info("Disconnected from Binance API")

    def get_ticker_price(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None

        params = {
            'symbol': self.symbol
        }

        data = self._make_request('/fapi/v1/ticker/price', params=params)
        if data is None:
            logger.warning(f"Failed to get ticker price for {self.symbol}")
            return None

        return {
            "symbol": self.symbol,
            "price": float(data['price']),
            "time": datetime.fromtimestamp(data['time'] / 1000).isoformat(),
        }

    def get_order_book(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None

        params = {
            'symbol': self.symbol,
            'limit': 5
        }

        data = self._make_request('/fapi/v1/depth', params=params)
        if data is None:
            logger.warning(f"Failed to get order book for {self.symbol}")
            return None

        if data['bids'] and data['asks']:
            best_bid = float(data['bids'][0][0])
            best_ask = float(data['asks'][0][0])
            spread = best_ask - best_bid
            spread_percent = (spread / best_bid) * 100

            return {
                "symbol": self.symbol,
                "bid": best_bid,
                "ask": best_ask,
                "spread": spread,
                "spread_percent": spread_percent,
                "time": datetime.now().isoformat(),
                "bid_volume": float(data['bids'][0][1]),
                "ask_volume": float(data['asks'][0][1]),
            }

        return None

    def get_24h_ticker(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None

        params = {
            'symbol': self.symbol
        }

        data = self._make_request('/fapi/v1/ticker/24hr', params=params)
        if data is None:
            logger.warning(f"Failed to get 24h ticker for {self.symbol}")
            return None

        return {
            "symbol": self.symbol,
            "price_change": float(data['priceChange']),
            "price_change_percent": float(data['priceChangePercent']),
            "high": float(data['highPrice']),
            "low": float(data['lowPrice']),
            "volume": float(data['volume']),
            "quote_volume": float(data['quoteVolume']),
            "open": float(data['openPrice']),
            "close": float(data['lastPrice']),
        }

    def start_streaming(self):
        if self.running:
            logger.warning("Streaming already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.thread.start()
        logger.info("Started Binance price streaming")

    def _stream_loop(self):
        while self.running and self.connected:
            ticker = self.get_ticker_price()
            order_book = self.get_order_book()
            ticker_24h = self.get_24h_ticker()

            if ticker and order_book and ticker_24h:
                combined_data = {
                    **ticker,
                    **order_book,
                    "price_change": ticker_24h["price_change"],
                    "price_change_percent": ticker_24h["price_change_percent"],
                    "high_24h": ticker_24h["high"],
                    "low_24h": ticker_24h["low"],
                    "volume_24h": ticker_24h["volume"],
                    "open_price": ticker_24h["open"],
                }
                self.last_price = combined_data
                self.last_update_time = datetime.now()

                for callback in self.callbacks:
                    try:
                        callback(combined_data)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

            time.sleep(1)

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def get_status(self) -> Dict[str, Any]:
        """获取网关状态"""
        status = {
            "connected": self.connected,
            "symbol": self.symbol,
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None,
            "last_price": self.last_price
        }
        
        if not self.connected:
            status["error"] = "Not connected"
        
        return status

    def send_order(self, direction: str, price: float, size: float, order_id: str = None) -> str:
        if not self.connected:
            logger.error("Not connected to Binance")
            return None

        endpoint = "/fapi/v1/order"
        params = {
            "symbol": self.symbol,
            "side": "BUY" if direction.lower() == "buy" else "SELL",
            "type": "LIMIT",
            "quantity": size,
            "price": price,
            "timeInForce": "GTC",
            "timestamp": int(time.time() * 1000)
        }

        if order_id:
            params["clientOrderId"] = order_id

        params["signature"] = self._generate_signature(params)

        result = self._make_request(endpoint, params, signed=True, method="POST")
        
        if result is None:
            logger.error("Failed to send order")
            return None

        if "orderId" in result:
            logger.info(f"Order sent successfully: {result['orderId']}")
            return str(result["orderId"])
        else:
            logger.error(f"Order failed: {result}")
            return None

    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "last_price": self.last_price,
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None,
            "running": self.running,
        }
