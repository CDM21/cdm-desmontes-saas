import base64
import io
import os
import time
import re
import unicodedata

import cv2
import numpy as np
import httpx
from PIL import Image, ImageEnhance, ImageOps
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
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




# CDM PHOTO AI V42 — remove.bg + BiRefNet (Replicate)
REMOVE_BG_API_URL = "https://api.remove.bg/v1.0/removebg"
REPLICATE_PREDICTIONS_URL = "https://api.replicate.com/v1/predictions"
REPLICATE_BIREFNET_VERSION = "sprited/birefnet:21f2c4a9159af128ab9b9126401eebe7f8c5310841ed628b74a4c462df00da67"


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


def _replicate_error_message(response):
    status = int(response.status_code or 0)
    if status in {401, 403}:
        return "O token do Replicate não foi aceito. Revise REPLICATE_API_TOKEN no Render."
    if status == 402:
        return "O Replicate recusou a cobrança desta execução. Revise o billing/créditos."
    if status == 429:
        return "O Replicate recebeu muitos pedidos ao mesmo tempo. Tente novamente em alguns segundos."
    if status >= 500:
        return "O Replicate está temporariamente indisponível. Tente novamente."

    try:
        payload = response.json()
        detail = payload.get("detail")
        if detail:
            return f"Replicate: {str(detail)[:240]}"
        title = payload.get("title")
        if title:
            return f"Replicate: {str(title)[:240]}"
    except Exception:
        pass

    text = (response.text or "").strip().replace("\n", " ")
    if text:
        return f"Replicate: {text[:240]}"
    return f"Replicate recusou a imagem (HTTP {status})."


def _normalize_provider(value: str):
    raw = (value or "").strip().lower()
    mapping = {
        "": "auto",
        "auto": "auto",
        "automatico": "auto",
        "automático": "auto",
        "remove_bg": "remove_bg",
        "remove.bg": "remove_bg",
        "removebg": "remove_bg",
        "premium": "remove_bg",
        "birefnet": "birefnet",
        "economica": "birefnet",
        "econômica": "birefnet",
        "replicate": "birefnet",
    }
    return mapping.get(raw, "auto")


def _prepare_birefnet_input(raw: bytes) -> tuple[bytes, str]:
    """Mantém ótima qualidade e evita mandar Data URI gigante ao Replicate."""
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        return raw, "image/jpeg"

    max_side = 2048
    scale = min(1.0, max_side / max(img.width, img.height))
    if scale < 1:
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.Resampling.LANCZOS,
        )

    best = None
    for quality in (92, 88, 84, 80, 76):
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, subsampling=0, optimize=True)
        best = out.getvalue()
        if len(best) <= 900 * 1024:
            break

    return best or raw, "image/jpeg"


def _white_catalog_jpeg(image_bytes: bytes, output_size=1600, safe_object=1260) -> bytes:
    pil = Image.open(io.BytesIO(image_bytes))
    pil = ImageOps.exif_transpose(pil).convert("RGBA")

    alpha = pil.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        pil = pil.crop(bbox)

    w, h = pil.size
    if w < 2 or h < 2:
        raise ValueError("A IA retornou uma imagem inválida.")

    fit = min(safe_object / max(w, 1), safe_object / max(h, 1), 1.9)
    nw = max(1, int(round(w * fit)))
    nh = max(1, int(round(h * fit)))
    pil = pil.resize((nw, nh), Image.Resampling.LANCZOS)

    bg = Image.new("RGBA", (output_size, output_size), (255, 255, 255, 255))
    x = (output_size - nw) // 2
    y = (output_size - nh) // 2
    bg.alpha_composite(pil, (x, y))

    out = io.BytesIO()
    bg.convert("RGB").save(out, format="JPEG", quality=95, subsampling=0)
    return out.getvalue()


