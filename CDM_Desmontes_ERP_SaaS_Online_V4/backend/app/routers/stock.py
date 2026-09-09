from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Product,Location
from ..deps import current_user

router=APIRouter()
class LocationIn(BaseModel):
    warehouse:str
    aisle:str=""
    shelf:str=""
    bin:str=""
class MoveIn(BaseModel):
    product_id:int
    location_id:int
    quantity:int=0

@router.get("/locations")
def locations(db:Session=Depends(get_db),user=Depends(current_user)):
    return db.query(Location).filter(Location.company_id==user.company_id).all()
@router.post("/locations")
def create_location(data:LocationIn,db:Session=Depends(get_db),user=Depends(current_user)):
    l=Location(company_id=user.company_id,**data.model_dump()); db.add(l); db.commit(); db.refresh(l); return l
@router.post("/move")
def move(data:MoveIn,db:Session=Depends(get_db),user=Depends(current_user)):
    p=db.query(Product).filter(Product.id==data.product_id,Product.company_id==user.company_id).first()
    l=db.query(Location).filter(Location.id==data.location_id,Location.company_id==user.company_id).first()
    if not p or not l: raise HTTPException(404,"Produto/local não encontrado")
    p.location_id=l.id
    if data.quantity: p.stock=data.quantity
    db.commit(); return {"ok":True,"product_id":p.id,"location_id":l.id,"stock":p.stock}
