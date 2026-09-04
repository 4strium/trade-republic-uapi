import uuid
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from trade_republic_uapi.__init__ import __version__
from trade_republic_uapi.fetch import (
    call_tr_rest_api,
    call_tr_ws_api,
    generate_traceparent,
)
from trade_republic_uapi.preferences import load_preferences

APPROVED_EXCHANGES = Literal["LSX", "TDG", "TIB", "XETR", "XMIL", "XPAR", "XWBO"]
APPROVED_MODES = Literal["stopMarket", "market", "limit"]
APPROVED_RANGES = Literal["1d", "5d", "1m", "1y", "max"]
APPROVED_VALIDITY = Literal["GFD", "GTD", "GTC"]

app = FastAPI(
    title="Trade Republic Unofficial API",
    description=(
        "Lightweight and fast unofficial REST/WebSocket-backed API for Trade "
        "Republic. It authenticates through the official Trade Republic app "
        "session and exposes convenient REST "
        "endpoints on top of Trade Republic's private REST and WebSocket APIs.\n\n"
        "All endpoints require that the underlying Trade Republic session is "
        "already authenticated (cookies/session established by this server at "
        "startup). No API key is needed to call this local server, but the "
        "server itself must be logged in to Trade Republic to answer requests."
    ),
    version=__version__,
    contact={"name": "trade-republic-uapi"},
)


class ExchangeSymbol(BaseModel):
    """Identifies a stock exchange, used to fetch its trading schedule."""

    symbol: APPROVED_EXCHANGES = Field(
        ...,
        description="Code of the exchange to look up.",
        examples=["XETR"],
    )


class InstrumentHistory(BaseModel):
    """Request body used to fetch the historical price of an instrument."""

    id: str = Field(
        ...,
        description="ISIN of the instrument (International Securities "
        "Identification Number).",
        examples=["US0378331005"],
    )
    range: APPROVED_RANGES = Field(
        ...,
        description="Time range of the history to retrieve.",
        examples=["1m"],
    )


class Instrument(BaseModel):
    """Identifies a financial instrument by its ISIN."""

    id: str = Field(
        ...,
        description="ISIN of the instrument (International Securities "
        "Identification Number).",
        examples=["US0378331005"],
    )


class AccountHistoryRequest(BaseModel):
    """Request body used to fetch the historical value of the portfolio."""

    range: APPROVED_RANGES = Field(
        ...,
        description="Time range of the history to retrieve.",
        examples=["1y"],
    )


class Order(BaseModel):
    """Parameters describing a stock/ETF order, used both to price an order
    (fees simulation) and to actually place it."""

    account_nb: str = Field(
        ...,
        description="Securities account number the order should be placed "
        "on (see `securitiesAccountNumber` returned by `GET /api/accounts`).",
        examples=["DE1234567890123456"],
    )
    exchange: APPROVED_EXCHANGES = Field(
        ...,
        description="Code of the exchange on which the order should be executed.",
        examples=["XETR"],
    )
    instrument: str = Field(
        ...,
        description="ISIN of the instrument to buy or sell.",
        examples=["US0378331005"],
    )
    mode: APPROVED_MODES = Field(
        ...,
        description="Order execution mode: `market` (executed immediately at "
        "market price), `limit` (executed only at or better than `limit`), "
        "or `stopMarket` (becomes a market order once the `stop` price is "
        "reached).",
        examples=["limit"],
    )
    quantity: int = Field(
        ...,
        description="Number of shares/units to buy or sell.",
        examples=[10],
        gt=0,
    )
    stop: float | None = Field(
        None,
        description="Stop price. Required when `mode` is `stopMarket`, "
        "ignored otherwise.",
        examples=[150.0],
    )
    limit: float | None = Field(
        None,
        description="Limit price. Required when `mode` is `limit`, ignored otherwise.",
        examples=[145.5],
    )
    type: Literal["buy", "sell"] = Field(
        ...,
        description="Whether this order buys or sells the instrument.",
        examples=["buy"],
    )
    validity: APPROVED_VALIDITY | None = Field(
        None,
        description="Order validity/time-in-force. Required to actually "
        "place an order (`/api/place-order`), optional when only estimating "
        "fees (`/api/order-fees`). `GFD` = Good For Day, `GTD` = Good Till "
        "Date, `GTC` = Good Till Cancelled.",
        examples=["GTC"],
    )


