import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
from ..db import get_db
from ..deps import current_user
from ..models import Subscription, Company
from ..subscriptions import subscription_is_active

router=APIRouter()


def _public_url():
    return (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("FRONTEND_URL") or "http://localhost:5173").rstrip("/")


def _mp_token():
    return os.getenv("MP_ACCESS_TOKEN", "").strip()


def _monthly_price():
    try:
        return float(os.getenv("CDM_MONTHLY_PRICE", "350").replace(",", "."))
    except Exception:
        return 350.0


def _mp_get(subscription_id:str):
    token=_mp_token()
    if not token: raise RuntimeError("Mercado Pago ainda não foi configurado no servidor")
    with httpx.Client(timeout=30) as c:
        r=c.get(f"https://api.mercadopago.com/preapproval/{subscription_id}",headers={"Authorization":f"Bearer {token}"})
    if r.status_code>=400: raise RuntimeError(f"Mercado Pago: não foi possível consultar a assinatura ({r.status_code})")
    return r.json()


def _apply_mp_status(db:Session, data:dict):
    ref=str(data.get("external_reference") or "")
    if not ref.startswith("cdm_company_"): return None
    try: company_id=int(ref.rsplit("_",1)[-1])
    except Exception: return None
    company=db.get(Company,company_id)
    if not company: return None
    sub=db.query(Subscription).filter(Subscription.company_id==company_id).first()
    if not sub:
        sub=Subscription(company_id=company_id);db.add(sub)
    raw=str(data.get("status") or "pending")
    mapped={"authorized":"active","paused":"past_due","cancelled":"canceled","canceled":"canceled","pending":"pending"}.get(raw,raw)
    sub.status=mapped
    sub.plan="mensal-350"
    sub.provider="mercadopago"
    sub.external_subscription_id=str(data.get("id") or sub.external_subscription_id or "")
    sub.auto_renew=mapped not in {"canceled","inactive"}
    if mapped=="active":
        # Janela de segurança maior que um ciclo mensal. Novas notificações/sincronizações renovam a data.
        sub.expires_at=datetime.utcnow()+timedelta(days=35)
    elif mapped in {"canceled","inactive"}:
        sub.expires_at=datetime.utcnow()
    db.commit();db.refresh(sub)
    return sub


@router.get("/status")
def status(db:Session=Depends(get_db),user=Depends(current_user)):
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    # Se já existe assinatura Mercado Pago, confirma o status diretamente no provedor.
    if sub and sub.provider=="mercadopago" and sub.external_subscription_id and _mp_token():
        try:
            sub=_apply_mp_status(db,_mp_get(sub.external_subscription_id)) or sub
        except Exception:
            pass
    return {
        "subscription":sub,
        "active":subscription_is_active(sub),
        "provider":"mercadopago" if _mp_token() else (os.getenv("BILLING_PROVIDER") or "manual"),
        "checkout_provider_configured":bool(_mp_token()),
        "monthly_price":_monthly_price(),
        "currency":"BRL",
    }


@router.post("/checkout")
def checkout(db:Session=Depends(get_db),user=Depends(current_user)):
    token=_mp_token()
    if not token: raise HTTPException(400,"Configure MP_ACCESS_TOKEN no Render para ativar a mensalidade")
    company=db.get(Company,user.company_id)
    payer_email=(company.email if company and company.email else user.email).strip()
    if not payer_email: raise HTTPException(400,"Cadastre um e-mail na empresa antes de assinar")
    payload={
        "reason":"CDM Desmontes - Plano mensal",
        "external_reference":f"cdm_company_{user.company_id}",
        "payer_email":payer_email,
        "auto_recurring":{
            "frequency":1,
            "frequency_type":"months",
            "transaction_amount":_monthly_price(),
            "currency_id":"BRL",
        },
        "back_url":f"{_public_url()}/?billing=return",
    }
    with httpx.Client(timeout=30) as c:
        r=c.post("https://api.mercadopago.com/preapproval",json=payload,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
    if r.status_code>=400:
        try: detail=r.json().get("message") or r.text[:500]
        except Exception: detail=r.text[:500]
        raise HTTPException(400,f"Mercado Pago: {detail}")
    data=r.json()
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    if not sub:
        sub=Subscription(company_id=user.company_id);db.add(sub)
    sub.plan="mensal-350";sub.provider="mercadopago";sub.status="pending";sub.external_subscription_id=str(data.get("id") or "")
    db.commit()
    return {"checkout_url":data.get("init_point"),"subscription_id":data.get("id"),"price":_monthly_price()}


@router.post("/sync")
def sync(db:Session=Depends(get_db),user=Depends(current_user)):
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    if not sub or not sub.external_subscription_id: raise HTTPException(404,"Assinatura do Mercado Pago ainda não encontrada")
    try: data=_mp_get(sub.external_subscription_id)
    except RuntimeError as e: raise HTTPException(400,str(e))
    row=_apply_mp_status(db,data)
    return {"subscription":row,"active":subscription_is_active(row)}


@router.post("/mercadopago/webhook",include_in_schema=False)
async def mercadopago_webhook(request:Request,db:Session=Depends(get_db)):
    # A fonte de verdade é consultada novamente na API do Mercado Pago; não confiamos no status recebido no webhook.
    try: body=await request.json()
    except Exception: body={}
    sid=""
    if isinstance(body,dict):
        data=body.get("data") or {}
        if isinstance(data,dict): sid=str(data.get("id") or "")
        sid=sid or str(body.get("id") or "")
    sid=sid or str(request.query_params.get("data.id") or request.query_params.get("id") or "")
    if not sid: return {"ok":True,"ignored":True}
    try:
        provider_data=_mp_get(sid)
        row=_apply_mp_status(db,provider_data)
        return {"ok":True,"updated":bool(row)}
    except Exception as exc:
        # Retorna 200 para evitar tempestade de retentativas; a tela do cliente também pode sincronizar manualmente.
        return {"ok":False,"message":str(exc)[:300]}


# Webhook genérico preservado para outros gateways/uso administrativo.
class BillingEvent(BaseModel):
    company_id:int
    status:str
    plan:str="mensal"
    provider:str="external"
    external_subscription_id:str=""
    days:int=31

@router.post("/webhook")
def webhook(data:BillingEvent, x_cdm_webhook_secret:str|None=Header(default=None), db:Session=Depends(get_db)):
    expected=os.getenv("BILLING_WEBHOOK_SECRET","")
    if not expected or x_cdm_webhook_secret!=expected: raise HTTPException(401,"Webhook não autorizado")
    company=db.get(Company,data.company_id)
    if not company: raise HTTPException(404,"Empresa não encontrada")
    sub=db.query(Subscription).filter(Subscription.company_id==data.company_id).first()
    if not sub:
        sub=Subscription(company_id=data.company_id);db.add(sub)
    sub.status=data.status
    sub.plan=data.plan
    sub.provider=data.provider
    sub.external_subscription_id=data.external_subscription_id
    if data.status in {"active","trial"}: sub.expires_at=datetime.utcnow()+timedelta(days=max(1,data.days))
    db.commit();db.refresh(sub)
    return {"ok":True,"subscription":sub}
