import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user
from ..models import Subscription, Company
from ..subscriptions import subscription_is_active

router=APIRouter()

@router.get("/status")
def status(db:Session=Depends(get_db),user=Depends(current_user)):
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    return {"subscription":sub,"active":subscription_is_active(sub),"checkout_provider_configured":bool(os.getenv("BILLING_PROVIDER"))}

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
