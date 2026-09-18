import hashlib
import hmac
import json
import os
import time
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from dotenv import load_dotenv
from jose import JWTError
from sqlalchemy.orm import Session

from ..crypto import encrypt_secret, decrypt_secret, rotate_secret
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




def _safe_error(value: str):
    text = str(value or "Erro desconhecido")
    for secret_name in ("ML_CLIENT_SECRET", "SHOPEE_PARTNER_KEY", "OLX_CLIENT_SECRET"):
        secret = _env(secret_name)
        if secret:
            text = text.replace(secret, "***")
    # Evita gravar tokens caso algum provedor os inclua numa mensagem de erro.
    import re
    text = re.sub(r"APP_USR-[A-Za-z0-9\-_]+", "APP_USR-***", text)
    text = re.sub(r"TG-[A-Za-z0-9\-_]+", "TG-***", text)
    return text[:1000]


def marketplace_diagnostics(db: Session, company_id: int, marketplace: str):
    conn = _connection(db, company_id, marketplace)
    return {
        "marketplace": marketplace,
        "app_ready": app_ready(marketplace),
        "redirect_uri": _redirect_uri(marketplace),
        "public_base_url": _public_base_url(),
        "connected": bool(conn and conn.active and conn.status == "connected"),
        "status": conn.status if conn else "disconnected",
        "account_name": conn.account_name if conn else "",
        "last_error": conn.last_error if conn else "",
        "has_refresh_token": bool(conn and conn.refresh_token_enc),
        "token_expires_at": conn.token_expires_at.isoformat() if conn and conn.token_expires_at else None,
    }


def record_connection_error(db: Session, company_id: int, marketplace: str, error):
    row = _connection(db, company_id, marketplace, create=True)
    row.active = False
    row.status = "error"
    row.last_error = _safe_error(str(error))
    db.commit()
    return row


def authorization_url(company_id:int, marketplace:str):
    if marketplace not in MARKETPLACES: raise ValueError("Canal de venda inválido")
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
    raise RuntimeError("Canal de venda inválido")


def _ml_oauth_error(response):
    try:
        data=response.json()
        code=str(data.get("error") or data.get("code") or "")
        message=str(data.get("message") or data.get("error_description") or response.text[:500])
    except Exception:
        code=""; message=response.text[:500]
    low=(code+" "+message).lower()
    if "invalid_operator" in low:
        return "Use a conta principal/administradora do Mercado Livre; contas de colaborador não podem autorizar a aplicação."
    if "redirect" in low:
        return f"Redirect URI recusado. Confira se no Mercado Livre está exatamente: {_redirect_uri('mercadolivre')}"
    if "invalid_client" in low or "client_secret" in low:
        return "Client ID ou Client Secret da aplicação estão inválidos. Revise as variáveis ML_CLIENT_ID e ML_CLIENT_SECRET no Render."
    if "invalid_grant" in low or "validating grant" in low:
        return f"Código de autorização inválido/expirado ou Redirect URI diferente. Tente Conectar novamente e confirme: {_redirect_uri('mercadolivre')}"
    return f"Mercado Livre OAuth: {message}"

def _exchange_ml(db,company_id,code):
    data={"grant_type":"authorization_code","client_id":_env("ML_CLIENT_ID"),"client_secret":_env("ML_CLIENT_SECRET"),"code":code,"redirect_uri":_redirect_uri("mercadolivre")}
    with httpx.Client(timeout=30) as c:
        r=c.post("https://api.mercadolibre.com/oauth/token",data=data)
        if r.status_code>=400: raise RuntimeError(_ml_oauth_error(r))
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
    if not row or not row.active or row.status!="connected":
        raise RuntimeError(f"CONNECT: Conecte sua conta {marketplace} na Central de Integrações")

    changed=False
    if row.access_token_enc:
        row.access_token_enc, rotated=rotate_secret(row.access_token_enc)
        changed=changed or rotated
    if row.refresh_token_enc:
        row.refresh_token_enc, rotated=rotate_secret(row.refresh_token_enc)
        changed=changed or rotated
    if changed:
        db.commit()
        db.refresh(row)
    return row


def _ml_token(db,row):
    access=decrypt_secret(row.access_token_enc)
    if row.token_expires_at and row.token_expires_at<=datetime.utcnow()+timedelta(minutes=2) and row.refresh_token_enc:
        refresh=decrypt_secret(row.refresh_token_enc)
        data={"grant_type":"refresh_token","client_id":_env("ML_CLIENT_ID"),"client_secret":_env("ML_CLIENT_SECRET"),"refresh_token":refresh}
        with httpx.Client(timeout=30) as c:
            r=c.post("https://api.mercadolibre.com/oauth/token",data=data)
            if r.status_code>=400: raise RuntimeError(_ml_oauth_error(r))
            t=r.json()
        access=t.get("access_token",access);row.access_token_enc=encrypt_secret(access);row.refresh_token_enc=encrypt_secret(t.get("refresh_token",refresh));row.token_expires_at=datetime.utcnow()+timedelta(seconds=max(0,int(t.get("expires_in",21600))-60));db.commit()
    return access



def _ml_normalize(value):
    text=unicodedata.normalize("NFKD",str(value or ""))
    text="".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(
        text.lower().replace("/"," ").replace("-"," ").replace("_"," ").split()
    )


def _ml_vehicle_segment(product):
    try:
        raw=json.loads(getattr(product,"ml_attributes_json","{}") or "{}")
    except Exception:
        raw={}
    if not isinstance(raw,dict):
        return ""

    internal=str(raw.get("_CDM_VEHICLE_SEGMENT") or "").strip()
    if internal in {"car_pickup","truck"}:
        return internal

    legacy=_ml_normalize(raw.get("VEHICLE_TYPE"))
    if "caminhao" in legacy:
        return "truck"
    if "carro" in legacy or "caminhonete" in legacy or "automovel" in legacy:
        return "car_pickup"
    return ""


