import time
from fetch import get_cookies, decode_cookie
import secrets


def check_authentification(context,page):
    cookies = get_cookies()
    tr_secret = decode_cookie(cookies.get("tr_claims", ""))
    # print(json.dumps(tr_secret, indent=2, ensure_ascii=False))
    now = int(time.time())
    exp = tr_secret.get("exp", 0)

    time_left = exp - now

    if time_left < 100:
        page.reload()
        time.sleep(2)
        context.storage_state(path="auth.json")

    if max(0, time_left) == 0:
        print(" Les cookies ont expiré.")
        return False
    else:
        print(f" Authentification valide. Temps restant : {time_left} secondes")
        return True