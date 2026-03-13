import time
import threading
import uvicorn
from app.config import config
from app.database import db
from app.notifier import notifier
from app.exchange import exchange_api
from app.strategy import strategy
from app.server import app

def calculate_buy_amount(symbol, current_price, balance):
    """Calculates how much of a coin to buy based on RISK_PERCENTAGE of the Paper Wallet"""
    quote_currency = symbol.split('/')[1]
    available_quote = balance['free'].get(quote_currency, 0)
    
    if available_quote <= 0:
        return 0
        
    spend_amount = available_quote * config.RISK_PERCENTAGE
    coin_amount = spend_amount / current_price
    return round(coin_amount, 5)

def execute_trade(symbol, signal, price, reason, dca_count=0):
    pos = db.get_position(symbol)
    
    # If the position exists in DB, it means we are actively in a trade and this is a DCA or SELL
    is_active_trade = pos is not None
    
    if not pos:
        pos = {'entry_price': 0.0, 'highest_price': 0.0, 'amount': 0.0, 'dca_count': 0}

    log_msg = f"--- Executing {signal} for {symbol} --- \nReason: {reason}\nPrice roughly: {price}"
    print(log_msg)
    
    # Paper Trading Simulator Only
    balance = exchange_api.fetch_balance() # Returns the DB paper wallet
    quote_currency = symbol.split('/')[1]
    base_currency = symbol.split('/')[0]
    
    if signal == 'BUY':
        trade_amount = calculate_buy_amount(symbol, price, balance)
        if trade_amount <= 0:
                notifier.send_telegram_message(f"🧪 [SIMULATOR] ⚠️ Not enough fake {quote_currency} to buy {symbol}.")
                return
                
        # Deduct USDT, Add Coin
        total_cost = trade_amount * price
        db.update_wallet_balance(quote_currency, -total_cost)
        db.update_wallet_balance(base_currency, trade_amount)
        
        final_price = price # Simulated fill price
        
        if is_active_trade: # It's a DCA Buy
            total_spent = (pos['amount'] * pos['entry_price']) + (trade_amount * final_price)
            new_total_amount = pos['amount'] + trade_amount
            new_avg_price = total_spent / new_total_amount if new_total_amount > 0 else 0
            db.save_position(symbol, new_avg_price, new_avg_price, new_total_amount, pos['dca_count'] + 1)
            db.log_trade(symbol, 'BUY (DCA)', final_price, trade_amount, reason)
            log_msg = f"🧪 [SIMULATOR] ✅ <b>DCA BUY Order successful!</b>\nPair: {symbol}\nAvg Price: ${new_avg_price:.4f}\nAdded Amount: {trade_amount}\nCost: ${total_cost:.2f} {quote_currency}\nReason: {reason}"
        else:
            db.save_position(symbol, final_price, final_price, trade_amount, 0)
            db.log_trade(symbol, 'BUY', final_price, trade_amount, reason)
            log_msg = f"🧪 [SIMULATOR] ✅ <b>BUY Order successful!</b>\nPair: {symbol}\nPrice: ${final_price:.4f}\nAmount: {trade_amount}\nCost: ${total_cost:.2f} {quote_currency}\nReason: {reason}"
        
        print(log_msg)
        notifier.send_telegram_message(log_msg)
        
    elif signal == 'SELL':
        trade_amount = pos['amount']
        coin_balance = balance['free'].get(base_currency, 0)
        
        if coin_balance < trade_amount:
            trade_amount = coin_balance
            
        if trade_amount > 0:
            total_revenue = trade_amount * price
            # Add USDT, Deduct Coin
            db.update_wallet_balance(quote_currency, total_revenue)
            db.update_wallet_balance(base_currency, -trade_amount)
            
            pnl_pct = ((price - pos['entry_price']) / pos['entry_price']) * 100 if pos['entry_price'] > 0 else 0
            db.delete_position(symbol)
            db.log_trade(symbol, 'SELL', price, trade_amount, reason, pnl_pct)
            
            log_msg = f"🧪 [SIMULATOR] 🔴 <b>SELL Order successful!</b>\nPair: {symbol}\nPrice: {price}\nAmount: {trade_amount}\nRevenue: {total_revenue:.2f} {quote_currency}\nReason: {reason}\nEstimated PnL: {pnl_pct:.2f}%"
            print(log_msg)
            notifier.send_telegram_message(log_msg)
        else:
            notifier.send_telegram_message(f"🧪 [SIMULATOR] ⚠️ No fake {base_currency} balance to sell.")

def bot_loop():
    startup_msg = (
        f"🚀 <b>Starting Pure Paper Trading Simulator v4</b>\n"
        f"Pairs: {', '.join(config.SYMBOLS)}\n"
        f"Timeframe: {config.TIMEFRAME}\n"
        f"Risk per Trade: {config.RISK_PERCENTAGE * 100}%\n"
        f"Starting Ammo: ${config.PAPER_TRADE_BALANCE}\n"
        f"Trailing Stop: {config.STOP_LOSS_PCT * 100}%\n"
        f"Take Profit: {config.TAKE_PROFIT_PCT * 100}%\n"
        f"DCA Enabled: {config.DCA_DROP_PCT * 100}% drop"
    )
    print("=======================================")
    print(startup_msg)
    print("=======================================")
    notifier.send_telegram_message(startup_msg)
    
    while True:
        try:
            for symbol in config.SYMBOLS:
                pos = db.get_position(symbol)
                
                signal, current_price, reason = strategy.analyze_market(symbol)
                
                # If the strategy failed to get a price (API limit or error), skip to next symbol
                if current_price == 0.0:
                    continue
                
                if pos:
                    # Update Trailing Stop highest price
                    if current_price > pos['highest_price']:
                        db.save_position(symbol, pos['entry_price'], current_price, pos['amount'], pos.get('dca_count', 0))
                        pos['highest_price'] = current_price
                        
                    trailing_stop_price = pos['highest_price'] * (1 - config.STOP_LOSS_PCT)
                    take_profit_price = pos['entry_price'] * (1 + config.TAKE_PROFIT_PCT)
                    
                    if current_price <= trailing_stop_price:
                        execute_trade(symbol, 'SELL', current_price, reason="Trailing Stop Loss")
                        continue
                    elif current_price >= take_profit_price:
                        execute_trade(symbol, 'SELL', current_price, reason="Take Profit")
                        continue
                        
                    # DCA Logic
                    should_dca, dca_reason = strategy.check_dca_opportunity(current_price, pos['entry_price'], pos.get('dca_count', 0))
                    if should_dca:
                        execute_trade(symbol, 'BUY', current_price, reason=dca_reason)
                        continue
                        
                    if signal == 'SELL':
                        execute_trade(symbol, 'SELL', current_price, reason=reason)
                else:
                    if signal == 'BUY':
                        execute_trade(symbol, 'BUY', current_price, reason=reason)
                        
        except Exception as e:
            notifier.send_telegram_message(f"Critical error in main loop: {e}")
            
        print(f"\n⏳ Sleeping for {config.TIMEFRAME}...\n")
        time.sleep(60 * 5) # 5 Minutes

if __name__ == "__main__":
    # Start the trading engine in a background thread
    trading_thread = threading.Thread(target=bot_loop, daemon=True)
    trading_thread.start()
    
    # Start the FastAPI Dashboard on the main thread
    uvicorn.run(app, host="0.0.0.0", port=8000)