def _ml_vehicle_value(category_attrs, segment):
    if segment not in {"car_pickup","truck"}:
        return ""
    vehicle_attr=next(
        (a for a in (category_attrs or []) if str(a.get("id") or "")=="VEHICLE_TYPE"),
        None,
    )
    if not vehicle_attr:
        return ""

    for value in vehicle_attr.get("values") or []:
        name=str(value.get("name") or "").strip()
        normalized=_ml_normalize(name)
        if segment=="truck" and (
            "caminhao" in normalized
            or "linha pesada" in normalized
        ):
            return name
        if segment=="car_pickup" and (
            ("carro" in normalized or "caminhonete" in normalized or "automovel" in normalized)
            and "caminhao" not in normalized
        ):
            return name
    return ""


def ml_category_suggestions(
    db:Session,
    company_id:int,
    title:str,
    limit:int=3,
    vehicle_type:str="",
):
    row=_active_connection(db,company_id,"mercadolivre")
    token=_ml_token(db,row)
    q=(title or "").strip()
    if not q:
        raise RuntimeError("Informe o título da peça para sugerir a categoria")

    segment=(vehicle_type or "").strip()
    if segment not in {"","car_pickup","truck"}:
        raise RuntimeError("Tipo de veículo inválido")

    wanted=max(1,min(int(limit),8))
    headers={"Authorization":f"Bearer {token}"}
    out=[]
    seen=set()
    category_cache={}

    def category_details(client, category_id):
        cid=str(category_id or "").strip()
        if not cid:
            return {}, []
        if cid in category_cache:
            return category_cache[cid]

        info={}
        attrs=[]
        cr=client.get(
            f"https://api.mercadolibre.com/categories/{cid}",
            headers=headers,
        )
        if cr.status_code<400:
            info=cr.json() or {}

        ar=client.get(
            f"https://api.mercadolibre.com/categories/{cid}/attributes",
            headers=headers,
        )
        if ar.status_code<400:
            attrs=ar.json() or []

        category_cache[cid]=(info,attrs)
        return info,attrs

    def try_add(
        client,
        category_id,
        category_name="",
        domain_id="",
        domain_name="",
        source="predictor",
    ):
        cid=str(category_id or "").strip()
        if not cid or cid in seen:
            return False

        info,attrs=category_details(client,cid)
        name=str(category_name or info.get("name") or cid)
        path_names=[
            str(x.get("name") or "")
            for x in (info.get("path_from_root") or [])
        ]
        path_text=_ml_normalize(" ".join(path_names+[name,domain_name or ""]))

        vehicle_attr=next(
            (a for a in attrs if str(a.get("id") or "")=="VEHICLE_TYPE"),
            None,
        )
        vehicle_value=""

        if segment:
            if vehicle_attr:
                vehicle_value=_ml_vehicle_value(attrs,segment)
                if not vehicle_value:
                    return False
            else:
                if segment=="truck":
                    if "caminhao" not in path_text and "linha pesada" not in path_text:
                        return False
                elif segment=="car_pickup":
                    if "caminhao" in path_text and "carro" not in path_text and "caminhonete" not in path_text:
                        return False

        seen.add(cid)
        out.append({
            "category_id":cid,
            "category_name":name,
            "domain_id":domain_id or "",
            "domain_name":domain_name or "",
            "vehicle_type":segment,
            "vehicle_type_value":vehicle_value,
            "source":source,
            "path":" > ".join(path_names),
        })
        return True

    if segment=="truck":
        predictor_queries=[
            f"{q} caminhão",
            f"{q} para caminhão",
            f"{q} linha pesada",
            f"{q} truck",
        ]
    elif segment=="car_pickup":
        predictor_queries=[
            f"{q} carro caminhonete",
            q,
        ]
    else:
        predictor_queries=[q]

    with httpx.Client(timeout=30) as c:
        for search_q in predictor_queries:
            r=c.get(
                "https://api.mercadolibre.com/sites/MLB/domain_discovery/search",
                params={"q":search_q,"limit":8},
                headers=headers,
            )
            if r.status_code>=400:
                continue

            for item in r.json() or []:
                try_add(
                    c,
                    item.get("category_id"),
                    item.get("category_name") or "",
                    item.get("domain_id") or "",
                    item.get("domain_name") or "",
                    source="predictor",
                )
                if len(out)>=wanted:
                    return out[:wanted]

        # O preditor pode não reconhecer títulos genéricos de linha pesada.
        # Nesse caso, procura anúncios semelhantes e aproveita somente
        # categorias que passam pela mesma validação de segmento.
        if segment=="truck" and len(out)<wanted:
            similar_queries=[
                f"{q} caminhão",
                f"{q} caminhão usado",
                f"{q} linha pesada",
            ]
            for search_q in similar_queries:
                sr=c.get(
                    "https://api.mercadolibre.com/sites/MLB/search",
                    params={"q":search_q,"limit":50},
                    headers=headers,
                )
                if sr.status_code>=400:
                    continue

                data=sr.json() or {}
                for item in data.get("results") or []:
                    try_add(
                        c,
                        item.get("category_id"),
                        "",
                        item.get("domain_id") or "",
                        "",
                        source="similar_items",
                    )
                    if len(out)>=wanted:
                        return out[:wanted]

                # Algumas respostas expõem categorias úteis nos filtros,
                # mesmo quando os primeiros resultados não ajudam.
                filter_groups=(data.get("filters") or [])+(data.get("available_filters") or [])
                for group in filter_groups:
                    if str(group.get("id") or "")!="category":
                        continue
                    for value in group.get("values") or []:
                        try_add(
                            c,
                            value.get("id"),
                            value.get("name") or "",
                            source="search_filter",
                        )
                        if len(out)>=wanted:
                            return out[:wanted]

    return out[:wanted]


