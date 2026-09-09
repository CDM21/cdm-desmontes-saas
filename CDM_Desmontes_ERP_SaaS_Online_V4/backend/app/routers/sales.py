from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Sale,SaleItem,Product
from ..deps import current_user, active_user

router=APIRouter()
class ItemIn(BaseModel):
    product_id:int
    quantity:int=1
class SaleIn(BaseModel):
    customer_id:int|None=None
    payment_method:str="pix"
    items:list[ItemIn]

@router.get("")
def list_sales(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Sale).filter(Sale.company_id==user.company_id).order_by(Sale.id.desc()).all()

@router.post("")
def create_sale(data:SaleIn,db:Session=Depends(get_db),user=Depends(active_user)):
    if not data.items: raise HTTPException(400,"Venda sem itens")
    sale=Sale(company_id=user.company_id,customer_id=data.customer_id,payment_method=data.payment_method,total=0)
    db.add(sale); db.flush()
    total=0
    for item in data.items:
        p=db.query(Product).filter(Product.id==item.product_id,Product.company_id==user.company_id).first()
        if not p: raise HTTPException(404,f"Produto {item.product_id} não encontrado")
        if p.stock < item.quantity: raise HTTPException(400,f"Estoque insuficiente: {p.name}")
        p.stock-=item.quantity
        line=p.price*item.quantity
        total+=line
        db.add(SaleItem(company_id=user.company_id,sale_id=sale.id,product_id=p.id,quantity=item.quantity,unit_price=p.price))
    sale.total=total
    db.commit(); db.refresh(sale)
    return sale
