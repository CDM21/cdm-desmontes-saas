from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Product
from ..deps import current_user
from ..services.marketplaces import publish_all

router=APIRouter()
class ProductIn(BaseModel):
    sku:str
    name:str
    category:str=""
    part_group:str=""
    brand:str=""
    model:str=""
    year:int|None=None
    oem:str=""
    condition:str="used"
    side:str=""
    position:str=""
    cost:float=0
    price:float=0
    stock:int=0
    location_id:int|None=None
    vehicle_id:int|None=None
    description:str=""
    compatibility:str=""
    image_urls:str=""
    weight:float=1
    package_length:float=20
    package_width:float=20
    package_height:float=20
    ml_category_id:str=""
    ml_listing_type:str="gold_special"
    shopee_category_id:str=""
    shopee_logistic_id:str=""
    shopee_image_ids:str=""
    olx_category_id:str=""
    auto_publish:bool=False

@router.get("")
def list_products(db:Session=Depends(get_db),user=Depends(current_user)):
    return db.query(Product).filter(Product.company_id==user.company_id,Product.active==True).order_by(Product.id.desc()).all()

@router.post("")
def create_product(data:ProductIn,db:Session=Depends(get_db),user=Depends(current_user)):
    if db.query(Product).filter(Product.company_id==user.company_id,Product.sku==data.sku).first(): raise HTTPException(409,"SKU já existe nesta empresa")
    payload=data.model_dump(exclude={"auto_publish"})
    p=Product(company_id=user.company_id,**payload); db.add(p); db.commit(); db.refresh(p)
    if data.auto_publish: publish_all(db,p,user.company_id)
    return p

@router.get("/{product_id}")
def get_product(product_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    p=db.query(Product).filter(Product.id==product_id,Product.company_id==user.company_id).first()
    if not p: raise HTTPException(404,"Peça não encontrada")
    return p
