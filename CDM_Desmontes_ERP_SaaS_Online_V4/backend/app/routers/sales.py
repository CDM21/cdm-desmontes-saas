from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Sale, SaleItem, Product, FinancialEntry, StockMovement, Customer
from ..deps import active_user
from ..admin import audit
from ..services.marketplaces import sync_marketplace_stock_for_product

router=APIRouter()

class ItemIn(BaseModel):
    product_id:int
    quantity:int=1

class SaleIn(BaseModel):
    customer_id:int|None=None
    payment_method:str="pix"
    items:list[ItemIn]


def _serialize_sale(db:Session, sale:Sale):
    items=[]
    for row in db.query(SaleItem).filter(SaleItem.sale_id==sale.id).all():
        p=db.get(Product,row.product_id)
        items.append({
            "id":row.id,"product_id":row.product_id,"quantity":row.quantity,"unit_price":row.unit_price,
            "sku":p.sku if p else "","name":p.name if p else ""
        })
    customer=db.get(Customer,sale.customer_id) if sale.customer_id else None
    return {
        "id":sale.id,"customer_id":sale.customer_id,"customer_name":customer.name if customer else "",
        "total":sale.total,"payment_method":sale.payment_method,"status":sale.status,
        "source":getattr(sale,"source","manual"),"external_order_id":getattr(sale,"external_order_id","") or "",
        "created_at":sale.created_at,"items":items,
    }

@router.get("")
def list_sales(db:Session=Depends(get_db),user=Depends(active_user)):
    rows=db.query(Sale).filter(Sale.company_id==user.company_id).order_by(Sale.id.desc()).limit(500).all()
    return [_serialize_sale(db,x) for x in rows]

@router.get("/{sale_id}")
def get_sale(sale_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(Sale).filter(Sale.id==sale_id,Sale.company_id==user.company_id).first()
    if not row: raise HTTPException(404,"Venda não encontrada")
    return _serialize_sale(db,row)

@router.post("")
def create_sale(data:SaleIn,db:Session=Depends(get_db),user=Depends(active_user)):
    if not data.items: raise HTTPException(400,"Venda sem itens")
    if data.customer_id and not db.query(Customer).filter(Customer.id==data.customer_id,Customer.company_id==user.company_id).first():
        raise HTTPException(404,"Cliente não encontrado")
    normalized={}
    for item in data.items:
        if item.quantity<=0: raise HTTPException(400,"Quantidade deve ser maior que zero")
        normalized[item.product_id]=normalized.get(item.product_id,0)+item.quantity
    products=[]
    for pid,qty in normalized.items():
        p=db.query(Product).filter(Product.id==pid,Product.company_id==user.company_id,Product.active==True).with_for_update().first()
        if not p: raise HTTPException(404,f"Produto {pid} não encontrado")
        if p.stock < qty: raise HTTPException(400,f"Estoque insuficiente: {p.name} ({p.stock} disponível)")
        products.append((p,qty))
    sale=Sale(company_id=user.company_id,customer_id=data.customer_id,payment_method=data.payment_method,total=0,status="paid",source="manual")
    db.add(sale); db.flush()
    total=0.0
    for p,qty in products:
        p.stock-=qty
        line=float(p.price or 0)*qty
        total+=line
        db.add(SaleItem(company_id=user.company_id,sale_id=sale.id,product_id=p.id,quantity=qty,unit_price=float(p.price or 0)))
        db.add(StockMovement(company_id=user.company_id,product_id=p.id,kind="sale",quantity_delta=-qty,balance_after=p.stock,reference=f"sale:{sale.id}"))
    sale.total=round(total,2)
    db.add(FinancialEntry(company_id=user.company_id,kind="income",description=f"Venda #{sale.id}",amount=sale.total,status="paid",due_date=datetime.utcnow().strftime("%Y-%m-%d")))
    audit(db,user,"sale.create","sale",str(sale.id),{"total":sale.total,"items":len(products)})
    db.commit(); db.refresh(sale)
    # A venda nunca falha por causa de marketplace. Sincronização é best-effort e registra a pendência no anúncio.
    for p,_ in products:
        try: sync_marketplace_stock_for_product(db,p,user.company_id)
        except Exception: pass
    return _serialize_sale(db,sale)
