import base64
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Product
from ..deps import active_user
from ..services.marketplaces import publish_all

router=APIRouter()

def next_sequential_sku(db:Session, company_id:int)->str:
    rows=db.query(Product.sku).filter(Product.company_id==company_id).all()
    numbers=[]
    for row in rows:
        value=str(row[0] or "").strip()
        if value.isdigit():
            numbers.append(int(value))
    return str((max(numbers) if numbers else 0)+1)

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
    publish_mercadolivre:bool=True
    publish_shopee:bool=True
    publish_olx:bool=True
    ml_has_warranty:bool=False
    ml_warranty_text:str=""
    ml_shipping_mode:str="me2"
    ml_free_shipping:bool=False
    ml_local_pickup:bool=True
    ml_attributes_json:str="{}"
    ml_store_id:str=""
    ml_network_node_id:str=""
    quality_grade:str="B"
    quality_notes:str=""
    warranty_days:int=90
    public_catalog:bool=True
    auto_publish:bool=False

@router.get("")
def list_products(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Product).filter(Product.company_id==user.company_id,Product.active==True).order_by(Product.id.desc()).all()

@router.get("/next-sku")
def get_next_sku(db:Session=Depends(get_db),user=Depends(active_user)):
    return {"sku":next_sequential_sku(db,user.company_id)}

@router.post("")
def create_product(data:ProductIn,db:Session=Depends(get_db),user=Depends(active_user)):
    if db.query(Product).filter(Product.company_id==user.company_id,Product.sku==data.sku).first():
        raise HTTPException(409,"SKU já existe nesta empresa")
    payload=data.model_dump(exclude={"auto_publish"})
    p=Product(company_id=user.company_id,**payload)
    db.add(p); db.commit(); db.refresh(p)
    if data.auto_publish:
        publish_all(db,p,user.company_id)
    return p

@router.put("/{product_id}")
def update_product(product_id:int,data:ProductIn,db:Session=Depends(get_db),user=Depends(active_user)):
    p=db.query(Product).filter(Product.id==product_id,Product.company_id==user.company_id,Product.active==True).first()
    if not p:
        raise HTTPException(404,"Peça não encontrada")
    duplicate=db.query(Product).filter(Product.company_id==user.company_id,Product.sku==data.sku,Product.id!=product_id).first()
    if duplicate:
        raise HTTPException(409,"SKU já existe nesta empresa")
    for key,value in data.model_dump(exclude={"auto_publish"}).items():
        setattr(p,key,value)
    db.commit(); db.refresh(p)
    if data.auto_publish:
        publish_all(db,p,user.company_id)
    return p

@router.delete("/{product_id}")
def archive_product(product_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    p=db.query(Product).filter(Product.id==product_id,Product.company_id==user.company_id,Product.active==True).first()
    if not p:
        raise HTTPException(404,"Peça não encontrada")
    p.active=False
    db.commit()
    return {"ok":True}

@router.get("/public/{product_id}/images/{image_index}", include_in_schema=False)
def public_product_image(product_id:int,image_index:int,db:Session=Depends(get_db)):
    p=db.query(Product).filter(Product.id==product_id,Product.active==True).first()
    if not p:
        raise HTTPException(404,"Imagem não encontrada")
    images=[x.strip() for x in (p.image_urls or "").splitlines() if x.strip()]
    if image_index<0 or image_index>=len(images):
        raise HTTPException(404,"Imagem não encontrada")
    value=images[image_index]
    m=re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$",value,re.S)
    if not m:
        raise HTTPException(404,"A imagem é externa")
    try:
        raw=base64.b64decode(m.group(2),validate=False)
    except Exception:
        raise HTTPException(400,"Imagem inválida")
    return Response(raw,media_type=m.group(1),headers={"Cache-Control":"public, max-age=86400"})

@router.get("/{product_id}")
def get_product(product_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    p=db.query(Product).filter(Product.id==product_id,Product.company_id==user.company_id).first()
    if not p:
        raise HTTPException(404,"Peça não encontrada")
    return p
