import threading
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Account:
    def __init__(self, account_id: str, platform: str, account_type: str, credentials: Dict[str, Any]):
        self.account_id = account_id
        self.platform = platform
        self.account_type = account_type
        self.credentials = credentials
        self.connected = False
        self.balance = 0.0
        self.equity = 0.0
        self.margin = 0.0
        self.free_margin = 0.0
        self.last_update = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "platform": self.platform,
            "account_type": self.account_type,
            "connected": self.connected,
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "last_update": self.last_update.isoformat() if self.last_update else None
        }


class AccountManager:
    def __init__(self):
        self.accounts: Dict[str, Account] = {}
        self.user_accounts: Dict[str, List[str]] = {}
        self.lock = threading.Lock()
        self.config_file = "accounts_config.json"
        self._load_config()

    def add_account(self, user_id: str, platform: str, account_type: str, credentials: Dict[str, Any]) -> str:
        account_id = self._generate_account_id(user_id, platform, account_type)
        
        with self.lock:
            if account_id in self.accounts:
                logger.warning(f"Account {account_id} already exists")
                return account_id

            account = Account(account_id, platform, account_type, credentials)
            self.accounts[account_id] = account

            if user_id not in self.user_accounts:
                self.user_accounts[user_id] = []
            self.user_accounts[user_id].append(account_id)

            self._save_config()
            logger.info(f"Added account: {account_id}")
            return account_id

    def remove_account(self, account_id: str) -> bool:
        with self.lock:
            if account_id not in self.accounts:
                logger.warning(f"Account {account_id} not found")
                return False

            account = self.accounts[account_id]
            if account.connected:
                logger.warning(f"Cannot remove connected account: {account_id}")
                return False

            del self.accounts[account_id]

            for user_id, account_ids in self.user_accounts.items():
                if account_id in account_ids:
                    account_ids.remove(account_id)
                    if not account_ids:
                        del self.user_accounts[user_id]
                    break

            self._save_config()
            logger.info(f"Removed account: {account_id}")
            return True

    def get_account(self, account_id: str) -> Optional[Account]:
        with self.lock:
            return self.accounts.get(account_id)

    def get_all_accounts(self) -> List[Account]:
        with self.lock:
            return list(self.accounts.values())

    def get_user_accounts(self, user_id: str) -> List[Account]:
        with self.lock:
            account_ids = self.user_accounts.get(user_id, [])
            return [self.accounts[aid] for aid in account_ids if aid in self.accounts]

    def update_account_status(self, account_id: str, connected: bool, account_info: Optional[Dict[str, Any]] = None):
        with self.lock:
            account = self.accounts.get(account_id)
            if not account:
                logger.warning(f"Account {account_id} not found")
                return

            account.connected = connected
            account.last_update = datetime.now()

            if account_info:
                account.balance = account_info.get('balance', account.balance)
                account.equity = account_info.get('equity', account.equity)
                account.margin = account_info.get('margin', account.margin)
                account.free_margin = account_info.get('free_margin', account.free_margin)

    def get_account_credentials(self, account_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            account = self.accounts.get(account_id)
            if not account:
                return None
            return account.credentials.copy()

    def _generate_account_id(self, user_id: str, platform: str, account_type: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{user_id}_{platform}_{account_type}_{timestamp}"
        account_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{user_id}_{platform}_{account_type}_{account_hash}"

    def _save_config(self):
        config = {
            "accounts": [
                {
                    "account_id": acc.account_id,
                    "platform": acc.platform,
                    "account_type": acc.account_type,
                    "credentials": self._encrypt_credentials(acc.credentials)
                }
                for acc in self.accounts.values()
            ],
            "user_accounts": self.user_accounts
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Account configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            for acc_config in config.get('accounts', []):
                credentials = self._decrypt_credentials(acc_config['credentials'])
                account = Account(
                    acc_config['account_id'],
                    acc_config['platform'],
                    acc_config['account_type'],
                    credentials
                )
                self.accounts[account.account_id] = account

            self.user_accounts = config.get('user_accounts', {})
            logger.info("Account configuration loaded")
        except FileNotFoundError:
            logger.info("No existing configuration found")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    def _encrypt_credentials(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        # 暂时不加密，直接存储明文用于测试
        return credentials.copy()

    def _decrypt_credentials(self, encrypted_credentials: Dict[str, str]) -> Dict[str, Any]:
        return encrypted_credentials.copy()

    def get_status_summary(self) -> Dict[str, Any]:
        with self.lock:
            total_accounts = len(self.accounts)
            connected_accounts = sum(1 for acc in self.accounts.values() if acc.connected)
            
            platform_stats = {}
            for acc in self.accounts.values():
                if acc.platform not in platform_stats:
                    platform_stats[acc.platform] = {"total": 0, "connected": 0}
                platform_stats[acc.platform]["total"] += 1
                if acc.connected:
                    platform_stats[acc.platform]["connected"] += 1

            return {
                "total_accounts": total_accounts,
                "connected_accounts": connected_accounts,
                "platform_stats": platform_stats,
                "users": len(self.user_accounts)
            }