class OrderPrice(BaseModel):
    """Request body used to fetch the current live buy/sell price of an
    instrument on a given exchange."""

    exchange: APPROVED_EXCHANGES = Field(
        ...,
        description="Code of the exchange to fetch the price from.",
        examples=["XETR"],
    )
    instrument: str = Field(
        ...,
        description="ISIN of the instrument to price.",
        examples=["US0378331005"],
    )


class OrderId(BaseModel):
    """Identifies an existing, still-open order."""

    orderId: str = Field(
        ...,
        description="Identifier of the order, as returned by "
        "`POST /api/place-order` or `GET /api/orders`.",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )


class PriceAlarm(BaseModel):
    """Parameters used to create a new price alarm on an instrument."""

    instrument: str = Field(
        ...,
        description="ISIN of the instrument to watch.",
        examples=["US0378331005"],
    )
    targetPrice: float = Field(
        ...,
        description="Price at which the alarm should trigger.",
        examples=[180.0],
    )


class PriceAlarmId(BaseModel):
    """Identifies an existing price alarm."""

    alarmId: str = Field(
        ...,
        description="Identifier of the price alarm, as returned by "
        "`GET /api/price-alarms` or `POST /api/set-price-alarm`.",
        examples=["9f8e7d6c-5b4a-3210-fedc-ba0987654321"],
    )


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
            raise HTTPException(
                status_code=400,
                detail="The stop price is required for stop market orders",
            )
        payload["parameters"]["stop"] = params.stop
    elif params.mode == "limit":
        if params.limit is None:
            raise HTTPException(
                status_code=400, detail="The limit price is required for limit orders"
            )
        payload["parameters"]["limit"] = params.limit

    return payload


def fix_string(text: str) -> str:
    if text is None:
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


@app.get(
    "/api/personal-details",
    tags=["Account"],
    summary="Get personal details",
    description=(
        "Returns the personal details of the authenticated Trade Republic "
        "customer (name, address, tax residency, etc.) merged with the "
        "banking information (IBAN/BIC)."
    ),
    response_description="Personal details enriched with banking information.",
)
def get_personal_details():
    personal_details = call_tr_rest_api("api/v1/customer/personal-details")
    relations = call_tr_rest_api("api/v1/customer/relationships/detailed")

    if relations is None or personal_details is None:
        raise HTTPException(status_code=500, detail="Failed to fetch personal details")

    for relation in relations["relationships"]:
        if relation["relationshipType"] == "SELF":
            personal_details["bankingInfo"] = relation["bankingInfo"]

    return personal_details


@app.get(
    "/api/tickets",
    tags=["Account"],
    summary="Get support tickets",
    description=(
        "Returns the customer's support/inbox tickets, split into `open` "
        "and `closed` lists."
    ),
    response_description="Object with `open` and `closed` lists of tickets.",
)
def get_open_tickets():
    result = {}

    open = call_tr_rest_api("api/v2/timeline/inbox/open")
    if open is not None:
        result["open"] = open["items"]
    closed = call_tr_rest_api("api/v2/timeline/inbox/closed")
    if closed is not None:
        result["closed"] = closed["items"]
    return result


@app.get(
    "/api/card",
    tags=["Card"],
    summary="Get debit card details",
    description=(
        "Returns the details of the customer's Trade Republic debit card: "
        "identifiers, status, cardholder name, security settings and "
        "funding source."
    ),
    response_description="Debit card details.",
)
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


@app.get(
    "/api/interests",
    tags=["Account"],
    summary="Get interest rate on cash",
    description=(
        "Returns the interest information (rate, icon, title) applied to the "
        "cash held in the customer's default cash account."
    ),
    response_description="Interest information for the default cash account.",
)
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
            raise HTTPException(
                status_code=500, detail="Failed to fetch interests details"
            )


@app.get(
    "/api/orders",
    tags=["Orders"],
    summary="List orders per account",
    description=(
        "Returns, for every non-cash securities account, the list of the "
        "500 most recent orders (sorted by last update, descending)."
    ),
    response_description=(
        "Object mapping each `securitiesAccountNumber` to its orders page."
    ),
)
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


@app.get(
    "/api/transactions",
    tags=["Account"],
    summary="List timeline transactions",
    description=(
        "Returns up to 500 items of the customer's transaction timeline "
        "(deposits, withdrawals, trades, dividends, card payments, etc.), "
        "with icon URLs resolved to full asset links."
    ),
    response_description="List of transaction timeline items.",
)
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


