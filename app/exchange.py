import requests
from app.database import db

class ExchangeAPI:
    def __init__(self):
        self.base_url = "https://data-api.binance.vision/api/v3"
        
    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        """Fetches historical candlestick data using Binance's public, free REST API"""
        # Binance API expects symbols like BTCUSDT, not BTC/USDT
        formatted_symbol = symbol.replace('/', '')
        
        url = f"{self.base_url}/klines"
        params = {
            'symbol': formatted_symbol,
            'interval': timeframe,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Format to match ccxt output structure: 
            # [ [timestamp, open, high, low, close, volume], ... ]
            ohlcv = []
            for candle in data:
                ohlcv.append([
                    candle[0],                # timestamp
                    float(candle[1]),         # open
                    float(candle[2]),         # high
                    float(candle[3]),         # low
                    float(candle[4]),         # close
                    float(candle[5])          # volume
                ])
            return ohlcv
        except Exception as e:
            print(f"Error fetching OHLCV for {symbol} from public API: {e}")
            return []
        
    def fetch_balance(self):
        """Fetches Paper Trading virtual account balance from MongoDB"""
        virtual_balances = db.get_wallet_balances()
        return {'free': virtual_balances}

exchange_api = ExchangeAPI()
