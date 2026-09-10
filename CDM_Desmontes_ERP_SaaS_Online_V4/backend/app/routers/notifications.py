from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import active_user
from ..models import Notification, Sale, SaleItem, Product

router=APIRouter()
SOURCE_LABELS={"manual":"Venda local","mercadolivre":"Mercado Livre","shopee":"Shopee","olx":"OLX","system":"Sistema"}


def _sale_message(db:Session, sale:Sale):
    partes=[]
    for item in db.query(SaleItem).filter(SaleItem.sale_id==sale.id).all():
        prod=db.get(Product,item.product_id)
        partes.append(f"{item.quantity}x {prod.name if prod else 'Peça'}")
    return ", ".join(partes)[:360] or f"Venda #{sale.id} registrada com sucesso."


def add_sale_notification(db:Session,company_id:int,sale_id:int,source:str,amount:float,message:str=""):
    existing=db.query(Notification).filter(Notification.company_id==company_id,Notification.sale_id==sale_id,Notification.kind=="sale").first()
    if existing:
        return existing
    source=source or "manual";label=SOURCE_LABELS.get(source,"Sistema")
    row=Notification(company_id=company_id,kind="sale",title=f"Nova venda • {label}",message=message or f"Venda #{sale_id} registrada com sucesso.",source=source,sale_id=sale_id,amount=float(amount or 0),is_read=False)
    db.add(row)
    return row


def _backfill_sale_notifications(db:Session, company_id:int):
    """Garante notificação para toda venda já registrada no CDM, qualquer que seja o canal."""
    sales=db.query(Sale).filter(Sale.company_id==company_id).order_by(Sale.id.desc()).limit(200).all()
    existing={x[0] for x in db.query(Notification.sale_id).filter(Notification.company_id==company_id,Notification.kind=="sale",Notification.sale_id.isnot(None)).all()}
    changed=False
    for sale in sales:
        if sale.id in existing:
            continue
        add_sale_notification(db,company_id,sale.id,getattr(sale,"source","") or "manual",sale.total,_sale_message(db,sale))
        changed=True
    if changed:
        db.commit()


def serialize(n, db:Session|None=None):
    sale=db.get(Sale,n.sale_id) if db is not None and n.sale_id else None
    return {
        "id":n.id,"kind":n.kind,"title":n.title,"message":n.message,
        "source":n.source,"source_label":SOURCE_LABELS.get(n.source,"Sistema"),
        "sale_id":n.sale_id,"amount":n.amount,"is_read":n.is_read,"created_at":n.created_at,
        "sale_status":getattr(sale,"status","") if sale else "",
        "external_order_id":getattr(sale,"external_order_id","") if sale else "",
    }


@router.get("")
def list_notifications(db:Session=Depends(get_db),user=Depends(active_user)):
    _backfill_sale_notifications(db,user.company_id)
    rows=db.query(Notification).filter(Notification.company_id==user.company_id).order_by(Notification.id.desc()).limit(100).all()
    return [serialize(x,db) for x in rows]


@router.get("/unread-count")
def unread_count(db:Session=Depends(get_db),user=Depends(active_user)):
    _backfill_sale_notifications(db,user.company_id)
    return {"count":db.query(Notification).filter(Notification.company_id==user.company_id,Notification.is_read==False).count()}


@router.post("/read-all")
def read_all(db:Session=Depends(get_db),user=Depends(active_user)):
    db.query(Notification).filter(Notification.company_id==user.company_id,Notification.is_read==False).update({"is_read":True},synchronize_session=False)
    db.commit();return {"ok":True}


@router.post("/{notification_id}/read")
def read_one(notification_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(Notification).filter(Notification.id==notification_id,Notification.company_id==user.company_id).first()
    if not row: raise HTTPException(404,"Notificação não encontrada")
    row.is_read=True;db.commit();return {"ok":True}
