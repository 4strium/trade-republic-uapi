from fastapi import FastAPI
import uvicorn
from fetch import call_tr_rest_api, call_tr_ws_api, generate_traceparent
from pydantic import BaseModel

JURISDICTION = "FR"

app = FastAPI()

class ExchangeSymbol(BaseModel):
  symbol: str

class InstrumentHistory(BaseModel):
  id: str
  range: str

class Instrument(BaseModel):
  id: str

class AccountHistoryRequest(BaseModel):
  range: str

async def get_accounts_data():
  payload = {
    "type": "accountPairs",
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }

  return await call_tr_ws_api(payload, 1)

def fix_string(text: str) -> str:
  if not isinstance(text, str):
    return text
  try:
    return text.encode("latin-1").decode("utf-8")
  except (UnicodeEncodeError, UnicodeDecodeError):
    return text

def fix_struct(data):
  if isinstance(data, dict):
    for k, v in data.items():
      data[k] = fix_struct(v)
    return data
  elif isinstance(data, list):
    return [fix_struct(item) for item in data]
  elif isinstance(data, str):
    return fix_string(data)
  else:
    return data

@app.get("/api/personal-details")
def get_personal_details():
  personal_details = call_tr_rest_api("api/v1/customer/personal-details")
  relations = call_tr_rest_api("api/v1/customer/relationships/detailed")

  if relations is None or personal_details is None:
    return personal_details
  
  for relation in relations["relationships"]:
    if relation["relationshipType"] == "SELF":
      personal_details["bankingInfo"] = relation["bankingInfo"]
  
  return personal_details

@app.get("/api/tickets")
def get_open_tickets():
  result = {}
  
  open =  call_tr_rest_api("api/v2/timeline/inbox/open")
  if open is not None:
    result["open"] = open["items"]
  closed = call_tr_rest_api("api/v2/timeline/inbox/closed")
  if closed is not None:
    result["closed"] = closed["items"]
  return result

@app.get("/api/card")
def get_card_details():
  card_infos = call_tr_rest_api("api/v1/card/cards/home")

  if card_infos is None:
    return "{}"

  result = {
    "id": card_infos["data"]["card"]["id"],
    "createdAt": card_infos["data"]["card"]["createTime"],
    "updatedAt": card_infos["data"]["card"]["updateTime"],
    "lastFourPan": card_infos["data"]["card"]["lastFourPan"],
    "status": card_infos["data"]["card"]["status"],
    "cardholderName": card_infos["data"]["card"]["cardholderName"],
    "activateAt": card_infos["data"]["card"]["activateTime"],
    "expireAt": card_infos["data"]["card"]["expireTime"],
    "security": card_infos["data"]["card"]["securitySettings"],
    "isPinSet": card_infos["data"]["card"]["isPinSet"],
    "xPayEligibility": card_infos["data"]["xPayEligibility"],
    "fundingSource": card_infos["data"]["fundingSource"]["type"],
    "clickToPay": card_infos["data"]["clickToPay"]["status"],
    "visaPlus": card_infos["data"]["visaPlus"]["status"]
  }
  
  return result

@app.get("/api/interests")
async def get_interests():
  accounts = await get_accounts_data()
  if accounts is None:
    return {}
    
  for account in accounts["accounts"]:
    if account["productType"] == "DEFAULT" :
      interests = call_tr_rest_api(f"api/v1/interest-experience/interest/{account["cashAccountNumber"]}/info")
      if interests is not None:
        interests["iconUrl"] = "https://assets.traderepublic.com/img/" + interests["iconUrl"] + "/dark.svg"
        interests["title"] = fix_string(interests["title"])
        return interests
      return {}

@app.get("/api/transactions")
async def get_transactions():
  transactions = call_tr_rest_api("api/v2/timeline/transactions?pageSize=500")
  if transactions is not None:
    for transaction in transactions["items"]:
      transaction.pop("avatar", None)
      transaction.pop("badge", None)
      transaction.pop("action", None)
      transaction["icon"] = "https://assets.traderepublic.com/img/" + transaction["icon"] + "/dark.svg"
    return transactions["items"]
  return {}

@app.post("/api/schedule-exchange")
def get_exchange_symbol(params: ExchangeSymbol):
  return call_tr_rest_api(f"api-gateway/instrument-universe/api/v1/exchanges/{params.symbol}/schedule")

