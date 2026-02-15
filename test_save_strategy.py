import requests
import json

# 测试数据
strategy_data = {
    "strategy": [
        {
            "layer": "1",
            "open_price": 1000.5,
            "spread": 0.5,
            "binance_size_limit": 1,
            "bybit_size_limit": 0.01,
            "strategy_type": "reverse_arbitrage_bybit"
        },
        {
            "layer": "2",
            "open_price": 2000.75,
            "spread": 1.0,
            "binance_size_limit": 2,
            "bybit_size_limit": 0.02,
            "strategy_type": "reverse_arbitrage_bybit"
        }
    ],
    "strategy_type": "reverse_arbitrage_bybit",
    "mcoin_order_size": 1,
    "open_sync": 1,
    "close_sync": 1
}

# 发送保存请求
try:
    response = requests.post('http://localhost:8000/api/strategy/save-grid', 
                         headers={'Content-Type': 'application/json'},
                         data=json.dumps(strategy_data))
    print('保存请求状态码:', response.status_code)
    print('保存请求响应:', response.json())
    
    # 发送获取请求，验证数据是否保存成功
    get_response = requests.get('http://localhost:8000/api/strategy/settings?strategy_type=reverse_arbitrage_bybit')
    print('\n获取请求状态码:', get_response.status_code)
    print('获取请求响应:', get_response.json())
    
    # 检查本地文件
    with open('arbitrage_settings.json', 'r', encoding='utf-8') as f:
        settings_data = json.load(f)
        print('\n文件中strategy_settings:', settings_data.get('strategy_settings', {}))
        print('反向套利策略数据:', settings_data.get('strategy_settings', {}).get('reverse_arbitrage_bybit', {}))
        
        if 'reverse_arbitrage_bybit' in settings_data.get('strategy_settings', {}):
            strategy = settings_data['strategy_settings']['reverse_arbitrage_bybit'].get('strategy', [])
            print('策略阶梯数量:', len(strategy))
            for i, layer in enumerate(strategy):
                print(f'阶梯 {i+1}:', layer)
                
except Exception as e:
    print('错误:', e)
