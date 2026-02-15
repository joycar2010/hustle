import requests
import json
import time
import hmac
import hashlib
from datetime import datetime
import MetaTrader5 as mt5
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionDiagnostics:
    def __init__(self):
        self.results = {
            "binance": {},
            "bybit": {},
            "network": {},
            "summary": []
        }

    def test_network_connection(self):
        """测试网络连接"""
        logger.info("=== 网络连接测试 ===")
        
        test_urls = [
            ("Google DNS", "https://8.8.8.8"),
            ("Binance API", "https://fapi.binance.com"),
            ("Binance Spot", "https://api.binance.com"),
            ("GitHub", "https://github.com")
        ]
        
        for name, url in test_urls:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=5)
                elapsed_time = (time.time() - start_time) * 1000
                
                self.results["network"][name] = {
                    "status": "success",
                    "response_time_ms": round(elapsed_time, 2),
                    "status_code": response.status_code
                }
                logger.info(f"✓ {name}: {response.status_code} ({elapsed_time:.2f}ms)")
            except Exception as e:
                self.results["network"][name] = {
                    "status": "failed",
                    "error": str(e)
                }
                logger.error(f"✗ {name}: {str(e)}")

    def test_binance_api(self, api_key, secret_key):
        """测试Binance API连接"""
        logger.info("\n=== Binance API 连接测试 ===")
        
        base_url = "https://fapi.binance.com"
        
        # 测试1: 服务器时间
        try:
            response = requests.get(f"{base_url}/fapi/v1/time", timeout=10)
            if response.status_code == 200:
                server_time = response.json()
                local_time = int(time.time() * 1000)
                time_diff = abs(server_time['serverTime'] - local_time)
                
                self.results["binance"]["server_time"] = {
                    "status": "success",
                    "server_time": server_time['serverTime'],
                    "local_time": local_time,
                    "time_diff_ms": time_diff,
                    "time_sync": "OK" if time_diff < 1000 else "WARNING"
                }
                logger.info(f"✓ 服务器时间: {server_time['serverTime']} (时间差: {time_diff}ms)")
            else:
                self.results["binance"]["server_time"] = {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": response.text
                }
                logger.error(f"✗ 服务器时间请求失败: {response.status_code}")
        except Exception as e:
            self.results["binance"]["server_time"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ 服务器时间请求异常: {str(e)}")

        # 测试2: 市场数据
        try:
            symbol = "XAUUSDT"
            response = requests.get(
                f"{base_url}/fapi/v1/ticker/price",
                params={"symbol": symbol},
                timeout=10
            )
            if response.status_code == 200:
                price_data = response.json()
                self.results["binance"]["market_data"] = {
                    "status": "success",
                    "symbol": symbol,
                    "price": price_data['price'],
                    "timestamp": price_data['time']
                }
                logger.info(f"✓ 市场数据: {symbol} = {price_data['price']}")
            else:
                self.results["binance"]["market_data"] = {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": response.text
                }
                logger.error(f"✗ 市场数据请求失败: {response.status_code}")
        except Exception as e:
            self.results["binance"]["market_data"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ 市场数据请求异常: {str(e)}")

        # 测试3: API密钥验证
        try:
            headers = {'X-MBX-APIKEY': api_key}
            response = requests.get(
                f"{base_url}/fapi/v2/account",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                account_data = response.json()
                self.results["binance"]["api_key"] = {
                    "status": "success",
                    "api_key_valid": True,
                    "account_type": account_data.get('accountType', 'unknown'),
                    "total_wallet_balance": account_data.get('totalWalletBalance', 0)
                }
                logger.info(f"✓ API密钥有效: 账户类型={account_data.get('accountType', 'unknown')}")
            elif response.status_code == 401:
                self.results["binance"]["api_key"] = {
                    "status": "failed",
                    "error": "API密钥无效或已过期",
                    "status_code": 401
                }
                logger.error("✗ API密钥无效或已过期 (401)")
            elif response.status_code == 403:
                self.results["binance"]["api_key"] = {
                    "status": "failed",
                    "error": "API密钥权限不足",
                    "status_code": 403
                }
                logger.error("✗ API密钥权限不足 (403)")
            else:
                self.results["binance"]["api_key"] = {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": response.text
                }
                logger.error(f"✗ API密钥验证失败: {response.status_code}")
        except Exception as e:
            self.results["binance"]["api_key"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ API密钥验证异常: {str(e)}")

        # 测试4: 签名验证
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'timestamp': timestamp,
                'recvWindow': 5000
            }
            
            query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
            signature = hmac.new(
                secret_key.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            params['signature'] = signature
            
            headers = {'X-MBX-APIKEY': api_key}
            response = requests.get(
                f"{base_url}/fapi/v2/account",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                self.results["binance"]["signature"] = {
                    "status": "success",
                    "signature_valid": True
                }
                logger.info("✓ 签名验证成功")
            else:
                self.results["binance"]["signature"] = {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": response.text
                }
                logger.error(f"✗ 签名验证失败: {response.status_code}")
        except Exception as e:
            self.results["binance"]["signature"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ 签名验证异常: {str(e)}")

    def test_bybit_mt5(self, login, password, server):
        """测试Bybit MT5连接"""
        logger.info("\n=== Bybit MT5 连接测试 ===")
        
        # 测试1: MT5初始化
        try:
            if not mt5.initialize():
                error = mt5.last_error()
                self.results["bybit"]["mt5_init"] = {
                    "status": "failed",
                    "error": str(error)
                }
                logger.error(f"✗ MT5初始化失败: {error}")
                return
            else:
                self.results["bybit"]["mt5_init"] = {
                    "status": "success"
                }
                logger.info("✓ MT5初始化成功")
        except Exception as e:
            self.results["bybit"]["mt5_init"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ MT5初始化异常: {str(e)}")
            return

        # 测试2: MT5登录
        try:
            if not mt5.login(int(login), password, server):
                error = mt5.last_error()
                self.results["bybit"]["mt5_login"] = {
                    "status": "failed",
                    "error": str(error)
                }
                logger.error(f"✗ MT5登录失败: {error}")
                mt5.shutdown()
                return
            else:
                self.results["bybit"]["mt5_login"] = {
                    "status": "success",
                    "login": login,
                    "server": server
                }
                logger.info(f"✓ MT5登录成功: {login}@{server}")
        except Exception as e:
            self.results["bybit"]["mt5_login"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ MT5登录异常: {str(e)}")
            mt5.shutdown()
            return

        # 测试3: 获取账户信息
        try:
            account_info = mt5.account_info()
            if account_info:
                self.results["bybit"]["account_info"] = {
                    "status": "success",
                    "login": account_info.login,
                    "server": account_info.server,
                    "company": account_info.company,
                    "currency": account_info.currency,
                    "balance": account_info.balance,
                    "equity": account_info.equity,
                    "margin": account_info.margin,
                    "free_margin": account_info.margin_free,
                    "margin_level": account_info.margin_level,
                    "profit": account_info.profit
                }
                logger.info(f"✓ 账户信息: 余额={account_info.balance}, 权益={account_info.equity}")
            else:
                self.results["bybit"]["account_info"] = {
                    "status": "failed",
                    "error": str(mt5.last_error())
                }
                logger.error(f"✗ 获取账户信息失败: {mt5.last_error()}")
        except Exception as e:
            self.results["bybit"]["account_info"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ 获取账户信息异常: {str(e)}")

        # 测试4: 获取交易品种信息
        try:
            symbol = "XAUUSD.s"
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                self.results["bybit"]["symbol_info"] = {
                    "status": "success",
                    "symbol": symbol,
                    "description": symbol_info.description,
                    "trade_mode": symbol_info.trade_mode,
                    "digits": symbol_info.digits,
                    "point": symbol_info.point,
                    "volume_min": symbol_info.volume_min,
                    "volume_max": symbol_info.volume_max,
                    "volume_step": symbol_info.volume_step,
                    "spread": symbol_info.spread
                }
                logger.info(f"✓ 交易品种信息: {symbol}, 点差={symbol_info.spread}")
            else:
                self.results["bybit"]["symbol_info"] = {
                    "status": "failed",
                    "error": str(mt5.last_error())
                }
                logger.error(f"✗ 获取交易品种信息失败: {mt5.last_error()}")
        except Exception as e:
            self.results["bybit"]["symbol_info"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ 获取交易品种信息异常: {str(e)}")

        # 测试5: 获取实时报价
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                self.results["bybit"]["tick_data"] = {
                    "status": "success",
                    "symbol": symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "spread": tick.ask - tick.bid,
                    "time": datetime.fromtimestamp(tick.time).isoformat(),
                    "volume": tick.volume
                }
                logger.info(f"✓ 实时报价: 买价={tick.bid}, 卖价={tick.ask}, 点差={tick.ask - tick.bid}")
            else:
                self.results["bybit"]["tick_data"] = {
                    "status": "failed",
                    "error": str(mt5.last_error())
                }
                logger.error(f"✗ 获取实时报价失败: {mt5.last_error()}")
        except Exception as e:
            self.results["bybit"]["tick_data"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"✗ 获取实时报价异常: {str(e)}")

        mt5.shutdown()

    def generate_summary(self):
        """生成诊断摘要"""
        logger.info("\n=== 诊断摘要 ===")
        
        # Binance摘要
        binance_ok = True
        for test_name, result in self.results["binance"].items():
            if result.get("status") != "success":
                binance_ok = False
                break
        
        if binance_ok:
            self.results["summary"].append("✓ Binance API 连接正常")
            logger.info("✓ Binance API 连接正常")
        else:
            self.results["summary"].append("✗ Binance API 连接存在问题")
            logger.error("✗ Binance API 连接存在问题")

        # Bybit摘要
        bybit_ok = True
        for test_name, result in self.results["bybit"].items():
            if result.get("status") != "success":
                bybit_ok = False
                break
        
        if bybit_ok:
            self.results["summary"].append("✓ Bybit MT5 连接正常")
            logger.info("✓ Bybit MT5 连接正常")
        else:
            self.results["summary"].append("✗ Bybit MT5 连接存在问题")
            logger.error("✗ Bybit MT5 连接存在问题")

        # 网络摘要
        network_ok = True
        for test_name, result in self.results["network"].items():
            if result.get("status") != "success":
                network_ok = False
                break
        
        if network_ok:
            self.results["summary"].append("✓ 网络连接正常")
            logger.info("✓ 网络连接正常")
        else:
            self.results["summary"].append("✗ 网络连接存在问题")
            logger.error("✗ 网络连接存在问题")

    def save_results(self, filename="diagnostic_results.json"):
        """保存诊断结果"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logger.info(f"\n诊断结果已保存到: {filename}")

    def print_detailed_report(self):
        """打印详细报告"""
        print("\n" + "="*80)
        print("详细诊断报告")
        print("="*80)
        
        print("\n【网络连接】")
        for test_name, result in self.results["network"].items():
            status_icon = "✓" if result.get("status") == "success" else "✗"
            print(f"{status_icon} {test_name}: {result}")
        
        print("\n【Binance API】")
        for test_name, result in self.results["binance"].items():
            status_icon = "✓" if result.get("status") == "success" else "✗"
            print(f"{status_icon} {test_name}: {result}")
        
        print("\n【Bybit MT5】")
        for test_name, result in self.results["bybit"].items():
            status_icon = "✓" if result.get("status") == "success" else "✗"
            print(f"{status_icon} {test_name}: {result}")
        
        print("\n【诊断摘要】")
        for summary in self.results["summary"]:
            print(summary)
        
        print("\n" + "="*80)


def main():
    from config import BINANCE_CONFIG, MT5_GATEWAY_CONFIG
    
    diagnostics = ConnectionDiagnostics()
    
    # 测试网络连接
    diagnostics.test_network_connection()
    
    # 测试Binance API
    diagnostics.test_binance_api(
        BINANCE_CONFIG['api_key'],
        BINANCE_CONFIG['secret_key']
    )
    
    # 测试Bybit MT5
    diagnostics.test_bybit_mt5(
        MT5_GATEWAY_CONFIG['login'],
        MT5_GATEWAY_CONFIG['password'],
        MT5_GATEWAY_CONFIG['server']
    )
    
    # 生成摘要
    diagnostics.generate_summary()
    
    # 保存结果
    diagnostics.save_results()
    
    # 打印详细报告
    diagnostics.print_detailed_report()


if __name__ == "__main__":
    main()
