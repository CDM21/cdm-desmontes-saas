import gzip
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import inspect, select, func
from sqlalchemy.orm import Session
from ..db import get_db, engine
from ..deps import current_user
from ..models import Company, User, Subscription, Product, Sale, MarketplaceConnection
from ..admin import require_platform_admin, audit

router=APIRouter()

class CompanyStatusIn(BaseModel):
    active: bool

class SubscriptionAdminIn(BaseModel):
    status: str
    days: int = 31

@router.get("/companies")
def companies(db:Session=Depends(get_db), user=Depends(current_user)):
    require_platform_admin(user)
    rows=[]
    for c in db.query(Company).order_by(Company.id.desc()).all():
        sub=db.query(Subscription).filter(Subscription.company_id==c.id).first()
        rows.append({
            "id":c.id,"trade_name":c.trade_name,"cnpj":c.cnpj,"email":c.email,"phone":c.phone,"active":c.active,"created_at":c.created_at,
            "subscription_status":sub.status if sub else "none","subscription_plan":sub.plan if sub else "","expires_at":sub.expires_at if sub else None,
            "users":db.query(User).filter(User.company_id==c.id).count(),
            "products":db.query(Product).filter(Product.company_id==c.id,Product.active==True).count(),
            "sales":db.query(Sale).filter(Sale.company_id==c.id).count(),
            "connections":db.query(MarketplaceConnection).filter(MarketplaceConnection.company_id==c.id,MarketplaceConnection.active==True).count(),
        })
    return rows

@router.put("/companies/{company_id}/active")
def company_active(company_id:int,data:CompanyStatusIn,db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    c=db.get(Company,company_id)
    if not c: raise HTTPException(404,"Empresa não encontrada")
    c.active=data.active
    audit(db,user,"company.active","company",str(company_id),{"active":data.active},company_id=company_id)
    db.commit();db.refresh(c)
    return c

@router.put("/companies/{company_id}/subscription")
def subscription(company_id:int,data:SubscriptionAdminIn,db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    allowed={"trial","active","pending","past_due","canceled","inactive"}
    if data.status not in allowed: raise HTTPException(400,"Status inválido")
    c=db.get(Company,company_id)
    if not c: raise HTTPException(404,"Empresa não encontrada")
    sub=db.query(Subscription).filter(Subscription.company_id==company_id).first()
    if not sub:
        sub=Subscription(company_id=company_id,plan="mensal-350",provider="admin")
        db.add(sub)
    sub.status=data.status
    if data.status in {"active","trial"}: sub.expires_at=datetime.utcnow()+timedelta(days=max(1,data.days))
    elif data.status in {"canceled","inactive"}: sub.expires_at=datetime.utcnow()
    audit(db,user,"subscription.status","subscription",str(company_id),{"status":data.status,"days":data.days},company_id=company_id)
    db.commit();db.refresh(sub)
    return sub

@router.get("/backup")
def backup(db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    # Backup lógico portátil: todas as tabelas em JSON gzip. Segredos de marketplace permanecem criptografados.
    inspector=inspect(engine)
    payload={"format":"cdm-logical-backup-v1","created_at":datetime.utcnow().isoformat()+"Z","tables":{}}
    with engine.connect() as conn:
        for table in inspector.get_table_names():
            rows=conn.exec_driver_sql(f'SELECT * FROM "{table}"').mappings().all()
            clean=[]
            for r in rows:
                item={}
                for k,v in dict(r).items():
                    item[k]=v.isoformat() if hasattr(v,"isoformat") else v
                clean.append(item)
            payload["tables"][table]=clean
    raw=json.dumps(payload,ensure_ascii=False,default=str).encode("utf-8")
    gz=gzip.compress(raw,compresslevel=6)
    audit(db,user,"backup.download","database","",{"bytes":len(gz)})
    db.commit()
    name=f"cdm-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json.gz"
    return Response(gz,media_type="application/gzip",headers={"Content-Disposition":f'attachment; filename="{name}"',"Cache-Control":"no-store"})
