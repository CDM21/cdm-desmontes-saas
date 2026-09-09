import os
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user
from ..models import Product,MarketplaceListing
from ..services.marketplaces import MARKETPLACES,connection_status,authorization_url,exchange_callback,disconnect,publish_product,publish_all,refresh_listing,FRONTEND_URL,marketplace_diagnostics,record_connection_error,ml_category_suggestions,process_ml_notification,_active_connection,_ml_token
from ..subscriptions import require_active_subscription
from ..security import decode_oauth_state

router=APIRouter()

@router.get("/status")
def status(db:Session=Depends(get_db),user=Depends(current_user)):
    return connection_status(db,user.company_id)

@router.get("/listings")
def listings(product_id:int|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(MarketplaceListing).filter(MarketplaceListing.company_id==user.company_id)
    if product_id: q=q.filter(MarketplaceListing.product_id==product_id)
    return q.order_by(MarketplaceListing.id.desc()).all()

@router.get("/mercadolivre/category-suggestions")
def ml_categories(q:str=Query(default=""),limit:int=Query(default=3),db:Session=Depends(get_db),user=Depends(current_user)):
    require_active_subscription(user,db)
    try: return ml_category_suggestions(db,user.company_id,q,limit)
    except RuntimeError as e: raise HTTPException(400,str(e))



@router.get("/mercadolivre/stores")
def ml_stores(db:Session=Depends(get_db),user=Depends(current_user)):
    require_active_subscription(user,db)
    try:
        row=_active_connection(db,user.company_id,"mercadolivre")
        token=_ml_token(db,row)
        import httpx
        headers={"Authorization":f"Bearer {token}"}
        with httpx.Client(timeout=30) as c:
            u=c.get(f"https://api.mercadolibre.com/users/{row.external_account_id}",headers=headers)
            if u.status_code>=400: raise RuntimeError(u.text[:700])
            tags=u.json().get("tags") or []
            if "warehouse_management" not in tags:
                return {"warehouse_management":False,"multiwarehouse":False,"stores":[]}
            r=c.get(f"https://api.mercadolibre.com/users/{row.external_account_id}/stores/search",params={"tags":"stock_location"},headers=headers)
            if r.status_code>=400: raise RuntimeError(r.text[:700])
        stores=[]
        for x in r.json().get("results") or []:
            loc=x.get("location") or {}
            stores.append({"id":str(x.get("id") or ""),"network_node_id":str(x.get("network_node_id") or ""),"description":x.get("description") or f"Depósito {x.get('id')}","city":loc.get("city") or "","state":loc.get("state") or ""})
        return {"warehouse_management":True,"multiwarehouse":"multiwarehouse" in tags,"stores":stores}
    except Exception as e:
        raise HTTPException(400,f"Mercado Livre: {str(e)}")

@router.get("/mercadolivre/category/{category_id}/attributes")
def ml_category_attributes(category_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    require_active_subscription(user,db)
    try:
        row=_active_connection(db,user.company_id,"mercadolivre")
        token=_ml_token(db,row)
        import httpx
        with httpx.Client(timeout=30) as c:
            r=c.get(f"https://api.mercadolibre.com/categories/{category_id}/attributes",headers={"Authorization":f"Bearer {token}"})
        if r.status_code>=400: raise RuntimeError(r.text[:700])
        out=[]
        for a in r.json() or []:
            tags=a.get("tags") or {}
            if tags.get("required") or tags.get("catalog_required") or tags.get("conditional_required"):
                vals=[{"id":v.get("id"),"name":v.get("name")} for v in (a.get("values") or [])[:80]]
                out.append({"id":a.get("id"),"name":a.get("name"),"value_type":a.get("value_type") or a.get("value_type_name"),"required":True,"values":vals})
        return out
    except Exception as e: raise HTTPException(400,f"Mercado Livre: {str(e)}")

@router.post("/webhooks/mercadolivre",include_in_schema=False)
async def mercadolivre_webhook(request:Request,db:Session=Depends(get_db)):
    try: body=await request.json()
    except Exception: body={}
    try: return process_ml_notification(db,body if isinstance(body,dict) else {})
    except Exception as exc:
        # Retorna 200 para evitar tempestade de retentativas; o erro fica visível nos logs do Render.
        print("Mercado Livre webhook warning:",str(exc)[:900])
        return {"ok":False,"message":str(exc)[:300]}

@router.get("/{marketplace}/diagnostics")
def diagnostics(marketplace:str,db:Session=Depends(get_db),user=Depends(current_user)):
    if marketplace not in MARKETPLACES: raise HTTPException(400,"Marketplace inválido")
    return marketplace_diagnostics(db,user.company_id,marketplace)

@router.get("/{marketplace}/authorize")
def authorize(marketplace:str,db:Session=Depends(get_db),user=Depends(current_user)):
    if marketplace not in MARKETPLACES: raise HTTPException(400,"Marketplace inválido")
    require_active_subscription(user,db)
    try: return {"url":authorization_url(user.company_id,marketplace)}
    except RuntimeError as e: raise HTTPException(400,str(e).replace("APP_CONFIG:","").strip())

@router.get("/oauth/{marketplace}/callback",include_in_schema=False)
def callback(marketplace:str,code:str=Query(default=""),state:str=Query(default=""),shop_id:str|None=Query(default=None),error:str|None=Query(default=None),error_description:str|None=Query(default=None),db:Session=Depends(get_db)):
    company_id=None
    try:
        payload=decode_oauth_state(state) if state else {}
        company_id=int(payload.get("company_id")) if payload.get("company_id") else None
    except Exception:
        company_id=None
    if error:
        if company_id and marketplace in MARKETPLACES:
            record_connection_error(db,company_id,marketplace,error_description or error)
        return RedirectResponse(f"{FRONTEND_URL}/?integration={marketplace}&status=error")
    if not code:
        if company_id and marketplace in MARKETPLACES:
            record_connection_error(db,company_id,marketplace,"O marketplace não retornou o código de autorização")
        return RedirectResponse(f"{FRONTEND_URL}/?integration={marketplace}&status=error")
    try:
        exchange_callback(db,marketplace,code,state,shop_id)
        return RedirectResponse(f"{FRONTEND_URL}/?integration={marketplace}&status=connected")
    except Exception as exc:
        if company_id and marketplace in MARKETPLACES:
            record_connection_error(db,company_id,marketplace,exc)
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
    enabled={"mercadolivre":p.publish_mercadolivre,"shopee":p.publish_shopee,"olx":p.publish_olx}
    if not enabled.get(marketplace,False):
        raise HTTPException(400,f"{marketplace} está desativado para esta peça")
    return publish_product(db,p,marketplace,user.company_id)

@router.post("/listings/{listing_id}/refresh")
def refresh(listing_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    row=db.query(MarketplaceListing).filter(MarketplaceListing.id==listing_id,MarketplaceListing.company_id==user.company_id).first()
    if not row: raise HTTPException(404,"Anúncio não encontrado")
    try: return refresh_listing(db,row)
    except Exception as e: raise HTTPException(400,str(e))
