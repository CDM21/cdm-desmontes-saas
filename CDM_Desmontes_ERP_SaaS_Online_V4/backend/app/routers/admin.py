import os
import hmac
import gzip
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import inspect, select, func, text
from sqlalchemy.orm import Session
from ..db import get_db, engine
from ..deps import current_user
from ..models import Company, User, Subscription, Product, Sale, SaleItem, Vehicle, VehicleExpense, StockMovement, MarketplaceConnection, MarketplaceListing, AuditLog
from ..admin import require_platform_admin, audit
from ..backup_service import offsite_config, upload_offsite, list_offsite, restore_drill_offsite

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
    # Backup lógico portátil. O SHA-256 interno permite validar a integridade antes de uma futura restauração.
    inspector=inspect(engine)
    payload={
        "format":"cdm-logical-backup-v2",
        "backup_id":uuid.uuid4().hex,
        "created_at":datetime.utcnow().isoformat()+"Z",
        "tables":{},
        "table_counts":{},
    }
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
            payload["table_counts"][table]=len(clean)
    integrity_source=json.dumps(
        {"tables":payload["tables"],"table_counts":payload["table_counts"]},
        ensure_ascii=False,default=str,sort_keys=True,separators=(",",":")
    ).encode("utf-8")
    digest=hashlib.sha256(integrity_source).hexdigest()
    payload["integrity"]={"algorithm":"sha256","sha256":digest}
    raw=json.dumps(payload,ensure_ascii=False,default=str).encode("utf-8")
    gz=gzip.compress(raw,compresslevel=6)
    audit(db,user,"backup.download","database","",{
        "bytes":len(gz),"format":"v2","backup_id":payload["backup_id"],
        "sha256":digest,"tables":len(payload["tables"])
    })
    db.commit()
    name=f"cdm-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json.gz"
    return Response(gz,media_type="application/gzip",headers={
        "Content-Disposition":f'attachment; filename="{name}"',
        "Cache-Control":"no-store",
        "Pragma":"no-cache",
        "X-CDM-Backup-Id":payload["backup_id"],
        "X-CDM-Backup-SHA256":digest,
    })

