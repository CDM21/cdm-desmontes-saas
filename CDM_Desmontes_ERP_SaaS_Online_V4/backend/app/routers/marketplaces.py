import os
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user
from ..models import Product,MarketplaceListing
from ..services.marketplaces import MARKETPLACES,connection_status,authorization_url,exchange_callback,disconnect,publish_product,publish_all,refresh_listing,FRONTEND_URL
from ..subscriptions import require_active_subscription

router=APIRouter()

@router.get("/status")
def status(db:Session=Depends(get_db),user=Depends(current_user)):
    return connection_status(db,user.company_id)

@router.get("/listings")
def listings(product_id:int|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(MarketplaceListing).filter(MarketplaceListing.company_id==user.company_id)
    if product_id: q=q.filter(MarketplaceListing.product_id==product_id)
    return q.order_by(MarketplaceListing.id.desc()).all()

@router.get("/{marketplace}/authorize")
def authorize(marketplace:str,db:Session=Depends(get_db),user=Depends(current_user)):
    if marketplace not in MARKETPLACES: raise HTTPException(400,"Marketplace inválido")
    require_active_subscription(user,db)
    try: return {"url":authorization_url(user.company_id,marketplace)}
    except RuntimeError as e: raise HTTPException(400,str(e).replace("APP_CONFIG:","").strip())

@router.get("/oauth/{marketplace}/callback",include_in_schema=False)
def callback(marketplace:str,code:str=Query(default=""),state:str=Query(default=""),shop_id:str|None=Query(default=None),error:str|None=Query(default=None),db:Session=Depends(get_db)):
    if error: return RedirectResponse(f"{FRONTEND_URL}/?integration={marketplace}&status=error")
    try:
        exchange_callback(db,marketplace,code,state,shop_id)
        return RedirectResponse(f"{FRONTEND_URL}/?integration={marketplace}&status=connected")
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/?integration={marketplace}&status=error")

@router.delete("/{marketplace}/connection")
def remove_connection(marketplace:str,db:Session=Depends(get_db),user=Depends(current_user)):
    if marketplace not in MARKETPLACES: raise HTTPException(400,"Marketplace inválido")
    return disconnect(db,user.company_id,marketplace)

@router.post("/products/{product_id}/publish-all")
def pub_all(product_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    require_active_subscription(user,db)
    p=db.query(Product).filter(Product.id==product_id,Product.company_id==user.company_id).first()
    if not p: raise HTTPException(404,"Peça não encontrada")
    return publish_all(db,p,user.company_id)

@router.post("/products/{product_id}/publish/{marketplace}")
def pub_one(product_id:int,marketplace:str,db:Session=Depends(get_db),user=Depends(current_user)):
    require_active_subscription(user,db)
    if marketplace not in MARKETPLACES: raise HTTPException(400,"Marketplace inválido")
    p=db.query(Product).filter(Product.id==product_id,Product.company_id==user.company_id).first()
    if not p: raise HTTPException(404,"Peça não encontrada")
    return publish_product(db,p,marketplace,user.company_id)

@router.post("/listings/{listing_id}/refresh")
def refresh(listing_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    row=db.query(MarketplaceListing).filter(MarketplaceListing.id==listing_id,MarketplaceListing.company_id==user.company_id).first()
    if not row: raise HTTPException(404,"Anúncio não encontrado")
    try: return refresh_listing(db,row)
    except Exception as e: raise HTTPException(400,str(e))