def _call_remove_bg(raw: bytes, filename: str, content_type: str) -> bytes:
    api_key = (os.getenv("REMOVE_BG_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(503, "A chave REMOVE_BG_API_KEY não está configurada no Render.")

    try:
        with httpx.Client(
            timeout=httpx.Timeout(40.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            response = client.post(
                REMOVE_BG_API_URL,
                headers={"X-Api-Key": api_key, "Accept": "image/jpeg"},
                files={"image_file": (filename, raw, content_type)},
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
        raise HTTPException(504, "A IA remove.bg demorou demais. Tente novamente.")
    except httpx.HTTPError:
        raise HTTPException(502, "Não foi possível conectar ao remove.bg.")

    if response.status_code != 200:
        raise HTTPException(
            response.status_code if 400 <= response.status_code < 500 else 502,
            _remove_bg_error_message(response),
        )
    if not response.content:
        raise HTTPException(502, "O remove.bg retornou uma imagem vazia.")
    return response.content


def _call_birefnet(raw: bytes, filename: str, content_type: str) -> bytes:
    token = (os.getenv("REPLICATE_API_TOKEN") or "").strip()
    if not token:
        raise HTTPException(503, "O token REPLICATE_API_TOKEN não está configurado no Render.")

    prepared, prepared_type = _prepare_birefnet_input(raw)
    data_url = "data:%s;base64,%s" % (
        prepared_type,
        base64.b64encode(prepared).decode("ascii"),
    )

    try:
        with httpx.Client(
            timeout=httpx.Timeout(70.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            create = client.post(
                REPLICATE_PREDICTIONS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Prefer": "wait=45",
                },
                json={
                    "version": REPLICATE_BIREFNET_VERSION,
                    "input": {
                        "image": data_url,
                        "variant": "general-hr",
                        "resolution": 0,
                        "output_format": "cutout",
                        "mask_blur": 0,
                        "mask_offset": 0,
                        "refine_fg": True,
                        "precision": "fp16",
                    },
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(504, "A IA BiRefNet demorou demais. Tente novamente.")
    except httpx.HTTPError:
        raise HTTPException(502, "Não foi possível conectar ao Replicate / BiRefNet.")

    if create.status_code not in (200, 201):
        raise HTTPException(
            create.status_code if 400 <= create.status_code < 500 else 502,
            _replicate_error_message(create),
        )

    try:
        prediction = create.json()
    except Exception:
        raise HTTPException(502, "Resposta inválida do Replicate.")

    status = str(prediction.get("status") or "").lower()
    poll_url = ((prediction.get("urls") or {}).get("get") or "").strip()

    if status not in {"succeeded", "failed", "canceled"} and poll_url:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(35.0, connect=10.0),
                follow_redirects=True,
            ) as client:
                for _ in range(12):
                    poll = client.get(
                        poll_url,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if poll.status_code != 200:
                        break
                    prediction = poll.json()
                    status = str(prediction.get("status") or "").lower()
                    if status in {"succeeded", "failed", "canceled"}:
                        break
                    time.sleep(1.2)
        except Exception:
            pass

    if status != "succeeded":
        error = str(prediction.get("error") or "").strip()
        if error:
            raise HTTPException(502, f"BiRefNet: {error[:240]}")
        raise HTTPException(502, "O BiRefNet não conseguiu finalizar esta foto.")

    output = prediction.get("output")
    output_url = str(
        output[0] if isinstance(output, list) and output else output or ""
    ).strip()
    if not output_url:
        raise HTTPException(502, "O BiRefNet não retornou a imagem tratada.")

    try:
        with httpx.Client(
            timeout=httpx.Timeout(40.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            asset = client.get(output_url)
    except httpx.TimeoutException:
        raise HTTPException(504, "A imagem final do BiRefNet demorou demais para baixar.")
    except httpx.HTTPError:
        raise HTTPException(502, "Não foi possível baixar a imagem final do BiRefNet.")

    if asset.status_code != 200 or not asset.content:
        raise HTTPException(502, "Não foi possível baixar a imagem tratada do BiRefNet.")

    try:
        return _white_catalog_jpeg(asset.content)
    except Exception:
        raise HTTPException(502, "O BiRefNet retornou uma imagem inválida.")


@router.get("/photo-ai-status")
def photo_ai_status(user=Depends(active_user)):
    remove_bg_key = (os.getenv("REMOVE_BG_API_KEY") or "").strip()
    replicate_key = (os.getenv("REPLICATE_API_TOKEN") or "").strip()
    return {
        "version": "v42",
        "providers": {
            "remove_bg": {
                "label": "remove.bg",
                "configured": bool(remove_bg_key),
                "mode": "premium",
            },
            "birefnet": {
                "label": "BiRefNet",
                "configured": bool(replicate_key),
                "mode": "economy",
            },
        },
        "default_provider": "auto",
        "auto_strategy": "birefnet_then_remove_bg",
    }


@router.post("/remove-background")
def remove_product_background(
    file: UploadFile = File(...),
    provider: str = Form("auto"),
    user=Depends(active_user),
):
    raw = file.file.read()
    if not raw:
        raise HTTPException(400, "Imagem vazia")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "A imagem deve ter no máximo 15 MB")

    content_type = (file.content_type or "image/jpeg").split(";")[0].strip()
    filename = (file.filename or "produto.jpg")[:180]
    chosen = _normalize_provider(provider)

    if chosen == "remove_bg":
        providers_to_try = ["remove_bg"]
    elif chosen == "birefnet":
        providers_to_try = ["birefnet"]
    else:
        providers_to_try = ["birefnet", "remove_bg"]

    errors = []
    for current in providers_to_try:
        try:
            result = (
                _call_birefnet(raw, filename, content_type)
                if current == "birefnet"
                else _call_remove_bg(raw, filename, content_type)
            )

            return Response(
                content=result,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-store",
                    "X-CDM-Photo-AI": current,
                    "X-CDM-Photo-AI-Requested": chosen,
                    "X-CDM-Photo-AI-Version": "v42",
                    "Access-Control-Expose-Headers": "X-CDM-Photo-AI,X-CDM-Photo-AI-Requested,X-CDM-Photo-AI-Version",
                },
            )
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            errors.append({
                "provider": current,
                "status": e.status_code,
                "detail": detail,
            })

    if errors:
        last = errors[-1]
        details = " | ".join(
            f"{x['provider']}: {x['detail']}" for x in errors
        )
        raise HTTPException(
            last["status"] if isinstance(last["status"], int) else 502,
            f"Não foi possível tratar a foto com nenhuma IA. {details[:500]}",
        )

    raise HTTPException(502, "Não foi possível tratar a foto com nenhuma IA.")

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
