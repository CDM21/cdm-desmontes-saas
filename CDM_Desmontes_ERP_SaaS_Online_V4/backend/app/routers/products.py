import base64
import io
import os
import re
import unicodedata

import cv2
import numpy as np
import httpx
from PIL import Image, ImageEnhance
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Product
from ..deps import active_user, require_roles
from ..services.marketplaces import publish_all

router=APIRouter()

def next_sequential_sku(db:Session, company_id:int)->str:
    rows=db.query(Product.sku).filter(Product.company_id==company_id).all()
    numbers=set()
    for row in rows:
        value=str(row[0] or "").strip()
        if value.isdigit():
            numbers.add(int(value))
    next_number=1
    while next_number in numbers:
        next_number+=1
    return str(next_number)

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


# CDM DUPLICATE DETECTION V1
def _dup_norm(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()

@router.get("/duplicates")
def find_product_duplicates(
    name: str = "",
    oem: str = "",
    brand: str = "",
    model: str = "",
    year: int | None = None,
    vehicle_id: int | None = None,
    exclude_id: int | None = None,
    db: Session = Depends(get_db),
    user = Depends(active_user),
):
    q_name = _dup_norm(name)
    q_oem = _dup_norm(oem)
    q_brand = _dup_norm(brand)
    q_model = _dup_norm(model)

    if len(q_name) < 3 and len(q_oem) < 3:
        return {"items": [], "strong_count": 0}

    rows = db.query(Product).filter(
        Product.company_id == user.company_id,
        Product.active == True,
    )
    if exclude_id:
        rows = rows.filter(Product.id != exclude_id)

    candidates = []
    for p in rows.order_by(Product.id.desc()).limit(500).all():
        score = 0
        reasons = []
        p_name = _dup_norm(p.name)
        p_oem = _dup_norm(p.oem)
        p_brand = _dup_norm(p.brand)
        p_model = _dup_norm(p.model)

        if q_oem and p_oem and q_oem == p_oem:
            score += 75
            reasons.append("Mesmo OEM")

        if q_name and p_name:
            if q_name == p_name:
                score += 40
                reasons.append("Mesmo nome")
            else:
                similarity = SequenceMatcher(None, q_name, p_name).ratio()
                if similarity >= 0.88:
                    score += 28
                    reasons.append(f"Nome muito parecido ({round(similarity * 100)}%)")
                elif similarity >= 0.78:
                    score += 18
                    reasons.append(f"Nome parecido ({round(similarity * 100)}%)")

        if q_brand and p_brand and q_brand == p_brand:
            score += 8
            reasons.append("Mesma marca")
        if q_model and p_model and q_model == p_model:
            score += 12
            reasons.append("Mesmo modelo")
        if year and p.year and int(year) == int(p.year):
            score += 8
            reasons.append("Mesmo ano")
        if vehicle_id and p.vehicle_id and int(vehicle_id) == int(p.vehicle_id):
            score += 15
            reasons.append("Mesmo veículo de origem")

        if score >= 38:
            candidates.append({
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "oem": p.oem,
                "brand": p.brand,
                "model": p.model,
                "year": p.year,
                "stock": p.stock,
                "location_id": p.location_id,
                "vehicle_id": p.vehicle_id,
                "score": min(score, 100),
                "strong": score >= 70,
                "reasons": reasons,
            })

    candidates.sort(key=lambda x: (x["score"], x["id"]), reverse=True)
    items = candidates[:8]
    return {
        "items": items,
        "strong_count": sum(1 for x in items if x["strong"]),
        "checked": {
            "name": name,
            "oem": oem,
            "brand": brand,
            "model": model,
            "year": year,
            "vehicle_id": vehicle_id,
        },
    }




# CDM PHOTO AI V41 — remove.bg profissional
REMOVE_BG_API_URL = "https://api.remove.bg/v1.0/removebg"


def _remove_bg_error_message(response):
    status = int(response.status_code or 0)
    if status in {401, 403}:
        return "A chave do remove.bg não foi aceita. Revise REMOVE_BG_API_KEY no Render."
    if status == 402:
        return "Os créditos do remove.bg acabaram ou não permitem esta resolução."
    if status == 429:
        return "O remove.bg recebeu muitas fotos ao mesmo tempo. Tente novamente em alguns segundos."
    if status >= 500:
        return "O remove.bg está temporariamente indisponível. Tente novamente."

    try:
        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            first = errors[0] or {}
            title = str(first.get("title") or first.get("code") or "").strip()
            if title:
                return f"remove.bg: {title[:240]}"
    except Exception:
        pass

    text = (response.text or "").strip().replace("\n", " ")
    if text:
        return f"remove.bg: {text[:240]}"
    return f"remove.bg recusou a imagem (HTTP {status})."


@router.get("/photo-ai-status")
def photo_ai_status(user=Depends(active_user)):
    key = (os.getenv("REMOVE_BG_API_KEY") or "").strip()
    return {
        "provider": "remove.bg",
        "configured": bool(key),
        "version": "v41",
    }


@router.post("/remove-background")
def remove_product_background(
    file: UploadFile = File(...),
    user = Depends(active_user),
):
    raw = file.file.read()
    if not raw:
        raise HTTPException(400, "Imagem vazia")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "A imagem deve ter no máximo 15 MB")

    api_key = (os.getenv("REMOVE_BG_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(
            503,
            "A IA de fotos ainda não está configurada no servidor. Defina REMOVE_BG_API_KEY."
        )

    content_type = (file.content_type or "image/jpeg").split(";")[0].strip()
    filename = (file.filename or "produto.jpg")[:180]

    try:
        with httpx.Client(
            timeout=httpx.Timeout(40.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            response = client.post(
                REMOVE_BG_API_URL,
                headers={
                    "X-Api-Key": api_key,
                    "Accept": "image/jpeg",
                },
                files={
                    "image_file": (filename, raw, content_type),
                },
                data={
                    "size": "auto",
                    "type": "auto",
                    "type_level": "latest",
                    "format": "jpg",
                    "bg_color": "ffffff",
                    "crop": "true",
                    "crop_margin": "10%",
                    "shadow_type": "none",
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(504, "A IA de fotos demorou demais. Tente novamente.")
    except httpx.HTTPError:
        raise HTTPException(502, "Não foi possível conectar à IA de fotos.")

    if response.status_code != 200:
        raise HTTPException(
            response.status_code if 400 <= response.status_code < 500 else 502,
            _remove_bg_error_message(response),
        )

    result = response.content
    if not result:
        raise HTTPException(502, "A IA retornou uma imagem vazia.")

    return Response(
        content=result,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-CDM-Photo-AI": "remove-bg-v41",
            "X-CDM-Foreground-Type": response.headers.get("X-Type", ""),
        },
    )

@router.post("")
def create_product(data:ProductIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
    if db.query(Product).filter(Product.company_id==user.company_id,Product.sku==data.sku).first():
        raise HTTPException(409,"SKU já existe nesta empresa")
    payload=data.model_dump(exclude={"auto_publish"})
    p=Product(company_id=user.company_id,**payload)
    db.add(p); db.commit(); db.refresh(p)
    if data.auto_publish:
        publish_all(db,p,user.company_id)
    return p

@router.put("/{product_id}")
def update_product(product_id:int,data:ProductIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
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
def archive_product(product_id:int,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
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
