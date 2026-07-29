# Trade Republic Unofficial API

> ⚠️ **Disclaimer**: this project is **not affiliated with Trade Republic Bank GmbH**. Use it at your own risk, especially for endpoints that place real orders.

<p align="center">
  <img src="https://github.com/4strium/trade-republic-uapi/blob/main/ressources/TradeRepublicUAPI_demo.gif?raw=true"  width="80%" alt="CLI demonstration">
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

| Method | Path                     | Tag          | Description                                                        | Body schema              |
|--------|--------------------------|--------------|----------------------------------------------------------------------------|---------------------------|
| GET    | `/api/personal-details`  | Account      | Personal details + banking info (IBAN/BIC) of the customer                 | —                         |
| GET    | `/api/tickets`           | Account      | Open and closed support tickets                                            | —                         |
| GET    | `/api/card`              | Card         | Debit card details (status, cardholder, security settings...)             | —                         |
| GET    | `/api/interests`         | Account      | Interest rate applied to cash in the default account                      | —                         |
| GET    | `/api/orders`            | Orders       | Last 500 orders per securities account                                    | —                         |
| GET    | `/api/transactions`      | Account      | Last 500 timeline transactions (trades, dividends, payments...)           | —                         |
| GET    | `/api/portfolio`         | Portfolio    | Current positions per account, enriched with stock details                | —                         |
| GET    | `/api/accounts`          | Account      | Accounts with cash balances (`cashAmount`, `availableCashAmount`)          | —                         |
| GET    | `/api/price-alarms`      | Price Alarms | List all configured price alarms                                          | —                         |
| GET    | `/api/accounts-activity` | Account      | Timeline activity log (logins, actions...)                                | —                         |
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
curl -s -X GET "http://127.0.0.1:8000/api/personal-details"

# Support tickets
curl -s -X GET "http://127.0.0.1:8000/api/tickets"

# Debit card details
curl -s -X GET "http://127.0.0.1:8000/api/card"

# Interest rate on cash
curl -s -X GET "http://127.0.0.1:8000/api/interests"

# Orders per account
curl -s -X GET "http://127.0.0.1:8000/api/orders"

# Transactions timeline
curl -s -X GET "http://127.0.0.1:8000/api/transactions"

# Portfolio positions
curl -s -X GET "http://127.0.0.1:8000/api/portfolio"

# Accounts + cash balances
curl -s -X GET "http://127.0.0.1:8000/api/accounts"

# Price alarms
curl -s -X GET "http://127.0.0.1:8000/api/price-alarms"

# Account activity log
curl -s -X GET "http://127.0.0.1:8000/api/accounts-activity"

# Exchange trading schedule
curl -s -X POST "http://127.0.0.1:8000/api/schedule-exchange" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XETR"}'

# Portfolio value history
curl -s -X POST "http://127.0.0.1:8000/api/accounts-history" \
  -H "Content-Type: application/json" \
  -d '{"range": "1y"}'

# Instrument price history
curl -s -X POST "http://127.0.0.1:8000/api/instrument-history" \
  -H "Content-Type: application/json" \
  -d '{"id": "US0378331005", "range": "1m"}'

# Global instrument details
curl -s -X POST "http://127.0.0.1:8000/api/instrument" \
  -H "Content-Type: application/json" \
  -d '{"id": "US0378331005"}'

# Trade Republic home exchange for an instrument
curl -s -X POST "http://127.0.0.1:8000/api/tr-instrument" \
  -H "Content-Type: application/json" \
  -d '{"id": "US0378331005"}'

# Live order price (buy/sell quote)
curl -s -X POST "http://127.0.0.1:8000/api/order-price" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "XETR", "instrument": "US0378331005", "unit": "EUR"}'

# Get order fees
curl -s -X POST "http://127.0.0.1:8000/api/order-fees" \
  -H "Content-Type: application/json" \
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
  -d '{"orderId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}'

# Create a price alarm
curl -s -X POST "http://127.0.0.1:8000/api/set-price-alarm" \
  -H "Content-Type: application/json" \
  -d '{"instrument": "US0378331005", "targetPrice": 180.0}'

# Delete a price alarm
curl -s -X POST "http://127.0.0.1:8000/api/delete-price-alarm" \
  -H "Content-Type: application/json" \
  -d '{"alarmId": "9f8e7d6c-5b4a-3210-fedc-ba0987654321"}'
```

### Python

Using the [`requests`](https://pypi.org/project/requests/) library (`pip install requests`):

```python
import requests

BASE_URL = "http://127.0.0.1:8000"