def _ml_item_attributes(client,token,product:Product):
    r=client.get(
        f"https://api.mercadolibre.com/categories/{product.ml_category_id}/attributes",
        headers={"Authorization":f"Bearer {token}"},
    )
    if r.status_code>=400:
        return []

    category_attrs=r.json() or []
    allowed={str(a.get("id")) for a in category_attrs}
    candidates={
        "BRAND":product.brand,
        "MODEL":product.model,
        "PART_NUMBER":product.oem,
        "OEM":product.oem,
    }

    attrs=[]
    for aid,value in candidates.items():
        if aid in allowed and value:
            attrs.append({"id":aid,"value_name":str(value)[:255]})

    segment=_ml_vehicle_segment(product)
    vehicle_value=_ml_vehicle_value(category_attrs,segment)
    if "VEHICLE_TYPE" in allowed and vehicle_value:
        attrs.append({"id":"VEHICLE_TYPE","value_name":vehicle_value})

    if "ITEM_CONDITION" in allowed:
        attrs.append({
            "id":"ITEM_CONDITION",
            "value_name":"Novo" if product.condition=="new" else (
                "Recondicionado" if product.condition=="reconditioned" else "Usado"
            ),
        })
    return attrs


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
        if marketplace=="mercadolivre": result=_publish_ml(db,conn,product,row)
        elif marketplace=="shopee": result=_publish_shopee(db,conn,product,row)
        elif marketplace=="olx": result=_publish_olx(conn,product,company,row)
        else: raise ValueError("Canal de venda inválido")
        row.external_id=str(result.get("external_id") or row.external_id or "")
        row.status=result.get("status","published")
        row.error_message=""
        if row.status=="published": row.published_at=datetime.utcnow()
    except Exception as exc:
        msg=_safe_error(str(exc))
        if "CONNECT:" in msg: row.status="needs_connection"
        elif "PRODUCT:" in msg: row.status="needs_product_data"
        elif "SUBSCRIPTION:" in msg: row.status="subscription_required"
        elif "APP_CONFIG:" in msg: row.status="app_config_required"
        else: row.status="error"
        row.error_message=msg.split(":",1)[-1].strip() if ":" in msg else msg
    db.commit(); db.refresh(row)
    return row


def publish_all(db:Session, product:Product, company_id:int):
    enabled={
        "mercadolivre": bool(getattr(product,"publish_mercadolivre",True)),
        "shopee": bool(getattr(product,"publish_shopee",True)),
        "olx": bool(getattr(product,"publish_olx",True)),
    }
    return [publish_product(db,product,m,company_id) for m in MARKETPLACES if enabled.get(m,False)]


def _public_base_url():
    return (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("FRONTEND_URL") or "http://localhost:8000").rstrip("/")


def _image_urls(product):
    text_value=product.image_urls or ""
    source=text_value if "data:image/" in text_value else text_value.replace(",","\n")
    raw=[x.strip() for x in source.splitlines() if x.strip()][:20]
    out=[]
    for idx,value in enumerate(raw):
        if value.startswith("data:image/"):
            out.append(f"{_public_base_url()}/api/products/public/{product.id}/images/{idx}")
        else:
            out.append(value)
    return out


def _extra_ml_attributes(product:Product):
    try:
        raw=json.loads(getattr(product,"ml_attributes_json","{}") or "{}")
    except Exception:
        return []

    segment=_ml_vehicle_segment(product)

    if isinstance(raw,list):
        return [
            x for x in raw
            if isinstance(x,dict)
            and x.get("id")
            and not str(x.get("id") or "").startswith("_CDM_")
            and not (segment and str(x.get("id") or "")=="VEHICLE_TYPE")
        ]

    if not isinstance(raw,dict):
        return []

    out=[]
    for aid,value in raw.items():
        aid=str(aid)
        if aid.startswith("_CDM_"):
            continue
        if segment and aid=="VEHICLE_TYPE":
            continue
        if value in (None,""):
            continue
        out.append({"id":aid,"value_name":str(value)[:255]})
    return out


def _ml_user_profile(client,token,row):
    seller_id=str(row.external_account_id or "").strip()
    if not seller_id: return {"tags":[]}
    r=client.get(f"https://api.mercadolibre.com/users/{seller_id}",headers={"Authorization":f"Bearer {token}"})
    if r.status_code>=400: raise RuntimeError(f"Mercado Livre usuário: {r.text[:700]}")
    return r.json()


def _ml_store_list(client,token,row):
    seller_id=str(row.external_account_id or "").strip()
    r=client.get(f"https://api.mercadolibre.com/users/{seller_id}/stores/search",params={"tags":"stock_location"},headers={"Authorization":f"Bearer {token}"})
    if r.status_code>=400: raise RuntimeError(f"Mercado Livre depósitos: {r.text[:700]}")
    return r.json().get("results") or []


def _ml_pick_store(client,token,row,product:Product):
    stores=_ml_store_list(client,token,row)
    wanted=str(getattr(product,"ml_store_id","") or "")
    store=next((x for x in stores if str(x.get("id"))==wanted),None) if wanted else None
    if not store and len(stores)==1:
        store=stores[0]
        product.ml_store_id=str(store.get("id") or "")
        product.ml_network_node_id=str(store.get("network_node_id") or "")
    if not store:
        if not stores: raise RuntimeError("PRODUCT: Sua conta Mercado Livre usa estoque por depósito, mas nenhum depósito de estoque foi encontrado")
        raise RuntimeError("PRODUCT: Escolha o depósito do Mercado Livre na configuração deste produto")
    return {"store_id":str(store.get("id") or ""),"network_node_id":str(store.get("network_node_id") or getattr(product,"ml_network_node_id","") or "")}


def _ml_payload(client,token,product:Product,for_update=False,use_up=False,multiwarehouse=False):
    attrs=_ml_item_attributes(client,token,product)
    # Campos extras preenchidos no modal Mercado Livre sobrescrevem os gerados automaticamente.
    extra=_extra_ml_attributes(product)
    byid={str(x.get("id")):x for x in attrs if x.get("id")}
    for x in extra: byid[str(x.get("id"))]=x
    payload={"price":float(product.price)}
    if not multiwarehouse:
        payload["available_quantity"]=max(0,int(product.stock))
    if not for_update:
        payload.update({
            "category_id":product.ml_category_id,"currency_id":"BRL",
            "buying_mode":"buy_it_now","listing_type_id":product.ml_listing_type or "gold_special",
            "condition":"new" if product.condition=="new" else "used","channels":["marketplace"],
        })
        if use_up: payload["family_name"]=product.name[:120]
        else: payload["title"]=product.name[:60]
    else:
        # Em sellers User Products o Mercado Livre gera title; editar title diretamente retorna erro.
        if use_up: payload["family_name"]=product.name[:120]
        else: payload["title"]=product.name[:60]
    if byid: payload["attributes"]=list(byid.values())
    shipping_mode=(getattr(product,"ml_shipping_mode","") or "").strip()
    if shipping_mode:
        payload["shipping"]={"mode":shipping_mode,"free_shipping":bool(getattr(product,"ml_free_shipping",False)),"local_pick_up":bool(getattr(product,"ml_local_pickup",True))}
    images=_image_urls(product)
    if images: payload["pictures"]=[{"source":u} for u in images]
    if getattr(product,"ml_has_warranty",False) and getattr(product,"ml_warranty_text",""):
        payload["warranty"]=str(product.ml_warranty_text).strip()[:200]
    return payload


