import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StrategyStatus(Enum):
    IDLE = "idle"
    OPENING = "opening"
    OPENED = "opened"
    CLOSING = "closing"
    CLOSED = "closed"
    CHASING = "chasing"


class SpreadData:
    def __init__(self):
        self.bybit_bid = None
        self.bybit_ask = None
        self.binance_bid = None
        self.binance_ask = None
        self.spread_positive = None
        self.spread_negative = None
        self.last_update = None

    def update(self, bybit_tick: Dict[str, Any], binance_tick: Dict[str, Any]):
        self.bybit_bid = bybit_tick.get('bid')
        self.bybit_ask = bybit_tick.get('ask')
        self.binance_bid = binance_tick.get('bid')
        self.binance_ask = binance_tick.get('ask')
        self.last_update = datetime.now()

        if self.bybit_ask is not None and self.binance_bid is not None:
            self.spread_positive = self.bybit_ask - self.binance_bid

        if self.binance_ask is not None and self.bybit_bid is not None:
            self.spread_negative = self.binance_ask - self.bybit_bid

    def is_valid(self) -> bool:
        return all([
            self.bybit_bid is not None,
            self.bybit_ask is not None,
            self.binance_bid is not None,
            self.binance_ask is not None
        ])


class ArbitragePair:
    def __init__(self, pair_id: str, bybit_account_id: str, binance_account_id: str):
        self.pair_id = pair_id
        self.bybit_account_id = bybit_account_id
        self.binance_account_id = binance_account_id
        self.status = StrategyStatus.IDLE
        self.spread_data = SpreadData()
        
        self.bybit_position = 0.0
        self.binance_position = 0.0
        
        self.bybit_order_id = None
        self.binance_order_id = None
        
        self.bybit_trade_filled = False
        self.binance_trade_filled = False
        
        self.unilateral_trade_flag = False
        self.chase_order_count = 0
        
        self.open_time = None
        self.close_time = None
        
        self.pnl = 0.0

    def reset(self):
        self.status = StrategyStatus.IDLE
        self.bybit_position = 0.0
        self.binance_position = 0.0
        self.bybit_order_id = None
        self.binance_order_id = None
        self.bybit_trade_filled = False
        self.binance_trade_filled = False
        self.unilateral_trade_flag = False
        self.chase_order_count = 0
        self.open_time = None
        self.close_time = None
        self.pnl = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "bybit_account_id": self.bybit_account_id,
            "binance_account_id": self.binance_account_id,
            "status": self.status.value,
            "bybit_position": self.bybit_position,
            "binance_position": self.binance_position,
            "bybit_order_id": self.bybit_order_id,
            "binance_order_id": self.binance_order_id,
            "bybit_trade_filled": self.bybit_trade_filled,
            "binance_trade_filled": self.binance_trade_filled,
            "unilateral_trade_flag": self.unilateral_trade_flag,
            "chase_order_count": self.chase_order_count,
            "open_time": self.open_time.isoformat() if self.open_time else None,
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "pnl": self.pnl,
            "current_spread": self.spread_data.spread_positive
        }


