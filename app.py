from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import threading
import time
from datetime import datetime
from typing import Dict
import logging
from config import MT5_GATEWAY_CONFIG, WEBSERVER_CONFIG, DATA_CONFIG, BINANCE_CONFIG
from mt5_gateway import MT5Gateway
from binance_gateway import BinanceGateway
from account_manager import AccountManager
from risk_manager import RiskManager
from arbitrage_strategy import ArbitrageStrategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vnpy-mt5-gateway-secret-key'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

gateway = None
binance_gateway = None
gateway_lock = threading.Lock()

account_manager = AccountManager()
risk_manager = RiskManager()
arbitrage_strategies: Dict[str, ArbitrageStrategy] = {}
strategy_lock = threading.Lock()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/mt5_login')
def render_mt5_login_page():
    return render_template('mt5_login.html')


@app.route('/api/mt5/login', methods=['POST'])
def mt5_login():
    global gateway

    data = request.get_json()
    login = data.get('login')
    password = data.get('password')
    server = data.get('server')

    if not all([login, password, server]):
        return jsonify({"success": False, "message": "Missing required fields"})

    with gateway_lock:
        if gateway and gateway.connected:
            return jsonify({"success": False, "message": "Already connected"})

        if gateway:
            gateway.disconnect()

        gateway = MT5Gateway(
            login=login,
            password=password,
            server=server,
            symbols=MT5_GATEWAY_CONFIG['symbols']
        )

        if gateway.connect():
            gateway.add_callback(broadcast_price)
            gateway.start_streaming()
            
            account_info = gateway.get_account_info()
            socketio.emit('mt5_login_status', {
                "success": True,
                "connected": True,
                "account_info": account_info
            })
            
            logger.info(f"MT5 login successful: {login}@{server}")
            return jsonify({"success": True, "message": "Login successful"})
        else:
            socketio.emit('mt5_login_status', {
                "success": False,
                "connected": False,
                "error": "Login failed"
            })
            return jsonify({"success": False, "message": "Login failed"})


@app.route('/api/mt5/logout', methods=['POST'])
def mt5_logout():
    global gateway

    with gateway_lock:
        if gateway:
            gateway.disconnect()
            gateway = None
            
            socketio.emit('mt5_login_status', {
                "success": True,
                "connected": False
            })
            
            logger.info("MT5 logout successful")
            return jsonify({"success": True, "message": "Logout successful"})
        return jsonify({"success": False, "message": "Not logged in"})


@app.route('/api/mt5/status')
def mt5_status():
    with gateway_lock:
        if gateway and gateway.connected:
            account_info = gateway.get_account_info()
            return jsonify({
                "success": True,
                "connected": True,
                "account_info": account_info
            })
        return jsonify({
            "success": True,
            "connected": False
        })


@app.route('/api/status')
def get_status():
    with gateway_lock:
        mt5_status = {"connected": False, "error": "Gateway not initialized"}
        binance_status = {"connected": False, "error": "Gateway not initialized"}

        if gateway:
            mt5_status = gateway.get_status()
            if mt5_status.get('last_update'):
                last_update = datetime.fromisoformat(mt5_status['last_update'])
                delay = (datetime.now() - last_update).total_seconds()
                mt5_status['delay_seconds'] = delay
                mt5_status['delay_ok'] = delay <= DATA_CONFIG['max_delay_seconds']

        if binance_gateway:
            binance_status = binance_gateway.get_status()
            if binance_status.get('last_update'):
                last_update = datetime.fromisoformat(binance_status['last_update'])
                delay = (datetime.now() - last_update).total_seconds()
                binance_status['delay_seconds'] = delay
                binance_status['delay_ok'] = delay <= DATA_CONFIG['max_delay_seconds']

        return jsonify({
            "mt5": mt5_status,
            "binance": binance_status
        })