def _ml_sync_stock_client(client,token,row,product:Product,item_id:str,profile:dict|None=None):
    profile=profile or _ml_user_profile(client,token,row)
    tags=profile.get("tags") or []
    headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"}
    if "warehouse_management" not in tags:
        r=client.put(f"https://api.mercadolibre.com/items/{item_id}",json={"available_quantity":max(0,int(product.stock))},headers=headers)
        if r.status_code>=400: raise RuntimeError(f"Mercado Livre estoque: {r.text[:700]}")
        return {"mode":"item"}
    # Multi-origem: estoque é gerenciado pelo User Product e exige x-version.
    ir=client.get(f"https://api.mercadolibre.com/items/{item_id}",headers={"Authorization":f"Bearer {token}"})
    if ir.status_code>=400: raise RuntimeError(f"Mercado Livre item: {ir.text[:700]}")
    up=str(ir.json().get("user_product_id") or "")
    if not up: raise RuntimeError("Mercado Livre: item sem user_product_id para sincronizar estoque multi-origem")
    sr=client.get(f"https://api.mercadolibre.com/user-products/{up}/stock",headers={"Authorization":f"Bearer {token}"})
    if sr.status_code>=400: raise RuntimeError(f"Mercado Livre estoque UP: {sr.text[:700]}")
    version=sr.headers.get("x-version")
    locations=sr.json().get("locations") or []
    seller=[x for x in locations if x.get("type")=="seller_warehouse"]
    if not seller:
        # Fulfillment é gerido pelo próprio Mercado Livre e não aceita alteração do seller.
        if any(x.get("type")=="meli_facility" for x in locations): return {"mode":"meli_facility","user_product_id":up}
        raise RuntimeError("Mercado Livre: não há depósito do vendedor inicializado para este User Product")
    wanted=str(getattr(product,"ml_store_id","") or "")
    target=next((x for x in seller if str(x.get("store_id"))==wanted),None) if wanted else None
    if not target and len(seller)==1: target=seller[0]
    if not target:
        raise RuntimeError("Mercado Livre: selecione no produto qual depósito deve receber a sincronização de estoque")
    out=[]
    for loc in seller:
        out.append({"store_id":str(loc.get("store_id") or ""),"network_node_id":str(loc.get("network_node_id") or ""),"quantity":max(0,int(product.stock)) if loc is target else int(loc.get("quantity") or 0)})
    if not version: raise RuntimeError("Mercado Livre: x-version do estoque não retornado")
    rr=client.put(f"https://api.mercadolibre.com/user-products/{up}/stock/type/seller_warehouse",json={"locations":out},headers={**headers,"x-version":str(version)})
    if rr.status_code==409:
        # Uma atualização concorrente pode trocar a versão. Tenta novamente uma vez.
        sr=client.get(f"https://api.mercadolibre.com/user-products/{up}/stock",headers={"Authorization":f"Bearer {token}"})
        version=sr.headers.get("x-version")
        fresh=sr.json().get("locations") or []
        seller=[x for x in fresh if x.get("type")=="seller_warehouse"]
        target=next((x for x in seller if str(x.get("store_id"))==str(target.get("store_id"))),None)
        out=[{"store_id":str(loc.get("store_id") or ""),"network_node_id":str(loc.get("network_node_id") or ""),"quantity":max(0,int(product.stock)) if target and str(loc.get("store_id"))==str(target.get("store_id")) else int(loc.get("quantity") or 0)} for loc in seller]
        rr=client.put(f"https://api.mercadolibre.com/user-products/{up}/stock/type/seller_warehouse",json={"locations":out},headers={**headers,"x-version":str(version or "")})
    if rr.status_code>=400: raise RuntimeError(f"Mercado Livre estoque multi-origem: {rr.text[:900]}")
    return {"mode":"seller_warehouse","user_product_id":up}



def ml_connection_check(db:Session, company_id:int):
    row=_active_connection(db,company_id,"mercadolivre")
    token=_ml_token(db,row)
    headers={"Authorization":f"Bearer {token}"}
    with httpx.Client(timeout=30) as c:
        r=c.get("https://api.mercadolibre.com/users/me",headers=headers)
    if r.status_code>=400:
        raise RuntimeError(f"Mercado Livre conexão: {r.text[:700]}")
    profile=r.json()
    returned_id=str(profile.get("id") or "")
    expected_id=str(row.external_account_id or "")
    if expected_id and returned_id and expected_id!=returned_id:
        raise RuntimeError("Mercado Livre retornou uma conta diferente da conta conectada")
    tags=profile.get("tags") or []
    return {
        "ok":True,
        "connected":True,
        "account_id":returned_id or expected_id,
        "account_name":profile.get("nickname") or row.account_name or "",
        "site_id":profile.get("site_id") or "MLB",
        "token_expires_at":row.token_expires_at.isoformat() if row.token_expires_at else None,
        "user_products":"user_product_seller" in tags,
        "warehouse_management":"warehouse_management" in tags,
        "multiwarehouse":"multiwarehouse" in tags,
        "redirect_uri":_redirect_uri("mercadolivre"),
        "notifications_callback":f"{_public_base_url()}/api/marketplaces/webhooks/mercadolivre",
    }


