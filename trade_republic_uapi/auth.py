import socket
import time

from trade_republic_uapi.fetch import decode_cookie, get_cookies
from trade_republic_uapi.paths import auth_path


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
    tr_claims = cookies.get("tr_claims", "")
    if not tr_claims:
        return False

    tr_secret = decode_cookie(tr_claims)
    now = int(time.time())
    exp = tr_secret.get("exp", 0)

    time_left = exp - now

    if time_left < 100:
        page.reload()
        time.sleep(2)
        context.storage_state(path=auth_path)

    return max(0, time_left) != 0