@app.route('/api/connect', methods=['POST'])
def connect_gateway():
    global gateway

    with gateway_lock:
        if gateway and gateway.connected:
            return jsonify({"success": False, "message": "Already connected"})

        if gateway:
            gateway.disconnect()

        gateway = MT5Gateway(
            login=MT5_GATEWAY_CONFIG['login'],
            password=MT5_GATEWAY_CONFIG['password'],
            server=MT5_GATEWAY_CONFIG['server'],
            symbols=MT5_GATEWAY_CONFIG['symbols']
        )

        if gateway.connect():
            gateway.add_callback(broadcast_price)
            gateway.start_streaming()
            logger.info("Gateway connected and streaming started")
            return jsonify({"success": True, "message": "Connected successfully"})
        else:
            return jsonify({"success": False, "message": "Connection failed"})


@app.route('/api/disconnect', methods=['POST'])
def disconnect_gateway():
    global gateway

    with gateway_lock:
        if gateway:
            gateway.disconnect()
            gateway = None
            logger.info("Gateway disconnected")
            return jsonify({"success": True, "message": "Disconnected successfully"})
        return jsonify({"success": False, "message": "Not connected"})


@app.route('/api/binance/connect', methods=['POST'])
def connect_binance():
    global binance_gateway

    with gateway_lock:
        if binance_gateway and binance_gateway.connected:
            return jsonify({"success": False, "message": "Already connected"})

        if binance_gateway:
            binance_gateway.disconnect()

        binance_gateway = BinanceGateway(
            api_key=BINANCE_CONFIG['api_key'],
            secret_key=BINANCE_CONFIG['secret_key'],
            base_url=BINANCE_CONFIG['base_url'],
            symbol=BINANCE_CONFIG['symbol']
        )

        if binance_gateway.connect():
            binance_gateway.add_callback(broadcast_binance_price)
            binance_gateway.start_streaming()
            logger.info("Binance gateway connected and streaming started")
            return jsonify({"success": True, "message": "Connected successfully"})
        else:
            return jsonify({"success": False, "message": "Connection failed"})


@app.route('/api/binance/disconnect', methods=['POST'])
def disconnect_binance():
    global binance_gateway

    with gateway_lock:
        if binance_gateway:
            binance_gateway.disconnect()
            binance_gateway = None
            logger.info("Binance gateway disconnected")
            return jsonify({"success": True, "message": "Disconnected successfully"})
        return jsonify({"success": False, "message": "Not connected"})


def broadcast_price(tick):
    socketio.emit('mt5_price_update', tick)
    logger.debug(f"Broadcast MT5 price: {tick}")


def broadcast_binance_price(tick):
    socketio.emit('binance_price_update', tick)
    logger.debug(f"Broadcast Binance price: {tick}")


@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    with gateway_lock:
        if gateway and gateway.last_price:
            socketio.emit('mt5_price_update', gateway.last_price)
        if binance_gateway and binance_gateway.last_price:
            socketio.emit('binance_price_update', binance_gateway.last_price)


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")


@app.route('/arbitrage')
def arbitrage_page():
    return render_template('arbitrage.html')


@app.route('/api/arbitrage/create', methods=['POST'])
def create_arbitrage_pair():
    data = request.get_json()
    bybit_account_id = data.get('bybit_account_id')
    binance_account_id = data.get('binance_account_id')

    if not all([bybit_account_id, binance_account_id]):
        return jsonify({"success": False, "message": "Missing required fields"})

    strategy_id = f"arb_{bybit_account_id}_{binance_account_id}"
    
    with strategy_lock:
        if strategy_id in arbitrage_strategies:
            return jsonify({"success": False, "message": "Strategy already exists"})

        strategy = ArbitrageStrategy(
            strategy_id=strategy_id,
            bybit_account_id=bybit_account_id,
            binance_account_id=binance_account_id,
            risk_manager=risk_manager,
            order_callback=execute_order,
            trade_callback=on_trade
        )
        
        arbitrage_strategies[strategy_id] = strategy
        
        default_risk_config = {
            'max_position': 1.0,
            'max_order_size': 0.1,
            'max_daily_loss': 100.0,
            'max_chase_count': 5
        }
        risk_manager.configure_default_rules(default_risk_config)

    logger.info(f"Created arbitrage strategy: {strategy_id}")
    return jsonify({"success": True, "strategy_id": strategy_id, "message": "Strategy created"})