def ml_publication_preflight(db:Session, company_id:int, product:Product):
    row=_active_connection(db,company_id,"mercadolivre")
    token=_ml_token(db,row)
    errors=[]
    warnings=[]
    vehicle_segment=_ml_vehicle_segment(product)

    if not vehicle_segment:
        errors.append("Escolha Carro/Caminhonete ou Caminhão")
    if not product.ml_category_id:
        errors.append("Informe a categoria do Mercado Livre")
    if float(product.price or 0)<=0:
        errors.append("Informe um preço maior que zero")
    if int(product.stock or 0)<=0:
        errors.append("Informe estoque maior que zero")
    if not (product.name or "").strip():
        errors.append("Informe o nome/título da peça")

    headers={"Authorization":f"Bearer {token}"}
    profile={}
    payload={}
    strict_required=[]
    conditional=[]
    supplied=set()

    with httpx.Client(timeout=30) as c:
        profile=_ml_user_profile(c,token,row)
        tags=profile.get("tags") or []
        use_up="user_product_seller" in tags
        multiwarehouse="warehouse_management" in tags

        if product.ml_category_id:
            ar=c.get(
                f"https://api.mercadolibre.com/categories/{product.ml_category_id}/attributes",
                headers=headers,
            )
            if ar.status_code>=400:
                errors.append(f"Categoria inválida ou indisponível: {ar.text[:300]}")
                attrs=[]
            else:
                attrs=ar.json() or []

            for attr in attrs:
                aid=str(attr.get("id") or "")
                tags_attr=attr.get("tags") or {}
                if tags_attr.get("required") or tags_attr.get("catalog_required"):
                    strict_required.append({"id":aid,"name":attr.get("name") or aid})
                elif tags_attr.get("conditional_required"):
                    conditional.append({"id":aid,"name":attr.get("name") or aid})

            vehicle_attr=next(
                (a for a in attrs if str(a.get("id") or "")=="VEHICLE_TYPE"),
                None,
            )
            if vehicle_segment and vehicle_attr:
                vehicle_value=_ml_vehicle_value(attrs,vehicle_segment)
                if not vehicle_value:
                    label="Caminhão" if vehicle_segment=="truck" else "Carro/Caminhonete"
                    errors.append(
                        f"A categoria selecionada não aceita o Tipo de veículo {label}"
                    )

            try:
                payload=_ml_payload(
                    c,token,product,
                    for_update=False,
                    use_up=use_up,
                    multiwarehouse=multiwarehouse,
                )
                supplied={
                    str(x.get("id") or "")
                    for x in (payload.get("attributes") or [])
                    if x.get("id")
                }
            except Exception as exc:
                errors.append(str(exc))

    missing=[x for x in strict_required if x["id"] and x["id"] not in supplied]
    if missing:
        errors.append(
            "Faltam atributos obrigatórios: "
            + ", ".join(x["name"] for x in missing[:12])
        )

    missing_cond=[x for x in conditional if x["id"] and x["id"] not in supplied]
    if missing_cond:
        warnings.append(
            "A categoria possui atributos condicionais que podem ser exigidos: "
            + ", ".join(x["name"] for x in missing_cond[:12])
        )

    images=_image_urls(product)
    if not images:
        warnings.append("A peça está sem imagem para o anúncio")
    description_text=_ml_description_text(product)

    return {
        "ok":True,
        "ready":len(errors)==0,
        "errors":errors,
        "warnings":warnings,
        "account":{
            "id":str(row.external_account_id or ""),
            "name":row.account_name or "",
            "user_products":"user_product_seller" in (profile.get("tags") or []),
            "warehouse_management":"warehouse_management" in (profile.get("tags") or []),
        },
        "product":{
            "id":product.id,
            "sku":product.sku or "",
            "name":product.name or "",
            "category_id":product.ml_category_id or "",
            "vehicle_type":vehicle_segment,
            "price":float(product.price or 0),
            "stock":int(product.stock or 0),
            "images":len(images),
        },
        "required_attributes":strict_required,
        "missing_required_attributes":missing,
        "payload_preview":payload,
        "description":{
            "mode":"manual" if (product.description or "").strip() else "automatic",
            "preview":description_text,
        },
    }


def _ml_condition_label(product:Product):
    value=str(getattr(product,"condition","") or "").strip().lower()
    if value=="new":
        return "Nova"
    if value=="reconditioned":
        return "Recondicionada"
    return "Usada"


def _ml_description_text(product:Product):
    manual=str(getattr(product,"description","") or "").strip()
    compatibility=str(getattr(product,"compatibility","") or "").strip()

    if manual:
        parts=[manual]
    else:
        title=str(getattr(product,"name","") or "").strip() or "Peça automotiva"
        lines=[title,"","Informações da peça:"]

        sku=str(getattr(product,"sku","") or "").strip()
        if sku:
            lines.append(f"- SKU: {sku}")

        brand=str(getattr(product,"brand","") or "").strip()
        model=str(getattr(product,"model","") or "").strip()
        year=getattr(product,"year",None)
        vehicle=[]
        if brand:
            vehicle.append(brand)
        if model:
            vehicle.append(model)
        if year:
            vehicle.append(str(year))
        if vehicle:
            lines.append("- Aplicação informada: " + " ".join(vehicle))

        oem=str(getattr(product,"oem","") or "").strip()
        if oem:
            lines.append(f"- Código/OEM: {oem}")

        side=str(getattr(product,"side","") or "").strip()
        if side:
            lines.append(f"- Lado: {side}")

        position=str(getattr(product,"position","") or "").strip()
        if position:
            lines.append(f"- Posição: {position}")

        lines.append(f"- Condição: {_ml_condition_label(product)}")
        lines.extend([
            "",
            "As informações acima foram geradas automaticamente a partir do cadastro da peça no CDM Desmontes.",
            "Confira as fotos, códigos e aplicação antes da compra.",
        ])
        parts=["\n".join(lines)]

    if compatibility:
        parts.extend(["Compatibilidade:", compatibility])

    warranty=""
    if bool(getattr(product,"ml_has_warranty",False)):
        warranty=str(getattr(product,"ml_warranty_text","") or "").strip()
    if warranty:
        parts.extend(["Garantia:", warranty])

    return "\n\n".join(x.strip() for x in parts if str(x or "").strip())[:50000]

def _ml_upsert_description(client,token,item_id,text):
    plain=str(text or "").strip()
    if not plain:
        return {"updated":False}
    headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"}
    url=f"https://api.mercadolibre.com/items/{item_id}/description"
    current=client.get(url,headers={"Authorization":f"Bearer {token}"})
    payload={"plain_text":plain[:50000]}
    if current.status_code==200:
        r=client.put(url,params={"api_version":"2"},json=payload,headers=headers)
    elif current.status_code==404:
        r=client.post(url,json=payload,headers=headers)
    else:
        raise RuntimeError(f"Mercado Livre descrição: {current.text[:700]}")
    if r.status_code>=400:
        raise RuntimeError(f"Mercado Livre descrição: {r.text[:900]}")
    return {"updated":True}


