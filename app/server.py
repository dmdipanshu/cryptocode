from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import db
import os

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
    
    return templates.TemplateResponse(
        request=request, name="index.html", 
        context={
            "positions": active_positions,
            "history": recent_history,
            "is_paper_trading": is_paper_trading,
            "wallet": wallet,
            "total_equity": total_equity
        }
    )

@app.get("/api/status")
async def get_status():
    return {"status": "running"}
