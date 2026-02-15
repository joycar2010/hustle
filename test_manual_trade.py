import requests
import json

# 测试场景1：使用不存在的账户ID
def test_nonexistent_account():
    print('=== 测试场景1：使用不存在的账户ID ===')
    test_data = {
        "account_id": "non_existent_account",
        "direction": "buy",
        "price": 5000.0,
        "size": 0.01
    }
    
    try:
        response = requests.post('http://localhost:8000/api/arbitrage/manual-trade', 
                             headers={'Content-Type': 'application/json'},
                             data=json.dumps(test_data))
        print('状态码:', response.status_code)
        print('响应:', response.json())
    except Exception as e:
        print('错误:', e)
    print()

# 测试场景2：使用Binance账户（当前未连接）
def test_binance_disconnected():
    print('=== 测试场景2：使用Binance账户（当前未连接）===')
    test_data = {
        "account_id": "binance_real",
        "direction": "buy",
        "price": 5000.0,
        "size": 0.01
    }
    
    try:
        response = requests.post('http://localhost:8000/api/arbitrage/manual-trade', 
                             headers={'Content-Type': 'application/json'},
                             data=json.dumps(test_data))
        print('状态码:', response.status_code)
        print('响应:', response.json())
    except Exception as e:
        print('错误:', e)
    print()

# 测试场景3：使用Bybit账户（当前未连接）
def test_bybit_disconnected():
    print('=== 测试场景3：使用Bybit账户（当前未连接）===')
    test_data = {
        "account_id": "bybit_real",
        "direction": "buy",
        "price": 5000.0,
        "size": 0.01
    }
    
    try:
        response = requests.post('http://localhost:8000/api/arbitrage/manual-trade', 
                             headers={'Content-Type': 'application/json'},
                             data=json.dumps(test_data))
        print('状态码:', response.status_code)
        print('响应:', response.json())
    except Exception as e:
        print('错误:', e)
    print()

# 测试场景4：缺少必填参数
def test_missing_params():
    print('=== 测试场景4：缺少必填参数 ===')
    test_data = {
        "account_id": "binance_real",
        "direction": "buy",
        "price": 5000.0
        # 缺少 size 参数
    }
    
    try:
        response = requests.post('http://localhost:8000/api/arbitrage/manual-trade', 
                             headers={'Content-Type': 'application/json'},
                             data=json.dumps(test_data))
        print('状态码:', response.status_code)
        print('响应:', response.json())
    except Exception as e:
        print('错误:', e)
    print()

# 运行所有测试
if __name__ == '__main__':
    print('开始测试手动交易功能...\n')
    test_nonexistent_account()
    test_binance_disconnected()
    test_bybit_disconnected()
    test_missing_params()
    print('测试完成！')