def process_ml_notification_background(body:dict):
    from ..db import SessionLocal
    db=SessionLocal()
    try:
        process_ml_notification(db,body)
    except Exception as exc:
        db.rollback()
        print("Mercado Livre webhook worker warning:",_safe_error(str(exc)))
    finally:
        db.close()


def _publish_ml(db,row,product:Product,listing:MarketplaceListing):
    if not product.ml_category_id: raise RuntimeError("PRODUCT: Informe a categoria do Mercado Livre no cadastro da peça")
    if product.price<=0 or product.stock<=0: raise RuntimeError("PRODUCT: Mercado Livre exige preço e estoque maiores que zero")
    token=_ml_token(db,row)
    headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"}
    with httpx.Client(timeout=45) as c:
        profile=_ml_user_profile(c,token,row)
        tags=profile.get("tags") or []
        use_up="user_product_seller" in tags
        multiwarehouse="warehouse_management" in tags
        existing=(listing.external_id or "").strip()
        if existing.upper().startswith("MLB"):
            payload=_ml_payload(c,token,product,for_update=True,use_up=use_up,multiwarehouse=multiwarehouse)
            r=c.put(f"https://api.mercadolibre.com/items/{existing}",json=payload,headers=headers)
            if r.status_code>=400: raise RuntimeError(f"Mercado Livre: {r.text[:1200]}")
            item_id=existing
            if multiwarehouse: _ml_sync_stock_client(c,token,row,product,item_id,profile)
        else:
            payload=_ml_payload(c,token,product,for_update=False,use_up=use_up,multiwarehouse=multiwarehouse)
            endpoint="https://api.mercadolibre.com/items"
            if multiwarehouse:
                store=_ml_pick_store(c,token,row,product)
                payload["stock_locations"]=[{"store_id":store["store_id"],"network_node_id":store["network_node_id"],"quantity":max(0,int(product.stock))}]
                endpoint="https://api.mercadolibre.com/items/multiwarehouse"
            r=c.post(endpoint,json=payload,headers=headers)
            if r.status_code>=400: raise RuntimeError(f"Mercado Livre: {r.text[:1200]}")
            data=r.json(); item_id=data.get("id")
            if multiwarehouse and getattr(product,"ml_store_id",""): db.commit()
        description_text=_ml_description_text(product)
        if item_id and description_text:
            _ml_upsert_description(c,token,item_id,description_text)
    return {"external_id":item_id,"status":"published"}


def _shopee_call(db,row,path,payload=None,method="POST"):
    token=_shopee_token(db,row);shop_id=int(row.external_account_id);ts=int(time.time())
    params={"partner_id":int(_env("SHOPEE_PARTNER_ID")),"timestamp":ts,"access_token":token,"shop_id":shop_id,"sign":_shopee_shop_sign(path,ts,token,shop_id)}
    with httpx.Client(timeout=45) as c:
        if method=="GET": r=c.get("https://partner.shopeemobile.com"+path,params={**params,**(payload or {})})
        else: r=c.post("https://partner.shopeemobile.com"+path,params=params,json=payload or {})
    if r.status_code>=400: raise RuntimeError(f"Shopee: {r.text[:1000]}")
    data=r.json()
    if data.get("error"): raise RuntimeError(f"Shopee: {data.get('message') or data.get('error')}")
    return data


def _shopee_upload_images(db,row,product:Product):
    ids=[]
    for url in _image_urls(product)[:9]:
        try:
            token=_shopee_token(db,row);shop_id=int(row.external_account_id);path="/api/v2/media_space/upload_image";ts=int(time.time())
            params={"partner_id":int(_env("SHOPEE_PARTNER_ID")),"timestamp":ts,"access_token":token,"shop_id":shop_id,"sign":_shopee_shop_sign(path,ts,token,shop_id)}
            with httpx.Client(timeout=45,follow_redirects=True) as c:
                img=c.get(url)
                img.raise_for_status()
                r=c.post("https://partner.shopeemobile.com"+path,params=params,files={"image":("produto.jpg",img.content,img.headers.get("content-type","image/jpeg"))})
            data=r.json()
            if r.status_code>=400 or data.get("error"): continue
            info=(data.get("response") or {}).get("image_info") or {}
            iid=info.get("image_id") or (data.get("response") or {}).get("image_id")
            if iid: ids.append(str(iid))
        except Exception:
            continue
    return ids


def _publish_shopee(db,row,product:Product,listing:MarketplaceListing):
    category=(product.shopee_category_id or "").strip();logistic=(product.shopee_logistic_id or "").strip()
    if not category or not logistic: raise RuntimeError("PRODUCT: Informe categoria e logística da Shopee no cadastro da peça")
    image_ids=[x.strip() for x in (product.shopee_image_ids or "").replace(",","\n").splitlines() if x.strip()]
    if not image_ids:
        image_ids=_shopee_upload_images(db,row,product)
        if image_ids:
            product.shopee_image_ids="\n".join(image_ids); db.commit()
    if not image_ids: raise RuntimeError("PRODUCT: A Shopee exige imagens. O envio automático não foi aceito; confira a conexão e as fotos.")
    base={"item_name":product.name[:120],"description":product.description or product.name,"category_id":int(category),"weight":max(.01,float(product.weight or 1)),"dimension":{"package_length":max(1,int(product.package_length or 20)),"package_width":max(1,int(product.package_width or 20)),"package_height":max(1,int(product.package_height or 20))},"image":{"image_id_list":image_ids[:9]},"logistic_info":[{"logistic_id":int(logistic),"enabled":True}]}
    existing=(listing.external_id or "").strip()
    if existing:
        _shopee_call(db,row,"/api/v2/product/update_item",{"item_id":int(existing),**base})
        _shopee_call(db,row,"/api/v2/product/update_price",{"item_id":int(existing),"price_list":[{"model_id":0,"original_price":float(product.price)}]})
        _shopee_call(db,row,"/api/v2/product/update_stock",{"item_id":int(existing),"stock_list":[{"model_id":0,"seller_stock":[{"stock":max(0,int(product.stock))}]}]})
        item_id=existing
    else:
        payload={**base,"original_price":float(product.price),"seller_stock":[{"stock":max(0,int(product.stock))}]}
        data=_shopee_call(db,row,"/api/v2/product/add_item",payload)
        item_id=(data.get("response") or {}).get("item_id")
    return {"external_id":item_id,"status":"published"}


