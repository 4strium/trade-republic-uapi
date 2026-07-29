import socket
import time
from pathlib import Path

from trade_republic_uapi.fetch import decode_cookie, get_cookies


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except OSError:
            local_ip = "127.0.0.1"
    return local_ip


def check_authentification(context, page):
    cookies = get_cookies()
    tr_secret = decode_cookie(cookies.get("tr_claims", ""))
    now = int(time.time())
    exp = tr_secret.get("exp", 0)

    time_left = exp - now

    if time_left < 100:
        page.reload()
        time.sleep(2)
        context.storage_state(path=Path("data/auth.json"))

    return max(0, time_left) != 0
