from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import threading
import time
from datetime import datetime
import logging
from config import MT5_GATEWAY_CONFIG, WEBSERVER_CONFIG, DATA_CONFIG, BINANCE_CONFIG
from mt5_gateway import MT5Gateway
from binance_gateway import BinanceGateway

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vnpy-mt5-gateway-secret-key'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

gateway = None
binance_gateway = None
gateway_lock = threading.Lock()


@app.route('/')
def index():
    return render_template('index.html')


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


if __name__ == '__main__':
    logger.info(f"Starting web server on {WEBSERVER_CONFIG['host']}:{WEBSERVER_CONFIG['port']}")
    socketio.run(app, host=WEBSERVER_CONFIG['host'], port=WEBSERVER_CONFIG['port'], debug=WEBSERVER_CONFIG['debug'])
