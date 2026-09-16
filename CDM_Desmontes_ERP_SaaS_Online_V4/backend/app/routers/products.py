import base64
import io
import re
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageEnhance
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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




# CDM SMART BACKGROUND V10
@router.post("/remove-background")
def remove_product_background(
    file: UploadFile = File(...),
    user = Depends(active_user),
):
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    raw = file.file.read()
    if not raw:
        raise HTTPException(400, "Imagem vazia")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "A imagem deve ter no máximo 15 MB")

    worker = Path(__file__).resolve().parents[1] / "image_bg_worker.py"
    if not worker.exists():
        raise HTTPException(500, "Processador de imagem não encontrado")

    with tempfile.TemporaryDirectory(prefix="cdm_bg_") as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "entrada.img"
        dst = tmp_dir / "saida.jpg"
        src.write_bytes(raw)

        try:
            proc = subprocess.run(
                [sys.executable, str(worker), str(src), str(dst)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=35,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(
                504,
                "O recorte demorou mais de 35 segundos e foi interrompido. Tente outra foto."
            )

        if proc.returncode != 0 or not dst.exists():
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            if not err:
                err = "Falha no processador de imagem"
            raise HTTPException(422, err[-500:])

        result = dst.read_bytes()

    return Response(
        content=result,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-CDM-Background": "smart-v10.3-process",
        },
    )

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
