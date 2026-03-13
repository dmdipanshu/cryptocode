from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import db
import os
from pydantic import BaseModel
from app.config import config

class WebhookPayload(BaseModel):
    passphrase: str
    symbol: str
    action: str  # BUY or SELL
    reason: str = "External Webhook Signal"

app = FastAPI(title="Crypto Bot Dashboard")

# Get the absolute path to the templates directory
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    active_positions = db.get_all_active_positions()
    recent_history = db.get_recent_history(limit=20)
    
    # Paper Trading logic (Always True now)
    is_paper_trading = True
    wallet = db.get_wallet_balances()
    
    # Calculate a rough equity value if paper trading (USDT + value of active positions at entry price)
    # A precise bot would fetch live API prices here, but entry price serves as a baseline estimate.
    total_equity = wallet.get('USDT', 0)
    for pos in active_positions:
        total_equity += (pos.get('amount', 0) * pos.get('entry_price', 0))
    
    # Calculate advanced stats
    total_trades = len(recent_history)
    wins = [h for h in recent_history if h.get('pnl_pct', 0) > 0]
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    
    return templates.TemplateResponse(
        request=request, name="index.html", 
        context={
            "positions": active_positions,
            "history": recent_history,
            "is_paper_trading": is_paper_trading,
            "wallet": wallet,
            "total_equity": total_equity,
            "win_rate": f"{win_rate:.1f}%",
            "total_trades": total_trades
        }
    )

@app.get("/api/stats")
async def get_stats():
    """Returns analytics data for real-time charts"""
    history = db.get_recent_history(limit=50)
    
    # Simple equity curve generation based on trade history
    equity_curve = [10000.0] # Starting balance
    current_eq = 10000.0
    for trade in reversed(history):
        # This is a simplification; a full system tracks balance daily
        pnl_val = (trade.get('amount', 0) * trade.get('entry_price', 0)) * (trade.get('pnl_pct', 0)/100)
        current_eq += pnl_val
        equity_curve.append(current_eq)
        
    return {
        "equity_curve": equity_curve,
        "labels": [trade.get('timestamp').strftime('%H:%M') if trade.get('timestamp') else "" for trade in reversed(history)] + ["Now"]
    }

@app.get("/api/status")
async def get_status():
    return {"status": "running"}

@app.post("/webhook")
async def receive_webhook(payload: WebhookPayload):
    # Security check
    if hasattr(config, 'WEBHOOK_PASSPHRASE') and config.WEBHOOK_PASSPHRASE:
        if payload.passphrase != config.WEBHOOK_PASSPHRASE:
            return {"status": "error", "message": "Invalid passphrase"}
            
    # We will import execute_trade dynamically to avoid circular imports 
    # since main.py imports app from server.py
    try:
        from main import execute_trade
        from app.exchange import exchange_api
        
        # Get current approximate price to execute the trade
        symbol_data = exchange_api.fetch_ohlcv(payload.symbol, "1m", limit=1)
        if not symbol_data:
            return {"status": "error", "message": f"Could not fetch current price for {payload.symbol}"}
            
        current_price = symbol_data[0][4] # Close price of the latest 1m candle
        
        action = payload.action.upper()
        if action in ['BUY', 'SELL']:
            execute_trade(payload.symbol, action, current_price, payload.reason)
            return {"status": "success", "message": f"Executed {action} for {payload.symbol}"}
        else:
            return {"status": "error", "message": "Invalid action. Must be BUY or SELL"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
