import MetaTrader5 as mt5
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MT5Gateway:
    def __init__(self, login: str, password: str, server: str, symbols: list):
        self.login = login
        self.password = password
        self.server = server
        self.symbols = symbols
        self.connected = False
        self.last_price = None
        self.last_update_time = None
        self.callbacks = []
        self.running = False
        self.thread = None

    def connect(self) -> bool:
        try:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False

            if not mt5.login(int(self.login), self.password, self.server):
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False

            account_info = mt5.account_info()
            if account_info is None:
                logger.error(f"Failed to get account info: {mt5.last_error()}")
                mt5.shutdown()
                return False

            logger.info(f"Connected to MT5: {account_info.server}")
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")

    def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.warning(f"Failed to get tick for {symbol}: {mt5.last_error()}")
            return None

        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": tick.ask - tick.bid,
            "time": datetime.fromtimestamp(tick.time).isoformat(),
            "volume": tick.volume,
        }

    def start_streaming(self):
        if self.running:
            logger.warning("Streaming already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.thread.start()
        logger.info("Started price streaming")

    def _stream_loop(self):
        while self.running and self.connected:
            for symbol in self.symbols:
                tick = self.get_tick(symbol)
                if tick:
                    self.last_price = tick
                    self.last_update_time = datetime.now()
                    for callback in self.callbacks:
                        try:
                            callback(tick)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

            time.sleep(1)

    def add_callback(self, callback):
        self.callbacks.append(callback)

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

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None

        account_info = mt5.account_info()
        if account_info is None:
            logger.error(f"Failed to get account info: {mt5.last_error()}")
            return None

        return {
            "login": account_info.login,
            "server": account_info.server,
            "company": account_info.company,
            "currency": account_info.currency,
            "balance": account_info.balance,
            "equity": account_info.equity,
            "margin": account_info.margin,
            "free_margin": account_info.margin_free,
            "margin_level": account_info.margin_level,
            "profit": account_info.profit,
        }

    def send_order(self, direction: str, price: float, size: float, order_id: str = None) -> str:
        if not self.connected:
            logger.error("Not connected to MT5")
            return None

        symbol = self.symbols[0] if self.symbols else "XAUUSD.s"
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {symbol}")
            return None

        request_dict = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": size,
            "type": mt5.ORDER_TYPE_BUY if direction.lower() == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "Arbitrage trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if order_id:
            request_dict["comment"] = f"Arbitrage trade {order_id}"

        result = mt5.order_send(request_dict)
        
        if result is None:
            logger.error(f"Failed to send order: {mt5.last_error()}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.retcode} - {result.comment}")
            return None

        logger.info(f"Order sent successfully: {result.order}")
        return str(result.order)
