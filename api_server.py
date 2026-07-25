import uuid
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fetch import call_tr_rest_api, call_tr_ws_api, generate_traceparent

JURISDICTION = "FR"
APPROVED_EXCHANGES = Literal["LSX", "TDG", "TIB", "XETR", "XMIL", "XPAR", "XWBO"]
APPROVED_UNITS = Literal["EUR", "USD"]
APPROVED_MODES = Literal["stopMarket", "market", "limit"]
APPROVED_RANGES = Literal["1d", "5d", "1m", "1y", "max"]
APPROVED_VALIDITY = Literal["GFD", "GTD", "GTC"]

app = FastAPI()


class ExchangeSymbol(BaseModel):
    symbol: APPROVED_EXCHANGES


class InstrumentHistory(BaseModel):
    id: str
    range: APPROVED_RANGES


class Instrument(BaseModel):
    id: str


class AccountHistoryRequest(BaseModel):
    range: APPROVED_RANGES


class Order(BaseModel):
    account_nb: str
    exchange: APPROVED_EXCHANGES
    instrument: str
    mode: APPROVED_MODES
    quantity: int
    stop: float | None = None
    limit: float | None = None
    type: Literal["buy", "sell"]
    validity: APPROVED_VALIDITY | None = None


class OrderPrice(BaseModel):
    exchange: APPROVED_EXCHANGES
    instrument: str
    unit: APPROVED_UNITS


class OrderId(BaseModel):
    orderId: str


class PriceAlarm(BaseModel):
    instrument: str
    targetPrice: float


class PriceAlarmId(BaseModel):
    alarmId: str


async def get_accounts_data():
    payload = {
        "type": "accountPairs",
        "__headers": {"traceparent": generate_traceparent()},
    }

    accounts = await call_tr_ws_api(payload, 1)
    if accounts is None:
        raise HTTPException(status_code=500, detail="Failed to fetch accounts details")

    return accounts["accounts"]

def complete_order_details(params, payload):
    if params.mode == "stopMarket":
        if params.stop is None:
            raise HTTPException(status_code=400, detail="The stop price is required for stop market orders")
        payload["parameters"]["stop"] = params.stop
    elif params.mode == "limit":
        if params.limit is None:
            raise HTTPException(status_code=400, detail="The limit price is required for limit orders")
        payload["parameters"]["limit"] = params.limit
    
    return payload

def fix_string(text: str) -> str:
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
        raise HTTPException(status_code=500, detail="Failed to fetch personal details")

    for relation in relations["relationships"]:
        if relation["relationshipType"] == "SELF":
            personal_details["bankingInfo"] = relation["bankingInfo"]

    return personal_details


@app.get("/api/tickets")
def get_open_tickets():
    result = {}

    open = call_tr_rest_api("api/v2/timeline/inbox/open")
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
        raise HTTPException(status_code=500, detail="Failed to fetch card details")

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
        "visaPlus": card_infos["data"]["visaPlus"]["status"],
    }

    return result


@app.get("/api/interests")
async def get_interests():
    accounts = await get_accounts_data()

    for account in accounts:
        if account["productType"] == "DEFAULT":
            interests = call_tr_rest_api(
                f"api/v1/interest-experience/interest/{account['cashAccountNumber']}/info"
            )
            if interests is not None:
                interests["iconUrl"] = (
                    "https://assets.traderepublic.com/img/"
                    + interests["iconUrl"]
                    + "/dark.svg"
                )
                interests["title"] = fix_string(interests["title"])
                return interests
            raise HTTPException(status_code=500, detail="Failed to fetch interests details")


@app.get("/api/orders")
async def get_orders():
    accounts = await get_accounts_data()
    
    result = {}
    for account in accounts:
        if account["productType"] != "DEFAULT":
            orders = call_tr_rest_api(
                f"web-trading-gateway/api/customer/v1/orders?sort=orderUpdatedAt,desc&secAccNo={account['securitiesAccountNumber']}&page=1&pageSize=500"
            )
            if orders is not None:
                result[account["securitiesAccountNumber"]] = orders

    return result


