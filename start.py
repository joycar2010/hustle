# 启动脚本
import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print(f"Python 版本: {sys.version}")
print(f"当前目录: {os.getcwd()}")
print(f"Python 路径: {sys.path}")

# 导入并运行应用
try:
    from app import app, socketio, WEBSERVER_CONFIG, start_margin_status_broadcast
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting web server on {WEBSERVER_CONFIG['host']}:{WEBSERVER_CONFIG['port']}")
    # 启动保证金状态广播
    start_margin_status_broadcast()
    socketio.run(app, host=WEBSERVER_CONFIG['host'], port=WEBSERVER_CONFIG['port'], debug=WEBSERVER_CONFIG['debug'])
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    input("按 Enter 键退出...")
