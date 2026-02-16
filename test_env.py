# 测试 Python 环境
import sys
print(f"Python 版本: {sys.version}")

# 测试依赖项
print("\n测试依赖项:")
try:
    import flask
    print(f"Flask: {flask.__version__}")
except ImportError as e:
    print(f"Flask 导入失败: {e}")

try:
    import flask_socketio
    print(f"Flask-SocketIO: {flask_socketio.__version__}")
except ImportError as e:
    print(f"Flask-SocketIO 导入失败: {e}")

try:
    import MetaTrader5
    print(f"MetaTrader5: {MetaTrader5.__version__}")
except ImportError as e:
    print(f"MetaTrader5 导入失败: {e}")

try:
    import numpy
    print(f"NumPy: {numpy.__version__}")
except ImportError as e:
    print(f"NumPy 导入失败: {e}")

try:
    import requests
    print(f"Requests: {requests.__version__}")
except ImportError as e:
    print(f"Requests 导入失败: {e}")

print("\n环境检查完成!")
