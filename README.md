# Trade Republic Unofficial API

> ⚠️ **Disclaimer**: this project is **not affiliated with Trade Republic Bank GmbH**. Use it at your own risk, especially for endpoints that place real orders.

<p align="center">
  <img src="https://github.com/4strium/trade-republic-uapi/blob/main/ressources/TradeRepublicUAPI_demo.gif?raw=true" width="80%" alt="">
</p>

Lightweight & Fast unofficial REST API for Trade Republic

## How it works

1. The main program launches a headless Chromium browser and guides you through the official Trade Republic login flow.
2. Once authenticated, it starts a local FastAPI server in the background, reusing that authenticated session to call Trade Republic's private REST and WebSocket APIs.
3. You then interact with your own account through simple, well-documented HTTP endpoints exposed by that local server.

## Install and start the API server

### Option 1: via pip (recommended)
```bash
  pip install trade-republic-uapi
  traderep-uapi
```

### Option 2: from source (development)
```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  python3 -m trade_republic_uapi.cli
```

Follow the on-screen instructions to scan the QR code with the Trade Republic app. Once authenticated, the API server starts automatically.

## Interactive API documentation

Once the server is running, interactive documentation where you can browse every endpoint, see the request/response schemas, try requests live, and view example payloads is available at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Raw OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

## Endpoints reference

All endpoints are served from the base URL of your running instance (e.g. `http://127.0.0.1:8000`). `GET` endpoints take no body; `POST` endpoints take a JSON body as described.

### GET endpoints

| Method | Path                     | Tag          | Description                                                        |
|--------|--------------------------|--------------|----------------------------------------------------------------------------|
| GET    | `/api/personal-details`  | Account      | Personal details + banking info (IBAN/BIC) of the customer                 |
| GET    | `/api/tickets`           | Account      | Open and closed support tickets                                            |
| GET    | `/api/card`              | Card         | Debit card details (status, cardholder, security settings...)             |
| GET    | `/api/interests`         | Account      | Interest rate applied to cash in the default account                      |
| GET    | `/api/orders`            | Orders       | Last 500 orders per securities account                                    |
| GET    | `/api/transactions`      | Account      | Last 500 timeline transactions (trades, dividends, payments...)           |
| GET    | `/api/portfolio`         | Portfolio    | Current positions per account, enriched with stock details                |
| GET    | `/api/accounts`          | Account      | Accounts with cash balances (`cashAmount`, `availableCashAmount`)          |
| GET    | `/api/price-alarms`      | Price Alarms | List all configured price alarms                                          |
| GET    | `/api/accounts-activity` | Account      | Timeline activity log (logins, actions...)                                |

### POST endpoints

