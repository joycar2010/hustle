import requests
import time

def test_binance_connection():
    print("测试 Binance API 连接...")
    
    # 测试基础连接
    print("\n1. 测试基础连接到 fapi.binance.com...")
    try:
        response = requests.get('https://fapi.binance.com/fapi/v1/time', timeout=30)
        print(f"✓ 连接成功！状态码: {response.status_code}")
        print(f"  响应时间: {response.elapsed.total_seconds():.2f}秒")
        print(f"  服务器时间: {response.json()}")
    except requests.exceptions.Timeout:
        print("✗ 连接超时（30秒）")
    except requests.exceptions.ConnectionError as e:
        print(f"✗ 连接错误: {e}")
        print("  可能原因：")
        print("  1. 网络连接问题")
        print("  2. 防火墙阻止了连接")
        print("  3. 需要配置代理")
    except Exception as e:
        print(f"✗ 其他错误: {e}")
    
    # 测试API密钥
    print("\n2. 测试API密钥...")
    api_key = "0OYJ2YLAoFNrZCMf5mKDgbm887JD69YXfYt1p5XMnao7PQxXVDxHPXSeQSe7f6Bi"
    base_url = "https://fapi.binance.com"
    
    try:
        headers = {'X-MBX-APIKEY': api_key}
        response = requests.get(f'{base_url}/fapi/v1/account', headers=headers, timeout=30)
        if response.status_code == 200:
            print("✓ API密钥有效")
            account_info = response.json()
            print(f"  账户余额: {account_info.get('totalWalletBalance', 'N/A')}")
        elif response.status_code == 401:
            print("✗ API密钥无效")
        elif response.status_code == 403:
            print("✗ IP地址被限制")
        else:
            print(f"✓ API响应，状态码: {response.status_code}")
    except requests.exceptions.Timeout:
        print("✗ API密钥测试超时")
    except requests.exceptions.ConnectionError as e:
        print(f"✗ API密钥测试连接错误: {e}")
    except Exception as e:
        print(f"✗ API密钥测试错误: {e}")
    
    # 测试网络连通性
    print("\n3. 测试网络连通性...")
    test_urls = [
        'https://www.google.com',
        'https://www.baidu.com',
        'https://fapi.binance.com'
    ]
    
    for url in test_urls:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start_time
            print(f"✓ {url} - {response.status_code} - {elapsed:.2f}秒")
        except Exception as e:
            print(f"✗ {url} - 错误: {str(e)[:50]}")

if __name__ == '__main__':
    test_binance_connection()
    input("\n按 Enter 键退出...")