@app.get("/api/transactions")
async def get_transactions():
    transactions = call_tr_rest_api("api/v2/timeline/transactions?pageSize=500")
    if transactions is not None:
        for transaction in transactions["items"]:
            transaction.pop("avatar", None)
            transaction.pop("badge", None)
            transaction.pop("action", None)
            transaction["icon"] = (
                "https://assets.traderepublic.com/img/"
                + transaction["icon"]
                + "/dark.svg"
            )
        return transactions["items"]
    raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@app.get("/api/portfolio")
async def get_portfolio():
    accounts = await get_accounts_data()

    result = {}
    for account in accounts:
        payload = {
            "type": "compactPortfolioByTypeV2",
            "secAccNo": account["securitiesAccountNumber"],
            "__headers": {"traceparent": generate_traceparent()},
        }

        account_portfolio = await call_tr_ws_api(payload, 22)

        if account_portfolio is not None:
            for categories in account_portfolio["categories"]:
                for position in categories["positions"]:
                    position["imageId"] = (
                        "https://assets.traderepublic.com/img/"
                        + position["imageId"]
                        + "/dark.svg"
                    )

                    # Add stock details :
                    stock_details_payload = {
                        "type": "stockDetails",
                        "id": position["isin"],
                        "jurisdiction": JURISDICTION,
                        "__headers": {"traceparent": generate_traceparent()},
                    }
                    stock_details = await call_tr_ws_api(stock_details_payload, 28)
                    if stock_details is not None:
                        position["aggregatedDividends"] = stock_details[
                            "aggregatedDividends"
                        ]
                        position["analystRating"] = stock_details["analystRating"]
                        position["company"] = stock_details["company"]
                        position["dividendFrequency"] = stock_details[
                            "dividendFrequency"
                        ]
                        position["dividends"] = stock_details["dividends"]

                        fix_struct(position)
            result[account["securitiesAccountNumber"]] = account_portfolio

    return result


@app.get("/api/accounts")
async def get_accounts():
    accounts = await get_accounts_data()

    for account in accounts:
        cash_payload = {
            "type": "cash",
            "accountNumber": account["cashAccountNumber"],
            "__headers": {"traceparent": generate_traceparent()},
        }
        cash_accounts = await call_tr_ws_api(cash_payload, 5)

        if cash_accounts is not None:
            for cash_account in cash_accounts:
                if account["cashAccountNumber"] == cash_account["accountNumber"]:
                    account["cashAmount"] = cash_account["amount"]

        available_cash_payload = {
            "type": "availableCash",
            "accountNumber": account["cashAccountNumber"],
            "__headers": {"traceparent": generate_traceparent()},
        }
        available_cash_accounts = await call_tr_ws_api(available_cash_payload, 6)

        if available_cash_accounts is not None:
            for av_cash_account in available_cash_accounts:
                if account["cashAccountNumber"] == av_cash_account["accountNumber"]:
                    account["availableCashAmount"] = av_cash_account["amount"]

    return accounts


@app.get("/api/price-alarms")
async def get_price_alarms():
    payload = {
        "type": "priceAlarms",
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 4)


@app.get("/api/accounts-activity")
async def get_accounts_activity() -> list:
    payload = {
        "type": "timelineActivityLog",
        "__headers": {"traceparent": generate_traceparent()},
    }

    logs = await call_tr_ws_api(payload, 4)
    if logs is None:
        raise HTTPException(status_code=500, detail="Failed to fetch logs")

    for action in logs["items"]:
        action["icon"] = (
            "https://assets.traderepublic.com/img/" + action["icon"] + "/dark.svg"
        )
        action["subtitle"] = fix_string(action["subtitle"])

    return logs["items"]


@app.post("/api/schedule-exchange")
def get_exchange_symbol(params: ExchangeSymbol):
    return call_tr_rest_api(
        f"api-gateway/instrument-universe/api/v1/exchanges/{params.symbol}/schedule"
    )


@app.post("/api/accounts-history")
async def get_accounts_history(params: AccountHistoryRequest):
    accounts = await get_accounts_data()

    result = {}
    for account in accounts:
        account_history = call_tr_rest_api(
            f"api-gateway/portfolio-chart/v2/chart?secAccNo={account['securitiesAccountNumber']}&range={params.range}&currency={account['currency']}"
        )
        if account_history is not None:
            for point in account_history["points"]:
                point["totalValue"] = float(point["cashBalance"]) + float(
                    point["netValue"]
                )

            result[account["securitiesAccountNumber"]] = account_history

    return result


