import re
import threading
import time

import qrcode
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from api_server import start_api_server
from auth import check_authentification


def extract_qr_data(container, page):
    """Extrait l'URL/token depuis l'aria-label du QR code."""
    aria_label = container.get_attribute("aria-label") or ""
    match = re.search(r"(https?://\S+)", aria_label)
    data = match.group(1) if match else None

    if not data:
        raw = page.evaluate(
            """() => {
                const el = document.querySelector(".qrCode");
                return el ? el.getAttribute("aria-label") : null;
            }"""
        )
        if raw:
            m = re.search(r"(https?://\S+)", raw)
            data = m.group(1) if m else None

    return data, aria_label


def print_qr(data):
    if data.startswith("https://traderepublic.com/web-login/challenge?"):
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make()
        qr.print_ascii(invert=True)
        print("\n" + "=" * 50 + "\n")


def keep_alive(page, context):
    while True:
        try:
            if check_authentification(context, page):
                time.sleep(60)
            else:
                print("Authentification perdue.")
                context.close()
                return
        except (ConnectionError, TimeoutError) as e:
            print(f"Connexion avec Trade Republic perdue. Erreur: {e}")
            break


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = context.new_page()

        print("Navigation vers la page de connexion...")
        page.goto("https://app.traderepublic.com/login")

        initial_url = page.url
        qr_container_selector = ".qrCode"

        print("Attente du QR Code...")
        try:
            qr_container = page.wait_for_selector(qr_container_selector, timeout=20000)

            last_label = None
            poll_interval = 1.0  # secondes entre chaque vérification
            max_watch_time = 60  # durée max de surveillance du QR (avant validation)
            start_time = time.time()

            while time.time() - start_time < max_watch_time:
                data, current_label = extract_qr_data(qr_container, page)

                if not data or len(data) < 5:
                    print("Échec de l'extraction automatique du token.")
                    context.close()
                    return

                # Regénère l'affichage uniquement si l'aria-label a changé
                if current_label != last_label:
                    print_qr(data)
                    last_label = current_label
                    print_qr(data)
                    last_label = current_label

                if page.url != initial_url:
                    print("Connexion réussie !")
                    context.storage_state(path="auth.json")
                    api_thread = threading.Thread(target=start_api_server)
                    api_thread.start()

                    keep_alive(page, context)

                time.sleep(poll_interval)

        except PlaywrightTimeoutError:
            print("Délai dépassé : le QR code n'est pas apparu dans les temps.")
            context.close()
            return
        except (PlaywrightError, ValueError, TypeError) as e:
            print(f"Erreur lors de la capture ou du décodage : {e}")
            context.close()
            return

        context.close()


if __name__ == "__main__":
    run()
