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
    def __init__(self, api_key: str, secret_key: str, base_url: str, symbol: str, proxies: dict = None, timeout: int = 30):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.symbol = symbol
        self.proxies = proxies or {"http": None, "https": None}
        self.timeout = timeout
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
                response = requests.post(url, headers=headers, json=params, timeout=self.timeout, proxies=self.proxies)
            else:
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout, proxies=self.proxies)
            
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    def connect(self) -> bool:
        try:
            # 根据base_url判断是现货还是合约API
            if 'fapi' in self.base_url:
                # 合约API
                endpoint = '/fapi/v1/time'
                api_name = "Binance Futures API"
            else:
                # 现货API
                endpoint = '/api/v3/time'
                api_name = "Binance Spot API"
            
            server_time = self._make_request(endpoint)
            if server_time and 'serverTime' in server_time:
                logger.info(f"Connected to {api_name}. Server time: {server_time['serverTime']}")
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

    def get_futures_time(self) -> Optional[Dict[str, Any]]:
        """获取Binance合约API时间戳（行情模块专用）"""
        try:
            # 强制使用合约API时间接口
            endpoint = '/fapi/v1/time'
            data = self._make_request(endpoint)
            if data and 'serverTime' in data:
                logger.debug("Futures time sync successful")
                return data
            else:
                logger.warning("Failed to get futures time")
                return None
        except Exception as e:
            logger.error(f"Error getting futures time: {e}")
            return None

    def get_spot_time(self) -> Optional[Dict[str, Any]]:
        """获取Binance现货API时间戳（账户面板专用）"""
        try:
            # 强制使用现货API时间接口
            endpoint = '/api/v3/time'
            data = self._make_request(endpoint)
            if data and 'serverTime' in data:
                logger.debug("Spot time sync successful")
                return data
            else:
                logger.warning("Failed to get spot time")
                return None
        except Exception as e:
            logger.error(f"Error getting spot time: {e}")
            return None

    def get_ticker_price(self) -> Optional[Dict[str, Any]]:
        """获取行情数据（行情模块专用）"""
        if not self.connected:
            return None

        params = {
            'symbol': self.symbol
        }

        # 行情模块专用：使用合约API接口
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
        """获取订单簿数据（行情模块专用）"""
        if not self.connected:
            return None

        params = {
            'symbol': self.symbol,
            'limit': 5
        }

        # 行情模块专用：使用合约API接口
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
        """获取24小时行情数据（行情模块专用）"""
        if not self.connected:
            return None

        params = {
            'symbol': self.symbol
        }

        # 行情模块专用：使用合约API接口
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

            time.sleep(0.85)

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

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """获取账户信息（账户面板专用）"""
        if not self.connected:
            return None

        try:
            # 先调用时间接口进行校准（账户面板专用）
            time_data = self.get_spot_time()
            if not time_data:
                logger.warning("Failed to sync time, continuing with account info retrieval")

            # 根据base_url判断是现货还是合约API
            if 'fapi' in self.base_url:
                # 合约API
                endpoint = '/fapi/v2/account'
                data = self._make_request(endpoint, signed=True)
                
                if data is None:
                    logger.warning("Failed to get futures account info")
                    return None

                # 检查是否有账户权限
                if isinstance(data, dict) and 'code' in data and data['code'] == -2015:
                    logger.error("API Key missing account permissions")
                    return {
                        "error": "API Key missing account permissions",
                        "message": "请确保API Key包含账户读取权限"
                    }

                # 提取合约账户信息
                balance = 0.0
                equity = 0.0
                margin = 0.0
                free_margin = 0.0
                total_wallet_balance = 0.0
                available_balance = 0.0
                frozen_balance = 0.0
                daily_pnl = 0.0
                margin_balance = 0.0
                risk_ratio = '--'

                if isinstance(data, dict):
                    if 'totalWalletBalance' in data:
                        balance = float(data['totalWalletBalance'])
                        total_wallet_balance = balance
                    if 'totalMarginBalance' in data:
                        equity = float(data['totalMarginBalance'])
                    if 'totalInitialMargin' in data:
                        margin = float(data['totalInitialMargin'])
                        margin_balance = margin
                    if 'totalAvailableMargin' in data:
                        free_margin = float(data['totalAvailableMargin'])
                        available_balance = free_margin
                    if 'totalUnrealizedProfit' in data:
                        daily_pnl = float(data['totalUnrealizedProfit'])
                    if margin > 0 and equity > 0:
                        risk_ratio = ((equity / margin) * 100).toFixed(2)

                    # 计算总持仓
                    positions = data.get('positions', [])
                    total_position = 0.0
                    for pos in positions:
                        if isinstance(pos, dict) and 'positionAmt' in pos:
                            total_position += abs(float(pos['positionAmt']))
                else:
                    positions = []
                    total_position = 0.0

                return {
                    "balance": balance,
                    "equity": equity,
                    "margin": margin,
                    "free_margin": free_margin,
                    "totalWalletBalance": total_wallet_balance,
                    "totalMarginBalance": equity,
                    "totalInitialMargin": margin,
                    "totalAvailableMargin": free_margin,
                    "positions": positions,
                    "api_key": self.api_key,
                    "api_type": "futures",
                    "uid": data.get('uid', '') if isinstance(data, dict) else '',  # 用户ID
                    "total_assets": total_wallet_balance,  # 账户总资产
                    "available_assets": available_balance,  # 可用总资产
                    "net_assets": equity,  # 净资产
                    "total_position": total_position,  # 总持仓
                    "frozen_assets": frozen_balance,  # 冻结资产
                    "daily_pnl": daily_pnl,  # 当日盈亏
                    "margin_balance": margin_balance,  # 保证金余额
                    "risk_ratio": risk_ratio,  # 风险率
                    "timestamp": time_data.get('serverTime') if time_data else None
                }
            else:
                # 现货API
                endpoint = '/api/v3/account'
                data = self._make_request(endpoint, signed=True)
                
                if data is None:
                    logger.warning("Failed to get spot account info")
                    return None

                # 检查是否有账户权限
                if isinstance(data, dict) and 'code' in data and data['code'] == -2015:
                    logger.error("API Key missing account permissions")
                    return {
                        "error": "API Key missing account permissions",
                        "message": "请确保API Key包含账户读取权限"
                    }

                # 提取现货账户信息
                balances = data.get('balances', []) if isinstance(data, dict) else []
                uid = data.get('uid', '') if isinstance(data, dict) else ''
                
                # 计算总余额（以USDT计价）
                total_balance = 0.0
                available_balance = 0.0
                frozen_balance = 0.0
                asset_values = {}

                for balance_item in balances:
                    if not isinstance(balance_item, dict):
                        continue
                    
                    asset = balance_item.get('asset', '')
                    free = float(balance_item.get('free', 0))
                    locked = float(balance_item.get('locked', 0))
                    total = free + locked
                    
                    if total > 0:
                        # 获取资产最新价格
                        price = self.get_asset_price(asset)
                        if price:
                            value = total * price
                            total_balance += value
                            available_balance += free * price
                            frozen_balance += locked * price
                            asset_values[asset] = {
                                'amount': total,
                                'price': price,
                                'value': value
                            }

                # 获取杠杆账户信息
                margin_info = self.get_margin_account_info()
                margin_balance = 0.0
                margin_available = 0.0
                risk_ratio = '--'

                if margin_info and isinstance(margin_info, dict):
                    if 'totalNetAssetOfBtc' in margin_info:
                        # 杠杆账户总资产（BTC计价），转换为USDT
                        btc_price = self.get_asset_price('BTC')
                        if btc_price:
                            margin_balance = float(margin_info['totalNetAssetOfBtc']) * btc_price
                    if 'availableBalanceOfBtc' in margin_info:
                        # 杠杆账户可用资产（BTC计价），转换为USDT
                        btc_price = self.get_asset_price('BTC')
                        if btc_price:
                            margin_available = float(margin_info['availableBalanceOfBtc']) * btc_price
                    if 'totalLiabilityOfBtc' in margin_info and 'totalAssetOfBtc' in margin_info:
                        # 计算风险率
                        total_asset = float(margin_info['totalAssetOfBtc'])
                        total_liability = float(margin_info['totalLiabilityOfBtc'])
                        if total_liability > 0:
                            risk_ratio = ((total_asset / total_liability) * 100).toFixed(2)

                # 计算总持仓
                total_position = 0.0
                # 这里简化处理，实际应该从持仓接口获取

                return {
                    "balance": total_balance,
                    "equity": total_balance,
                    "margin": margin_balance,
                    "free_margin": available_balance + margin_available,
                    "balances": balances,
                    "asset_values": asset_values,
                    "margin_info": margin_info,
                    "api_key": self.api_key,
                    "api_type": "spot",
                    "uid": uid,  # 用户ID
                    "total_assets": total_balance + margin_balance,  # 账户总资产（现货+杠杆）
                    "available_assets": available_balance + margin_available,  # 可用总资产
                    "net_assets": total_balance + margin_balance,  # 净资产
                    "total_position": total_position,  # 总持仓
                    "frozen_assets": frozen_balance,  # 冻结资产
                    "daily_pnl": 0.0,  # 当日盈亏（需要从其他接口获取）
                    "margin_balance": margin_balance,  # 保证金余额
                    "risk_ratio": risk_ratio,  # 风险率
                    "timestamp": time_data.get('serverTime') if time_data else None
                }

        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            # 区分鉴权错误和其他错误
            error_message = str(e)
            if "API-key format invalid" in error_message or "Invalid API-key" in error_message:
                return {
                    "error": "Invalid API Key",
                    "message": "API Key格式错误，请检查"
                }
            elif "Signature for this request is not valid" in error_message:
                return {
                    "error": "Invalid Signature",
                    "message": "API密钥或签名错误，请检查"
                }
            elif "Account has insufficient permissions" in error_message or "api-key permissions" in error_message:
                return {
                    "error": "Insufficient Permissions",
                    "message": "API Key缺少账户读取权限，请在Binance后台开启"
                }
            else:
                return {
                    "error": "Unknown Error",
                    "message": f"获取账户信息失败: {error_message}"
                }

    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def get_asset_price(self, asset: str) -> Optional[float]:
        """获取资产的最新价格（以USDT计价）"""
        if not self.connected:
            return None

        try:
            # 对于USDT，直接返回1
            if asset == 'USDT':
                return 1.0

            # 构建交易对符号
            symbol = f'{asset}USDT'
            params = {'symbol': symbol}

            # 使用现货API获取价格
            data = self._make_request('/api/v3/ticker/price', params=params)
            if data and 'price' in data:
                return float(data['price'])
            else:
                logger.warning(f"Failed to get price for {symbol}")
                return None
        except Exception as e:
            logger.error(f"Error getting asset price: {e}")
            return None

    def get_margin_account_info(self) -> Optional[Dict[str, Any]]:
        """获取杠杆账户信息"""
        if not self.connected:
            return None

        try:
            endpoint = '/sapi/v1/margin/account'
            data = self._make_request(endpoint, signed=True)
            if data:
                logger.debug("Margin account info retrieved successfully")
                return data
            else:
                logger.warning("Failed to get margin account info")
                return None
        except Exception as e:
            logger.error(f"Error getting margin account info: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "last_price": self.last_price,
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None,
            "running": self.running,
        }