@app.post("/api/accounts-history")
async def get_accounts_history(params: AccountHistoryRequest):
  accounts = await get_accounts_data()

  if accounts is None:
    return "{}"

  result = {}
  for account in accounts["accounts"]:
    # Range available: 1d, 5d, 1m, 1y & max
    account_history = call_tr_rest_api(f"api-gateway/portfolio-chart/v2/chart?secAccNo={account['securitiesAccountNumber']}&range={params.range}&currency={account['currency']}")
    if account_history is not None :
      for point in account_history["points"] :
        point["totalValue"] = float(point["cashBalance"]) + float(point["netValue"])

      result[account['securitiesAccountNumber']] = account_history

  return result

@app.post("/api/instrument-history")
async def get_instrument_history(params: InstrumentHistory):
  payload = {
    "type": "aggregateHistoryLight",
    "range": params.range,
    "id": params.id + ".TIB",
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }

  return await call_tr_ws_api(payload, 100)

@app.get("/api/portfolio")
async def get_portfolio():

  accounts = await get_accounts_data()
  result = {}

  if accounts is not None:
    for account in accounts["accounts"]:

      payload = {
        "type": "compactPortfolioByTypeV2",
        "secAccNo": account["securitiesAccountNumber"],
        "__headers": {
          "traceparent": generate_traceparent()
        }
      }

      account_portfolio = await call_tr_ws_api(payload, 22)

      if account_portfolio is not None :
        for categories in account_portfolio["categories"]:
          for position in categories["positions"]:
            position["imageId"] = "https://assets.traderepublic.com/img/" + position["imageId"] + "/dark.svg"

            # Add stock details :
            stock_details_payload = {
              "type": "stockDetails",
              "id": position["isin"],
              "jurisdiction": JURISDICTION,
              "__headers": {
                "traceparent": generate_traceparent()
              }
            }
            stock_details = await call_tr_ws_api(stock_details_payload, 28)
            if stock_details is not None:
              position["aggregatedDividends"] = stock_details["aggregatedDividends"]
              position["analystRating"] = stock_details["analystRating"]
              position["company"] = stock_details["company"]
              position["dividendFrequency"] = stock_details["dividendFrequency"]
              position["dividends"] = stock_details["dividends"]

              fix_struct(position)
        result[account["securitiesAccountNumber"]] = account_portfolio

  return result

@app.get("/api/accounts")
async def get_accounts():

  accounts = await get_accounts_data()
  if accounts is None:
    return "{}"

  accounts_list = accounts["accounts"]

  for account in accounts_list:
    cash_payload = {
      "type": "cash",
      "accountNumber": account["cashAccountNumber"],
      "__headers": {
        "traceparent": generate_traceparent()
      }
    }
    cash_accounts = await call_tr_ws_api(cash_payload, 5)

    if cash_accounts is not None :
      for cash_account in cash_accounts:
        if account["cashAccountNumber"] == cash_account["accountNumber"]:
          account["cashAmount"] = cash_account["amount"]

    available_cash_payload = {
      "type": "availableCash",
      "accountNumber": account["cashAccountNumber"],
      "__headers": {
        "traceparent": generate_traceparent()
      }
    }
    available_cash_accounts = await call_tr_ws_api(available_cash_payload, 6)

    if available_cash_accounts is not None:
      for av_cash_account in available_cash_accounts:
        if account["cashAccountNumber"] == av_cash_account["accountNumber"]:
          account["availableCashAmount"] = av_cash_account["amount"]

  return accounts_list

@app.post("/api/instrument")
async def get_global_instrument(params: Instrument):
  payload = {
    "type": "instrument",
    "id": params.id,
    "jurisdiction": JURISDICTION,
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }

  return await call_tr_ws_api(payload, 30)

@app.post("/api/tr-instrument")
async def get_tr_instrument(params: Instrument):
  payload = {
    "type": "homeInstrumentExchange",
    "id": params.id,
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }

  return await call_tr_ws_api(payload, 31)

@app.get("/api/price-alarms")
async def get_price_alarms():
  payload = {
    "type": "priceAlarms",
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }

  return await call_tr_ws_api(payload, 4)

@app.get("/api/accounts-activity")
async def get_accounts_activity() -> list:
  payload = {
    "type": "timelineActivityLog",
    "__headers": {
      "traceparent": generate_traceparent()
    }
  }

  logs = await call_tr_ws_api(payload, 4)
  if logs is None:
    return []

  for action in logs["items"]:
    action["icon"] = "https://assets.traderepublic.com/img/" + action["icon"] + "/dark.svg"
    action["subtitle"] = fix_string(action["subtitle"])

  return logs["items"]

def start_api_server():
  uvicorn.run(app, host="0.0.0.0", port=8000)