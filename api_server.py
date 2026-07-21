from fastapi import FastAPI
import uvicorn
import json
from fetch import call_tr_rest_api, call_tr_ws_api, generate_traceparent
from pydantic import BaseModel

app = FastAPI()

class ExchangeSymbol(BaseModel):
  symbol: str

@app.get("/api/personal-details")
def get_personal_details():
  return call_tr_rest_api("api/v1/customer/personal-details")

@app.get("/api/open-tickets")
def get_open_tickets():
  return call_tr_rest_api("api/v2/timeline/inbox/open")

@app.get("/api/closed-tickets")
def get_closed_tickets():
  return call_tr_rest_api("api/v2/timeline/inbox/closed")

@app.get("/api/daily-positions")
def get_daily_positions():
  return call_tr_rest_api("web-trading-gateway/api/customer/v1/pnl/daily")

@app.post("/api/schedule-exchange")
def get_exchange_symbol(params: ExchangeSymbol):
  return call_tr_rest_api(f"api-gateway/instrument-universe/api/v1/exchanges/{params.symbol}/schedule")

@app.get("/api/portfolio")
async def get_portfolio():
  payload = {
    "type": "compactPortfolioByTypeV2",
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }
  return await call_tr_ws_api(payload, 22)

@app.get("/api/accounts")
async def get_accounts():
  payload = {
    "type": "accountPairs",
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }
  return await call_tr_ws_api(payload, 1)

def start_api_server():
  uvicorn.run(app, host="0.0.0.0", port=8000)
