import pandas as pd
import pandas_ta as ta
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from app.exchange import exchange_api
from app.config import config

class Strategy:
    def __init__(self):
        # We store trained models per symbol in memory so we don't retrain unnecessarily
        self.models = {}

    def get_historical_data(self, symbol, timeframe, limit=1000):
        # Fetch up to 1000 candles for robust ML training
        ohlcv = exchange_api.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
        
    def prepare_ml_features(self, df):
        """Calculates features for the Machine Learning model"""
        df = df.copy()
        
        # Standard Indicators
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True) # Average True Range for volatility sizing
        
        # Volatility / Momentum Features
        df['Returns'] = df['close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=10).std()
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['Vol_Ratio'] = df['volume'] / df['Volume_SMA']
        
        # Distance Features
        df['Dist_EMA9'] = (df['close'] - df['EMA_9']) / df['EMA_9']
        df['Dist_EMA21'] = (df['close'] - df['EMA_21']) / df['EMA_21']
        
        # Target Variable (1 if next candle is higher, 0 if lower)
        df['Target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        # Drop NaN values created by rolling windows/shifts
        df.dropna(inplace=True)
        
        return df

    def train_model(self, symbol, df):
        """Trains a Random Forest Classifier on historical data"""
        features = ['RSI_14', 'Returns', 'Volatility', 'Vol_Ratio', 'Dist_EMA9', 'Dist_EMA21']
        
        X = df[features]
        y = df['Target']
        
        # Train model
        model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)
        
        self.models[symbol] = model
        return model

    def analyze_market(self, symbol):
        """
        Analyzes the market using ML Prediction + EMA Crossover + Volume spikes.
        Returns (signal, current_price, reason)
        """
        try:
            # Fetch 300 candles (enough for rolling indicators and a quick train if needed)
            df_raw = self.get_historical_data(symbol, config.TIMEFRAME, limit=300)
            if df_raw.empty:
                return 'HOLD', 0.0, "No data"
                
            df = self.prepare_ml_features(df_raw)
            if len(df) < 50:
                 return 'HOLD', df_raw.iloc[-1]['close'] if not df_raw.empty else 0.0, "Not enough data for ML"
            
            # 1. Train or Retrieve ML Model
            # In a heavy production environment, training happens daily in the background.
            # Here, we do a quick lightweight train in memory periodically.
            model = self.train_model(symbol, df[:-1]) # Train on all but the last unseen candle
            
            # 2. Get Current State (Last row)
            current_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            current_price = current_row['close']
            
            # 3. AI Prediction
            features = ['RSI_14', 'Returns', 'Volatility', 'Vol_Ratio', 'Dist_EMA9', 'Dist_EMA21']
            # Prepare input for prediction as a DataFrame to keep feature names
            current_features_df = pd.DataFrame([current_row[features]])
            
            # Predict probability of class '1' (Price going UP)
            prob_up = model.predict_proba(current_features_df)[0][1]
            prob_down = 1 - prob_up
            
            # 4. Standard Strategy Metrics
            ema_short = current_row['EMA_9']
            ema_long = current_row['EMA_21']
            prev_ema_short = prev_row['EMA_9']
            prev_ema_long = prev_row['EMA_21']
            current_rsi = current_row['RSI_14']
            vol_ratio = current_row['Vol_Ratio']
            
            print(f"[{symbol} - Price: {current_price:.2f} | AI Bullish Prob: {prob_up*100:.1f}% | RSI: {current_rsi:.1f} | Vol Ratio: {vol_ratio:.2f}]")
            
            signal = 'HOLD'
            reason = 'No Setup'
            
            # BUY CONDITIONS:
            # Low thresholds for "High Frequency" / Active Automation
            if prev_ema_short < prev_ema_long and ema_short > ema_long:
                if current_rsi < 70 and vol_ratio > 1.0: # Vol ratio down from 1.5
                    if prob_up > 0.45: # AI Prob down from 0.55
                        signal = 'BUY'
                        reason = f'EMA Cross + Vol: {vol_ratio:.2f} + AI: {prob_up*100:.1f}%'
                    else:
                        reason = f'EMA Cross ignored: AI predicted bearish ({prob_down*100:.1f}%)'
                        print(f"[{symbol}] {reason}")
                elif vol_ratio <= 1.5:
                    reason = 'EMA Cross ignored: Weak Volume (Fakeout protection)'
                    print(f"[{symbol}] {reason}")
            
            # SELL CONDITIONS:
            # 1. EMA Cross Under
            # 2. OR AI is highly confident of a crash (>70% bear probability) and RSI > 50
            elif prev_ema_short > prev_ema_long and ema_short < ema_long and current_rsi > 30:
                signal = 'SELL'
                reason = 'EMA Cross Under'
            elif prob_down > 0.70 and current_rsi > 50:
                 signal = 'SELL'
                 reason = f'AI detected high crash probability ({prob_down*100:.1f}%)'
            
            return signal, current_price, reason
            
        except Exception as e:
            print(f"Error analyzing market for {symbol}: {e}")
            return 'HOLD', 0.0, f"Error: {e}"

    def check_dca_opportunity(self, current_price, entry_price, dca_count):
        """Checks if the coin has dropped enough to warrant buying more"""
        if dca_count >= 2:
            return False, "Max DCA reached"
            
        drop_pct = (entry_price - current_price) / entry_price
        
        if drop_pct >= config.DCA_DROP_PCT:
            return True, f"Price dropped {drop_pct*100:.2f}% from entry. DCA step {dca_count+1}/2 triggered."
            
        return False, "Drop not deep enough"

    def get_market_volatility(self, symbol):
        """Returns the current ATR value for a symbol"""
        df_raw = self.get_historical_data(symbol, config.TIMEFRAME, limit=100)
        if df_raw.empty: return 0.0
        df = self.prepare_ml_features(df_raw)
        if df.empty: return 0.0
        return df.iloc[-1]['ATRr_14']

strategy = Strategy()
