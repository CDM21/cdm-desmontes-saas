import os
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..admin import audit, platform_admin_emails, require_platform_admin
from ..db import engine, get_db
from ..deps import active_user, current_user, require_roles
from ..security import secret_key_status, TOKEN_HOURS
from ..crypto import encryption_key_status
from ..backup_service import offsite_config
from ..models import (
    AuditLog, Company, Dismantling, MarketplaceConnection, Product,
    Sale, SaleItem, Subscription, User, Vehicle, VehicleExpense,
)

router = APIRouter()

FOUNDER_LIMIT = 10
DEFAULT_MONTHLY_PRICE = 350.0
DEFAULT_IMPLEMENTATION_FEE = 1500.0


def _money_env(name: str, default: float) -> float:
    try:
        return round(float((os.getenv(name) or str(default)).replace(",", ".")), 2)
    except Exception:
        return default


def _ensure_v14_tables():
    statements = [
        """
        CREATE TABLE IF NOT EXISTS founder_program (
            company_id INTEGER PRIMARY KEY,
            slot INTEGER UNIQUE NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS setup_fee_ledger (
            company_id INTEGER PRIMARY KEY,
            amount FLOAT NOT NULL DEFAULT 0,
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            provider VARCHAR(60) NOT NULL DEFAULT 'manual',
            external_payment_id VARCHAR(180) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP NULL
        )
        """,
    ]
    try:
        with engine.begin() as conn:
            for sql in statements:
                conn.execute(text(sql))
    except Exception as exc:
        print("V14 schema warning:", exc)


_ensure_v14_tables()

