import shutil
import socket
import subprocess
import time
from pathlib import Path

from src.fetch import decode_cookie, get_cookies


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except OSError:
            local_ip = "127.0.0.1"
    return local_ip


def test_firewall_status(port: int = 8000) -> bool:
    """Vérifie auprès de firewalld (Fedora) ou ufw (Ubuntu) si le port est autorisé."""

    if shutil.which("firewall-cmd"):
        cmd = ["sudo", "firewall-cmd", "--query-port", f"{port}/tcp"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0

    if shutil.which("ufw"):
        cmd = ["sudo", "ufw", "status"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return f"{port}/tcp" in result.stdout and "ALLOW" in result.stdout

    return True


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
