import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Trading Config
    SYMBOLS_ENV = os.environ.get('SYMBOLS', 'BTC/USDT,ETH/USDT,SOL/USDT')
    SYMBOLS = [s.strip() for s in SYMBOLS_ENV.split(',') if s.strip()]
    TIMEFRAME = os.environ.get('TIMEFRAME', '1m')
    
    # Risk Management
    STOP_LOSS_PCT = float(os.environ.get('STOP_LOSS_PCT', '0.02'))
    TAKE_PROFIT_PCT = float(os.environ.get('TAKE_PROFIT_PCT', '0.08'))
    RISK_PERCENTAGE = float(os.environ.get('RISK_PERCENTAGE', '0.10'))
    DCA_DROP_PCT = float(os.environ.get('DCA_DROP_PCT', '0.05')) # Price drop needed to trigger DCA buy
    
    # External Services
    PAPER_TRADE_BALANCE = float(os.environ.get('PAPER_TRADE_BALANCE', '10000.0'))
    MONGO_URI = os.environ.get('MONGO_URI', None)
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
    WEBHOOK_PASSPHRASE = os.environ.get('WEBHOOK_PASSPHRASE', 'secret_webhook_key_123')

config = Config()
