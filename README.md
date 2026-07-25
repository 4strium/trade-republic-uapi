# trade-republic-uapi
Lightweight & Fast unofficial REST API for Trade Republic

## Installing dependencies
```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
```

## Build command
```bash
  pyinstaller --onefile --clean --name=traderep-uapi --add-data ".venv/lib/python3.14/site-packages/playwright/driver:playwright/driver" main.py
```