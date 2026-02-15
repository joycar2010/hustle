import requests
import json

# 测试手动备份 API，包含备注功能
print("Testing manual backup with note...")

backup_data = {
    "message": "手动备份: 2026-02-15 20:30:00 - 测试备注功能",
    "includeConfig": True,
    "autoPush": True
}

response = requests.post('http://localhost:8000/api/backup/run', json=backup_data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# 测试获取备份历史
print("\nTesting backup history...")
history_response = requests.get('http://localhost:8000/api/backup/history')
print(f"Status Code: {history_response.status_code}")
history_data = history_response.json()
if history_data.get('success'):
    print(f"Number of backups: {len(history_data.get('history', []))}")
    # 打印最新的几个备份
    for i, backup in enumerate(history_data.get('history', [])[:3]):
        print(f"Backup {i+1}: {backup.get('message')}")
else:
    print(f"Error getting history: {history_data.get('message')}")
