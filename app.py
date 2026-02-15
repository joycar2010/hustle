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

trade_history = []
trade_history_lock = threading.Lock()

# 设置存储
sync_settings_store = {}
strategy_settings_store = {}
alert_settings_store = {}
settings_lock = threading.Lock()
settings_file = "arbitrage_settings.json"

# 加载设置
try:
    import json
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings_data = json.load(f)
        sync_settings_store = settings_data.get('sync_settings', {})
        strategy_settings_store = settings_data.get('strategy_settings', {})
        alert_settings_store = settings_data.get('alert_settings', {})
    logger.info("Settings loaded from file")
except FileNotFoundError:
    logger.info("No settings file found, using defaults")
except Exception as e:
    logger.error(f"Error loading settings: {e}")


@app.route('/test')
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


@app.route('/')
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


@app.route('/api/sync/settings', methods=['POST'])
def save_sync_settings():
    """保存套利策略的开仓数据同步和平仓数据同步设置"""
    data = request.get_json()
    open_sync = data.get('open_sync')
    close_sync = data.get('close_sync')
    strategy_type = data.get('strategy_type', 'reverse_arbitrage_bybit')

    if open_sync is None or close_sync is None:
        return jsonify({"success": False, "message": "Missing required fields"})

    try:
        # 保存到内存存储
        sync_settings = {
            'open_sync': open_sync,
            'close_sync': close_sync,
            'strategy_type': strategy_type,
            'updated_at': datetime.now().isoformat()
        }

        # 保存到文件
        with settings_lock:
            sync_settings_store[strategy_type] = sync_settings
            # 保存到文件
            import json
            settings_data = {
                'sync_settings': sync_settings_store,
                'strategy_settings': strategy_settings_store,
                'alert_settings': alert_settings_store
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved sync settings: {sync_settings}")
        return jsonify({"success": True, "message": "同步设置保存成功", "data": sync_settings})
    except Exception as e:
        logger.error(f"Error saving sync settings: {e}")
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"})


@app.route('/api/strategy/save-grid', methods=['POST'])
def save_grid_strategy():
    """保存套利策略的阶梯策略设置"""
    data = request.get_json()
    strategy = data.get('strategy')
    mcoin_order_size = data.get('mcoin_order_size')
    open_sync = data.get('open_sync')
    close_sync = data.get('close_sync')

    if mcoin_order_size is None:
        return jsonify({"success": False, "message": "Missing required fields"})

    try:
        # 从策略中提取策略类型，如果没有则默认为反向套利
        strategy_type = 'reverse_arbitrage_bybit'
        if strategy and len(strategy) > 0:
            strategy_type = strategy[0].get('strategy_type', 'reverse_arbitrage_bybit')
        # 也可以从请求数据的顶层获取 strategy_type
        elif data.get('strategy_type'):
            strategy_type = data.get('strategy_type')

        # 保存到内存存储
        grid_strategy = {
            'strategy': strategy,
            'mcoin_order_size': mcoin_order_size,
            'open_sync': open_sync or 1,
            'close_sync': close_sync or 1,
            'strategy_type': strategy_type,
            'updated_at': datetime.now().isoformat()
        }

        # 保存到文件
        with settings_lock:
            strategy_settings_store[strategy_type] = grid_strategy
            # 保存到文件
            import json
            settings_data = {
                'sync_settings': sync_settings_store,
                'strategy_settings': strategy_settings_store,
                'alert_settings': alert_settings_store
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved grid strategy: {grid_strategy}")
        return jsonify({"success": True, "message": "阶梯策略保存成功", "data": grid_strategy})
    except Exception as e:
        logger.error(f"Error saving grid strategy: {e}")
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"})


@app.route('/api/trade/save', methods=['POST'])
def save_trade_record():
    """保存反向套利（做多Bybit）的交易记录"""
    data = request.get_json()
    type_ = data.get('type')
    binance_price = data.get('binancePrice')
    bybit_price = data.get('bybitPrice')
    binance_size = data.get('binanceSize')
    bybit_size = data.get('bybitSize')
    spread = data.get('spread')

    if type_ is None or binance_price is None or bybit_price is None:
        return jsonify({"success": False, "message": "Missing required fields"})

    try:
        # 这里应该保存到数据库
        # 暂时使用内存存储作为示例
        # 实际应用中应该保存到数据库
        trade_record = {
            'type': type_,
            'binance_price': binance_price,
            'bybit_price': bybit_price,
            'binance_size': binance_size,
            'bybit_size': bybit_size,
            'spread': spread,
            'timestamp': data.get('timestamp') or datetime.now().isoformat(),
            'created_at': datetime.now().isoformat()
        }

        # 添加到内存中的trade_history
        with trade_history_lock:
            trade_history.append(trade_record)
            # 限制历史记录数量
            if len(trade_history) > 1000:
                trade_history = trade_history[-1000:]

        logger.info(f"Saved trade record: {trade_record}")
        return jsonify({"success": True, "message": "交易记录保存成功", "data": trade_record})
    except Exception as e:
        logger.error(f"Error saving trade record: {e}")
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"})


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
        if account_id.startswith('bybit') and gateway and hasattr(gateway, 'connected') and gateway.connected:
            order_id = execute_order(account_id, direction, price, size)
            return jsonify({"success": True, "order_id": order_id, "message": "Order placed"})
        elif account_id.startswith('binance') and binance_gateway and hasattr(binance_gateway, 'connected') and binance_gateway.connected:
            order_id = execute_order(account_id, direction, price, size)
            return jsonify({"success": True, "order_id": order_id, "message": "Order placed"})
        elif account_id.startswith('bybit'):
            return jsonify({"success": False, "message": "Bybit account not connected"})
        elif account_id.startswith('binance'):
            return jsonify({"success": False, "message": "Binance account not connected"})
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
        
        filter_type = request.args.get('filter', 'all')
        
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
                    commit = {
                        "hash": parts[0],
                        "author": parts[1],
                        "message": parts[2],
                        "timestamp": int(parts[3])
                    }
                    
                    # 根据筛选条件过滤
                    if filter_type == 'all':
                        history.append(commit)
                    elif filter_type == 'backup':
                        if '自动备份' in commit['message']:
                            history.append(commit)
                    elif filter_type == 'manual':
                        if '自动备份' not in commit['message']:
                            history.append(commit)
        
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


@app.route('/api/backup/config', methods=['GET', 'POST'])
def backup_config():
    try:
        if request.method == 'POST':
            data = request.get_json()
            
            # 保存配置到文件
            import json
            with open('backup_config.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return jsonify({"success": True, "message": "Backup config saved"})
        else:
            # 获取配置
            import json
            try:
                with open('backup_config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return jsonify({"success": True, "config": config})
            except FileNotFoundError:
                # 返回默认配置
                default_config = {
                    "frequency": "daily",
                    "time": "00:00",
                    "branch": "master",
                    "commitTemplate": "自动备份: {datetime}",
                    "includeConfig": True,
                    "autoPush": True,
                    "sendNotification": True
                }
                return jsonify({"success": True, "config": default_config})
    except Exception as e:
        logger.error(f"Error handling backup config: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/sync/settings', methods=['GET'])
def get_sync_settings():
    """获取套利策略的同步设置"""
    strategy_type = request.args.get('strategy_type', 'reverse_arbitrage_bybit')

    try:
        with settings_lock:
            settings = sync_settings_store.get(strategy_type, {
                'open_sync': 1,
                'close_sync': 1,
                'strategy_type': strategy_type,
                'updated_at': datetime.now().isoformat()
            })

        return jsonify({"success": True, "data": settings})
    except Exception as e:
        logger.error(f"Error getting sync settings: {e}")
        return jsonify({"success": False, "message": f"获取失败: {str(e)}"})


@app.route('/api/strategy/settings', methods=['GET'])
def get_strategy_settings():
    """获取套利策略的阶梯策略设置"""
    strategy_type = request.args.get('strategy_type', 'reverse_arbitrage_bybit')

    try:
        with settings_lock:
            settings = strategy_settings_store.get(strategy_type, {
                'strategy': [],
                'mcoin_order_size': 1,
                'open_sync': 1,
                'close_sync': 1,
                'strategy_type': strategy_type,
                'updated_at': datetime.now().isoformat()
            })

        return jsonify({"success": True, "data": settings})
    except Exception as e:
        logger.error(f"Error getting strategy settings: {e}")
        return jsonify({"success": False, "message": f"获取失败: {str(e)}"})


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


@app.route('/api/history/limit')
def get_limit_history():
    try:
        with trade_history_lock:
            history_data = []
            for trade in trade_history:
                history_data.append({
                    "time": int(trade["time"].timestamp()),
                    "symbol": "XAUUSD",
                    "price": trade["price"],
                    "volume": trade["size"],
                    "type": f"{trade['platform']} {trade['direction']}"
                })
        
        return jsonify({"success": True, "data": history_data})
    except Exception as e:
        logger.error(f"Error getting limit history: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/history/positions')
def get_positions_history():
    try:
        positions = []
        
        with gateway_lock:
            if gateway and gateway.connected:
                positions_data = gateway.get_positions()
                if positions_data:
                    for pos in positions_data:
                        positions.append({
                            "ticket": pos.get('ticket', 0),
                            "symbol": pos.get('symbol', ''),
                            "type": '买入' if pos.get('type') == 0 else '卖出',
                            "volume": pos.get('volume', 0),
                            "price": pos.get('price_open', 0),
                            "profit": pos.get('profit', 0)
                        })
        
        return jsonify({"success": True, "data": positions})
    except Exception as e:
        logger.error(f"Error getting positions history: {e}")
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


@app.route('/api/alert/settings', methods=['GET'])
def get_alert_settings():
    """获取提醒设置"""
    try:
        with settings_lock:
            return jsonify({"success": True, "data": alert_settings_store})
    except Exception as e:
        logger.error(f"Error getting alert settings: {e}")
        return jsonify({"success": False, "message": f"获取失败: {str(e)}"})


@app.route('/api/alert/settings', methods=['POST'])
def save_alert_settings():
    """保存提醒设置"""
    try:
        data = request.get_json()
        
        with settings_lock:
            alert_settings_store.update(data)
            # 保存到文件
            import json
            settings_data = {
                'sync_settings': sync_settings_store,
                'strategy_settings': strategy_settings_store,
                'alert_settings': alert_settings_store
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Alert settings saved: {data}")
        return jsonify({"success": True, "message": "保存成功", "data": alert_settings_store})
    except Exception as e:
        logger.error(f"Error saving alert settings: {e}")
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"})


def execute_order(account_id: str, direction: str, price: float, size: float, order_id: str = None, strategy_type: str = 'reverse_arbitrage_bybit') -> str:
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
            # 广播订单更新
            socketio.emit('order_update', {
                "strategy_type": strategy_type,
                "orders": [{
                    "symbol": "XAU/USD" if account_id.startswith('bybit') else "XAUUSDT",
                    "side": direction,
                    "price": price,
                    "quantity": size,
                    "timestamp": datetime.now().isoformat()
                }]
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
            # 广播订单更新
            socketio.emit('order_update', {
                "strategy_type": strategy_type,
                "orders": [{
                    "symbol": "XAUUSDT" if account_id.startswith('binance') else "XAU/USD",
                    "side": direction,
                    "price": price,
                    "quantity": size,
                    "timestamp": datetime.now().isoformat()
                }]
            })
    
    return result_order_id


def on_trade(platform: str, trade_data: Dict):
    for strategy_id, strategy in arbitrage_strategies.items():
        strategy.on_trade(platform, trade_data)
    
    with trade_history_lock:
        trade_history.append({
            "time": datetime.now(),
            "platform": platform,
            "direction": trade_data.get('direction', ''),
            "price": trade_data.get('price', 0),
            "size": trade_data.get('size', 0)
        })
        
        if len(trade_history) > 100:
            trade_history.pop(0)
    
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


def broadcast_margin_status():
    """广播保证金状态"""
    # 模拟Binance保证金数据
    binance_margin_data = {
        "platform": "binance",
        "equity": 10000.0,
        "maintenance_margin": 1000.0,
        "used_margin": 500.0,
        "free_margin": 9500.0
    }
    
    # 模拟Bybit保证金数据
    bybit_margin_data = {
        "platform": "bybit",
        "equity": 15000.0,
        "maintenance_margin": 750.0,
        "used_margin": 300.0,
        "free_margin": 14700.0
    }
    
    socketio.emit('margin_status_update', binance_margin_data)
    socketio.emit('margin_status_update', bybit_margin_data)


def start_margin_status_broadcast():
    """启动保证金状态广播线程"""
    def broadcast_loop():
        while True:
            try:
                broadcast_margin_status()
                time.sleep(5)  # 每5秒广播一次
            except Exception as e:
                logger.error(f"Error broadcasting margin status: {e}")
                time.sleep(5)
    
    thread = threading.Thread(target=broadcast_loop, daemon=True)
    thread.start()
    logger.info("Margin status broadcast thread started")


@app.route('/api/history/account')
def get_account_history():
    try:
        date = request.args.get('date', time.strftime('%Y-%m-%d'))
        merge = request.args.get('merge', 'false').lower() == 'true'
        
        # 模拟账户成交历史数据
        mock_data = [
            {
                "time": int(time.time()),
                "symbol": "XAUUSDT",
                "price": 5000.25,
                "volume": 0.01,
                "type": "buy",
                "fee": 0.025,
                "rebate": 0.01
            },
            {
                "time": int(time.time()) - 1800,
                "symbol": "XAUUSDT",
                "price": 4998.75,
                "volume": 0.01,
                "type": "sell",
                "fee": 0.025,
                "rebate": 0.01
            }
        ]
        
        return jsonify({"success": True, "data": mock_data})
    except Exception as e:
        logger.error(f"Error getting account history: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/history/mt5')
def get_mt5_history():
    try:
        date = request.args.get('date', time.strftime('%Y-%m-%d'))
        merge = request.args.get('merge', 'false').lower() == 'true'
        
        # 模拟MT5成交历史数据
        mock_data = [
            {
                "time": int(time.time()),
                "symbol": "XAUUSD.s",
                "price": 5002.50,
                "volume": 0.01,
                "type": "buy",
                "fee": 0.03,
                "rebate": 0.012
            },
            {
                "time": int(time.time()) - 3600,
                "symbol": "XAUUSD.s",
                "price": 4999.80,
                "volume": 0.01,
                "type": "sell",
                "fee": 0.03,
                "rebate": 0.012
            }
        ]
        
        return jsonify({"success": True, "data": mock_data})
    except Exception as e:
        logger.error(f"Error getting MT5 history: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/history/delete-all', methods=['POST'])
def delete_all_history():
    try:
        with trade_history_lock:
            # 清空交易历史
            trade_history.clear()
            logger.info("All trade history deleted")
        
        return jsonify({"success": True, "message": "删除所有历史数据成功"})
    except Exception as e:
        logger.error(f"Error deleting all history: {e}")
        return jsonify({"success": False, "message": str(e)})


if __name__ == '__main__':
    logger.info(f"Starting web server on {WEBSERVER_CONFIG['host']}:{WEBSERVER_CONFIG['port']}")
    # 启动保证金状态广播
    start_margin_status_broadcast()
    socketio.run(app, host=WEBSERVER_CONFIG['host'], port=WEBSERVER_CONFIG['port'], debug=WEBSERVER_CONFIG['debug'])
