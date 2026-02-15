import requests
import json

# 测试 GET 请求
print("Testing GET request...")
get_response = requests.get('http://localhost:8000/api/backup/config')
print(f"GET Status Code: {get_response.status_code}")
print(f"GET Response: {get_response.json()}")
print()

# 测试 POST 请求
print("Testing POST request...")
test_config = {
    "frequency": "hourly",
    "time": "12:00",
    "branch": "master",
    "commitTemplate": "自动备份: {datetime}",
    "includeConfig": True,
    "autoPush": True,
    "sendNotification": False
}

post_response = requests.post('http://localhost:8000/api/backup/config', json=test_config)
print(f"POST Status Code: {post_response.status_code}")
print(f"POST Response: {post_response.json()}")
print()

# 再次测试 GET 请求，验证配置是否已保存
print("Testing GET request again to verify config was saved...")
get_response2 = requests.get('http://localhost:8000/api/backup/config')
print(f"GET Status Code: {get_response2.status_code}")
print(f"GET Response: {get_response2.json()}")