def _digits(value): return "".join(ch for ch in (value or "") if ch.isdigit())


def _olx_internal_id(company_id:int, product_id:int): return f"CDM{company_id}_{product_id}"[:19]


def _publish_olx(row,product:Product,company:Company,listing:MarketplaceListing):
    if not product.olx_category_id: raise RuntimeError("PRODUCT: Informe a categoria OLX no cadastro da peça")
    images=_image_urls(product)
    phone=_digits(company.phone);zipcode=_digits(company.cep)
    if not images: raise RuntimeError("PRODUCT: OLX exige ao menos uma URL de imagem")
    if len(phone) not in {10,11}: raise RuntimeError("PRODUCT: Cadastre um telefone com DDD nas Informações da Empresa para publicar na OLX")
    if len(zipcode)!=8: raise RuntimeError("PRODUCT: Cadastre um CEP válido nas Informações da Empresa para publicar na OLX")
    token=decrypt_secret(row.access_token_enc)
    internal_id=_olx_internal_id(company.id,product.id)
    ad={"id":internal_id,"operation":"insert","category":int(product.olx_category_id),"Subject":product.name[:90],"Body":((product.description or product.name)+(f"\n\nCompatibilidade:\n{product.compatibility}" if product.compatibility else ""))[:6000],"Phone":int(phone),"type":"s","price":int(round(product.price)),"zipcode":zipcode,"images":images}
    payload={"access_token":token,"ad_list":[ad]}
    with httpx.Client(timeout=45) as c:
        r=c.put("https://apps.olx.com.br/autoupload/import",json=payload,headers={"Content-Type":"application/json"})
        if r.status_code>=400: raise RuntimeError(f"OLX: {r.text[:1200]}")
        data=r.json()
    if data.get("statusCode") not in {0,-8,None}: raise RuntimeError(f"OLX: {data.get('statusMessage') or data}")
    # token é usado para acompanhar o lote; o ID do anúncio permanece determinístico para permitir edição/deleção.
    return {"external_id":data.get("token") or listing.external_id or internal_id,"status":"processing"}


def _mark_sync_error(db,listing,msg):
    listing.status="sync_error";listing.error_message=_safe_error(msg);db.commit()


def sync_marketplace_stock_for_product(db:Session,product:Product,company_id:int):
    results=[]
    for listing in db.query(MarketplaceListing).filter(MarketplaceListing.company_id==company_id,MarketplaceListing.product_id==product.id).all():
        try:
            conn=_active_connection(db,company_id,listing.marketplace)
            if listing.marketplace=="mercadolivre" and listing.external_id.upper().startswith("MLB"):
                token=_ml_token(db,conn)
                with httpx.Client(timeout=30) as c:
                    _ml_sync_stock_client(c,token,conn,product,listing.external_id)
                listing.status="published" if product.stock>0 else "paused"
            elif listing.marketplace=="shopee" and listing.external_id:
                _shopee_call(db,conn,"/api/v2/product/update_stock",{"item_id":int(listing.external_id),"stock_list":[{"model_id":0,"seller_stock":[{"stock":max(0,int(product.stock))}]}]})
                listing.status="published" if product.stock>0 else "sold_out"
            elif listing.marketplace=="olx" and product.stock<=0:
                company=db.get(Company,company_id);token=decrypt_secret(conn.access_token_enc)
                payload={"access_token":token,"ad_list":[{"id":_olx_internal_id(company_id,product.id),"operation":"delete"}]}
                with httpx.Client(timeout=30) as c:
                    r=c.put("https://apps.olx.com.br/autoupload/import",json=payload,headers={"Content-Type":"application/json"})
                if r.status_code>=400: raise RuntimeError(f"OLX estoque: {r.text[:700]}")
                listing.status="processing"
            listing.error_message="";db.commit();results.append({"marketplace":listing.marketplace,"ok":True})
        except Exception as exc:
            _mark_sync_error(db,listing,str(exc));results.append({"marketplace":listing.marketplace,"ok":False,"error":_safe_error(str(exc))})
    return results


def refresh_listing(db:Session, listing:MarketplaceListing):
    conn=_active_connection(db,listing.company_id,listing.marketplace)
    if listing.marketplace=="mercadolivre" and listing.external_id:
        token=_ml_token(db,conn)
        with httpx.Client(timeout=30) as c:
            r=c.get(f"https://api.mercadolibre.com/items/{listing.external_id}",headers={"Authorization":f"Bearer {token}"})
        if r.status_code>=400: raise RuntimeError(f"Mercado Livre: {r.text[:700]}")
        data=r.json(); status=str(data.get("status") or "")
        listing.status="published" if status=="active" else status or listing.status
    elif listing.marketplace=="shopee" and listing.external_id:
        data=_shopee_call(db,conn,"/api/v2/product/get_item_base_info",{"item_id_list":listing.external_id},method="GET")
        items=(data.get("response") or {}).get("item_list") or []
        if items:
            st=str(items[0].get("item_status") or "").lower(); listing.status="published" if "normal" in st else st or listing.status
    elif listing.marketplace=="olx":
        token=decrypt_secret(conn.access_token_enc)
        with httpx.Client(timeout=30) as c:
            r=c.get("https://apps.olx.com.br/autoupload/v1/published",params={"fetch_size":200},headers={"Authorization":f"Bearer {token}"})
        if r.status_code>=400: raise RuntimeError(f"OLX: {r.text[:700]}")
        data=r.json(); target=_olx_internal_id(listing.company_id,listing.product_id)
        found=next((x for x in (data.get("data") or []) if str(x.get("id"))==target),None)
        if found:
            listing.external_id=str(found.get("list_id") or listing.external_id);listing.status="published";listing.published_at=listing.published_at or datetime.utcnow()
        elif listing.status=="processing": listing.status="processing"
    listing.error_message="";db.commit();db.refresh(listing);return listing



