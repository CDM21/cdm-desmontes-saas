import json
import os
import threading
import time
import httpx

from .db import SessionLocal
from .models import FiscalConfig, FiscalDocument, MarketplaceListing
from .crypto import decrypt_secret
from .services.marketplaces import refresh_listing

_started = False
_lock = threading.Lock()


def _focus_base(environment: str):
    return "https://api.focusnfe.com.br" if environment == "producao" else "https://homologacao.focusnfe.com.br"


def _normalize_fiscal_status(data: dict):
    raw = str(data.get("status") or data.get("status_sefaz") or "processando").lower()
    if raw in {"autorizado", "autorizada", "authorized", "approved"}:
        return "autorizada"
    if raw in {"cancelado", "cancelada", "canceled"}:
        return "cancelada"
    if raw in {"erro_autorizacao", "rejeitada", "rejeitado", "error", "failed", "denied"}:
        return "rejeitada"
    return "processando" if raw in {"processando_autorizacao", "processando", "processing", "queued", "pending"} else raw


def _refresh_fiscal(db, row: FiscalDocument):
    cfg = db.query(FiscalConfig).filter(FiscalConfig.company_id == row.company_id).first()
    if not cfg or not row.provider_ref:
        return
    enc = cfg.production_token_enc if cfg.environment == "producao" else cfg.homologation_token_enc
    token = decrypt_secret(enc)
    if not token:
        return
    with httpx.Client(timeout=35) as client:
        response = client.get(f"{_focus_base(cfg.environment)}/v2/nfe/{row.provider_ref}", auth=(token, ""))
    if response.status_code >= 400:
        return
    data = response.json() if "application/json" in response.headers.get("content-type", "") else {}
    row.status = _normalize_fiscal_status(data)
    row.access_key = str(data.get("chave_nfe") or data.get("chave") or data.get("access_key") or row.access_key or "")
    row.number = str(data.get("numero") or row.number or "")
    row.series = str(data.get("serie") or row.series or "")
    row.xml_url = str(data.get("caminho_xml_nota_fiscal") or data.get("url_xml") or row.xml_url or "")
    row.danfe_url = str(data.get("caminho_danfe") or data.get("url_danfe") or row.danfe_url or "")
    row.provider_response = json.dumps(data, ensure_ascii=False)[:20000]
    db.commit()


def _tick():
    db = SessionLocal()
    try:
        listings = db.query(MarketplaceListing).filter(
            MarketplaceListing.status.in_(["processing", "pending", "queued"])
        ).limit(100).all()
        for row in listings:
            try:
                refresh_listing(db, row)
            except Exception as exc:
                db.rollback()
                print("CDM integration scheduler marketplace warning:", row.id, str(exc)[:300])

        fiscal_docs = db.query(FiscalDocument).filter(
            FiscalDocument.status == "processando"
        ).limit(100).all()
        for row in fiscal_docs:
            try:
                _refresh_fiscal(db, row)
            except Exception as exc:
                db.rollback()
                print("CDM integration scheduler fiscal warning:", row.id, str(exc)[:300])
    finally:
        db.close()


def _loop():
    time.sleep(30)
    while True:
        try:
            _tick()
        except Exception as exc:
            print("CDM integration scheduler warning:", str(exc)[:500])
        time.sleep(max(60, int(os.getenv("INTEGRATION_SYNC_SECONDS", "180"))))


def start_integration_scheduler():
    global _started
    disabled = (os.getenv("INTEGRATION_SCHEDULER_DISABLED") or "").strip().lower() in {"1", "true", "yes", "on"}
    if disabled:
        print("CDM integration scheduler: disabled by environment.")
        return False
    with _lock:
        if _started:
            return True
        _started = True
        threading.Thread(target=_loop, name="cdm-integration-sync", daemon=True).start()
    print("CDM integration scheduler: active.")
    return True
