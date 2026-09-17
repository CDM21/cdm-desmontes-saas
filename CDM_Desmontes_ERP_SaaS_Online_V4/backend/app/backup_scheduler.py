import json
import threading
import time

from .backup_service import offsite_config, upload_offsite
from .db import SessionLocal
from .models import AuditLog

_started = False
_lock = threading.Lock()


def _record(action, details):
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                company_id=None,
                user_id=None,
                action=action,
                entity="database",
                entity_id="",
                details_json=json.dumps(details, ensure_ascii=False, default=str)[:8000],
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _loop():
    # Dá tempo para o serviço terminar o startup antes do primeiro backup.
    time.sleep(120)
    while True:
        cfg = offsite_config()
        if cfg["configured"] and cfg["automatic_enabled"]:
            try:
                result = upload_offsite()
                _record(
                    "backup.offsite.automatic",
                    {
                        "backup_id": result["backup_id"],
                        "sha256": result["sha256"],
                        "bytes": result["bytes"],
                        "key": result["key"],
                    },
                )
                print("CDM automatic offsite backup OK:", result["key"])
            except Exception as exc:
                _record("backup.offsite.error", {"error": str(exc)[:1000]})
                print("CDM automatic offsite backup warning:", exc)

        interval = max(1, int(cfg.get("interval_hours", 24))) * 3600
        time.sleep(interval)


def start_backup_scheduler():
    global _started
    cfg = offsite_config()
    if not cfg["configured"]:
        print("CDM offsite backup: aguardando credenciais S3/R2.")
        return False
    with _lock:
        if _started:
            return True
        _started = True
        threading.Thread(
            target=_loop,
            name="cdm-offsite-backup",
            daemon=True,
        ).start()
    print(
        "CDM offsite backup: scheduler ativo a cada",
        cfg["interval_hours"],
        "hora(s).",
    )
    return True
