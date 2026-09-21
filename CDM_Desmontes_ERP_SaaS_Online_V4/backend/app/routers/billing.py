import os
import hashlib
import hmac
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..admin import require_platform_admin
from ..db import get_db
from ..deps import current_user
from ..models import Company, Subscription
from ..subscriptions import subscription_is_active
from .platform_v14 import _billing_quote

router = APIRouter()


def _public_url():
    return (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("FRONTEND_URL")
        or "http://localhost:5173"
    ).rstrip("/")


def _mp_token():
    return os.getenv("MP_ACCESS_TOKEN", "").strip()


def _mp_headers():
    token = _mp_token()
    if not token:
        raise RuntimeError("Mercado Pago ainda não foi configurado no servidor")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _monthly_price():
    try:
        return float(os.getenv("CDM_MONTHLY_PRICE", "350").replace(",", "."))
    except Exception:
        return 350.0


def _mp_get(subscription_id: str):
    with httpx.Client(timeout=30) as c:
        r = c.get(
            f"https://api.mercadopago.com/preapproval/{subscription_id}",
            headers=_mp_headers(),
        )
    if r.status_code >= 400:
        raise RuntimeError(
            f"Mercado Pago: não foi possível consultar a assinatura ({r.status_code})"
        )
    return r.json()


def _mp_get_payment(payment_id: str):
    with httpx.Client(timeout=30) as c:
        r = c.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers=_mp_headers(),
        )
    if r.status_code >= 400:
        raise RuntimeError(
            f"Mercado Pago: não foi possível consultar o pagamento ({r.status_code})"
        )
    return r.json()


def _apply_mp_status(db: Session, data: dict):
    ref = str(data.get("external_reference") or "")
    if not ref.startswith("cdm_company_"):
        return None
    try:
        company_id = int(ref.rsplit("_", 1)[-1])
    except Exception:
        return None
    company = db.get(Company, company_id)
    if not company:
        return None
    sub = db.query(Subscription).filter(Subscription.company_id == company_id).first()
    if not sub:
        sub = Subscription(company_id=company_id)
        db.add(sub)
    raw = str(data.get("status") or "pending")
    mapped = {
        "authorized": "active",
        "paused": "past_due",
        "cancelled": "canceled",
        "canceled": "canceled",
        "pending": "pending",
    }.get(raw, raw)
    sub.status = mapped
    sub.plan = "mensal-350"
    sub.provider = "mercadopago"
    sub.external_subscription_id = str(
        data.get("id") or sub.external_subscription_id or ""
    )
    sub.auto_renew = mapped not in {"canceled", "inactive"}
    if mapped == "active":
        sub.expires_at = datetime.utcnow() + timedelta(days=35)
    elif mapped in {"canceled", "inactive"}:
        sub.expires_at = datetime.utcnow()
    db.commit()
    db.refresh(sub)
    return sub


def _apply_setup_payment(db: Session, data: dict):
    """Atualiza a implantação somente a partir de um pagamento consultado no MP."""
    ref = str(data.get("external_reference") or "")
    if not ref.startswith("cdm_setup_company_"):
        return None
    try:
        company_id = int(ref.rsplit("_", 1)[-1])
    except Exception:
        return None
    if not db.get(Company, company_id):
        return None

    payment_id = str(data.get("id") or "")
    raw_status = str(data.get("status") or "pending").lower()
    approved = raw_status == "approved"
    status = "paid" if approved else "pending"
    paid_at = datetime.utcnow() if approved else None

    row = db.execute(
        text("SELECT company_id FROM setup_fee_ledger WHERE company_id=:company_id"),
        {"company_id": company_id},
    ).first()
    amount = float(data.get("transaction_amount") or 0)
    if row:
        db.execute(
            text(
                "UPDATE setup_fee_ledger SET "
                "status=:status, provider='mercadopago', "
                "external_payment_id=:payment_id, "
                "paid_at=CASE WHEN :status='paid' THEN :paid_at ELSE paid_at END "
                "WHERE company_id=:company_id"
            ),
            {
                "status": status,
                "payment_id": payment_id,
                "paid_at": paid_at,
                "company_id": company_id,
            },
        )
    else:
        db.execute(
            text(
                "INSERT INTO setup_fee_ledger "
                "(company_id, amount, status, provider, external_payment_id, created_at, paid_at) "
                "VALUES (:company_id,:amount,:status,'mercadopago',:payment_id,:created_at,:paid_at)"
            ),
            {
                "company_id": company_id,
                "amount": amount,
                "status": status,
                "payment_id": payment_id,
                "created_at": datetime.utcnow(),
                "paid_at": paid_at,
            },
        )
    db.commit()
    return {"company_id": company_id, "status": status, "payment_id": payment_id}


