import argparse
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import qrcode
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from trade_republic_uapi.api_server import start_api_server
from trade_republic_uapi.auth import check_authentification, get_local_ip
from trade_republic_uapi.preferences import (
    ask_preferences,
    check_preferences,
    load_preferences,
)

APP_LOGO = """
████████ ██████   █████  ██████  ███████     ██████  ███████ ██████  ██    ██ ██████  ██      ██  ██████     ██    ██  █████  ██████  ██
   ██    ██   ██ ██   ██ ██   ██ ██          ██   ██ ██      ██   ██ ██    ██ ██   ██ ██      ██ ██          ██    ██ ██   ██ ██   ██ ██
   ██    ██████  ███████ ██   ██ █████       ██████  █████   ██████  ██    ██ ██████  ██      ██ ██          ██    ██ ███████ ██████  ██
   ██    ██   ██ ██   ██ ██   ██ ██          ██   ██ ██      ██      ██    ██ ██   ██ ██      ██ ██          ██    ██ ██   ██ ██      ██
   ██    ██   ██ ██   ██ ██████  ███████     ██   ██ ███████ ██       ██████  ██████  ███████ ██  ██████      ██████  ██   ██ ██      ██
"""

console = Console()
auth_path = Path("data/auth.json")
server_log_path = Path("data/server.log")
server_pid_path = Path("data/server.pid")


def ensure_chromium_installed() -> None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as e:
        msg = str(e).lower()
        if "executable doesn't exist" not in msg and "browser" not in msg:
            raise

        console.print(
            "[bold yellow]⚠️ Chromium is missing. Installing Playwright Chromium now...[/bold yellow]"
        )
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            console.print(
                Panel(
                    "[bold white]Failed to install Chromium automatically.[/bold white]\n"
                    "[dim]Please run: python -m playwright install chromium[/dim]",
                    title="[bold white on red] ERROR [/bold white on red]",
                    border_style="red",
                    expand=False,
                )
            )
            sys.exit(1)


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
        console.print("\n[bold yellow]⚠️  New QR Code available\n[/bold yellow]")
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make()
        qr.print_ascii(invert=True)
        console.print(Rule(style="#7aa2f7"))


def keep_alive(page, context):
    while True:
        try:
            if check_authentification(context, page):
                time.sleep(60)
            else:
                console.print(
                    Panel(
                        "[bold white]Authentication lost.[/bold white]\n"
                        "[dim]Please try again later.[/dim]",
                        title="[bold white on red] ERROR [/bold white on red]",
                        border_style="red",
                        expand=False,
                    )
                )
                context.close()
                return
        except (ConnectionError, TimeoutError) as e:
            console.print(
                Panel(
                    f"Connection with Trade Republic lost. Error: {e}\n"
                    "[dim]Please try again later.[/dim]",
                    title="[bold white on red] ERROR [/bold white on red]",
                    border_style="red",
                    expand=False,
                )
            )
            break


def get_launch_command() -> str:
    """Reconstruit la commande utilisée pour lancer ce CLI, afin que les
    messages affichés (ex: commande d'arrêt) correspondent réellement à la
    façon dont l'utilisateur a lancé le programme.
    """
    if Path(sys.argv[0]).name == "cli.py":
        return f"{sys.executable} -m trade_republic_uapi.cli"
    return "traderep-uapi"


def stop_background_server():
    if not server_pid_path.exists():
        console.print(
            "[bold yellow]⚠️ No running background server found (no PID file).[/bold yellow]"
        )
        return

    pid = int(server_pid_path.read_text().strip())

    try:
        # start_new_session=True met le process dans son propre groupe :
        # on tue tout le groupe (process principal + thread API/Playwright).
        os.killpg(pid, signal.SIGTERM)
        console.print(f"[bold #7aa2f7]🛑 Server (PID {pid}) stopped.[/bold #7aa2f7]")
    except ProcessLookupError:
        console.print(
            "[bold yellow]⚠️  Server was not running (stale PID file removed).[/bold yellow]"
        )
    finally:
        server_pid_path.unlink(missing_ok=True)


def run_background_server(port: int):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            storage_state=auth_path,
        )
        page = context.new_page()
        page.goto("https://app.traderepublic.com/")

        api_thread = threading.Thread(
            target=start_api_server, args=(port,), daemon=True
        )
        api_thread.start()

        keep_alive(page, context)