class ArbitrageStrategy:
    def __init__(self, strategy_id: str, bybit_account_id: str, binance_account_id: str,
                 risk_manager, order_callback: Callable, trade_callback: Callable):
        self.strategy_id = strategy_id
        self.bybit_account_id = bybit_account_id
        self.binance_account_id = binance_account_id
        self.risk_manager = risk_manager
        self.order_callback = order_callback
        self.trade_callback = trade_callback
        
        self.arbitrage_pair = ArbitragePair(strategy_id, bybit_account_id, binance_account_id)
        
        self.enabled = False
        self.auto_mode = True
        
        self.open_threshold = 0.5
        self.close_threshold = 0.3
        self.order_size = 0.01
        self.max_chase_count = 5
        self.trade_timeout = 3
        
        self.lock = threading.Lock()
        self.thread = None
        self.running = False

    def start(self):
        if self.running:
            logger.warning(f"Strategy {self.strategy_id} already running")
            return

        self.enabled = True
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"Strategy {self.strategy_id} started")

    def stop(self):
        self.enabled = False
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"Strategy {self.strategy_id} stopped")

    def update_tick(self, platform: str, tick_data: Dict[str, Any]):
        if not self.enabled or not self.auto_mode:
            return

        with self.lock:
            if platform == 'bybit':
                self._process_bybit_tick(tick_data)
            elif platform == 'binance':
                self._process_binance_tick(tick_data)

            self._check_conditions()

    def _process_bybit_tick(self, tick_data: Dict[str, Any]):
        self.arbitrage_pair.spread_data.update(tick_data, self.arbitrage_pair.spread_data)

    def _process_binance_tick(self, tick_data: Dict[str, Any]):
        self.arbitrage_pair.spread_data.update(self.arbitrage_pair.spread_data, tick_data)

    def _check_conditions(self):
        pair = self.arbitrage_pair
        spread = pair.spread_data

        if not spread.is_valid():
            return

        if pair.status == StrategyStatus.IDLE:
            self._check_open_conditions(spread)
        elif pair.status == StrategyStatus.OPENED:
            self._check_close_conditions(spread)
        elif pair.status in [StrategyStatus.OPENING, StrategyStatus.CLOSING]:
            self._check_trade_timeout()

    def _check_open_conditions(self, spread: SpreadData):
        pair = self.arbitrage_pair

        if spread.spread_positive is not None and spread.spread_positive >= self.open_threshold:
            self._execute_open_positive()
        elif spread.spread_negative is not None and spread.spread_negative <= -self.open_threshold:
            self._execute_open_negative()

    def _check_close_conditions(self, spread: SpreadData):
        pair = self.arbitrage_pair

        if pair.bybit_position > 0 and pair.binance_position < 0:
            if spread.spread_positive is not None and spread.spread_positive <= self.close_threshold:
                self._execute_close_positive()
        elif pair.bybit_position < 0 and pair.binance_position > 0:
            if spread.spread_negative is not None and spread.spread_negative >= -self.close_threshold:
                self._execute_close_negative()

    def _execute_open_positive(self):
        pair = self.arbitrage_pair
        spread = pair.spread_data

        passed, message = self.risk_manager.check_order(
            self.bybit_account_id,
            -self.order_size
        )
        if not passed:
            logger.warning(f"Risk check failed for Bybit: {message}")
            return

        passed, message = self.risk_manager.check_order(
            self.binance_account_id,
            self.order_size
        )
        if not passed:
            logger.warning(f"Risk check failed for Binance: {message}")
            return

        bybit_price = spread.bybit_ask - 0.01
        binance_price = spread.binance_bid + 0.01

        pair.bybit_order_id = self.order_callback(
            self.bybit_account_id,
            'sell',
            bybit_price,
            self.order_size
        )

        pair.binance_order_id = self.order_callback(
            self.binance_account_id,
            'buy',
            binance_price,
            self.order_size
        )

        pair.status = StrategyStatus.OPENING
        pair.open_time = datetime.now()
        pair.bybit_trade_filled = False
        pair.binance_trade_filled = False

        logger.info(f"Opening positive spread: {spread.spread_positive}")

    def _execute_open_negative(self):
        pair = self.arbitrage_pair
        spread = pair.spread_data

        passed, message = self.risk_manager.check_order(
            self.binance_account_id,
            -self.order_size
        )
        if not passed:
            logger.warning(f"Risk check failed for Binance: {message}")
            return

        passed, message = self.risk_manager.check_order(
            self.bybit_account_id,
            self.order_size
        )
        if not passed:
            logger.warning(f"Risk check failed for Bybit: {message}")
            return

        binance_price = spread.binance_ask - 0.01
        bybit_price = spread.bybit_bid + 0.01

        pair.binance_order_id = self.order_callback(
            self.binance_account_id,
            'sell',
            binance_price,
            self.order_size
        )

        pair.bybit_order_id = self.order_callback(
            self.bybit_account_id,
            'buy',
            bybit_price,
            self.order_size
        )

        pair.status = StrategyStatus.OPENING
        pair.open_time = datetime.now()
        pair.bybit_trade_filled = False
        pair.binance_trade_filled = False

        logger.info(f"Opening negative spread: {spread.spread_negative}")

    def _execute_close_positive(self):
        pair = self.arbitrage_pair
        spread = pair.spread_data

        bybit_price = spread.bybit_bid + 0.01
        binance_price = spread.binance_ask - 0.01

        pair.bybit_order_id = self.order_callback(
            self.bybit_account_id,
            'buy',
            bybit_price,
            self.order_size
        )

        pair.binance_order_id = self.order_callback(
            self.binance_account_id,
            'sell',
            binance_price,
            self.order_size
        )

        pair.status = StrategyStatus.CLOSING
        pair.close_time = datetime.now()
        pair.bybit_trade_filled = False
        pair.binance_trade_filled = False

        logger.info(f"Closing positive spread")

    def _execute_close_negative(self):
        pair = self.arbitrage_pair
        spread = pair.spread_data

        binance_price = spread.binance_bid + 0.01
        bybit_price = spread.bybit_ask - 0.01

        pair.binance_order_id = self.order_callback(
            self.binance_account_id,
            'buy',
            binance_price,
            self.order_size
        )

        pair.bybit_order_id = self.order_callback(
            self.bybit_account_id,
            'sell',
            bybit_price,
            self.order_size
        )

        pair.status = StrategyStatus.CLOSING
        pair.close_time = datetime.now()
        pair.bybit_trade_filled = False
        pair.binance_trade_filled = False

        logger.info(f"Closing negative spread")

    def _check_trade_timeout(self):
        pair = self.arbitrage_pair
        now = datetime.now()

        if pair.status == StrategyStatus.OPENING:
            if pair.open_time and (now - pair.open_time).total_seconds() >= self.trade_timeout:
                self._handle_trade_timeout(pair.open_time)
        elif pair.status == StrategyStatus.CLOSING:
            if pair.close_time and (now - pair.close_time).total_seconds() >= self.trade_timeout:
                self._handle_trade_timeout(pair.close_time)

    def _handle_trade_timeout(self, order_time: datetime):
        pair = self.arbitrage_pair

        if pair.bybit_trade_filled and not pair.binance_trade_filled:
            self._execute_chase_order('binance', order_time)
        elif pair.binance_trade_filled and not pair.bybit_trade_filled:
            self._execute_chase_order('bybit', order_time)
        elif not pair.bybit_trade_filled and not pair.binance_trade_filled:
            logger.warning(f"Both sides not filled after timeout")
            self._cancel_all_orders()
            pair.status = StrategyStatus.IDLE

    def _execute_chase_order(self, platform: str, original_time: datetime):
        pair = self.arbitrage_pair

        passed, message = self.risk_manager.check_chase_order(
            self.strategy_id,
            pair.chase_order_count + 1
        )
        if not passed:
            logger.warning(f"Chase order risk check failed: {message}")
            return

        self._cancel_all_orders()

        spread = pair.spread_data
        price = None

        if platform == 'bybit':
            if pair.bybit_position > 0:
                price = spread.bybit_bid
            else:
                price = spread.bybit_ask
        elif platform == 'binance':
            if pair.binance_position > 0:
                price = spread.binance_bid
            else:
                price = spread.binance_ask

        if price is None:
            logger.warning(f"Cannot determine chase price for {platform}")
            return

        account_id = self.bybit_account_id if platform == 'bybit' else self.binance_account_id
        direction = 'buy' if pair.bybit_position > 0 or pair.binance_position > 0 else 'sell'

        new_order_id = self.order_callback(
            account_id,
            direction,
            price,
            self.order_size
        )

        if platform == 'bybit':
            pair.bybit_order_id = new_order_id
        else:
            pair.binance_order_id = new_order_id

        pair.unilateral_trade_flag = True
        pair.chase_order_count += 1

        logger.info(f"Executing chase order for {platform}, count: {pair.chase_order_count}")

    def _cancel_all_orders(self):
        pair = self.arbitrage_pair

        if pair.bybit_order_id:
            self.order_callback(self.bybit_account_id, 'cancel', 0, 0, pair.bybit_order_id)
            pair.bybit_order_id = None

        if pair.binance_order_id:
            self.order_callback(self.binance_account_id, 'cancel', 0, 0, pair.binance_order_id)
            pair.binance_order_id = None

    def on_trade(self, platform: str, trade_data: Dict[str, Any]):
        if not self.enabled:
            return

        with self.lock:
            pair = self.arbitrage_pair

            if platform == 'bybit':
                pair.bybit_trade_filled = True
                pair.bybit_position = trade_data.get('position', pair.bybit_position)
            elif platform == 'binance':
                pair.binance_trade_filled = True
                pair.binance_position = trade_data.get('position', pair.binance_position)

            self._check_both_filled()

    def _check_both_filled(self):
        pair = self.arbitrage_pair

        if pair.bybit_trade_filled and pair.binance_trade_filled:
            if pair.status == StrategyStatus.OPENING:
                pair.status = StrategyStatus.OPENED
                logger.info(f"Position opened for {self.strategy_id}")
            elif pair.status == StrategyStatus.CLOSING:
                pair.status = StrategyStatus.CLOSED
                pair.pnl = pair.spread_data.spread_positive or pair.spread_data.spread_negative or 0.0
                logger.info(f"Position closed for {self.strategy_id}, PnL: {pair.pnl}")

                passed, message = self.risk_manager.check_trade(
                    self.strategy_id,
                    pair.pnl,
                    pair.chase_order_count
                )
                if not passed:
                    logger.warning(f"Trade risk check failed: {message}")

            pair.unilateral_trade_flag = False
            pair.chase_order_count = 0

    def _run_loop(self):
        while self.running:
            time.sleep(0.1)

    def set_parameters(self, **kwargs):
        with self.lock:
            if 'open_threshold' in kwargs:
                self.open_threshold = kwargs['open_threshold']
            if 'close_threshold' in kwargs:
                self.close_threshold = kwargs['close_threshold']
            if 'order_size' in kwargs:
                self.order_size = kwargs['order_size']
            if 'max_chase_count' in kwargs:
                self.max_chase_count = kwargs['max_chase_count']
            if 'trade_timeout' in kwargs:
                self.trade_timeout = kwargs['trade_timeout']
            logger.info(f"Strategy {self.strategy_id} parameters updated")

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "strategy_id": self.strategy_id,
                "enabled": self.enabled,
                "auto_mode": self.auto_mode,
                "status": self.arbitrage_pair.to_dict(),
                "parameters": {
                    "open_threshold": self.open_threshold,
                    "close_threshold": self.close_threshold,
                    "order_size": self.order_size,
                    "max_chase_count": self.max_chase_count,
                    "trade_timeout": self.trade_timeout
                }
            }