def _sync_setup_fee_from_mp(db: Session, company_id: int):
    """Procura no Mercado Pago um pagamento aprovado da implantação.

    Isso deixa o fluxo resiliente mesmo se o webhook atrasar.
    """
    if not _mp_token():
        return None
    ref = f"cdm_setup_company_{company_id}"
    try:
        with httpx.Client(timeout=30) as c:
            r = c.get(
                "https://api.mercadopago.com/v1/payments/search",
                params={
                    "external_reference": ref,
                    "sort": "date_created",
                    "criteria": "desc",
                    "limit": 20,
                },
                headers=_mp_headers(),
            )
        if r.status_code >= 400:
            return None
        results = (r.json() or {}).get("results") or []
        approved = next(
            (x for x in results if str(x.get("status") or "").lower() == "approved"),
            None,
        )
        candidate = approved or (results[0] if results else None)
        return _apply_setup_payment(db, candidate) if candidate else None
    except Exception:
        return None


def _setup_checkout(company_id: int, payer_email: str, amount: float):
    base = _public_url()
    payload = {
        "items": [
            {
                "id": "cdm-implantacao",
                "title": "Implantação CDM Desmontes",
                "description": "Implantação inicial da plataforma CDM Desmontes",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(amount),
            }
        ],
        "payer": {"email": payer_email},
        "external_reference": f"cdm_setup_company_{company_id}",
        "back_urls": {
            "success": f"{base}/?billing=return&stage=implementation&result=success",
            "pending": f"{base}/?billing=return&stage=implementation&result=pending",
            "failure": f"{base}/?billing=return&stage=implementation&result=failure",
        },
        "auto_return": "approved",
        "notification_url": f"{base}/api/billing/mercadopago/webhook",
    }
    with httpx.Client(timeout=30) as c:
        r = c.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=payload,
            headers=_mp_headers(),
        )
    if r.status_code >= 400:
        try:
            detail = r.json().get("message") or r.text[:500]
        except Exception:
            detail = r.text[:500]
        raise RuntimeError(f"Mercado Pago: {detail}")
    data = r.json()
    return {
        "checkout_url": data.get("init_point"),
        "preference_id": data.get("id"),
        "kind": "implementation",
        "price": amount,
    }


def _subscription_checkout(db: Session, user, company: Company, payer_email: str):
    payload = {
        "reason": "CDM Desmontes - Plano mensal",
        "external_reference": f"cdm_company_{user.company_id}",
        "payer_email": payer_email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": _monthly_price(),
            "currency_id": "BRL",
        },
        "back_url": f"{_public_url()}/?billing=return&stage=subscription",
    }
    with httpx.Client(timeout=30) as c:
        r = c.post(
            "https://api.mercadopago.com/preapproval",
            json=payload,
            headers=_mp_headers(),
        )
    if r.status_code >= 400:
        try:
            detail = r.json().get("message") or r.text[:500]
        except Exception:
            detail = r.text[:500]
        raise RuntimeError(f"Mercado Pago: {detail}")
    data = r.json()
    sub = db.query(Subscription).filter(Subscription.company_id == user.company_id).first()
    if not sub:
        sub = Subscription(company_id=user.company_id)
        db.add(sub)
    sub.plan = "mensal-350"
    sub.provider = "mercadopago"
    sub.status = "pending"
    sub.external_subscription_id = str(data.get("id") or "")
    db.commit()
    return {
        "checkout_url": data.get("init_point"),
        "subscription_id": data.get("id"),
        "kind": "subscription",
        "price": _monthly_price(),
    }



_MP_HEALTH_CACHE = {"checked_at": None, "data": None}


def _implementation_fee():
    try:
        return float(os.getenv("CDM_IMPLEMENTATION_FEE", "1500").replace(",", "."))
    except Exception:
        return 1500.0


