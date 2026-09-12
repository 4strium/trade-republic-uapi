import random
import socket
import time
from typing import cast

from playwright.sync_api import BrowserContext, Page
from playwright.sync_api import Error as PlaywrightError

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


def simulate_human(page: Page, duration: int) -> None:
    """Simule une activité humaine pendant environ 'duration' secondes."""
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            viewport = page.viewport_size
            width = viewport["width"] if viewport else 1280
            height = viewport["height"] if viewport else 720

            target_x = random.randint(100, width - 100)
            target_y = random.randint(100, height - 100)

            page.mouse.move(target_x, target_y, steps=random.randint(10, 20))

            sleep_time = random.uniform(2, 5)
            time.sleep(sleep_time)
            
    except PlaywrightError:
        pass

def check_authentification(context: BrowserContext):
    cookies = get_cookies()
    tr_claims = cookies.get("tr_claims", "")
    if not tr_claims:
        return False

    tr_secret = decode_cookie(tr_claims)
    now = int(time.time())
    exp = cast(int, tr_secret.get("exp", 0))

    time_left = exp - now

    print(f"Time left: {time_left}s ", flush=True)

    if time_left < 100:
        _ = context.storage_state(path=auth_path)

    return max(0, time_left) != 0