@app.get(
    "/api/portfolio",
    tags=["Portfolio"],
    summary="Get portfolio positions per account",
    description=(
        "Returns, for every securities account, the current portfolio "
        "positions grouped by category. Each position is enriched with a "
        "resolved image URL and additional stock details (aggregated "
        "dividends, analyst rating, company info, dividend frequency)."
    ),
    response_description=(
        "Object mapping each `securitiesAccountNumber` to its portfolio."
    ),
)
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
                        "jurisdiction": load_preferences().get("jurisdiction"),
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


@app.get(
    "/api/accounts",
    tags=["Account"],
    summary="List accounts with cash balances",
    description=(
        "Returns the customer's account pairs (cash + securities accounts), "
        "each enriched with its current `cashAmount` and "
        "`availableCashAmount`."
    ),
    response_description="List of accounts with their cash balances.",
)
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


@app.get(
    "/api/price-alarms",
    tags=["Price Alarms"],
    summary="List price alarms",
    description="Returns all price alarms currently configured by the customer.",
    response_description="Price alarms data as returned by Trade Republic.",
)
async def get_price_alarms():
    payload = {
        "type": "priceAlarms",
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 4)


@app.get(
    "/api/accounts-activity",
    tags=["Account"],
    summary="Get account activity log",
    description=(
        "Returns the timeline activity log (logins, actions, changes, "
        "etc.) for the customer's accounts, with icon URLs resolved to "
        "full asset links."
    ),
    response_description="List of activity log entries.",
)
async def get_accounts_activity() -> list:
    payload = {
        "type": "timelineActivityLog",
        "__headers": {"traceparent": generate_traceparent()},
    }

    logs = await call_tr_ws_api(payload, 17)

    if logs is None:
        raise HTTPException(status_code=500, detail="Failed to fetch logs")

    for action in logs["items"]:
        if action.get("icon"):
            action["icon"] = (
                "https://assets.traderepublic.com/img/" + action["icon"] + "/dark.svg"
            )
        if action.get("subtitle") is not None:
            action["subtitle"] = fix_string(action["subtitle"])

    return logs["items"]


@app.post(
    "/api/schedule-exchange",
    tags=["Instruments"],
    summary="Get an exchange's trading schedule",
    description=(
        "Returns the opening/closing schedule of the given exchange "
        "(e.g. `XETR`, `XPAR`, `XMIL`...)."
    ),
    response_description="Trading schedule of the requested exchange.",
)
def get_exchange_symbol(params: ExchangeSymbol):
    return call_tr_rest_api(
        f"api-gateway/instrument-universe/api/v1/exchanges/{params.symbol}/schedule"
    )


@app.post(
    "/api/accounts-history",
    tags=["Portfolio"],
    summary="Get portfolio value history per account",
    description=(
        "Returns, for every securities account, the historical evolution "
        "of the portfolio value (cash balance + net value) over the "
        "requested `range`."
    ),
    response_description=(
        "Object mapping each `securitiesAccountNumber` to its value history."
    ),
)
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


@app.post(
    "/api/instrument-history",
    tags=["Instruments"],
    summary="Get an instrument's price history",
    description=(
        "Returns the aggregated historical price series of an instrument "
        "(identified by its ISIN) over the requested `range`."
    ),
    response_description="Aggregated price history of the instrument.",
)
async def get_instrument_history(params: InstrumentHistory):
    payload = {
        "type": "aggregateHistoryLight",
        "range": params.range,
        "id": params.id + ".TIB",
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 100)


@app.post(
    "/api/instrument",
    tags=["Instruments"],
    summary="Get global instrument details",
    description=(
        "Returns general information about an instrument (identified by "
        "its ISIN): name, type, tags, available exchanges, etc."
    ),
    response_description="Instrument details.",
)
async def get_global_instrument(params: Instrument):
    payload = {
        "type": "instrument",
        "id": params.id,
        "jurisdiction": load_preferences().get("jurisdiction"),
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 30)


@app.post(
    "/api/tr-instrument",
    tags=["Instruments"],
    summary="Get Trade Republic's home exchange for an instrument",
    description=(
        "Returns Trade Republic's default (home) exchange information for "
        "the given instrument (identified by its ISIN)."
    ),
    response_description="Home exchange details for the instrument.",
)
async def get_tr_instrument(params: Instrument):
    payload = {
        "type": "homeInstrumentExchange",
        "id": params.id,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 31)