def _mercadopago_health(force: bool = False):
    """Valida a credencial sem criar pagamento, preferencia ou assinatura."""
    now = datetime.utcnow()
    cached_at = _MP_HEALTH_CACHE.get("checked_at")
    cached_data = _MP_HEALTH_CACHE.get("data")
    if (
        not force
        and cached_at is not None
        and cached_data is not None
        and (now - cached_at).total_seconds() < 300
    ):
        return cached_data

    token = _mp_token()
    webhook_configured = bool(os.getenv("MP_WEBHOOK_SECRET", "").strip())
    base = {
        "token_configured": bool(token),
        "valid": False,
        "ready": False,
        "api_status": None,
        "latency_ms": None,
        "webhook_configured": webhook_configured,
        "payment_methods_count": 0,
        "pix_available": False,
        "monthly_price": _monthly_price(),
        "implementation_fee": _implementation_fee(),
        "checked_at": now.isoformat() + "Z",
        "message": "",
    }

    if not token:
        base["message"] = "Credencial do Mercado Pago nao configurada no servidor."
        _MP_HEALTH_CACHE.update({"checked_at": now, "data": base})
        return base

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                "https://api.mercadopago.com/v1/payment_methods",
                headers=_mp_headers(),
            )
        base["latency_ms"] = round((time.perf_counter() - started) * 1000)
        base["api_status"] = response.status_code

        if response.status_code == 200:
            payload = response.json()
            methods = payload if isinstance(payload, list) else []
            active_ids = {
                str(item.get("id") or "").lower()
                for item in methods
                if str(item.get("status") or "").lower() == "active"
            }
            base["valid"] = True
            base["payment_methods_count"] = len(methods)
            base["pix_available"] = "pix" in active_ids
            base["ready"] = bool(webhook_configured)
            base["message"] = (
                "Credencial autenticada pelo Mercado Pago e webhook configurado."
                if base["ready"]
                else "Credencial autenticada. Falta configurar a assinatura segura do webhook."
            )
        elif response.status_code in {401, 403}:
            base["message"] = "O Mercado Pago recusou a credencial configurada."
        else:
            base["message"] = (
                f"O Mercado Pago respondeu com HTTP {response.status_code}. "
                "Tente validar novamente em alguns instantes."
            )
    except httpx.RequestError:
        base["message"] = "Nao foi possivel alcancar a API do Mercado Pago neste momento."
    except Exception:
        base["message"] = "Falha ao validar a integracao do Mercado Pago."

    _MP_HEALTH_CACHE.update({"checked_at": now, "data": base})
    return base


@router.get("/admin/mercadopago-health")
def mercadopago_health(
    refresh: bool = False,
    user=Depends(current_user),
):
    require_platform_admin(user)
    return _mercadopago_health(force=refresh)


@router.get("/status")
def status(db: Session = Depends(get_db), user=Depends(current_user)):
    sub = db.query(Subscription).filter(Subscription.company_id == user.company_id).first()
    if sub and sub.provider == "mercadopago" and sub.external_subscription_id and _mp_token():
        try:
            sub = _apply_mp_status(db, _mp_get(sub.external_subscription_id)) or sub
        except Exception:
            pass

    # Também concilia a implantação sem depender exclusivamente do webhook.
    try:
        _sync_setup_fee_from_mp(db, user.company_id)
    except Exception:
        pass
    quote = _billing_quote(db, user.company_id)
    active = subscription_is_active(sub)
    if quote["implementation_fee_due_now"] > 0:
        activation_stage = "implementation"
    elif not active:
        activation_stage = "subscription"
    else:
        activation_stage = "active"

    return {
        "subscription": sub,
        "active": active,
        "provider": "mercadopago" if _mp_token() else (os.getenv("BILLING_PROVIDER") or "manual"),
        "checkout_provider_configured": bool(_mp_token()),
        "monthly_price": _monthly_price(),
        "currency": "BRL",
        "webhook_url": f"{_public_url()}/api/billing/mercadopago/webhook",
        "webhook_signature_configured": bool(os.getenv("MP_WEBHOOK_SECRET", "").strip()),
        "quote": quote,
        "founder": quote.get("founder", False),
        "founder_slot": quote.get("founder_slot"),
        "implementation_fee": quote.get("implementation_fee", 0),
        "implementation_fee_status": quote.get("implementation_fee_status", "pending"),
        "implementation_fee_due_now": quote.get("implementation_fee_due_now", 0),
        "first_charge_total": quote.get("first_charge_total", _monthly_price()),
        "activation_stage": activation_stage,
    }


@router.post("/checkout")
def checkout(db: Session = Depends(get_db), user=Depends(current_user)):
    if not _mp_token():
        raise HTTPException(400, "O pagamento online ainda não foi habilitado na plataforma")
    company = db.get(Company, user.company_id)
    payer_email = (company.email if company and company.email else user.email).strip()
    if not payer_email:
        raise HTTPException(400, "Cadastre um e-mail na empresa antes de continuar")

    _sync_setup_fee_from_mp(db, user.company_id)
    quote = _billing_quote(db, user.company_id)
    if float(quote.get("implementation_fee_due_now") or 0) > 0:
        try:
            return _setup_checkout(
                user.company_id,
                payer_email,
                float(quote["implementation_fee_due_now"]),
            )
        except RuntimeError as exc:
            raise HTTPException(400, str(exc))

    sub = db.query(Subscription).filter(Subscription.company_id == user.company_id).first()
    if sub and subscription_is_active(sub):
        return {"kind": "active", "active": True, "message": "Assinatura já está ativa"}

    try:
        return _subscription_checkout(db, user, company, payer_email)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@router.post("/sync")
