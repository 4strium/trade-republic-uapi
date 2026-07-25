import json
import sys
from pathlib import Path

import questionary
from prompt_toolkit.shortcuts import yes_no_dialog
from prompt_toolkit.styles import Style

from src.auth import test_firewall_status


def save_preferences(user_agreement: bool, jurisdiction: str, api_port: int):
    path = Path("data/preferences.json")
    with path.open("w") as f:
        json.dump(
            {
                "user_agreement": user_agreement,
                "jurisdiction": jurisdiction,
                "api_port": api_port,
            },
            f,
            indent=4,
            ensure_ascii=False,
        )


def load_preferences() -> dict:
    path = Path("data/preferences.json")
    if not path.exists():
        return {}
    with path.open("r") as f:
        return json.load(f)


def check_preferences() -> bool:
    if Path("data/preferences.json").exists():
        data = load_preferences()
        port = data.get("api_port")

        if (
            data.get("user_agreement") is True
            and data.get("jurisdiction") is not None
            and port is not None
            and test_firewall_status(port)
        ):
            return True
    return False


def ask_preferences(console):
    user_agreement_style = Style.from_dict(
        {
            # Fond et texte du dialogue
            "dialog": "bg:#7aa2f7",
            "dialog frame.label": "fg:#1a1a2e bold",
            "dialog.body": "fg:#1a1a2e",
            # 1. BOUTONS INACTIFS
            "button": "bg:#1a1a2e",
            "button.text": "fg:#888888",
            "button.arrow": "fg:#1a1a2e",  # Cache les flèches inactives
            # 2. BOUTON SÉLECTIONNÉ (Ciblage des éléments texte/flèches internes)
            "button.focused": "bg:#0f3460",
            "button.focused button.text": "fg:#ffffff bold",
            "button.focused button.arrow": "fg:#7aa2f7 bold",
        }
    )

    user_agreement = yes_no_dialog(
        title="User Agreement",
        text="""
            Setting up and using the Trade Republic UAPI requires an understanding of the associated risks.
            Since the server's IP address is public, anyone could gain TOTAL control over your bank accounts.
            It is imperative to use a private server (I recommend using tools such as Tailscale).\n
            Likewise, ensure you do not grant uncontrolled access to agents such as OpenClaw or Hermes.\n
            The devs of this project and Trade Republic are not responsible for any security breaches or unauthorized access.\n
            Are you certain of your network's security, and do you wish to proceed?
      """,
        style=user_agreement_style,
    ).run()
    if not user_agreement:
        sys.exit()

    console.print(
        "[bold #7aa2f7]☑️  The user has been made aware of the potential risks.\n[/bold #7aa2f7]"
    )

    jurisdiction = questionary.select(
        "Select your jurisdiction 🌍 (used for tax calculation and regulations)",
        choices=[
            "Austria (AT)",
            "Belgium (BE)",
            "Estonia (EE)",
            "Finland (FI)",
            "France (FR)",
            "Germany (DE)",
            "Greece (GR)",
            "Ireland (IE)",
            "Italy (IT)",
            "Latvia (LV)",
            "Lithuania (LT)",
            "Luxembourg (LU)",
            "Netherlands (NL)",
            "Portugal (PT)",
            "Slovakia (SK)",
            "Slovenia (SI)",
            "Spain (ES)",
        ],
        style=questionary.Style(
            [
                ("selected", "fg:#7aa2f7 bold"),
                ("pointer", "fg:#7aa2f7 bold"),
            ]
        ),
    ).ask()

    api_port_str = questionary.text(
        "On which port of your server do you want to make the API available?",
        validate=lambda val: val.isdigit() or "Please enter a valid integer.",
        default="8000",
    ).ask()

    api_port = int(api_port_str)

    if not test_firewall_status(api_port):
        console.print(
            f"[bold red]❌ Port {api_port} is blocked by the firewall. Please make sure the port is available and try again.[/bold red]"
        )
        sys.exit()

    save_preferences(user_agreement, jurisdiction.split("(")[1].strip(")"), api_port)
