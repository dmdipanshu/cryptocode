import json
import asyncio
import threading
from websockets.sync.client import connect
from app.config import config

class WebSocketClient:
    def __init__(self):
        self.prices = {symbol: 0.0 for symbol in config.SYMBOLS}
        self.running = False
        self._thread = None

    def _get_stream_url(self):
        # Format: btcusdt@kline_1m/ethusdt@kline_1m
        streams = []
        for symbol in config.SYMBOLS:
            formatted = symbol.replace('/', '').lower()
            streams.append(f"{formatted}@ticker")
        
        return f"wss://stream.binance.com:9443/ws/{'/'.join(streams)}"

    def _listen(self):
        url = self._get_stream_url()
        print(f"Connecting to Binance WebSocket: {url}")
        
        while self.running:
            try:
                with connect(url) as websocket:
                    while self.running:
                        message = websocket.recv()
                        data = json.loads(message)
                        
                        # Process ticker data
                        if 's' in data and 'c' in data:
                            # Map back to our symbol format (e.g., BTCUSDT -> BTC/USDT)
                            symbol_raw = data['s']
                            current_price = float(data['c'])
                            
                            # Find matching configured symbol
                            for config_symbol in config.SYMBOLS:
                                if config_symbol.replace('/', '') == symbol_raw:
                                    self.prices[config_symbol] = current_price
                                    break
            except Exception as e:
                print(f"WebSocket Error: {e}. reconnecting in 5s...")
                if self.running:
                    asyncio.run(asyncio.sleep(5))

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def get_price(self, symbol):
        return self.prices.get(symbol, 0.0)

ws_client = WebSocketClient()