@router.get("/ping")
def v14_ping():
    return {
        "ok": True,
        "version": "14.3.2",
        "founder_limit": FOUNDER_LIMIT,
        "monthly_price": _money_env("CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE),
        "implementation_fee": _money_env("CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE),
    }


def _platform_admin_company_ids(db: Session):
    emails = platform_admin_emails()
    if not emails:
        return set()
    rows = db.query(User.company_id, User.email).filter(User.email != None).all()
    return {
        int(company_id)
        for company_id, email in rows
        if (email or "").lower() in emails
    }


def _sync_founders(db: Session):
    """Persiste as 10 primeiras vagas para não mudar quem é fundador no futuro."""
    admin_company_ids = _platform_admin_company_ids(db)

    # Remove eventual empresa administrativa que tenha sido incluída por versão antiga.
    if admin_company_ids:
        db.execute(
            text("DELETE FROM founder_program WHERE company_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": list(admin_company_ids)},
        )
        db.commit()

    existing = db.execute(
        text("SELECT company_id, slot, assigned_at FROM founder_program ORDER BY slot ASC")
    ).mappings().all()
    used_companies = {int(r["company_id"]) for r in existing}
    used_slots = {int(r["slot"]) for r in existing}

    if len(existing) < FOUNDER_LIMIT:
        companies = db.query(Company).order_by(Company.created_at.asc(), Company.id.asc()).all()
        candidates = [
            c for c in companies
            if c.id not in admin_company_ids and c.id not in used_companies
        ]
        free_slots = [n for n in range(1, FOUNDER_LIMIT + 1) if n not in used_slots]
        for slot, company in zip(free_slots, candidates):
            db.execute(
                text(
                    "INSERT INTO founder_program (company_id, slot, assigned_at) "
                    "VALUES (:company_id,:slot,:assigned_at) ON CONFLICT DO NOTHING"
                ),
                {
                    "company_id": int(company.id),
                    "slot": int(slot),
                    "assigned_at": getattr(company, "created_at", None) or datetime.utcnow(),
                },
            )
        db.commit()

    rows = db.execute(
        text("SELECT company_id, slot, assigned_at FROM founder_program ORDER BY slot ASC")
    ).mappings().all()
    return [dict(r) for r in rows[:FOUNDER_LIMIT]]


def _founder_for_company(db: Session, company_id: int):
    for row in _sync_founders(db):
        if int(row["company_id"]) == int(company_id):
            return dict(row)
    return None


def _setup_fee(db: Session, company_id: int, founder: bool):
    amount = (
        0.0 if founder
        else _money_env("CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE)
    )
    row = db.execute(
        text(
            "SELECT company_id, amount, status, provider, external_payment_id, "
            "created_at, paid_at FROM setup_fee_ledger "
            "WHERE company_id=:company_id"
        ),
        {"company_id": company_id},
    ).mappings().first()
    if row:
        current = dict(row)
        if founder and str(current.get("status") or "") != "paid":
            db.execute(
                text(
                    "UPDATE setup_fee_ledger SET amount=0,status='waived' "
                    "WHERE company_id=:company_id"
                ),
                {"company_id": company_id},
            )
            db.commit()
            current["amount"] = 0.0
            current["status"] = "waived"
        return current

    status = "waived" if founder else "pending"
    db.execute(
        text(
            "INSERT INTO setup_fee_ledger "
            "(company_id, amount, status, provider, external_payment_id, created_at) "
            "VALUES (:company_id,:amount,:status,'manual','',:created_at)"
        ),
        {
            "company_id": company_id,
            "amount": amount,
            "status": status,
            "created_at": datetime.utcnow(),
        },
    )
    db.commit()
    row = db.execute(
        text(
            "SELECT company_id, amount, status, provider, external_payment_id, "
            "created_at, paid_at FROM setup_fee_ledger "
            "WHERE company_id=:company_id"
        ),
        {"company_id": company_id},
    ).mappings().first()
    return dict(row) if row else {"company_id": company_id, "amount": amount, "status": status}


def _billing_quote(db: Session, company_id: int):
    founder_row = _founder_for_company(db, company_id)
    founder = bool(founder_row)
    monthly = _money_env("CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE)
    fee = _setup_fee(db, company_id, founder)
    fee_status = str(fee.get("status") or "pending")
    implementation_due = (
        0.0 if fee_status in {"paid", "waived"}
        else round(float(fee.get("amount") or 0), 2)
    )
    return {
        "company_id": company_id,
        "founder": founder,
        "founder_slot": int(founder_row["slot"]) if founder_row else None,
        "founder_limit": FOUNDER_LIMIT,
        "monthly_price": monthly,
        "implementation_fee": round(float(fee.get("amount") or 0), 2),
        "implementation_fee_status": fee_status,
        "implementation_fee_due_now": implementation_due,
        "first_charge_total": round(monthly + implementation_due, 2),
        "recurring_charge": monthly,
        "currency": "BRL",
        "rule": (
            "Os 10 clientes fundadores pagam somente a mensalidade. "
            "A partir do 11º cliente, a implantação é cobrada uma única vez, "
            "além da mensalidade."
        ),
        "mercadopago_configured": bool((os.getenv("MP_ACCESS_TOKEN") or "").strip()),
        "mercadopago_webhook_signature_configured": bool(
            (os.getenv("MP_WEBHOOK_SECRET") or "").strip()
        ),
    }


@router.get("/billing/quote")
def billing_quote(db: Session = Depends(get_db), user=Depends(current_user)):
    return _billing_quote(db, user.company_id)


@router.get("/billing/checkout-plan")
def checkout_plan(db: Session = Depends(get_db), user=Depends(current_user)):
    quote = _billing_quote(db, user.company_id)
    steps = []
    if quote["implementation_fee_due_now"] > 0:
        steps.append({
            "kind": "one_time",
            "label": "Implantação CDM Desmontes",
            "amount": quote["implementation_fee_due_now"],
            "status": "ready_for_gateway",
        })
    steps.append({
        "kind": "recurring",
        "label": "Plano mensal CDM Desmontes",
        "amount": quote["monthly_price"],
        "frequency": "monthly",
        "status": "ready_for_gateway",
    })
    return {
        "quote": quote,
        "steps": steps,
        "ready_for_real_checkout": quote["mercadopago_configured"],
        "message": (
            "Estrutura de cobrança preparada. A criação dos pagamentos reais "
            "depende das credenciais do Mercado Pago no servidor."
        ),
    }


class SetupFeeStatusIn(BaseModel):
    status: str
    external_payment_id: str = ""
    provider: str = "manual"


@router.post("/admin/setup-fee/{company_id}")
def admin_setup_fee(
    company_id: int,
    data: SetupFeeStatusIn,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    require_platform_admin(user)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Empresa não encontrada")

    status = (data.status or "").strip().lower()
    if status not in {"pending", "paid", "waived"}:
        raise HTTPException(400, "Status inválido")

    quote = _billing_quote(db, company_id)
    amount = (
        0.0 if quote["founder"]
        else _money_env("CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE)
    )
    row = db.execute(
        text("SELECT company_id FROM setup_fee_ledger WHERE company_id=:company_id"),
        {"company_id": company_id},
    ).first()
    paid_at = datetime.utcnow() if status == "paid" else None
    payload = {
        "company_id": company_id,
        "amount": amount,
        "status": status,
        "provider": data.provider[:60],
        "external_payment_id": data.external_payment_id[:180],
        "paid_at": paid_at,
    }
    if row:
        db.execute(
            text(
                "UPDATE setup_fee_ledger SET amount=:amount,status=:status,"
                "provider=:provider,external_payment_id=:external_payment_id,"
                "paid_at=:paid_at WHERE company_id=:company_id"
            ),
            payload,
        )
    else:
        payload["created_at"] = datetime.utcnow()
        db.execute(
            text(
                "INSERT INTO setup_fee_ledger "
                "(company_id,amount,status,provider,external_payment_id,created_at,paid_at) "
                "VALUES (:company_id,:amount,:status,:provider,:external_payment_id,"
                ":created_at,:paid_at)"
            ),
            payload,
        )

    audit(
        db, user, "platform.setup_fee", "company", str(company_id),
        {"status": status, "amount": amount}, company_id=company_id,
    )
    db.commit()
    return {"ok": True, "quote": _billing_quote(db, company_id)}


@router.post("/admin/founders/sync")
def admin_sync_founders(db: Session = Depends(get_db), user=Depends(current_user)):
    require_platform_admin(user)
    rows = _sync_founders(db)
    audit(db, user, "platform.founders.sync", "platform", "", {"assigned": len(rows)})
    db.commit()
    return {
        "ok": True,
        "limit": FOUNDER_LIMIT,
        "assigned": len(rows),
        "founders": rows,
    }


@router.get("/admin/founders")
def admin_founders(db: Session = Depends(get_db), user=Depends(current_user)):
    require_platform_admin(user)
    rows = _sync_founders(db)
    companies = {c.id: c for c in db.query(Company).all()}
    founders = []
    for row in rows:
        company = companies.get(int(row["company_id"]))
        founders.append({
            "slot": int(row["slot"]),
            "company_id": int(row["company_id"]),
            "company_name": company.trade_name if company else "Empresa",
            "assigned_at": row.get("assigned_at"),
        })
    return {
        "limit": FOUNDER_LIMIT,
        "assigned": len(rows),
        "remaining": max(0, FOUNDER_LIMIT - len(rows)),
        "monthly_price": _money_env("CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE),
        "implementation_fee_after_founders": _money_env(
            "CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE
        ),
        "founders": founders,
    }


@router.get("/admin/billing-overview")
def admin_billing_overview(db: Session = Depends(get_db), user=Depends(current_user)):
    require_platform_admin(user)
    _sync_founders(db)
    companies = {int(c.id): c for c in db.query(Company).all()}
    rows = db.execute(
        text(
            "SELECT company_id, amount, status, provider, external_payment_id, paid_at "
            "FROM setup_fee_ledger ORDER BY company_id ASC"
        )
    ).mappings().all()
    items = []
    paid_total = 0.0
    counts = {"paid": 0, "pending": 0, "waived": 0}
    for raw in rows:
        row = dict(raw)
        status = str(row.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
        if status == "paid":
            paid_total += float(row.get("amount") or 0)
        company = companies.get(int(row["company_id"]))
        items.append({
            **row,
            "company_name": company.trade_name if company else f"Empresa #{row['company_id']}",
        })
    active_subscriptions = db.query(Subscription).filter(Subscription.status == "active").count()
    return {
        "implementation": {
            "paid": counts.get("paid", 0),
            "pending": counts.get("pending", 0),
            "waived": counts.get("waived", 0),
            "received_total": round(paid_total, 2),
            "standard_fee": _money_env("CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE),
        },
        "subscriptions": {
            "active": active_subscriptions,
            "monthly_price": _money_env("CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE),
            "projected_mrr": round(active_subscriptions * _money_env("CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE), 2),
        },
        "items": items,
    }


SMART_PARTS = [
    ("Motor completo", ["motor completo", "motor"], 100),
    ("Câmbio", ["cambio", "câmbio", "transmissao", "transmissão"], 98),
    ("Módulo de injeção / ECU", ["modulo", "módulo", "ecu", "central injecao", "central injeção"], 94),
    ("Kit airbag", ["airbag", "air bag"], 92),
    ("Compressor do ar-condicionado", ["compressor ar", "compressor do ar"], 88),
    ("Alternador", ["alternador"], 86),
    ("Motor de partida", ["motor partida", "arranque"], 84),
    ("Caixa de direção", ["caixa direcao", "caixa direção"], 82),
    ("Bomba de direção", ["bomba direcao", "bomba direção"], 80),
    ("Painel de instrumentos", ["painel instrumento", "painel de instrumento"], 78),
    ("Central multimídia / rádio", ["multimidia", "multimídia", "radio", "rádio"], 76),
    ("Faróis", ["farol"], 74),
    ("Lanternas", ["lanterna"], 72),
    ("Retrovisores", ["retrovisor"], 70),
    ("Portas", ["porta dianteira", "porta traseira", "porta"], 68),
    ("Capô", ["capo", "capô"], 66),
    ("Tampa traseira / porta-malas", ["tampa traseira", "porta malas", "porta-malas"], 64),
    ("Para-choques", ["parachoque", "para choque", "para-choque"], 62),
    ("Radiador", ["radiador"], 60),
    ("Condensador", ["condensador"], 58),
    ("Bancos", ["banco dianteiro", "banco traseiro", "banco"], 56),
    ("Rodas", ["roda", "rodas"], 54),
    ("Semi-eixos", ["semi eixo", "semieixo", "semi-eixo"], 52),
    ("Amortecedores / suspensão", ["amortecedor", "suspensao", "suspensão"], 50),
]


def _norm(value):
    value = str(value or "").lower()
    return value.translate(str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc"))


def _smart_dismantling_payload(db: Session, company_id: int, vehicle_id: int):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == company_id,
    ).first()
    if not vehicle:
        raise HTTPException(404, "Veículo não encontrado")

    vehicle_products = db.query(Product).filter(
        Product.company_id == company_id,
        Product.vehicle_id == vehicle_id,
    ).all()
    all_products = db.query(Product).filter(Product.company_id == company_id).all()

    cutoff = datetime.utcnow() - timedelta(days=365)
    sale_rows = (
        db.query(SaleItem, Sale)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(
            Sale.company_id == company_id,
            Sale.created_at >= cutoff,
            Sale.status.notin_(["canceled", "cancelled", "rejected"]),
        )
        .all()
    )
    sales_by_product = {}
    for item, sale in sale_rows:
        product_id = int(item.product_id or 0)
        info = sales_by_product.setdefault(product_id, {"qty": 0, "revenue": 0.0})
        info["qty"] += int(item.quantity or 0)
        info["revenue"] += float(item.unit_price or 0) * int(item.quantity or 0)

    current_text = [(_norm(p.name), p) for p in vehicle_products]
    catalog_text = [
        (_norm(" ".join([p.name or "", p.part_group or "", p.category or ""])), p)
        for p in all_products
    ]

    suggestions = []
    for title, keywords, base_score in SMART_PARTS:
        normalized_keywords = [_norm(k) for k in keywords]
        registered = [
            p for txt, p in current_text
            if any(k in txt for k in normalized_keywords)
        ]
        comparable = [
            p for txt, p in catalog_text
            if any(k in txt for k in normalized_keywords)
        ]
        sold_qty = 0
        sold_revenue = 0.0
        for product in comparable:
            stat = sales_by_product.get(product.id, {})
            sold_qty += int(stat.get("qty") or 0)
            sold_revenue += float(stat.get("revenue") or 0)

        average_sale_price = round(sold_revenue / sold_qty, 2) if sold_qty > 0 else 0.0
        stock_now = sum(max(0, int(p.stock or 0)) for p in registered)
        score = min(100, int(base_score + min(12, sold_qty * 2)))
        if registered:
            score = max(20, score - 35)

        suggestions.append({
            "title": title,
            "priority": score,
            "registered": bool(registered),
            "registered_count": len(registered),
            "stock_now": stock_now,
            "company_sales_12m": sold_qty,
            "company_revenue_12m": round(sold_revenue, 2),
            "average_sale_price": average_sale_price,
            "action": (
                "Já possui cadastro ligado a este veículo"
                if registered
                else "Conferir estado, fotografar e cadastrar"
            ),
        })

    suggestions.sort(key=lambda x: (x["registered"], -x["priority"]))

    dismantling = (
        db.query(Dismantling)
        .filter(
            Dismantling.company_id == company_id,
            Dismantling.vehicle_id == vehicle_id,
        )
        .order_by(Dismantling.id.desc())
        .first()
    )
    expenses = db.query(VehicleExpense).filter(
        VehicleExpense.company_id == company_id,
        VehicleExpense.vehicle_id == vehicle_id,
    ).all()
    total_invested = (
        float(vehicle.acquisition_value or 0)
        + float(vehicle.other_costs or 0)
        + sum(float(x.amount or 0) for x in expenses)
    )
    estimated_catalog_value = sum(
        max(0, int(p.stock or 0)) * float(p.price or 0)
        for p in vehicle_products
    )

    return {
        "vehicle": {
            "id": vehicle.id,
            "label": " ".join(
                str(x) for x in [vehicle.brand, vehicle.model, vehicle.year] if x
            ),
            "plate": vehicle.plate or "",
            "status": vehicle.status or "received",
        },
        "dismantling": {
            "status": dismantling.status if dismantling else "pending",
            "started_at": dismantling.started_at if dismantling else None,
            "finished_at": dismantling.finished_at if dismantling else None,
        },
        "summary": {
            "suggestions": len(suggestions),
            "already_registered": sum(1 for x in suggestions if x["registered"]),
            "pending_suggestions": sum(1 for x in suggestions if not x["registered"]),
            "vehicle_products": len(vehicle_products),
            "total_invested": round(total_invested, 2),
            "estimated_current_stock_value": round(estimated_catalog_value, 2),
        },
        "suggestions": suggestions,
        "generated_at": datetime.utcnow(),
        "mode": "inteligencia_local",
    }


@router.get("/vehicles/{vehicle_id}/smart-dismantling")
def smart_dismantling(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user=Depends(active_user),
):
    return _smart_dismantling_payload(db, user.company_id, vehicle_id)


class DismantlingStateIn(BaseModel):
    status: str
    notes: str = ""


@router.post("/vehicles/{vehicle_id}/dismantling-state")
def dismantling_state(
    vehicle_id: int,
    data: DismantlingStateIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("owner", "admin", "manager", "stock")),
):
    status = (data.status or "").strip().lower()
    if status not in {"pending", "in_progress", "completed", "finished"}:
        raise HTTPException(400, "Status de desmontagem inválido")

    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == user.company_id,
    ).first()
    if not vehicle:
        raise HTTPException(404, "Veículo não encontrado")

    row = (
        db.query(Dismantling)
        .filter(
            Dismantling.company_id == user.company_id,
            Dismantling.vehicle_id == vehicle_id,
        )
        .order_by(Dismantling.id.desc())
        .first()
    )
    if not row:
        row = Dismantling(
            company_id=user.company_id,
            vehicle_id=vehicle_id,
            status="pending",
        )
        db.add(row)

    row.status = status
    row.notes = (data.notes or row.notes or "")[:5000]
    if status == "in_progress" and not row.started_at:
        row.started_at = datetime.utcnow()
    if status in {"completed", "finished"}:
        row.finished_at = datetime.utcnow()
        vehicle.status = "available"
    elif status == "in_progress":
        vehicle.status = "dismantling"
    elif status == "pending":
        vehicle.status = "received"

    audit(
        db, user, "vehicle.dismantling.status", "vehicle", str(vehicle_id),
        {"status": status},
    )
    db.commit()
    return {
        "ok": True,
        "plan": _smart_dismantling_payload(db, user.company_id, vehicle_id),
    }


@router.get("/admin/platform-readiness")
def platform_readiness(
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    require_platform_admin(user)

    started = time.perf_counter()
    db.execute(text("SELECT 1"))
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    founders = _sync_founders(db)

    last_backup = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_([
            "backup.offsite.cron",
            "backup.offsite.success",
            "backup.download",
        ]))
        .order_by(AuditLog.id.desc())
        .first()
    )
    last_audit = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    active_subs = db.query(Subscription).filter(
        Subscription.status == "active"
    ).count()
    active_connections = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.active == True
    ).count()
    secret_status = secret_key_status()
    encryption_status = encryption_key_status()
    backup_cfg = offsite_config()
    external_cron = (
        (os.getenv("BACKUP_CRON_EXTERNAL") or "").strip().lower()
        in {"1","true","yes","on"}
    )
    bootstrap_enabled = (
        (os.getenv("ALLOW_BOOTSTRAP") or "").strip().lower()
        in {"1","true","yes","on"}
    )
    backup_age_hours = None
    if last_backup and last_backup.created_at:
        backup_age_hours = round(max(0,(datetime.utcnow()-last_backup.created_at).total_seconds()/3600),1)

    return {
        "ok": True,
        "checked_at": datetime.utcnow(),
        "database": {"online": True, "latency_ms": latency_ms},
        "security": {
            "platform_admin_configured": bool(platform_admin_emails()),
            "billing_webhook_secret": bool(
                (os.getenv("MP_WEBHOOK_SECRET") or "").strip()
            ),
            "app_encryption_key": encryption_status["configured"],
            "app_encryption_key_valid": encryption_status["valid"],
            "app_encryption_using_secret_fallback": encryption_status["using_secret_fallback"],
            "bootstrap_enabled": bootstrap_enabled,
            "bootstrap_disabled": not bootstrap_enabled,
            "cors_explicit": bool((os.getenv("CORS_ORIGINS") or "").strip()),
            "secret_key_configured": secret_status["configured"],
            "secret_key_strong": secret_status["strong"],
            "secret_key_using_default": secret_status["using_default"],
            "token_hours": TOKEN_HOURS,
            "password_policy": "10+ caracteres e 3 grupos de caracteres",
            "login_rate_limit": True,
            "ready": bool(
                secret_status["strong"]
                and platform_admin_emails()
                and encryption_status["configured"]
                and encryption_status["valid"]
                and not bootstrap_enabled
            ),
        },
        "backup": {
            "available": True,
            "format": "cdm-logical-backup-v2",
            "integrity": "sha256",
            "last_success_at": last_backup.created_at if last_backup else None,
            "last_action": last_backup.action if last_backup else None,
            "last_download_at": last_backup.created_at if last_backup else None,
            "last_download_by_user": last_backup.user_id if last_backup else None,
            "age_hours": backup_age_hours,
            "fresh_24h": bool(backup_age_hours is not None and backup_age_hours <= 24),
            "offsite_storage": bool(backup_cfg["configured"]),
            "automatic_enabled": bool(
                external_cron or backup_cfg["automatic_enabled"]
            ),
            "mode": (
                "render-cron"
                if external_cron
                else ("internal" if backup_cfg["automatic_enabled"] else "disabled")
            ),
            "interval_hours": backup_cfg["interval_hours"],
            "restore_drill_available": True,
            "note": "Backup R2 com verificação SHA-256 e teste isolado de restauração.",
        },
        "audit": {
            "enabled": True,
            "events": db.query(AuditLog).count(),
            "last_event_at": last_audit.created_at if last_audit else None,
        },
        "billing": {
            "mercadopago_configured": bool(
                (os.getenv("MP_ACCESS_TOKEN") or "").strip()
            ),
            "monthly_price": _money_env(
                "CDM_MONTHLY_PRICE", DEFAULT_MONTHLY_PRICE
            ),
            "implementation_fee": _money_env(
                "CDM_IMPLEMENTATION_FEE", DEFAULT_IMPLEMENTATION_FEE
            ),
            "active_subscriptions": active_subs,
        },
        "founders": {
            "limit": FOUNDER_LIMIT,
            "assigned": len(founders),
            "remaining": max(0, FOUNDER_LIMIT - len(founders)),
        },
        "integrations": {
            "active_marketplace_connections": active_connections,
            "mercadolivre_credentials_present": bool(
                (os.getenv("ML_CLIENT_ID") or "").strip()
                and (os.getenv("ML_CLIENT_SECRET") or "").strip()
            ),
            "shopee_credentials_present": bool(
                (os.getenv("SHOPEE_PARTNER_ID") or "").strip()
                and (os.getenv("SHOPEE_PARTNER_KEY") or "").strip()
            ),
            "olx_credentials_present": bool(
                (os.getenv("OLX_CLIENT_ID") or "").strip()
                and (os.getenv("OLX_CLIENT_SECRET") or "").strip()
            ),
            "openai_credentials_present": bool(
                (os.getenv("OPENAI_API_KEY") or "").strip()
            ),
        },
        "next_external_stage": [
            "Mercado Pago real", "Mercado Livre", "Shopee", "OLX", "Fiscal homologado"
        ],
    }