@router.get("/backup/offsite/status")
def offsite_backup_status(db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    cfg=offsite_config()
    try:
        recent=list_offsite(10).get("items",[]) if cfg["configured"] else []
        error=""
    except Exception as exc:
        recent=[]
        error=str(exc)[:1000]
    external_cron=(os.getenv("BACKUP_CRON_EXTERNAL") or "").strip().lower() in {"1","true","yes","on"}
    return {
        "configured":cfg["configured"],
        "automatic_enabled":bool(cfg["automatic_enabled"] or external_cron),
        "mode":"render-cron" if external_cron else ("internal" if cfg["automatic_enabled"] else "disabled"),
        "interval_hours":cfg["interval_hours"],
        "bucket":cfg["bucket"] if cfg["configured"] else "",
        "prefix":cfg["prefix"],
        "recent":recent,
        "error":error,
    }

@router.post("/backup/offsite/run")
def offsite_backup_run(db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    try:
        result=upload_offsite()
    except Exception as exc:
        audit(db,user,"backup.offsite.error","database","",{"error":str(exc)[:1000]})
        db.commit()
        raise HTTPException(503,f"Não foi possível salvar o backup externo: {exc}")
    audit(db,user,"backup.offsite.success","database","",{
        "backup_id":result["backup_id"],
        "sha256":result["sha256"],
        "bytes":result["bytes"],
        "key":result["key"],
    })
    db.commit()
    return result

@router.post("/backup/offsite/cron")
def offsite_backup_cron(
    x_cdm_backup_token: str = Header(default="", alias="X-CDM-Backup-Token"),
    db: Session = Depends(get_db),
):
    expected=(os.getenv("BACKUP_CRON_TOKEN") or "").strip()
    supplied=(x_cdm_backup_token or "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401,"Não autorizado")

    try:
        result=upload_offsite()
    except Exception as exc:
        db.rollback()
        try:
            db.add(AuditLog(
                company_id=None,user_id=None,
                action="backup.offsite.cron.error",entity="database",entity_id="",
                details_json=json.dumps({"error":str(exc)[:1000]},ensure_ascii=False),
            ))
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(503,f"Falha no backup automático externo: {exc}")

    db.add(AuditLog(
        company_id=None,user_id=None,
        action="backup.offsite.cron",entity="database",entity_id="",
        details_json=json.dumps({
            "backup_id":result["backup_id"],
            "sha256":result["sha256"],
            "bytes":result["bytes"],
            "key":result["key"],
        },ensure_ascii=False,default=str)[:8000],
    ))
    db.commit()

    try:
        restore=restore_drill_offsite(result.get("key",""))
        db.add(AuditLog(
            company_id=None,user_id=None,
            action="backup.restore_drill.success",entity="database",entity_id="",
            details_json=json.dumps({
                "backup_id":restore.get("backup_id"),
                "sha256":restore.get("sha256"),
                "tables":restore.get("tables"),
                "rows":restore.get("rows"),
                "counts_match":restore.get("counts_match"),
                "key":restore.get("key"),
            },ensure_ascii=False,default=str)[:8000],
        ))
        db.commit()
        return {
            **result,
            "restore_drill":{
                "ok":True,
                "tables":restore.get("tables"),
                "rows":restore.get("rows"),
                "counts_match":restore.get("counts_match"),
            },
        }
    except Exception as exc:
        db.rollback()
        try:
            db.add(AuditLog(
                company_id=None,user_id=None,
                action="backup.restore_drill.error",entity="database",entity_id="",
                details_json=json.dumps({
                    "key":result.get("key",""),
                    "error":str(exc)[:1000],
                },ensure_ascii=False),
            ))
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            503,
            f"Backup salvo, mas o teste automático de restauração falhou: {exc}",
        )


class RestoreDrillIn(BaseModel):
    key: str = ""


@router.post("/backup/offsite/restore-drill")
def offsite_restore_drill(
    data: RestoreDrillIn,
    user=Depends(current_user),
):
    require_platform_admin(user)
    try:
        return restore_drill_offsite(data.key)
    except Exception as exc:
        raise HTTPException(
            503,
            f"Teste de restauração não concluído: {exc}",
        )

@router.get("/overview")
def overview(db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    total=db.query(Company).count();active=db.query(Company).filter(Company.active==True).count()
    subs=db.query(Subscription).filter(Subscription.status=="active").count()
    price=float(__import__("os").getenv("MONTHLY_PRICE","350") or 350)
    return {"companies_total":total,"companies_active":active,"companies_inactive":max(0,total-active),
            "subscriptions_active":subs,"subscriptions_trial":db.query(Subscription).filter(Subscription.status=="trial").count(),
            "subscriptions_past_due":db.query(Subscription).filter(Subscription.status=="past_due").count(),
            "users_total":db.query(User).count(),"products_total":db.query(Product).filter(Product.active==True).count(),
            "sales_total":db.query(Sale).count(),"projected_mrr":round(subs*price,2)}

@router.get("/audit-logs")
def audit_logs(limit:int=80,db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    rows=db.query(AuditLog).order_by(AuditLog.id.desc()).limit(max(1,min(limit,200))).all()
    return [{"id":x.id,"company_id":x.company_id,"user_id":x.user_id,"action":x.action,"entity":x.entity,
             "entity_id":x.entity_id,"details":x.details_json,"created_at":x.created_at} for x in rows]

@router.get("/system-health")
def system_health(db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user);db.execute(text("SELECT 1"));inspector=inspect(engine)
    return {"ok":True,"database":"online","tables":len(inspector.get_table_names()),"checked_at":datetime.utcnow()}

@router.get("/tenant-audit")
def tenant_audit(db:Session=Depends(get_db),user=Depends(current_user)):
    require_platform_admin(user)
    checks={
      "users_without_company":db.query(User).outerjoin(Company,Company.id==User.company_id).filter(Company.id==None).count(),
      "product_vehicle_cross_company":db.query(Product).join(Vehicle,Vehicle.id==Product.vehicle_id).filter(Product.vehicle_id!=None,Product.company_id!=Vehicle.company_id).count(),
      "sale_item_sale_cross_company":db.query(SaleItem).join(Sale,Sale.id==SaleItem.sale_id).filter(SaleItem.company_id!=Sale.company_id).count(),
      "sale_item_product_cross_company":db.query(SaleItem).join(Product,Product.id==SaleItem.product_id).filter(SaleItem.company_id!=Product.company_id).count(),
      "stock_product_cross_company":db.query(StockMovement).join(Product,Product.id==StockMovement.product_id).filter(StockMovement.company_id!=Product.company_id).count(),
      "listing_product_cross_company":db.query(MarketplaceListing).join(Product,Product.id==MarketplaceListing.product_id).filter(MarketplaceListing.company_id!=Product.company_id).count(),
    }
    total=sum(checks.values())
    return {"ok":total==0,"issues":total,"checks":checks,"checked_at":datetime.utcnow()}

# CDM V12.2 - PAINEL SaaS DO DONO PRO
def _v122_sync_subscriptions(db):
    now = datetime.utcnow()
    changed = 0
    subs = db.query(Subscription).all()
    for sub in subs:
        exp = getattr(sub, "expires_at", None)
        status = (getattr(sub, "status", "") or "").lower()
        if exp and status in ("trial", "active") and exp < now:
            sub.status = "past_due"
            changed += 1
    if changed:
        db.commit()
    return changed

def _v122_log(db, user, action, entity="company", entity_id=None, details=None):
    try:
        db.add(AuditLog(
            company_id=getattr(user, "company_id", None),
            user_id=getattr(user, "id", None),
            action=action,
            entity=entity,
            entity_id=entity_id,
            details_json=json.dumps(details or {}, ensure_ascii=False, default=str)[:8000],
        ))
    except Exception:
        pass

def _v122_company_payload(db, company):
    sub = db.query(Subscription).filter(Subscription.company_id == company.id).first()
    now = datetime.utcnow()
    exp = getattr(sub, "expires_at", None) if sub else None
    days = (exp.date() - now.date()).days if exp else None
    status = (getattr(sub, "status", None) or "inactive") if sub else "inactive"
    if not getattr(company, "active", True):
        visual_status = "blocked"
    elif status in ("past_due", "canceled", "trial", "active"):
        visual_status = status
    else:
        visual_status = status or "inactive"
    return {
        "id": company.id,
        "trade_name": getattr(company, "trade_name", "") or getattr(company, "legal_name", "") or f"Empresa #{company.id}",
        "legal_name": getattr(company, "legal_name", "") or "",
        "cnpj": getattr(company, "cnpj", "") or "",
        "email": getattr(company, "email", "") or "",
        "phone": getattr(company, "phone", "") or "",
        "created_at": company.created_at.isoformat() if getattr(company, "created_at", None) else None,
        "active": bool(getattr(company, "active", True)),
        "subscription_status": status,
        "provider": getattr(sub, "provider", "") if sub else "",
        "last_login_at": (lambda x: x.isoformat() if x else None)(db.query(func.max(User.last_login_at)).filter(User.company_id == company.id).scalar()),
        "connections": db.query(MarketplaceConnection).filter(MarketplaceConnection.company_id == company.id, MarketplaceConnection.active == True).count(),
        "visual_status": visual_status,
        "expires_at": exp.isoformat() if exp else None,
        "days_remaining": days,
        "users": db.query(User).filter(User.company_id == company.id).count(),
        "products": db.query(Product).filter(Product.company_id == company.id).count(),
        "sales": db.query(Sale).filter(Sale.company_id == company.id).count(),
        "vehicles": db.query(Vehicle).filter(Vehicle.company_id == company.id).count(),
    }

def _v122_platform_admin_user(user=Depends(current_user)):
    require_platform_admin(user)
    return user

@router.get("/dashboard-v2")
def admin_dashboard_v2(db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    synced = _v122_sync_subscriptions(db)
    companies = db.query(Company).order_by(Company.id.desc()).all()
    rows = [_v122_company_payload(db, c) for c in companies]
    active = sum(1 for x in rows if x["visual_status"] == "active")
    trial = sum(1 for x in rows if x["visual_status"] == "trial")
    overdue = sum(1 for x in rows if x["visual_status"] == "past_due")
    blocked = sum(1 for x in rows if x["visual_status"] == "blocked")
    canceled = sum(1 for x in rows if x["visual_status"] == "canceled")
    monthly_price = float(os.getenv("CDM_MONTHLY_PRICE", os.getenv("MONTHLY_PRICE", "350")) or 350)
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    new_this_month = sum(1 for x in companies if getattr(x, "created_at", None) and x.created_at >= month_start)
    new_last_30_days = sum(1 for x in companies if getattr(x, "created_at", None) and x.created_at >= now - timedelta(days=30))
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(60).all()
    recent_logs = [{
        "id": x.id,
        "company_id": x.company_id,
        "user_id": x.user_id,
        "action": x.action,
        "entity": x.entity,
        "entity_id": x.entity_id,
        "details_json": x.details_json,
        "created_at": x.created_at.isoformat() if x.created_at else None,
    } for x in logs]
    return {
        "summary": {
            "companies_total": len(rows),
            "active": active,
            "trial": trial,
            "past_due": overdue,
            "blocked": blocked,
            "canceled": canceled,
            "users_total": db.query(User).count(),
            "products_total": db.query(Product).count(),
            "sales_total": db.query(Sale).count(),
            "projected_mrr": round(active * monthly_price, 2),
            "projected_arr": round(active * monthly_price * 12, 2),
            "monthly_price": monthly_price,
            "new_this_month": new_this_month,
            "new_last_30_days": new_last_30_days,
            "attention": overdue + blocked,
            "synced_now": synced,
        },
        "companies": rows,
        "recent_logs": recent_logs,
        "automation": {
            "expiry_sync": True,
            "payment_webhook_required_for_real_payment_confirmation": True,
        },
    }

@router.post("/companies/{company_id}/trial")
def admin_company_trial(company_id: int, days: int = 7, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    days = max(1, min(int(days or 7), 90))
    sub = db.query(Subscription).filter(Subscription.company_id == company_id).first()
    if not sub:
        sub = Subscription(company_id=company_id, plan="mensal-350", status="trial")
        db.add(sub)
    sub.status = "trial"
    sub.started_at = datetime.utcnow()
    sub.expires_at = datetime.utcnow() + timedelta(days=days)
    company.active = True
    _v122_log(db, user, "admin.company.trial", entity_id=company_id, details={"days": days})
    db.commit()
    return {"ok": True, "status": "trial", "days": days}

@router.post("/companies/{company_id}/activate")
def admin_company_activate(company_id: int, days: int = 31, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    days = max(1, min(int(days or 31), 365))
    sub = db.query(Subscription).filter(Subscription.company_id == company_id).first()
    if not sub:
        sub = Subscription(company_id=company_id, plan="mensal-350", status="active")
        db.add(sub)
    sub.status = "active"
    sub.expires_at = datetime.utcnow() + timedelta(days=days)
    company.active = True
    _v122_log(db, user, "admin.company.activate", entity_id=company_id, details={"days": days})
    db.commit()
    return {"ok": True, "status": "active", "days": days}

@router.post("/companies/{company_id}/past-due")
def admin_company_past_due(company_id: int, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    sub = db.query(Subscription).filter(Subscription.company_id == company_id).first()
    if not sub:
        sub = Subscription(company_id=company_id, plan="mensal-350", status="past_due")
        db.add(sub)
    sub.status = "past_due"
    _v122_log(db, user, "admin.company.past_due", entity_id=company_id)
    db.commit()
    return {"ok": True, "status": "past_due"}

@router.post("/companies/{company_id}/cancel")
def admin_company_cancel(company_id: int, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    sub = db.query(Subscription).filter(Subscription.company_id == company_id).first()
    if sub:
        sub.status = "canceled"
    _v122_log(db, user, "admin.company.cancel", entity_id=company_id)
    db.commit()
    return {"ok": True, "status": "canceled"}

@router.post("/companies/{company_id}/block")
def admin_company_block(company_id: int, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    if company.id == getattr(user, "company_id", None):
        raise HTTPException(400, "Você não pode bloquear a própria empresa administradora por este painel")
    company.active = False
    _v122_log(db, user, "admin.company.block", entity_id=company_id)
    db.commit()
    return {"ok": True, "active": False}

@router.post("/companies/{company_id}/unblock")
def admin_company_unblock(company_id: int, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    company.active = True
    _v122_log(db, user, "admin.company.unblock", entity_id=company_id)
    db.commit()
    return {"ok": True, "active": True}

@router.delete("/companies/{company_id}")
def admin_company_delete_empty(company_id: int, db: Session = Depends(get_db), user: User = Depends(_v122_platform_admin_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Empresa não encontrada")
    if company.id == getattr(user, "company_id", None):
        raise HTTPException(400, "A empresa administradora da plataforma não pode ser excluída")
    operational = (
        db.query(Product).filter(Product.company_id == company_id).count()
        + db.query(Sale).filter(Sale.company_id == company_id).count()
        + db.query(Vehicle).filter(Vehicle.company_id == company_id).count()
    )
    if operational:
        raise HTTPException(409, "Esta empresa possui dados operacionais. Por segurança, bloqueie ou cancele em vez de excluir.")
    try:
        db.query(AuditLog).filter(AuditLog.company_id == company_id).delete(synchronize_session=False)
        db.query(Subscription).filter(Subscription.company_id == company_id).delete(synchronize_session=False)
        db.query(User).filter(User.company_id == company_id).delete(synchronize_session=False)
        db.delete(company)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Não foi possível excluir porque ainda existem dados ligados à empresa. Use Bloquear/Cancelar.")
    return {"ok": True, "deleted": company_id}