def process_ml_notification(db:Session, body:dict):
    from ..models import MarketplaceOrderEvent, Sale, SaleItem, StockMovement, FinancialEntry
    from ..routers.notifications import add_sale_notification

    resource=str((body or {}).get("resource") or "")
    topic=str((body or {}).get("topic") or "")
    user_id=str((body or {}).get("user_id") or "")

    if "order" not in topic.lower() and "/orders/" not in resource:
        return {"ok":True,"ignored":True}

    order_id=resource.rstrip("/").split("/")[-1]
    if not order_id:
        return {"ok":True,"ignored":True}

    conn=db.query(MarketplaceConnection).filter(
        MarketplaceConnection.marketplace=="mercadolivre",
        MarketplaceConnection.external_account_id==user_id,
        MarketplaceConnection.active==True,
    ).first()
    if not conn:
        return {"ok":True,"ignored":True,"reason":"account_not_connected"}

    token=_ml_token(db,conn)
    with httpx.Client(timeout=30) as c:
        r=c.get(
            f"https://api.mercadolibre.com/orders/{order_id}",
            headers={"Authorization":f"Bearer {token}"},
        )
    if r.status_code>=400:
        raise RuntimeError(f"Mercado Livre pedido: {r.text[:700]}")

    order=r.json()
    status=str(order.get("status") or "unknown").lower()
    canceled=status in {"cancelled","canceled"}
    total=float(order.get("total_amount") or 0)
    paid=float(order.get("paid_amount") or 0)

    sale=db.query(Sale).filter(
        Sale.company_id==conn.company_id,
        Sale.source=="mercadolivre",
        Sale.external_order_id==order_id,
    ).first()

    created=sale is None
    touched={}

    if not sale:
        sale=Sale(
            company_id=conn.company_id,
            total=total,
            payment_method="mercadolivre",
            status=status,
            source="mercadolivre",
            external_order_id=order_id,
        )
        db.add(sale)
        db.flush()

        for oi in order.get("order_items") or []:
            item=oi.get("item") or {}
            item_id=str(item.get("id") or "")
            qty=max(1,int(oi.get("quantity") or 1))
            listing=db.query(MarketplaceListing).filter(
                MarketplaceListing.company_id==conn.company_id,
                MarketplaceListing.marketplace=="mercadolivre",
                MarketplaceListing.external_id==item_id,
            ).first()
            if not listing:
                continue

            product=db.query(Product).filter(
                Product.id==listing.product_id,
                Product.company_id==conn.company_id,
            ).with_for_update().first()
            if not product:
                continue

            price=float(oi.get("unit_price") or product.price or 0)
            db.add(SaleItem(
                company_id=conn.company_id,
                sale_id=sale.id,
                product_id=product.id,
                quantity=qty,
                unit_price=price,
            ))

            if not canceled:
                old=int(product.stock or 0)
                product.stock=max(0,old-qty)
                actual=old-product.stock
                if actual:
                    db.add(StockMovement(
                        company_id=conn.company_id,
                        product_id=product.id,
                        kind="marketplace",
                        quantity_delta=-actual,
                        balance_after=product.stock,
                        reference=f"mercadolivre:{order_id}",
                    ))
                    touched[product.id]=product
    else:
        sale.total=total
        sale.status=status

    if canceled:
        reversal_ref=f"mercadolivre:{order_id}:cancel"
        already_reversed=db.query(StockMovement).filter(
            StockMovement.company_id==conn.company_id,
            StockMovement.reference==reversal_ref,
        ).first()

        if not already_reversed:
            items=db.query(SaleItem).filter(SaleItem.sale_id==sale.id).all()
            for item in items:
                movements=db.query(StockMovement).filter(
                    StockMovement.company_id==conn.company_id,
                    StockMovement.product_id==item.product_id,
                    StockMovement.reference==f"mercadolivre:{order_id}",
                    StockMovement.quantity_delta<0,
                ).all()
                restore=sum(abs(int(x.quantity_delta or 0)) for x in movements)
                if restore<=0:
                    continue

                product=db.query(Product).filter(
                    Product.id==item.product_id,
                    Product.company_id==conn.company_id,
                ).with_for_update().first()
                if not product:
                    continue

                product.stock=int(product.stock or 0)+restore
                db.add(StockMovement(
                    company_id=conn.company_id,
                    product_id=product.id,
                    kind="marketplace",
                    quantity_delta=restore,
                    balance_after=product.stock,
                    reference=reversal_ref,
                ))
                touched[product.id]=product

    description=f"Mercado Livre pedido {order_id}"
    finance=db.query(FinancialEntry).filter(
        FinancialEntry.company_id==conn.company_id,
        FinancialEntry.kind=="income",
        FinancialEntry.description==description,
    ).first()

    if canceled:
        if finance:
            finance.status="canceled"
    elif paid>0:
        if not finance:
            finance=FinancialEntry(
                company_id=conn.company_id,
                kind="income",
                description=description,
                amount=paid,
                status="paid",
                due_date=datetime.utcnow().strftime("%Y-%m-%d"),
            )
            db.add(finance)
        else:
            finance.amount=paid
            finance.status="paid"

    event=db.query(MarketplaceOrderEvent).filter(
        MarketplaceOrderEvent.company_id==conn.company_id,
        MarketplaceOrderEvent.marketplace=="mercadolivre",
        MarketplaceOrderEvent.external_order_id==order_id,
    ).first()
    if not event:
        event=MarketplaceOrderEvent(
            company_id=conn.company_id,
            marketplace="mercadolivre",
            external_order_id=order_id,
            sale_id=sale.id,
            payload_json="{}",
        )
        db.add(event)
    event.sale_id=sale.id
    event.payload_json=json.dumps(order,ensure_ascii=False,default=str)[:20000]

    if created:
        nomes=[]
        for item_row in db.query(SaleItem).filter(SaleItem.sale_id==sale.id).all():
            prod=db.get(Product,item_row.product_id)
            nomes.append(f"{item_row.quantity}x {prod.name if prod else 'Peça'}")
        add_sale_notification(
            db,
            conn.company_id,
            sale.id,
            "mercadolivre",
            total,
            ", ".join(nomes)[:360] or f"Pedido {order_id}",
        )

    db.commit()

    for product in touched.values():
        try:
            sync_marketplace_stock_for_product(db,product,conn.company_id)
        except Exception:
            pass

    return {
        "ok":True,
        "sale_id":sale.id,
        "created":created,
        "status":status,
        "paid_amount":paid,
        "total_amount":total,
        "canceled":canceled,
        "products_updated":len(touched),
    }
