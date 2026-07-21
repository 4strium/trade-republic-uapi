import base64
import json

import httpx
import websockets
import secrets

def generate_traceparent() -> str:
  trace_id = secrets.token_hex(16)
  parent_id = secrets.token_hex(8)
  return f"00-{trace_id}-{parent_id}-01"

def get_cookies():
    with open("auth.json", "r") as f:
        auth_data = json.load(f)
    return {cookie["name"]: cookie["value"] for cookie in auth_data.get("cookies", [])}


def call_tr_rest_api(endpoint: str):

    cookies = get_cookies()
    aws_waf_token = cookies.get("aws-waf-token", "")

    # 3. Headers mimant parfaitement le navigateur
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr",
        "Origin": "https://app.traderepublic.com",
        "Referer": "https://app.traderepublic.com/",
        "x-tr-platform": "web-pro",
        "x-aws-waf-token": aws_waf_token,
    }

    url = f"https://api.traderepublic.com/{endpoint}"

    # 4. Requête HTTP REST
    with httpx.Client(cookies=cookies, headers=headers) as client:
        response = client.get(url)

        if response.status_code == 200:
            print(" Réponse API REST reçue avec succès ! ")
            return response.json()
        else:
            print(f" Échec ({response.status_code}) : {response.text}")
            return None

async def call_tr_ws_api(command: dict, id: int):
    uri = "wss://api.traderepublic.com/"

    cookies = get_cookies()
    aws_waf_token = cookies.get("aws-waf-token", "")

    cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])

    headers = {
        "Cookie": cookie_header,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr",
        "Origin": "https://app.traderepublic.com",
        "Referer": "https://app.traderepublic.com/",
        "x-tr-platform": "web",
        "x-aws-waf-token": aws_waf_token,
    }

    async with websockets.connect(uri, additional_headers=headers, user_agent_header="Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0") as ws:
        # Init connection :
        connect_payload = {
                    "locale": "fr",
                    "platformId": "webtrading",
                    "platformVersion": "firefox - 152.0.0",
                    "clientId": "app.traderepublic.com",
                    "clientVersion": "2.2630.4",
                    "__headers": {
                        "traceparent": generate_traceparent()
                    }
                }

        connect_cmd = f"connect 34 {json.dumps(connect_payload, separators=(',', ':'))}"
        await ws.send(connect_cmd)

        async for message in ws :
          if message == "connected":
            break

        sub_command = f"sub {id} {json.dumps(command, separators=(',', ':'))}"
        await ws.send(sub_command)

        async for message in ws :
            parts = message.split(" ", 2)
            if len(parts) < 3 :
              continue

            msg_id, msg_type, payload = parts[0], parts[1], parts[2]

            if msg_id == str(id) and msg_type in ["A", "D"]:

                # Une fois la donnée reçue, on désabonne et on quitte la boucle
                await ws.send(f"unsub {id}")

                return json.loads(payload)
                break


def decode_cookie(cookie):
    padded = cookie + "=" * ((4 - len(cookie) % 4) % 4)
    decoded = base64.b64decode(padded).decode("utf-8")
    return json.loads(decoded)
