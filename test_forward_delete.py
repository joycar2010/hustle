import requests
import json

# 测试数据 - 空策略数组，模拟删除所有阶梯后的情况
strategy_data = {
    "strategy": [],  # 空策略数组
    "strategy_type": "forward_arbitrage_binance",
    "mcoin_order_size": 1,
    "open_sync": 1,
    "close_sync": 1
}

# 发送保存请求（模拟删除所有阶梯后的保存操作）
try:
    print('=== 测试正向套利策略删除后保存 ===')
    response = requests.post('http://localhost:8000/api/strategy/save-grid', 
                         headers={'Content-Type': 'application/json'},
                         data=json.dumps(strategy_data))
    print('删除后保存请求状态码:', response.status_code)
    print('删除后保存请求响应:', response.json())
    
    # 发送获取请求，验证数据是否保存成功
    print('\n=== 测试正向套利策略获取 ===')
    get_response = requests.get('http://localhost:8000/api/strategy/settings?strategy_type=forward_arbitrage_binance')
    print('获取请求状态码:', get_response.status_code)
    print('获取请求响应:', get_response.json())
    
    # 检查本地文件
    print('\n=== 检查本地文件 ===')
    with open('arbitrage_settings.json', 'r', encoding='utf-8') as f:
        settings_data = json.load(f)
        print('正向套利策略数据:', settings_data.get('strategy_settings', {}).get('forward_arbitrage_binance', {}))
        
        if 'forward_arbitrage_binance' in settings_data.get('strategy_settings', {}):
            strategy = settings_data['strategy_settings']['forward_arbitrage_binance'].get('strategy', [])
            print('策略阶梯数量:', len(strategy))
            if len(strategy) == 0:
                print('✅ 成功：所有阶梯已删除，策略数组为空')
            else:
                print('❌ 失败：策略数组不为空')
                
except Exception as e:
    print('错误:', e)