@app.post(
    "/api/order-price",
    tags=["Orders"],
    summary="Get live buy/sell price of an instrument",
    description=(
        "Returns the current live `sell` and `buy` prices in EURO for an "
        "instrument on a given exchange."
    ),
    response_description="Object with `sell` and `buy` price quotes.",
)
async def get_order_price(params: OrderPrice):
    base_payload = {
        "type": "priceForOrderV2",
        "isin": params.instrument,
        "exchangeId": params.exchange,
        "unit": "EUR",
        "__headers": {"traceparent": generate_traceparent()},
    }

    base_payload["side"] = "sell"
    sell_prices = await call_tr_ws_api(base_payload, 140)

    base_payload["side"] = "buy"
    buy_prices = await call_tr_ws_api(base_payload, 141)

    return {"sell": sell_prices, "buy": buy_prices}


@app.post(
    "/api/order-fees",
    tags=["Orders"],
    summary="Simulate an order and get its fees",
    description=(
        "Simulates the given order (without placing it) and returns the "
        "fees that would be charged, based on the order's exchange, "
        "instrument, mode, quantity and side. The `account_nb` must match "
        "one of the customer's securities accounts. `validity` is not "
        "required for a simulation."
    ),
    response_description="Fees breakdown for the simulated order.",
    responses={
        400: {
            "description": (
                "Invalid account number, or missing `stop`/`limit` price "
                "for the requested `mode`."
            )
        }
    },
)
async def get_order_fees(params: Order):
    accounts = await get_accounts_data()
    securities_numbers = [acc["securitiesAccountNumber"] for acc in accounts]
    if params.account_nb not in securities_numbers:
        raise HTTPException(
            status_code=400,
            detail="The account number you provided does not match any of your accounts",
        )

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


@app.post(
    "/api/place-order",
    tags=["Orders"],
    summary="Place a buy or sell order",
    description=(
        "Places a real buy or sell order on Trade Republic for the given "
        "instrument, exchange, quantity and mode. `validity` is "
        "**mandatory** for this endpoint (`GFD`, `GTD` or `GTC`), and "
        "`account_nb` must match one of the customer's securities "
        "accounts. `stop` is required when `mode=stopMarket`, `limit` is "
        "required when `mode=limit`.\n\n"
        "**Warning: this places a real order with real money.**"
    ),
    response_description="Result of the order placement request.",
    responses={
        400: {
            "description": (
                "Missing `validity`, invalid account number, or missing "
                "`stop`/`limit` price for the requested `mode`."
            )
        }
    },
)
async def place_order(params: Order):
    if params.validity is None:
        raise HTTPException(
            status_code=400, detail="Validity is required : GFD, GTD, GTC"
        )

    accounts = await get_accounts_data()

    securities_numbers = [acc["securitiesAccountNumber"] for acc in accounts]
    if params.account_nb not in securities_numbers:
        raise HTTPException(
            status_code=400,
            detail="The account number you provided does not match any of your accounts",
        )

    currency = next(
        (
            acc["currency"]
            for acc in accounts
            if acc["securitiesAccountNumber"] == params.account_nb
        ),
        None,
    )
    if currency is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch currency for the account number you provided",
        )

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


@app.post(
    "/api/cancel-order",
    tags=["Orders"],
    summary="Cancel an open order",
    description="Cancels a previously placed, still-open order by its `orderId`.",
    response_description="Result of the cancellation request.",
)
async def cancel_order(params: OrderId):
    payload = {
        "type": "cancelOrder",
        "orderId": params.orderId,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 145)


@app.post(
    "/api/set-price-alarm",
    tags=["Price Alarms"],
    summary="Create a price alarm",
    description=(
        "Creates a new price alarm that will trigger a notification once "
        "the given instrument reaches `targetPrice`."
    ),
    response_description="Result of the price alarm creation request.",
)
async def set_price_alarm(params: PriceAlarm):
    payload = {
        "type": "createPriceAlarm",
        "instrumentId": params.instrument,
        "targetPrice": params.targetPrice,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 143)


@app.post(
    "/api/delete-price-alarm",
    tags=["Price Alarms"],
    summary="Delete a price alarm",
    description="Deletes an existing price alarm by its `alarmId`.",
    response_description="Result of the price alarm deletion request.",
)
async def delete_price_alarm(params: PriceAlarmId):
    payload = {
        "type": "cancelPriceAlarm",
        "id": params.alarmId,
        "__headers": {"traceparent": generate_traceparent()},
    }

    return await call_tr_ws_api(payload, 144)


def start_api_server(port):
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