@app.route('/api/arbitrage/start', methods=['POST'])
def start_arbitrage_strategy():
    data = request.get_json()
    strategy_id = data.get('strategy_id')

    if not strategy_id:
        return jsonify({"success": False, "message": "Missing strategy_id"})

    with strategy_lock:
        strategy = arbitrage_strategies.get(strategy_id)
        if not strategy:
            return jsonify({"success": False, "message": "Strategy not found"})

        strategy.start()
        
        socketio.emit('arbitrage_status', strategy.get_status())

    return jsonify({"success": True, "message": "Strategy started"})


@app.route('/api/arbitrage/stop', methods=['POST'])
def stop_arbitrage_strategy():
    data = request.get_json()
    strategy_id = data.get('strategy_id')

    if not strategy_id:
        return jsonify({"success": False, "message": "Missing strategy_id"})

    with strategy_lock:
        strategy = arbitrage_strategies.get(strategy_id)
        if not strategy:
            return jsonify({"success": False, "message": "Strategy not found"})

        strategy.stop()
        
        socketio.emit('arbitrage_status', strategy.get_status())

    return jsonify({"success": True, "message": "Strategy stopped"})


@app.route('/api/arbitrage/parameters', methods=['POST'])
def update_arbitrage_parameters():
    data = request.get_json()
    strategy_id = data.get('strategy_id')

    if not strategy_id:
        return jsonify({"success": False, "message": "Missing strategy_id"})

    with strategy_lock:
        strategy = arbitrage_strategies.get(strategy_id)
        if not strategy:
            return jsonify({"success": False, "message": "Strategy not found"})

        strategy.set_parameters(**{k: v for k, v in data.items() if k != 'strategy_id'})
        
        socketio.emit('arbitrage_status', strategy.get_status())

    return jsonify({"success": True, "message": "Parameters updated"})


@app.route('/api/arbitrage/status')
def get_arbitrage_status():
    with strategy_lock:
        strategies_status = {
            strategy_id: strategy.get_status()
            for strategy_id, strategy in arbitrage_strategies.items()
        }

    return jsonify({
        "success": True,
        "strategies": strategies_status,
        "count": len(arbitrage_strategies)
    })


@app.route('/api/arbitrage/manual-trade', methods=['POST'])
def manual_trade():
    data = request.get_json()
    account_id = data.get('account_id')
    direction = data.get('direction')
    price = data.get('price')
    size = data.get('size')

    if not all([account_id, direction, price, size]):
        return jsonify({"success": False, "message": "Missing required fields"})

    with gateway_lock:
        if account_id.startswith('bybit') and gateway:
            order_id = execute_order(account_id, direction, price, size)
            return jsonify({"success": True, "order_id": order_id, "message": "Order placed"})
        elif account_id.startswith('binance') and binance_gateway:
            order_id = execute_order(account_id, direction, price, size)
            return jsonify({"success": True, "order_id": order_id, "message": "Order placed"})
        else:
            return jsonify({"success": False, "message": "Account not connected"})


@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    accounts = account_manager.get_all_accounts()
    return jsonify({
        "success": True,
        "accounts": [acc.to_dict() for acc in accounts]
    })


