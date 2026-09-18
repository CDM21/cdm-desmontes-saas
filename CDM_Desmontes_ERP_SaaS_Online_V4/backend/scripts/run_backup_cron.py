import json
import os
import sys
import urllib.error
import urllib.request

URL = (os.getenv("CDM_BACKUP_CRON_URL") or "").strip()
TOKEN = (os.getenv("BACKUP_CRON_TOKEN") or "").strip()

if not URL:
    print("CDM backup cron: CDM_BACKUP_CRON_URL ausente.")
    sys.exit(2)
if not TOKEN:
    print("CDM backup cron: BACKUP_CRON_TOKEN ausente.")
    sys.exit(2)

req = urllib.request.Request(
    URL,
    data=b"",
    method="POST",
    headers={
        "Accept": "application/json",
        "X-CDM-Backup-Token": TOKEN,
        "User-Agent": "cdm-render-cron/1.0",
    },
)

try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw else {}
        if resp.status < 200 or resp.status >= 300:
            raise RuntimeError(f"HTTP {resp.status}: {data}")
        print(
            "CDM backup cron OK:",
            data.get("key") or data.get("backup_id") or "backup enviado",
        )
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    print(f"CDM backup cron HTTP {exc.code}: {body[:1500]}")
    sys.exit(1)
except Exception as exc:
    print("CDM backup cron erro:", exc)
    sys.exit(1)
