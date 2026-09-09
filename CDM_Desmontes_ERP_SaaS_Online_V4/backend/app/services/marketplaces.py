import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from dotenv import load_dotenv
from jose import JWTError
from sqlalchemy.orm import Session

from ..crypto import encrypt_secret, decrypt_secret
from ..models import Company, MarketplaceConnection, MarketplaceListing, Product, Subscription
from ..security import create_oauth_state, decode_oauth_state
from ..subscriptions import subscription_is_active

load_dotenv()
MARKETPLACES=("mercadolivre","shopee","olx")

def _public_base_url():
    return (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")

FRONTEND_URL=(os.getenv("FRONTEND_URL") or _public_base_url() or "http://localhost:5173").rstrip("/")


def _env(name, default=""):
    return os.getenv(name, default).strip()


def _redirect_uri(marketplace:str):
    explicit={
        "mercadolivre":"ML_REDIRECT_URI",
        "shopee":"SHOPEE_REDIRECT_URI",
        "olx":"OLX_REDIRECT_URI",
    }[marketplace]
    if _env(explicit):
        return _env(explicit)
    base=_public_base_url()
    if base:
        return f"{base}/api/marketplaces/oauth/{marketplace}/callback"
    return f"http://localhost:8000/api/marketplaces/oauth/{marketplace}/callback"


def app_ready(marketplace:str):
    if marketplace=="mercadolivre":
        return bool(_env("ML_CLIENT_ID") and _env("ML_CLIENT_SECRET"))
    if marketplace=="shopee":
        return bool(_env("SHOPEE_PARTNER_ID") and _env("SHOPEE_PARTNER_KEY"))
    if marketplace=="olx":
        return bool(_env("OLX_CLIENT_ID") and _env("OLX_CLIENT_SECRET"))
    return False


def _connection(db:Session, company_id:int, marketplace:str, create=False):
    row=db.query(MarketplaceConnection).filter(
        MarketplaceConnection.company_id==company_id,
        MarketplaceConnection.marketplace==marketplace,
    ).first()
    if not row and create:
        row=MarketplaceConnection(company_id=company_id,marketplace=marketplace,status="disconnected",active=False)
        db.add(row); db.flush()
    return row


def connection_status(db:Session, company_id:int):
    counts={m:{"published":0,"issues":0,"processing":0} for m in MARKETPLACES}
    for row in db.query(MarketplaceListing).filter(MarketplaceListing.company_id==company_id).all():
        if row.marketplace not in counts: continue
        if row.status=="published": counts[row.marketplace]["published"]+=1
        elif row.status in {"processing","queued","pending"}: counts[row.marketplace]["processing"]+=1
        else: counts[row.marketplace]["issues"]+=1
    result=[]
    for m in MARKETPLACES:
        conn=_connection(db,company_id,m)
        result.append({
            "id":m,
            "configured":bool(conn and conn.active and conn.status=="connected"),
            "connected":bool(conn and conn.active and conn.status=="connected"),
            "app_ready":app_ready(m),
            "account_name":conn.account_name if conn else "",
            "external_account_id":conn.external_account_id if conn else "",
            "status":conn.status if conn else "disconnected",
            "last_error":conn.last_error if conn else "",
            **counts[m],
        })
    return result


def authorization_url(company_id:int, marketplace:str):
    if marketplace not in MARKETPLACES: raise ValueError("Marketplace inválido")
    if not app_ready(marketplace):
        raise RuntimeError("APP_CONFIG: As credenciais da aplicação deste marketplace ainda não foram configuradas no servidor.")
    state=create_oauth_state(company_id,marketplace)
    if marketplace=="mercadolivre":
        params={"response_type":"code","client_id":_env("ML_CLIENT_ID"),"redirect_uri":_redirect_uri("mercadolivre"),"state":state}
        return "https://auth.mercadolivre.com.br/authorization?"+urlencode(params)
    if marketplace=="olx":
        params={"client_id":_env("OLX_CLIENT_ID"),"response_type":"code","scope":"autoupload basic_user_info","redirect_uri":_redirect_uri("olx"),"state":state}
        return "https://auth.olx.com.br/oauth?"+urlencode(params)
    path="/api/v2/shop/auth_partner"
    ts=int(time.time())
    partner_id=int(_env("SHOPEE_PARTNER_ID"))
    sign=_shopee_public_sign(path,ts)
    redirect=_redirect_uri("shopee")
    redirect += ("&" if "?" in redirect else "?") + "state=" + state
    params={"partner_id":partner_id,"timestamp":ts,"sign":sign,"redirect":redirect}
    return "https://partner.shopeemobile.com"+path+"?"+urlencode(params)


def _save_connection(db:Session, company_id:int, marketplace:str, access_token:str, refresh_token:str="", expires_in:int|None=None, account_name:str="", external_account_id:str="", metadata:dict|None=None):
    row=_connection(db,company_id,marketplace,create=True)
    row.access_token_enc=encrypt_secret(access_token)
    row.refresh_token_enc=encrypt_secret(refresh_token)
    row.token_expires_at=datetime.utcnow()+timedelta(seconds=max(0,int(expires_in)-60)) if expires_in else None
    row.account_name=account_name or row.account_name
    row.external_account_id=str(external_account_id or row.external_account_id or "")
    row.metadata_json=json.dumps(metadata or {},ensure_ascii=False)
    row.active=True; row.status="connected"; row.last_error=""
    db.commit(); db.refresh(row)
    return row


def exchange_callback(db:Session, marketplace:str, code:str, state:str, shop_id:str|None=None):
    try:
        payload=decode_oauth_state(state)
    except JWTError:
        raise RuntimeError("Estado OAuth inválido ou expirado")
    if payload.get("purpose")!="marketplace_oauth" or payload.get("marketplace")!=marketplace:
        raise RuntimeError("Estado OAuth inválido")
    company_id=int(payload["company_id"])
    if marketplace=="mercadolivre": return _exchange_ml(db,company_id,code)
    if marketplace=="olx": return _exchange_olx(db,company_id,code)
    if marketplace=="shopee":
        if not shop_id: raise RuntimeError("Shopee não retornou shop_id")
        return _exchange_shopee(db,company_id,code,shop_id)
    raise RuntimeError("Marketplace inválido")


def _exchange_ml(db,company_id,code):
    data={"grant_type":"authorization_code","client_id":_env("ML_CLIENT_ID"),"client_secret":_env("ML_CLIENT_SECRET"),"code":code,"redirect_uri":_redirect_uri("mercadolivre")}
    with httpx.Client(timeout=30) as c:
        r=c.post("https://api.mercadolibre.com/oauth/token",data=data)
        if r.status_code>=400: raise RuntimeError(f"Mercado Livre OAuth: {r.text[:600]}")
        token=r.json()
        access=token.get("access_token","")
        me=c.get("https://api.mercadolibre.com/users/me",headers={"Authorization":f"Bearer {access}"})
        profile=me.json() if me.status_code<400 else {}
    return _save_connection(db,company_id,"mercadolivre",access,token.get("refresh_token","") ,token.get("expires_in"),profile.get("nickname") or profile.get("first_name") or "Conta Mercado Livre",profile.get("id") or token.get("user_id"),profile)


def _exchange_olx(db,company_id,code):
    data={"code":code,"client_id":_env("OLX_CLIENT_ID"),"client_secret":_env("OLX_CLIENT_SECRET"),"redirect_uri":_redirect_uri("olx"),"grant_type":"authorization_code"}
    with httpx.Client(timeout=30) as c:
        r=c.post("https://auth.olx.com.br/oauth/token",data=data,headers={"Content-Type":"application/x-www-form-urlencoded"})
        if r.status_code>=400: raise RuntimeError(f"OLX OAuth: {r.text[:600]}")
        token=r.json(); access=token.get("access_token","")
        me=c.post("https://apps.olx.com.br/oauth_api/basic_user_info",json={"access_token":access})
        profile=me.json() if me.status_code<400 else {}
    return _save_connection(db,company_id,"olx",access,"",token.get("expires_in"),profile.get("user_name") or profile.get("user_email") or "Conta OLX",profile.get("user_email") or "",profile)


def _shopee_public_sign(path, timestamp):
    partner_id=int(_env("SHOPEE_PARTNER_ID","0")); key=_env("SHOPEE_PARTNER_KEY")
    base=f"{partner_id}{path}{timestamp}"
    return hmac.new(key.encode(),base.encode(),hashlib.sha256).hexdigest()


def _shopee_shop_sign(path, timestamp, access_token, shop_id):
    partner_id=int(_env("SHOPEE_PARTNER_ID","0")); key=_env("SHOPEE_PARTNER_KEY")
    base=f"{partner_id}{path}{timestamp}{access_token}{shop_id}"
    return hmac.new(key.encode(),base.encode(),hashlib.sha256).hexdigest()


def _exchange_shopee(db,company_id,code,shop_id):
    path="/api/v2/auth/token/get"; ts=int(time.time()); partner_id=int(_env("SHOPEE_PARTNER_ID"))
    params={"partner_id":partner_id,"timestamp":ts,"sign":_shopee_public_sign(path,ts)}
    payload={"code":code,"shop_id":int(shop_id),"partner_id":partner_id}
    with httpx.Client(timeout=30) as c:
        r=c.post("https://partner.shopeemobile.com"+path,params=params,json=payload)
        if r.status_code>=400: raise RuntimeError(f"Shopee OAuth: {r.text[:600]}")
        token=r.json()
    if token.get("error"): raise RuntimeError(f"Shopee OAuth: {token.get('message') or token.get('error')}")
    return _save_connection(db,company_id,"shopee",token.get("access_token","") ,token.get("refresh_token","") ,token.get("expire_in") or token.get("expires_in") or 14400,f"Loja Shopee #{shop_id}",shop_id,token)


def disconnect(db:Session,company_id:int,marketplace:str):
    row=_connection(db,company_id,marketplace)
    if not row: return {"ok":True}
    row.access_token_enc="";row.refresh_token_enc="";row.active=False;row.status="disconnected";row.last_error=""
    db.commit();return {"ok":True}


def _ensure_subscription(db:Session,company_id:int):
    sub=db.query(Subscription).filter(Subscription.company_id==company_id).first()
    if not subscription_is_active(sub): raise RuntimeError("SUBSCRIPTION: Assinatura inativa ou expirada")


def _active_connection(db:Session,company_id:int,marketplace:str):
    row=_connection(db,company_id,marketplace)
    if not row or not row.active or row.status!="connected": raise RuntimeError(f"CONNECT: Conecte sua conta {marketplace} na Central de Integrações")
    return row


def _ml_token(db,row):
    access=decrypt_secret(row.access_token_enc)
    if row.token_expires_at and row.token_expires_at<=datetime.utcnow()+timedelta(minutes=2) and row.refresh_token_enc:
        refresh=decrypt_secret(row.refresh_token_enc)
        data={"grant_type":"refresh_token","client_id":_env("ML_CLIENT_ID"),"client_secret":_env("ML_CLIENT_SECRET"),"refresh_token":refresh}
        with httpx.Client(timeout=30) as c:
            r=c.post("https://api.mercadolibre.com/oauth/token",data=data)
            if r.status_code>=400: raise RuntimeError(f"Mercado Livre token: {r.text[:500]}")
            t=r.json()
        access=t.get("access_token",access);row.access_token_enc=encrypt_secret(access);row.refresh_token_enc=encrypt_secret(t.get("refresh_token",refresh));row.token_expires_at=datetime.utcnow()+timedelta(seconds=max(0,int(t.get("expires_in",21600))-60));db.commit()
    return access


def _shopee_token(db,row):
    access=decrypt_secret(row.access_token_enc)
    if row.token_expires_at and row.token_expires_at<=datetime.utcnow()+timedelta(minutes=2) and row.refresh_token_enc:
        refresh=decrypt_secret(row.refresh_token_enc); path="/api/v2/auth/access_token/get";ts=int(time.time());partner_id=int(_env("SHOPEE_PARTNER_ID"));shop_id=int(row.external_account_id)
        params={"partner_id":partner_id,"timestamp":ts,"sign":_shopee_public_sign(path,ts)}
        payload={"refresh_token":refresh,"shop_id":shop_id,"partner_id":partner_id}
        with httpx.Client(timeout=30) as c:
            r=c.post("https://partner.shopeemobile.com"+path,params=params,json=payload)
            if r.status_code>=400: raise RuntimeError(f"Shopee token: {r.text[:500]}")
            t=r.json()
        if t.get("error"): raise RuntimeError(f"Shopee token: {t.get('message') or t.get('error')}")
        access=t.get("access_token",access);row.access_token_enc=encrypt_secret(access);row.refresh_token_enc=encrypt_secret(t.get("refresh_token",refresh));row.token_expires_at=datetime.utcnow()+timedelta(seconds=max(0,int(t.get("expire_in",14400))-60));db.commit()
    return access


def _listing(db:Session, company_id:int, product_id:int, marketplace:str):
    row=db.query(MarketplaceListing).filter_by(company_id=company_id,product_id=product_id,marketplace=marketplace).first()
    if not row:
        row=MarketplaceListing(company_id=company_id,product_id=product_id,marketplace=marketplace,status="pending")
        db.add(row); db.flush()
    return row


def publish_product(db:Session, product:Product, marketplace:str, company_id:int):
    row=_listing(db,company_id,product.id,marketplace)
    try:
        _ensure_subscription(db,company_id)
        conn=_active_connection(db,company_id,marketplace)
        company=db.get(Company,company_id)
        if marketplace=="mercadolivre": result=_publish_ml(db,conn,product)
        elif marketplace=="shopee": result=_publish_shopee(db,conn,product)
        elif marketplace=="olx": result=_publish_olx(conn,product,company)
        else: raise ValueError("Marketplace inválido")
        row.external_id=str(result.get("external_id") or "")
        row.status=result.get("status","published")
        row.error_message=""
        if row.status=="published": row.published_at=datetime.utcnow()
    except Exception as exc:
        msg=str(exc)
        if "CONNECT:" in msg: row.status="needs_connection"
        elif "PRODUCT:" in msg: row.status="needs_product_data"
        elif "SUBSCRIPTION:" in msg: row.status="subscription_required"
        elif "APP_CONFIG:" in msg: row.status="app_config_required"
        else: row.status="error"
        row.error_message=msg.split(":",1)[-1].strip() if ":" in msg else msg
    db.commit(); db.refresh(row)
    return row


def publish_all(db:Session, product:Product, company_id:int):
    return [publish_product(db,product,m,company_id) for m in MARKETPLACES]


def _image_urls(product):
    return [x.strip() for x in (product.image_urls or "").replace(",","\n").splitlines() if x.strip()][:20]


def _publish_ml(db,row,product:Product):
    if not product.ml_category_id: raise RuntimeError("PRODUCT: Informe a categoria do Mercado Livre no cadastro da peça")
    if product.price<=0 or product.stock<=0: raise RuntimeError("PRODUCT: Mercado Livre exige preço e estoque maiores que zero")
    token=_ml_token(db,row)
    payload={"title":product.name[:60],"category_id":product.ml_category_id,"price":product.price,"currency_id":"BRL","available_quantity":product.stock,"buying_mode":"buy_it_now","listing_type_id":product.ml_listing_type or "gold_special","condition":"used" if product.condition!="new" else "new"}
    images=_image_urls(product)
    if images: payload["pictures"]=[{"source":u} for u in images]
    with httpx.Client(timeout=40) as c:
        r=c.post("https://api.mercadolibre.com/items",json=payload,headers={"Authorization":f"Bearer {token}"})
        if r.status_code>=400: raise RuntimeError(f"Mercado Livre: {r.text[:900]}")
        data=r.json();item_id=data.get("id")
        if item_id and (product.description or product.compatibility):
            text=(product.description or product.name)+(f"\n\nCompatibilidade:\n{product.compatibility}" if product.compatibility else "")
            c.post(f"https://api.mercadolibre.com/items/{item_id}/description",json={"plain_text":text[:50000]},headers={"Authorization":f"Bearer {token}"})
    return {"external_id":item_id,"status":"published"}


def _publish_shopee(db,row,product:Product):
    category=(product.shopee_category_id or "").strip();logistic=(product.shopee_logistic_id or "").strip();image_ids=[x.strip() for x in (product.shopee_image_ids or "").replace(",","\n").splitlines() if x.strip()]
    if not category or not logistic: raise RuntimeError("PRODUCT: Informe categoria e logística da Shopee no cadastro da peça")
    if not image_ids: raise RuntimeError("PRODUCT: Informe os IDs de imagem da Shopee no cadastro da peça")
    token=_shopee_token(db,row);shop_id=int(row.external_account_id);path="/api/v2/product/add_item";ts=int(time.time())
    params={"partner_id":int(_env("SHOPEE_PARTNER_ID")),"timestamp":ts,"access_token":token,"shop_id":shop_id,"sign":_shopee_shop_sign(path,ts,token,shop_id)}
    payload={"item_name":product.name,"description":product.description or product.name,"category_id":int(category),"original_price":product.price,"weight":max(.01,float(product.weight or 1)),"dimension":{"package_length":max(1,int(product.package_length or 20)),"package_width":max(1,int(product.package_width or 20)),"package_height":max(1,int(product.package_height or 20))},"seller_stock":[{"stock":max(0,int(product.stock))}],"image":{"image_id_list":image_ids[:9]},"logistic_info":[{"logistic_id":int(logistic),"enabled":True}]}
    with httpx.Client(timeout=40) as c:
        r=c.post("https://partner.shopeemobile.com"+path,params=params,json=payload)
        if r.status_code>=400: raise RuntimeError(f"Shopee: {r.text[:900]}")
        data=r.json()
    if data.get("error"): raise RuntimeError(f"Shopee: {data.get('message') or data.get('error')}")
    return {"external_id":(data.get("response") or {}).get("item_id"),"status":"published"}


def _digits(value): return "".join(ch for ch in (value or "") if ch.isdigit())


def _publish_olx(row,product:Product,company:Company):
    if not product.olx_category_id: raise RuntimeError("PRODUCT: Informe a categoria OLX no cadastro da peça")
    images=_image_urls(product)
    phone=_digits(company.phone);zipcode=_digits(company.cep)
    if not images: raise RuntimeError("PRODUCT: OLX exige ao menos uma URL de imagem")
    if len(phone) not in {10,11}: raise RuntimeError("PRODUCT: Cadastre um telefone com DDD nas Informações da Empresa para publicar na OLX")
    if len(zipcode)!=8: raise RuntimeError("PRODUCT: Cadastre um CEP válido nas Informações da Empresa para publicar na OLX")
    token=decrypt_secret(row.access_token_enc)
    internal_id=f"CDM{company.id}_{product.id}"[:19]
    ad={"id":internal_id,"operation":"insert","category":int(product.olx_category_id),"Subject":product.name[:90],"Body":((product.description or product.name)+(f"\n\nCompatibilidade:\n{product.compatibility}" if product.compatibility else ""))[:6000],"Phone":int(phone),"type":"s","price":int(round(product.price)),"zipcode":zipcode,"images":images}
    payload={"access_token":token,"ad_list":[ad]}
    with httpx.Client(timeout=40) as c:
        r=c.put("https://apps.olx.com.br/autoupload/import",json=payload,headers={"Content-Type":"application/json"})
        if r.status_code>=400: raise RuntimeError(f"OLX: {r.text[:900]}")
        data=r.json()
    if data.get("statusCode") not in {0,-8,None}: raise RuntimeError(f"OLX: {data.get('statusMessage') or data}")
    return {"external_id":data.get("token") or internal_id,"status":"processing"}


def refresh_listing(db:Session, listing:MarketplaceListing):
    if listing.marketplace!="olx" or not listing.external_id: return listing
    conn=_active_connection(db,listing.company_id,"olx")
    token=decrypt_secret(conn.access_token_enc)
    with httpx.Client(timeout=30) as c:
        r=c.post(f"https://apps.olx.com.br/autoupload/import/{listing.external_id}",json={"access_token":token})
        if r.status_code>=400: raise RuntimeError(f"OLX: {r.text[:700]}")
        data=r.json()
    ads=data.get("ads") or {}
    ad=next(iter(ads.values()),{}) if isinstance(ads,dict) else (ads[0] if ads else {})
    status=ad.get("status") or data.get("autoupload_status")
    if status in {"accepted","accept"}:
        listing.status="published";listing.published_at=datetime.utcnow();listing.error_message="";listing.external_id=str(ad.get("list_id") or listing.external_id)
    elif status in {"refused","error"}:
        listing.status="error";listing.error_message=json.dumps(ad.get("message") or data,ensure_ascii=False)[:1000]
    else:
        listing.status="processing"
    db.commit();db.refresh(listing);return listing