@app.route('/api/accounts', methods=['POST'])
def add_account():
    data = request.get_json()
    user_id = data.get('user_id', 'default')
    platform = data.get('platform')
    account_type = data.get('account_type')
    credentials = data.get('credentials', {})

    if not all([platform, account_type]):
        return jsonify({"success": False, "message": "Missing required fields"})

    account_id = account_manager.add_account(user_id, platform, account_type, credentials)
    
    return jsonify({
        "success": True,
        "account_id": account_id,
        "message": "Account added"
    })


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def remove_account(account_id):
    success = account_manager.remove_account(account_id)
    
    if success:
        return jsonify({"success": True, "message": "Account removed"})
    else:
        return jsonify({"success": False, "message": "Failed to remove account"})


@app.route('/api/accounts/<account_id>/connect', methods=['POST'])
def connect_account(account_id):
    global gateway, binance_gateway
    
    account = account_manager.get_account(account_id)
    if not account:
        return jsonify({"success": False, "message": "Account not found"})
    
    try:
        if account.platform == 'bybit':
            credentials = account_manager.get_account_credentials(account_id)
            if not credentials:
                return jsonify({"success": False, "message": "Account credentials not found"})
            
            login = credentials.get('account_id')
            password = credentials.get('password')
            server = credentials.get('server')
            
            if not all([login, password, server]):
                return jsonify({"success": False, "message": "Missing required credentials"})
            
            with gateway_lock:
                if gateway and gateway.connected:
                    return jsonify({"success": False, "message": "Another MT5 account is already connected"})
                
                if gateway:
                    gateway.disconnect()
                
                gateway = MT5Gateway(
                    login=login,
                    password=password,
                    server=server,
                    symbols=MT5_GATEWAY_CONFIG['symbols']
                )
                
                if gateway.connect():
                    gateway.add_callback(broadcast_price)
                    gateway.start_streaming()
                    
                    account_manager.update_account_status(account_id, True, gateway.get_account_info())
                    
                    socketio.emit('account_status_update', {
                        "account_id": account_id,
                        "connected": True,
                        "account_info": gateway.get_account_info()
                    })
                    
                    logger.info(f"MT5 account connected: {account_id}")
                    return jsonify({"success": True, "message": "Connected successfully"})
                else:
                    return jsonify({"success": False, "message": "Connection failed"})
        
        elif account.platform == 'binance':
            credentials = account_manager.get_account_credentials(account_id)
            if not credentials:
                return jsonify({"success": False, "message": "Account credentials not found"})
            
            api_key = credentials.get('account_id')
            secret_key = credentials.get('password')
            
            if not all([api_key, secret_key]):
                return jsonify({"success": False, "message": "Missing required credentials"})
            
            with gateway_lock:
                if binance_gateway and binance_gateway.connected:
                    return jsonify({"success": False, "message": "Another Binance account is already connected"})
                
                if binance_gateway:
                    binance_gateway.disconnect()
                
                binance_gateway = BinanceGateway(
                    api_key=api_key,
                    secret_key=secret_key,
                    base_url=BINANCE_CONFIG['base_url'],
                    symbol=BINANCE_CONFIG['symbol']
                )
                
                if binance_gateway.connect():
                    binance_gateway.add_callback(broadcast_binance_price)
                    binance_gateway.start_streaming()
                    
                    ticker = binance_gateway.get_24h_ticker()
                    balance = ticker.get('quoteVolume', 0) if ticker else 0
                    
                    account_manager.update_account_status(account_id, True, {"balance": balance})
                    
                    socketio.emit('account_status_update', {
                        "account_id": account_id,
                        "connected": True,
                        "account_info": {"balance": balance}
                    })
                    
                    logger.info(f"Binance account connected: {account_id}")
                    return jsonify({"success": True, "message": "Connected successfully"})
                else:
                    return jsonify({"success": False, "message": "Connection failed"})
        
        else:
            return jsonify({"success": False, "message": "Unsupported platform"})
    
    except Exception as e:
        logger.error(f"Error connecting account {account_id}: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/version-control')
def version_control_page():
    return render_template('version_control.html')


@app.route('/api/backup/status')
def backup_status():
    try:
        import subprocess
        import datetime
        
        # 检查 GitHub 连接
        github_status = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True, cwd='.')
        github_connected = github_status.returncode == 0
        
        # 获取当前分支
        branch_status = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True, cwd='.')
        current_branch = branch_status.stdout.strip() if branch_status.returncode == 0 else 'Unknown'
        
        # 获取最新提交
        commit_status = subprocess.run(['git', 'log', '-1', '--format=%H'], capture_output=True, text=True, cwd='.')
        latest_commit = commit_status.stdout.strip() if commit_status.returncode == 0 else 'Unknown'
        
        # 检查未提交变更
        status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, cwd='.')
        uncommitted_changes = len(status.stdout.strip().split('\n')) if status.stdout.strip() else 0
        
        # 模拟备份状态
        backup_enabled = True
        last_backup = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            "success": True,
            "status": {
                "github_connected": github_connected,
                "current_branch": current_branch,
                "latest_commit": latest_commit,
                "uncommitted_changes": uncommitted_changes,
                "backup_enabled": backup_enabled,
                "last_backup": last_backup
            }
        })
    except Exception as e:
        logger.error(f"Error getting backup status: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/backup/run', methods=['POST'])
def run_backup():
    try:
        import subprocess
        import datetime
        
        data = request.get_json()
        message = data.get('message', f'自动备份: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        include_config = data.get('includeConfig', True)
        auto_push = data.get('autoPush', True)
        
        # 添加所有文件
        subprocess.run(['git', 'add', '.'], cwd='.')
        
        # 提交变更
        commit_result = subprocess.run(['git', 'commit', '-m', message], capture_output=True, text=True, cwd='.')
        
        # 推送变更
        push_result = None
        if auto_push:
            push_result = subprocess.run(['git', 'push', 'origin', 'master'], capture_output=True, text=True, cwd='.')
        
        return jsonify({
            "success": True,
            "message": "备份成功",
            "commit_result": commit_result.stdout if commit_result else "No commit needed",
            "push_result": push_result.stdout if push_result else "No push needed"
        })
    except Exception as e:
        logger.error(f"Error running backup: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/backup/history')
def backup_history():
    try:
        import subprocess
        
        # 获取提交历史
        history_result = subprocess.run([
            'git', 'log', '--pretty=format:%H|%an|%s|%at', '-n', '50'
        ], capture_output=True, text=True, cwd='.')
        
        if history_result.returncode != 0:
            return jsonify({"success": False, "message": "Failed to get git history"})
        
        # 解析历史记录
        history = []
        for line in history_result.stdout.strip().split('\n'):
            if line:
                parts = line.split('|', 3)
                if len(parts) == 4:
                    history.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "message": parts[2],
                        "timestamp": int(parts[3])
                    })
        
        return jsonify({"success": True, "history": history})
    except Exception as e:
        logger.error(f"Error getting backup history: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/backup/rollback', methods=['POST'])
def backup_rollback():
    try:
        import subprocess
        
        data = request.get_json()
        commit_hash = data.get('commit_hash')
        
        if not commit_hash:
            return jsonify({"success": False, "message": "Missing commit hash"})
        
        # 执行回滚
        reset_result = subprocess.run(
            ['git', 'reset', '--hard', commit_hash],
            capture_output=True, text=True, cwd='.'
        )
        
        if reset_result.returncode != 0:
            return jsonify({"success": False, "message": f"Rollback failed: {reset_result.stderr}"})
        
        # 推送回滚
        push_result = subprocess.run(
            ['git', 'push', 'origin', 'master', '--force'],
            capture_output=True, text=True, cwd='.'
        )
        
        if push_result.returncode != 0:
            return jsonify({"success": False, "message": f"Push failed: {push_result.stderr}"})
        
        return jsonify({"success": True, "message": f"Successfully rolled back to {commit_hash}"})
    except Exception as e:
        logger.error(f"Error rolling back: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/backup/config', methods=['POST'])
def backup_config():
    try:
        data = request.get_json()
        
        # 保存配置到文件
        import json
        with open('backup_config.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "message": "Backup config saved"})
    except Exception as e:
        logger.error(f"Error saving backup config: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/accounts/<account_id>/disconnect', methods=['POST'])
def disconnect_account(account_id):
    global gateway, binance_gateway
    
    account = account_manager.get_account(account_id)
    if not account:
        return jsonify({"success": False, "message": "Account not found"})
    
    try:
        if account.platform == 'bybit':
            with gateway_lock:
                if gateway and gateway.connected:
                    gateway.disconnect()
                    gateway = None
                    
                    account_manager.update_account_status(account_id, False, None)
                    
                    socketio.emit('account_status_update', {
                        "account_id": account_id,
                        "connected": False
                    })
                    
                    logger.info(f"MT5 account disconnected: {account_id}")
                    return jsonify({"success": True, "message": "Disconnected successfully"})
                else:
                    return jsonify({"success": False, "message": "Not connected"})
        
        elif account.platform == 'binance':
            with gateway_lock:
                if binance_gateway and binance_gateway.connected:
                    binance_gateway.disconnect()
                    binance_gateway = None
                    
                    account_manager.update_account_status(account_id, False, None)
                    
                    socketio.emit('account_status_update', {
                        "account_id": account_id,
                        "connected": False
                    })
                    
                    logger.info(f"Binance account disconnected: {account_id}")
                    return jsonify({"success": True, "message": "Disconnected successfully"})
                else:
                    return jsonify({"success": False, "message": "Not connected"})
        
        else:
            return jsonify({"success": False, "message": "Unsupported platform"})
    
    except Exception as e:
        logger.error(f"Error disconnecting account {account_id}: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/risk/status')
def get_risk_status():
    risk_summary = risk_manager.get_risk_summary()
    return jsonify({
        "success": True,
        "risk": risk_summary
    })


@app.route('/api/risk/reset', methods=['POST'])
def reset_risk_counters():
    risk_manager.reset_daily_counters()
    return jsonify({
        "success": True,
        "message": "Risk counters reset"
    })


def execute_order(account_id: str, direction: str, price: float, size: float, order_id: str = None) -> str:
    result_order_id = None
    
    if account_id.startswith('bybit') and gateway:
        result_order_id = gateway.send_order(direction, price, size, order_id)
        if result_order_id:
            on_trade('bybit', {
                'direction': direction,
                'price': price,
                'size': size,
                'order_id': result_order_id,
                'status': 'filled'
            })
    elif account_id.startswith('binance') and binance_gateway:
        result_order_id = binance_gateway.send_order(direction, price, size, order_id)
        if result_order_id:
            on_trade('binance', {
                'direction': direction,
                'price': price,
                'size': size,
                'order_id': result_order_id,
                'status': 'filled'
            })
    
    return result_order_id


def on_trade(platform: str, trade_data: Dict):
    for strategy_id, strategy in arbitrage_strategies.items():
        strategy.on_trade(platform, trade_data)
    
    socketio.emit('trade_update', {
        "platform": platform,
        "trade_data": trade_data
    })


def broadcast_price(tick):
    socketio.emit('mt5_price_update', tick)
    
    for strategy_id, strategy in arbitrage_strategies.items():
        strategy.update_tick('bybit', tick)


def broadcast_binance_price(tick):
    socketio.emit('binance_price_update', tick)
    
    for strategy_id, strategy in arbitrage_strategies.items():
        strategy.update_tick('binance', tick)


if __name__ == '__main__':
    logger.info(f"Starting web server on {WEBSERVER_CONFIG['host']}:{WEBSERVER_CONFIG['port']}")
    socketio.run(app, host=WEBSERVER_CONFIG['host'], port=WEBSERVER_CONFIG['port'], debug=WEBSERVER_CONFIG['debug'])
