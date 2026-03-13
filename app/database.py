from pymongo import MongoClient
import datetime
from app.config import config

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.positions_col = None
        self.history_col = None
        self.wallet_col = None
        
        if config.MONGO_URI:
            try:
                self.client = MongoClient(config.MONGO_URI)
                self.db = self.client['crypto_bot']
                self.positions_col = self.db['active_positions']
                self.history_col = self.db['trade_history']
                self.wallet_col = self.db['wallet']
                print("✅ Successfully connected to MongoDB")
                self._init_mongo_wallet()
            except Exception as e:
                print(f"❌ Failed to connect to MongoDB: {e}")
        else:
            print("⚠️ No MONGO_URI provided. Using in-memory database only (Data will be lost on restart).")
            # Fallback for local testing without DB
            self.memory_positions = {}
            self.memory_wallet = {"USDT": config.PAPER_TRADE_BALANCE}

    def _init_mongo_wallet(self):
        """Initializes the MongoDB fake wallet if it doesn't exist"""
        if self.wallet_col is not None:
            wallet = self.wallet_col.find_one({"_id": "paper_wallet"})
            if not wallet:
                print(f"💰 Initializing new Paper Trading Wallet with ${config.PAPER_TRADE_BALANCE} USDT")
                self.wallet_col.insert_one({"_id": "paper_wallet", "balances": {"USDT": config.PAPER_TRADE_BALANCE}})

    def get_wallet_balances(self):
        """Returns the paper trading wallet balances"""
        if self.wallet_col is not None:
            wallet = self.wallet_col.find_one({"_id": "paper_wallet"})
            return wallet.get("balances", {}) if wallet else {"USDT": 0}
        else:
            return self.memory_wallet

    def update_wallet_balance(self, asset, amount_change):
        """Adds or subtracts from a paper trading asset balance"""
        if self.wallet_col is not None:
            self.wallet_col.update_one(
                {"_id": "paper_wallet"},
                {"$inc": {f"balances.{asset}": float(amount_change)}}
            )
        else:
            current = self.memory_wallet.get(asset, 0.0)
            self.memory_wallet[asset] = current + float(amount_change)

    def get_position(self, symbol):
        """Returns the active position for a symbol if it exists"""
        if self.positions_col is not None:
            return self.positions_col.find_one({"symbol": symbol})
        else:
            return self.memory_positions.get(symbol, None)

    def save_position(self, symbol, entry_price, highest_price, amount, dca_count=0):
        """Upserts an active position to the database"""
        data = {
            "symbol": symbol,
            "entry_price": float(entry_price),
            "highest_price": float(highest_price),
            "amount": float(amount),
            "dca_count": int(dca_count),
            "updated_at": datetime.datetime.utcnow()
        }
        
        if self.positions_col is not None:
            self.positions_col.update_one({"symbol": symbol}, {"$set": data}, upsert=True)
        else:
            self.memory_positions[symbol] = data

    def delete_position(self, symbol):
        """Removes a position after it is sold"""
        if self.positions_col is not None:
            self.positions_col.delete_one({"symbol": symbol})
        else:
            if symbol in self.memory_positions:
                del self.memory_positions[symbol]
                
    def log_trade(self, symbol, side, price, amount, reason, pnl_pct=0.0):
        """Logs a completed trade to history"""
        data = {
            "symbol": symbol,
            "side": side, # 'BUY' or 'SELL'
            "price": float(price),
            "amount": float(amount),
            "reason": reason,
            "pnl_pct": float(pnl_pct),
            "timestamp": datetime.datetime.utcnow()
        }
        if self.history_col is not None:
            self.history_col.insert_one(data)
            
    def get_recent_history(self, limit=50):
        if self.history_col is not None:
            return list(self.history_col.find().sort("timestamp", -1).limit(limit))
        return []

    def get_all_active_positions(self):
        if self.positions_col is not None:
            return list(self.positions_col.find())
        return list(self.memory_positions.values())

db = Database()