| Method | Path                     | Tag          | Description                                                        | Body schema              |
|--------|--------------------------|--------------|----------------------------------------------------------------------------|---------------------------|
| POST   | `/api/schedule-exchange` | Instruments  | Trading schedule of an exchange                                           | [`ExchangeSymbol`](#exchangesymbol)          |
| POST   | `/api/accounts-history`  | Portfolio    | Historical portfolio value per account, over a time range                 | [`AccountHistoryRequest`](#accounthistoryrequest)   |
| POST   | `/api/instrument-history`| Instruments  | Historical price series of an instrument, over a time range               | [`InstrumentHistory`](#instrumenthistory)       |
| POST   | `/api/instrument`        | Instruments  | General details about an instrument (name, type, exchanges...)            | [`Instrument`](#instrument)              |
| POST   | `/api/tr-instrument`     | Instruments  | Trade Republic's home exchange for an instrument                          | [`Instrument`](#instrument)              |
| POST   | `/api/order-price`       | Orders       | Live buy/sell price quote for an instrument                               | [`OrderPrice`](#orderprice)              |
| POST   | `/api/order-fees`        | Orders       | Simulates an order and returns its fees (no order is placed)              | [`Order`](#order) (`validity` optional) |
| POST   | `/api/place-order`       | Orders       | **Places a real order** ⚠️                                                | [`Order`](#order) (`validity` required) |
| POST   | `/api/cancel-order`      | Orders       | Cancels an open order                                                     | [`OrderId`](#orderid)                 |
| POST   | `/api/set-price-alarm`   | Price Alarms | Creates a new price alarm                                                 | [`PriceAlarm`](#pricealarm)              |
| POST   | `/api/delete-price-alarm`| Price Alarms | Deletes an existing price alarm                                           | [`PriceAlarmId`](#pricealarmid)            |

### Schemas

#### ExchangeSymbol
```jsonc
{ "symbol": "XETR" }  // one of: LSX, TDG, TIB, XETR, XMIL, XPAR, XWBO
```

#### InstrumentHistory
```jsonc
{ "id": "US0378331005", "range": "1m" }  // range: 1d, 5d, 1m, 1y, max
```

#### Instrument
```jsonc
{ "id": "US0378331005" }  // ISIN
```

#### AccountHistoryRequest
```jsonc
{ "range": "1y" }  // range: 1d, 5d, 1m, 1y, max
```

#### OrderPrice
```jsonc
{ "exchange": "XETR", "instrument": "US0378331005" }
```

#### Order
```jsonc
{
  "account_nb": "DE1234567890123456",
  "exchange": "XETR",
  "instrument": "US0378331005",
  "mode": "limit",       // stopMarket, market, limit
  "quantity": 10,
  "stop": null,          // required if mode = stopMarket
  "limit": 145.5,        // required if mode = limit
  "type": "buy",         // buy, sell
  "validity": "GTC"      // GFD, GTD, GTC — required for /api/place-order
}
```

#### OrderId
```jsonc
{ "orderId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
```

#### PriceAlarm
```jsonc
{ "instrument": "US0378331005", "targetPrice": 180.0 }
```

#### PriceAlarmId
```jsonc
{ "alarmId": "9f8e7d6c-5b4a-3210-fedc-ba0987654321" }
```

## Usage examples

The examples below use fictitious values (fake ISIN, account number, order IDs). Replace them with your own data. All examples assume the server runs on `http://127.0.0.1:8000`.

### curl

```bash
# Personal details
curl -s -X GET "http://127.0.0.1:8000/api/personal-details" -H "X-API-Key: <api_key>"

# Support tickets
curl -s -X GET "http://127.0.0.1:8000/api/tickets" -H "X-API-Key: <api_key>"

# Debit card details
curl -s -X GET "http://127.0.0.1:8000/api/card" -H "X-API-Key: <api_key>"

# Interest rate on cash
curl -s -X GET "http://127.0.0.1:8000/api/interests" -H "X-API-Key: <api_key>"

# Orders per account
curl -s -X GET "http://127.0.0.1:8000/api/orders" -H "X-API-Key: <api_key>"

# Transactions timeline
curl -s -X GET "http://127.0.0.1:8000/api/transactions" -H "X-API-Key: <api_key>"

# Portfolio positions
curl -s -X GET "http://127.0.0.1:8000/api/portfolio" -H "X-API-Key: <api_key>"

# Accounts + cash balances
curl -s -X GET "http://127.0.0.1:8000/api/accounts" -H "X-API-Key: <api_key>"

# Price alarms
curl -s -X GET "http://127.0.0.1:8000/api/price-alarms" -H "X-API-Key: <api_key>"

# Account activity log
curl -s -X GET "http://127.0.0.1:8000/api/accounts-activity" -H "X-API-Key: <api_key>"

# Exchange trading schedule
curl -s -X POST "http://127.0.0.1:8000/api/schedule-exchange" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"symbol": "XETR"}'

# Portfolio value history
curl -s -X POST "http://127.0.0.1:8000/api/accounts-history" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"range": "1y"}'

# Instrument price history
curl -s -X POST "http://127.0.0.1:8000/api/instrument-history" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"id": "US0378331005", "range": "1m"}'

# Global instrument details
curl -s -X POST "http://127.0.0.1:8000/api/instrument" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"id": "US0378331005"}'

# Trade Republic home exchange for an instrument
curl -s -X POST "http://127.0.0.1:8000/api/tr-instrument" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"id": "US0378331005"}'

# Live order price (buy/sell quote)
curl -s -X POST "http://127.0.0.1:8000/api/order-price" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"exchange": "XETR", "instrument": "US0378331005", "unit": "EUR"}'

# Get order fees
curl -s -X POST "http://127.0.0.1:8000/api/order-fees" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{
    "account_nb": "DE1234567890123456",
    "exchange": "XETR",
    "instrument": "US0378331005",
    "mode": "limit",
    "quantity": 10,
    "limit": 145.5,
    "type": "buy"
  }'

# Place a real order ⚠️
curl -s -X POST "http://127.0.0.1:8000/api/place-order" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{
    "account_nb": "DE1234567890123456",
    "exchange": "XETR",
    "instrument": "US0378331005",
    "mode": "limit",
    "quantity": 10,
    "limit": 145.5,
    "type": "buy",
    "validity": "GTC"
  }'

# Cancel an order
curl -s -X POST "http://127.0.0.1:8000/api/cancel-order" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"orderId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}'

# Create a price alarm
curl -s -X POST "http://127.0.0.1:8000/api/set-price-alarm" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"instrument": "US0378331005", "targetPrice": 180.0}'

# Delete a price alarm
curl -s -X POST "http://127.0.0.1:8000/api/delete-price-alarm" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api_key>" \
  -d '{"alarmId": "9f8e7d6c-5b4a-3210-fedc-ba0987654321"}'
```