@app.post("/api/instrument-history")
async def get_instrument_history(params: InstrumentHistory):
    payload = {
        "type": "aggregateHistoryLight",
        "range": params.range,
        "id": params.id + ".TIB",
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 100)


@app.post("/api/instrument")
async def get_global_instrument(params: Instrument):
    payload = {
        "type": "instrument",
        "id": params.id,
        "jurisdiction": JURISDICTION,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 30)


@app.post("/api/tr-instrument")
async def get_tr_instrument(params: Instrument):
    payload = {
        "type": "homeInstrumentExchange",
        "id": params.id,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 31)


@app.post("/api/order-price")
async def get_order_price(params: OrderPrice):
    base_payload = {
        "type": "priceForOrderV2",
        "isin": params.instrument,
        "exchangeId": params.exchange,
        "unit": params.unit,
        "__headers": {"traceparent": generate_traceparent()},
    }

    base_payload["side"] = "sell"
    sell_prices = await call_tr_ws_api(base_payload, 140)

    base_payload["side"] = "buy"
    buy_prices = await call_tr_ws_api(base_payload, 141)

    return {"sell": sell_prices, "buy": buy_prices}


@app.post("/api/order-fees")
async def get_order_fees(params: Order):
    accounts = await get_accounts_data()
    securities_numbers = [
        acc["securitiesAccountNumber"] for acc in accounts
    ]
    if params.account_nb not in securities_numbers:
        raise HTTPException(status_code=400, detail="The account number you provided does not match any of your accounts")

    payload = {
        "type": "orderFeesV2",
        "parameters": {
            "exchangeId": params.exchange,
            "instrumentId": params.instrument,
            "mode": params.mode,
            "size": params.quantity,
            "type": params.type,
            "currency": next(
                (
                    acc["currency"]
                    for acc in accounts
                    if acc["securitiesAccountNumber"] == params.account_nb
                ),
                None,
            ),
        },
        "secAccNo": params.account_nb,
        "__headers": {"traceparent": generate_traceparent()},
    }

    payload = complete_order_details(params, payload)

    return await call_tr_ws_api(payload, 110)


@app.post("/api/place-order")
async def place_order(params: Order):
    if params.validity is None:
        raise HTTPException(
            status_code=400, detail="Validity is required : GFD, GTD, GTC"
        )

    accounts = await get_accounts_data()

    securities_numbers = [
        acc["securitiesAccountNumber"] for acc in accounts
    ]
    if params.account_nb not in securities_numbers:
        raise HTTPException(status_code=400, detail="The account number you provided does not match any of your accounts")

    currency = next(
        (
            acc["currency"]
            for acc in accounts
            if acc["securitiesAccountNumber"] == params.account_nb
        ),
        None,
    )
    if currency is None:
        raise HTTPException(status_code=500, detail="Failed to fetch currency for the account number you provided")

    payload = {
        "type": "simpleCreateOrder",
        "parameters": {
            "exchangeId": params.exchange,
            "expiry": {"type": params.validity.lower()},
            "instrumentId": params.instrument,
            "mode": params.mode,
            "sellFractions": False,
            "settlementCurrency": currency,
            "tradingCurrency": currency,
            "side": params.type,
            "size": params.quantity,
            "type": params.type,
        },
        "secAccNo": params.account_nb,
        "clientProcessId": str(uuid.uuid4()),
        "warningsShown": ["appropriatenessTestingAppropriateUser"],
        "__headers": {"traceparent": generate_traceparent()},
    }

    payload = complete_order_details(params, payload)

    return await call_tr_ws_api(payload, 142)


@app.post("/api/cancel-order")
async def cancel_order(params: OrderId):
    payload = {
        "type": "cancelOrder",
        "orderId": params.orderId,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 145)


@app.post("/api/set-price-alarm")
async def set_price_alarm(params: PriceAlarm):
    payload = {
        "type": "createPriceAlarm",
        "instrumentId": params.instrument,
        "targetPrice": params.targetPrice,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 143)


@app.post("/api/delete-price-alarm")
async def delete_price_alarm(params: PriceAlarmId):
    payload = {
        "type": "cancelPriceAlarm",
        "id": params.alarmId,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 144)


def start_api_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)