def main():
    ensure_chromium_installed()
    console.print(f"[bold #7aa2f7]{APP_LOGO}[/bold #7aa2f7]")
    console.print(
        "[italic white]Trade Republic UAPI is [bold]NOT[/bold] affiliated with Trade Republic Bank GmbH.\n[/italic white]"
    )

    data_folder = Path("data")
    data_folder.mkdir(parents=True, exist_ok=True)

    time.sleep(2)

    if not check_preferences():
        console.print(
            "[bold red]👤 No user preferences found. You will have to answer a few questions.\n[/bold red]"
        )

        time.sleep(2)
        ask_preferences(console)
        console.print("\n")

    console.print(
        Panel(
            """
            [italic white]The authentication process will now take place.[/italic white]
            [white]It is very simple: [bold]pick up your smartphone, scan the QR code that will appear below, and confirm the connection in your app.[/bold][/white]
            [white]Once authentication is validated, the gateway will start automatically.
            It will ensure the connection is maintained continuously in the background (as long as you do not shut down your server). \n
            Several login QR codes will be provided by the official Trade Republic server. [bold]As soon as a QR code is generated, it is valid for 2 minutes.[/bold][/white]
            """,
            title="[bold black on #7aa2f7] AUTHENTIFICATION PROCESS [/bold black on #7aa2f7]",
            border_style="#7aa2f7",
            expand=False,
        )
    )

    time.sleep(10)
    auth_wait = 5
    console.print("")
    while auth_wait > 0:
        console.print(
            f"[bold #7aa2f7]Authentification starting in {auth_wait} seconds...[/bold #7aa2f7]"
        )
        auth_wait -= 1
        time.sleep(1)
    console.print("")

    with sync_playwright() as p:
        with console.status(
            "[bold yellow]Authentication with Trade Republic server...[/bold yellow]",
            spinner="dots",
            spinner_style="yellow",
        ):
            browser = p.chromium.launch(headless=True)

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            page = context.new_page()

            page.goto("https://app.traderepublic.com/login")

            initial_url = page.url
            qr_container_selector = ".qrCode"

        try:
            qr_container = page.wait_for_selector(qr_container_selector, timeout=20000)

            last_label = None
            poll_interval = 1.0  # secondes entre chaque vérification
            max_watch_time = 60  # durée max de surveillance du QR (avant validation)
            start_time = time.time()

            while time.time() - start_time < max_watch_time:
                data, current_label = extract_qr_data(qr_container, page)

                if not data or len(data) < 5:
                    console.print(
                        Panel(
                            "[bold white]Automatic token extraction failed.[/bold white]\n"
                            "[dim]Please try again later.[/dim]",
                            title="[bold white on red] ERROR [/bold white on red]",
                            border_style="red",
                            expand=False,
                        )
                    )
                    context.close()
                    return

                # Regénère l'affichage uniquement si l'aria-label a changé
                if current_label != last_label:
                    print_qr(data)
                    last_label = current_label

                if page.url != initial_url:
                    context.storage_state(path=auth_path)
                    console.print(
                        "[bold #7aa2f7]\n🎉 Authentification successful 🎉[/bold #7aa2f7]"
                    )

                    port = load_preferences().get("api_port")

                    local_ip = get_local_ip()
                    console.print(
                        Panel.fit(
                            "[bold #7aa2f7]🚀 API Gateway server is running in background![/bold #7aa2f7]\n\n"
                            f"• [bold white]Local URL:[/bold white]    [link=http://127.0.0.1:{port}]http://127.0.0.1:{port}[/link]\n"
                            f"• [bold white]Network URL:[/bold white] [link=http://{local_ip}:{port}]http://{local_ip}:{port}[/link]\n\n"
                            f"[white][bold red][code]{get_launch_command()} --stop[/code][/bold red] to stop the server.[/white]",
                            border_style="#7aa2f7",
                            padding=(1, 2),
                        )
                    )

                    time.sleep(2)
                    console.print(
                        f'[bold #7aa2f7]\n😉 Typing [code]curl -s -X GET "http://127.0.0.1:{port}/api/personal-details"[/code] is a good way to test the API.[/bold #7aa2f7]'
                    )
                    console.print(
                        f"[bold #7aa2f7]\n📚 All endpoints are documented at [link=http://{local_ip}:{port}/docs]http://{local_ip}:{port}/docs[/link].\n[/bold #7aa2f7]"
                    )

                    with open(server_log_path, "a") as logfile:
                        process = subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "trade_republic_uapi.cli",
                                "--background",
                                "--port",
                                str(port),
                            ],
                            stdout=logfile,
                            stderr=logfile,
                            stdin=subprocess.DEVNULL,
                            start_new_session=True,
                        )
                        server_pid_path.write_text(str(process.pid))

                    sys.exit(0)

                time.sleep(poll_interval)

        except PlaywrightTimeoutError:
            console.print(
                Panel(
                    "[bold white]Time limit exceeded: the QR code did not appear in time.[/bold white]\n"
                    "[dim]Please try again later.[/dim]",
                    title="[bold white on red] ERROR [/bold white on red]",
                    border_style="red",
                    expand=False,
                )
            )
            context.close()
            return
        except (PlaywrightError, ValueError, TypeError) as e:
            console.print(
                Panel(
                    f"[bold white]Error during capture or decoding: {e}[/bold white]\n"
                    "[dim]Please try again later.[/dim]",
                    title="[bold white on red] ERROR [/bold white on red]",
                    border_style="red",
                    expand=False,
                )
            )
            context.close()
            return

        context.close()


def run():
    ensure_chromium_installed()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--background",
        action="store_true",
        help="Internal option for background mode",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Listening port for the API"
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the background server started previously",
    )
    args = parser.parse_args()
    if args.stop:
        stop_background_server()
    elif "--background" in sys.argv:
        run_background_server(args.port)
    else:
        main()


if __name__ == "__main__":
    run()