# --- Simple GET endpoints -------------------------------------------------
portfolio = requests.get(f"{BASE_URL}/api/portfolio").json()
accounts = requests.get(f"{BASE_URL}/api/accounts").json()
print(portfolio, accounts)

# --- Get the live price of an instrument ----------------------------------
price = requests.post(
    f"{BASE_URL}/api/order-price",
    json={
        "exchange": "XETR",
        "instrument": "US0378331005",  # fictitious ISIN
        "unit": "EUR",
    },
).json()
print("Sell price:", price["sell"])
print("Buy price:", price["buy"])

# --- Simulate an order and check its fees before placing it ---------------
order_payload = {
    "account_nb": "DE1234567890123456",  # fictitious securities account number
    "exchange": "XETR",
    "instrument": "US0378331005",
    "mode": "limit",
    "quantity": 10,
    "limit": 145.5,
    "type": "buy",
}
fees_response = requests.post(f"{BASE_URL}/api/order-fees", json=order_payload)
fees_response.raise_for_status()
print("Estimated fees:", fees_response.json())

# --- Place a real order (validity is required) ⚠️ --------------------------
order_payload["validity"] = "GTC"
place_response = requests.post(f"{BASE_URL}/api/place-order", json=order_payload)
if place_response.status_code == 200:
    print("Order placed:", place_response.json())
else:
    print("Error placing order:", place_response.status_code, place_response.json())

# --- Create and then delete a price alarm ----------------------------------
alarm = requests.post(
    f"{BASE_URL}/api/set-price-alarm",
    json={"instrument": "US0378331005", "targetPrice": 180.0},
).json()
print("Alarm created:", alarm)

requests.post(
    f"{BASE_URL}/api/delete-price-alarm",
    json={"alarmId": "9f8e7d6c-5b4a-3210-fedc-ba0987654321"},
)
```

### Rust

Using [`reqwest`](https://crates.io/crates/reqwest) and [`serde_json`](https://crates.io/crates/serde_json). Add to `Cargo.toml`:

```toml
[dependencies]
reqwest = { version = "0.12", features = ["json", "blocking"] }
serde_json = "1"
```

```rust
use reqwest::blocking::Client;
use serde_json::json;

const BASE_URL: &str = "http://127.0.0.1:8000";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();

    // --- Simple GET endpoints ---------------------------------------------
    let portfolio: serde_json::Value = client
        .get(format!("{BASE_URL}/api/portfolio"))
        .send()?
        .json()?;
    println!("Portfolio: {portfolio}");

    let accounts: serde_json::Value = client
        .get(format!("{BASE_URL}/api/accounts"))
        .send()?
        .json()?;
    println!("Accounts: {accounts}");

    // --- Get the live price of an instrument -------------------------------
    let price: serde_json::Value = client
        .post(format!("{BASE_URL}/api/order-price"))
        .json(&json!({
            "exchange": "XETR",
            "instrument": "US0378331005", // fictitious ISIN
            "unit": "EUR"
        }))
        .send()?
        .json()?;
    println!("Sell price: {}", price["sell"]);
    println!("Buy price: {}", price["buy"]);

    // --- Simulate an order and check its fees before placing it -----------
    let mut order_payload = json!({
        "account_nb": "DE1234567890123456", // fictitious securities account number
        "exchange": "XETR",
        "instrument": "US0378331005",
        "mode": "limit",
        "quantity": 10,
        "limit": 145.5,
        "type": "buy"
    });

    let fees: serde_json::Value = client
        .post(format!("{BASE_URL}/api/order-fees"))
        .json(&order_payload)
        .send()?
        .json()?;
    println!("Estimated fees: {fees}");

    // --- Place a real order (validity is required) ⚠️ -----------------------
    order_payload["validity"] = json!("GTC");
    let response = client
        .post(format!("{BASE_URL}/api/place-order"))
        .json(&order_payload)
        .send()?;

    if response.status().is_success() {
        println!("Order placed: {:?}", response.json::<serde_json::Value>()?);
    } else {
        println!(
            "Error placing order ({}): {:?}",
            response.status(),
            response.json::<serde_json::Value>()?
        );
    }

    // --- Create and then delete a price alarm ------------------------------
    let alarm: serde_json::Value = client
        .post(format!("{BASE_URL}/api/set-price-alarm"))
        .json(&json!({ "instrument": "US0378331005", "targetPrice": 180.0 }))
        .send()?
        .json()?;
    println!("Alarm created: {alarm}");

    client
        .post(format!("{BASE_URL}/api/delete-price-alarm"))
        .json(&json!({ "alarmId": "9f8e7d6c-5b4a-3210-fedc-ba0987654321" }))
        .send()?;

    Ok(())
}
```
