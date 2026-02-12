import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskRule:
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.violations = 0
        self.last_violation_time = None

    def check(self, **kwargs) -> tuple[bool, str]:
        raise NotImplementedError

    def record_violation(self, message: str):
        self.violations += 1
        self.last_violation_time = datetime.now()
        logger.warning(f"Risk rule violation: {self.name} - {message}")


class MaxPositionRiskRule(RiskRule):
    def __init__(self, max_position: float):
        super().__init__("Max Position Risk")
        self.max_position = max_position

    def check(self, current_position: float, **kwargs) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        if abs(current_position) >= self.max_position:
            return False, f"Position {current_position} exceeds max {self.max_position}"
        return True, ""


class MaxOrderSizeRiskRule(RiskRule):
    def __init__(self, max_order_size: float):
        super().__init__("Max Order Size Risk")
        self.max_order_size = max_order_size

    def check(self, order_size: float, **kwargs) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        if abs(order_size) > self.max_order_size:
            return False, f"Order size {order_size} exceeds max {self.max_order_size}"
        return True, ""


class DailyLossRiskRule(RiskRule):
    def __init__(self, max_daily_loss: float):
        super().__init__("Daily Loss Risk")
        self.max_daily_loss = max_daily_loss
        self.daily_pnl = 0.0
        self.reset_date = datetime.now().date()

    def check(self, trade_pnl: float = 0.0, **kwargs) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        today = datetime.now().date()
        if today != self.reset_date:
            self.daily_pnl = 0.0
            self.reset_date = today
            logger.info("Daily loss counter reset")

        self.daily_pnl += trade_pnl

        if self.daily_pnl < -self.max_daily_loss:
            return False, f"Daily loss {self.daily_pnl} exceeds max {self.max_daily_loss}"
        return True, ""

    def reset(self):
        self.daily_pnl = 0.0
        self.reset_date = datetime.now().date()


class MaxChaseOrderRiskRule(RiskRule):
    def __init__(self, max_chase_count: int):
        super().__init__("Max Chase Order Risk")
        self.max_chase_count = max_chase_count

    def check(self, chase_count: int, **kwargs) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        if chase_count >= self.max_chase_count:
            return False, f"Chase count {chase_count} exceeds max {self.max_chase_count}"
        return True, ""


class RiskManager:
    def __init__(self):
        self.rules: List[RiskRule] = []
        self.lock = threading.Lock()
        self.enabled = True
        self.risk_events: List[Dict[str, Any]] = []
        self.max_event_history = 100

    def add_rule(self, rule: RiskRule):
        with self.lock:
            self.rules.append(rule)
            logger.info(f"Added risk rule: {rule.name}")

    def remove_rule(self, rule_name: str):
        with self.lock:
            self.rules = [r for r in self.rules if r.name != rule_name]
            logger.info(f"Removed risk rule: {rule_name}")

    def check_order(self, account_id: str, order_size: float, current_position: float = 0.0) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        with self.lock:
            for rule in self.rules:
                try:
                    passed, message = rule.check(
                        order_size=order_size,
                        current_position=current_position,
                        account_id=account_id
                    )
                    if not passed:
                        self._record_risk_event(account_id, rule.name, message)
                        rule.record_violation(message)
                        return False, message
                except Exception as e:
                    logger.error(f"Error checking rule {rule.name}: {e}")

            return True, ""

    def check_trade(self, account_id: str, trade_pnl: float, chase_count: int = 0) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        with self.lock:
            for rule in self.rules:
                try:
                    passed, message = rule.check(
                        trade_pnl=trade_pnl,
                        chase_count=chase_count,
                        account_id=account_id
                    )
                    if not passed:
                        self._record_risk_event(account_id, rule.name, message)
                        rule.record_violation(message)
                        return False, message
                except Exception as e:
                    logger.error(f"Error checking rule {rule.name}: {e}")

            return True, ""

    def check_chase_order(self, account_id: str, chase_count: int) -> tuple[bool, str]:
        if not self.enabled:
            return True, ""

        with self.lock:
            for rule in self.rules:
                try:
                    passed, message = rule.check(chase_count=chase_count)
                    if not passed:
                        self._record_risk_event(account_id, rule.name, message)
                        rule.record_violation(message)
                        return False, message
                except Exception as e:
                    logger.error(f"Error checking rule {rule.name}: {e}")

            return True, ""

    def enable(self):
        self.enabled = True
        logger.info("Risk manager enabled")

    def disable(self):
        self.enabled = False
        logger.warning("Risk manager disabled")

    def reset_daily_counters(self):
        with self.lock:
            for rule in self.rules:
                if isinstance(rule, DailyLossRiskRule):
                    rule.reset()
            logger.info("Daily risk counters reset")

    def get_risk_summary(self) -> Dict[str, Any]:
        with self.lock:
            total_violations = sum(rule.violations for rule in self.rules)
            active_rules = [rule.name for rule in self.rules if rule.enabled]
            
            recent_events = [
                event for event in self.risk_events
                if datetime.now() - event['timestamp'] < timedelta(hours=24)
            ]

            return {
                "enabled": self.enabled,
                "total_violations": total_violations,
                "active_rules": active_rules,
                "recent_events": recent_events[-10:],
                "rule_details": [
                    {
                        "name": rule.name,
                        "enabled": rule.enabled,
                        "violations": rule.violations,
                        "last_violation": rule.last_violation_time.isoformat() if rule.last_violation_time else None
                    }
                    for rule in self.rules
                ]
            }

    def _record_risk_event(self, account_id: str, rule_name: str, message: str):
        event = {
            "timestamp": datetime.now(),
            "account_id": account_id,
            "rule": rule_name,
            "message": message
        }
        self.risk_events.append(event)

        if len(self.risk_events) > self.max_event_history:
            self.risk_events = self.risk_events[-self.max_event_history:]

        logger.warning(f"Risk event recorded: {event}")

    def configure_default_rules(self, config: Dict[str, Any]):
        self.rules.clear()

        if config.get('max_position'):
            self.add_rule(MaxPositionRiskRule(config['max_position']))

        if config.get('max_order_size'):
            self.add_rule(MaxOrderSizeRiskRule(config['max_order_size']))

        if config.get('max_daily_loss'):
            self.add_rule(DailyLossRiskRule(config['max_daily_loss']))

        if config.get('max_chase_count'):
            self.add_rule(MaxChaseOrderRiskRule(config['max_chase_count']))

        logger.info(f"Configured {len(self.rules)} default risk rules")