def sync(db: Session = Depends(get_db), user=Depends(current_user)):
    _sync_setup_fee_from_mp(db, user.company_id)
    sub = db.query(Subscription).filter(Subscription.company_id == user.company_id).first()
    if sub and sub.external_subscription_id and _mp_token():
        try:
            sub = _apply_mp_status(db, _mp_get(sub.external_subscription_id)) or sub
        except RuntimeError as exc:
            raise HTTPException(400, str(exc))
    quote = _billing_quote(db, user.company_id)
    return {
        "subscription": sub,
        "active": subscription_is_active(sub),
        "quote": quote,
    }


def _valid_mp_signature(request: Request, data_id: str):
    secret = os.getenv("MP_WEBHOOK_SECRET", "").strip()
    if not secret:
        return True
    sig = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    parts = {}
    for chunk in sig.split(","):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    ts = parts.get("ts", "")
    v1 = parts.get("v1", "")
    if not ts or not v1:
        return False
    did = str(data_id or "")
    if did and did.isalnum():
        did = did.lower()
    manifest = ""
    if did:
        manifest += f"id:{did};"
    if request_id:
        manifest += f"request-id:{request_id};"
    if ts:
        manifest += f"ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


@router.post("/cancel")
def cancel_subscription(db: Session = Depends(get_db), user=Depends(current_user)):
    sub = db.query(Subscription).filter(Subscription.company_id == user.company_id).first()
    if not sub or not sub.external_subscription_id:
        raise HTTPException(404, "Assinatura não encontrada")
    if not _mp_token():
        raise HTTPException(400, "Mercado Pago não configurado")
    with httpx.Client(timeout=30) as c:
        r = c.put(
            f"https://api.mercadopago.com/preapproval/{sub.external_subscription_id}",
            json={"status": "canceled"},
            headers=_mp_headers(),
        )
    if r.status_code >= 400:
        raise HTTPException(400, f"Mercado Pago: {r.text[:500]}")
    data = r.json()
    row = _apply_mp_status(db, data)
    return {"ok": True, "subscription": row}


@router.post("/mercadopago/webhook", include_in_schema=False)
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    # Fonte de verdade: sempre consultamos novamente a API do Mercado Pago.
    try:
        body = await request.json()
    except Exception:
        body = {}
    query_id = str(request.query_params.get("data.id") or request.query_params.get("id") or "")
    event_id = query_id
    if not event_id and isinstance(body, dict):
        data = body.get("data") or {}
        if isinstance(data, dict):
            event_id = str(data.get("id") or "")
        event_id = event_id or str(body.get("id") or "")
    if not event_id:
        return {"ok": True, "ignored": True}
    if not _valid_mp_signature(request, query_id):
        raise HTTPException(401, "Assinatura de webhook inválida")

    event_type = str(
        request.query_params.get("type")
        or request.query_params.get("topic")
        or (body.get("type") if isinstance(body, dict) else "")
        or (body.get("action") if isinstance(body, dict) else "")
        or ""
    ).lower()
    try:
        if "payment" in event_type:
            provider_data = _mp_get_payment(event_id)
            row = _apply_setup_payment(db, provider_data)
            return {"ok": True, "updated": bool(row), "kind": "payment"}
        provider_data = _mp_get(event_id)
        row = _apply_mp_status(db, provider_data)
        return {"ok": True, "updated": bool(row), "kind": "subscription"}
    except Exception as exc:
        # 200 evita tempestade de retentativas; /status e /sync reconciliam novamente.
        return {"ok": False, "message": str(exc)[:300]}


class BillingEvent(BaseModel):
    company_id: int
    status: str
    plan: str = "mensal"
    provider: str = "external"
    external_subscription_id: str = ""
    days: int = 31


@router.post("/webhook")
def webhook(
    data: BillingEvent,
    x_cdm_webhook_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = os.getenv("BILLING_WEBHOOK_SECRET", "")
    if not expected or x_cdm_webhook_secret != expected:
        raise HTTPException(401, "Webhook não autorizado")
    company = db.get(Company, data.company_id)
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    sub = db.query(Subscription).filter(Subscription.company_id == data.company_id).first()
    if not sub:
        sub = Subscription(company_id=data.company_id)
        db.add(sub)
    sub.status = data.status
    sub.plan = data.plan
    sub.provider = data.provider
    sub.external_subscription_id = data.external_subscription_id
    if data.status in {"active", "trial"}:
        sub.expires_at = datetime.utcnow() + timedelta(days=max(1, data.days))
    db.commit()
    db.refresh(sub)
    return {"ok": True, "subscription": sub}
