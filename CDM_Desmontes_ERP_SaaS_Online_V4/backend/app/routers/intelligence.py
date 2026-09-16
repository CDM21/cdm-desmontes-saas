import json, os, hmac, hashlib, base64
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=True)
from datetime import datetime, timedelta
from statistics import mean
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..deps import active_user
from ..security import SECRET_KEY
from ..models import (
    User, Company, Product, Vehicle, Sale, SaleItem, FinancialEntry,
    AssistantMessage, SaleEvidence, ShippingCheck, SearchEvent
)

router = APIRouter()

def _assistant_quota():
    try:
        return max(50, int(os.getenv("ASSISTANT_MONTHLY_MESSAGES", "1000")))
    except Exception:
        return 1000

def _assistant_usage(db: Session, company_id: int):
    now = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    used = db.query(AssistantMessage).filter(
        AssistantMessage.company_id == company_id,
        AssistantMessage.role == "user",
        AssistantMessage.created_at >= start,
    ).count()
    return used, _assistant_quota()


def _money(v):
    return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _snapshot(db: Session, company_id: int):
    now = datetime.utcnow()
    today = now.date()
    month_start = now - timedelta(days=30)
    products = db.query(Product).filter(Product.company_id == company_id, Product.active == True).all()
    sales = db.query(Sale).filter(Sale.company_id == company_id).all()
    finance = db.query(FinancialEntry).filter(FinancialEntry.company_id == company_id).all()

    today_sales = [s for s in sales if s.created_at and s.created_at.date() == today]
    sales_30 = [s for s in sales if s.created_at and s.created_at >= month_start]
    revenue_today = sum(float(s.total or 0) for s in today_sales)
    revenue_30 = sum(float(s.total or 0) for s in sales_30)
    stock_qty = sum(int(p.stock or 0) for p in products)
    stock_cost = sum(float(p.cost or 0) * int(p.stock or 0) for p in products)
    low_stock = sum(1 for p in products if int(p.stock or 0) <= 1)
    stale = [p for p in products if p.created_at and p.created_at <= now - timedelta(days=120) and int(p.stock or 0) > 0]
    income = sum(float(x.amount or 0) for x in finance if x.kind == "income")
    expense = sum(float(x.amount or 0) for x in finance if x.kind == "expense")

    by_channel = {}
    for s in sales_30:
        source = getattr(s, "source", "") or "manual"
        by_channel[source] = by_channel.get(source, 0) + 1

    return {
        "revenue_today": round(revenue_today, 2),
        "revenue_30d": round(revenue_30, 2),
        "sales_today": len(today_sales),
        "sales_30d": len(sales_30),
        "stock_qty": stock_qty,
        "stock_cost": round(stock_cost, 2),
        "low_stock": low_stock,
        "stale_count": len(stale),
        "balance": round(income - expense, 2),
        "channels": by_channel,
        "products": len(products),
    }


def _top_products(db: Session, company_id: int, days: int = 90, limit: int = 8):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            Product.id, Product.name, Product.sku,
            func.sum(SaleItem.quantity).label("qty"),
            func.sum(SaleItem.quantity * SaleItem.unit_price).label("revenue")
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Product.company_id == company_id, Sale.created_at >= cutoff)
        .group_by(Product.id, Product.name, Product.sku)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "product_id": r.id, "name": r.name, "sku": r.sku,
            "quantity": int(r.qty or 0), "revenue": float(r.revenue or 0)
        }
        for r in rows
    ]


@router.get("/status")
def status(db: Session = Depends(get_db), user = Depends(active_user)):
    used, limit = _assistant_usage(db, user.company_id)
    return {
        "assistant_enabled": True,
        "automatic": True,
        "company_id": user.company_id,
        "mode": "ia" if (os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")) else "inteligencia_local",
        "messages_used_month": used,
        "messages_limit_month": limit,
        "message": "O Assistente CDM é liberado automaticamente para esta empresa enquanto a assinatura estiver ativa ou em período de teste."
    }


@router.get("/owner-dashboard")
def owner_dashboard(db: Session = Depends(get_db), user = Depends(active_user)):
    snap = _snapshot(db, user.company_id)
    company = db.get(Company, user.company_id)
    snap["company_id"] = user.company_id
    snap["company_name"] = company.trade_name if company else "Empresa"
    snap["company_phone"] = company.phone if company else ""
    snap["top_products"] = _top_products(db, user.company_id)
    vehicle_revenue = {}
    for item in db.query(SaleItem).filter(SaleItem.company_id == user.company_id).all():
        p = db.get(Product, item.product_id)
        if p and p.vehicle_id:
            vehicle_revenue[p.vehicle_id] = vehicle_revenue.get(p.vehicle_id, 0) + float(item.quantity or 0) * float(item.unit_price or 0)

    best_vehicle = None
    if vehicle_revenue:
        vid = max(vehicle_revenue, key=vehicle_revenue.get)
        v = db.get(Vehicle, vid)
        if v:
            best_vehicle = {
                "id": v.id,
                "label": f"{v.brand or ''} {v.model or ''} {v.year or ''}".strip(),
                "plate": v.plate or "",
                "revenue": round(vehicle_revenue[vid], 2),
                "acquisition_value": float(v.acquisition_value or 0),
                "return_percent": round((vehicle_revenue[vid] / max(float(v.acquisition_value or 0), 1)) * 100, 1),
            }
    snap["best_vehicle"] = best_vehicle
    return snap



# CDM SMART STOCK V1
@router.get("/smart-stock")
def smart_stock(db: Session = Depends(get_db), user = Depends(active_user)):
    now = datetime.utcnow()
    products = (
        db.query(Product)
        .filter(Product.company_id == user.company_id, Product.active == True)
        .order_by(Product.created_at.asc())
        .all()
    )

    sale_rows = (
        db.query(SaleItem, Sale)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.company_id == user.company_id)
        .all()
    )

    sales_by_product = {}
    for item, sale in sale_rows:
        pid = int(item.product_id or 0)
        if not pid:
            continue
        sales_by_product.setdefault(pid, []).append((item, sale))

    items = []
    low_stock_count = 0
    stale_120_count = 0
    stale_180_count = 0
    stock_sale_value = 0.0
    stock_cost_value = 0.0

    for p in products:
        stock = int(p.stock or 0)
        price = float(p.price or 0)
        cost = float(p.cost or 0)
        age_days = max(0, (now - p.created_at).days) if p.created_at else 0

        rows = sales_by_product.get(p.id, [])
        sold_30 = 0
        sold_90 = 0
        revenue_90 = 0.0
        last_sale_at = None

        for item, sale in rows:
            created = sale.created_at
            qty = int(item.quantity or 0)
            unit = float(item.unit_price or 0)
            if created:
                if last_sale_at is None or created > last_sale_at:
                    last_sale_at = created
                days_ago = (now - created).days
                if days_ago <= 30:
                    sold_30 += qty
                if days_ago <= 90:
                    sold_90 += qty
                    revenue_90 += qty * unit

        margin_value = price - cost
        margin_percent = ((margin_value / price) * 100) if price > 0 else 0.0

        low_stock = stock <= 1
        stale_120 = stock > 0 and age_days >= 120 and sold_90 == 0
        stale_180 = stock > 0 and age_days >= 180 and sold_90 == 0

        if low_stock:
            low_stock_count += 1
        if stale_120:
            stale_120_count += 1
        if stale_180:
            stale_180_count += 1

        stock_sale_value += max(stock, 0) * price
        stock_cost_value += max(stock, 0) * cost

        discount = 0
        if stock > 0 and sold_90 == 0:
            if age_days >= 240:
                discount = 15
            elif age_days >= 180:
                discount = 10
            elif age_days >= 120:
                discount = 5

        suggested_price = price
        if discount and price > 0:
            floor = cost * 1.30 if cost > 0 else price * 0.70
            suggested_price = max(floor, price * (1 - discount / 100))
            suggested_price = round(suggested_price / 5) * 5 if suggested_price >= 50 else round(suggested_price, 2)

        if stock <= 0:
            status = "sem_estoque"
            priority = 95
            action = "Repor ou revisar cadastro"
        elif stale_180:
            status = "parada"
            priority = min(94, 70 + min(24, age_days // 30))
            action = "Revisar preço e anúncio"
        elif stale_120:
            status = "atencao"
            priority = 68
            action = "Acompanhar e considerar ajuste"
        elif low_stock:
            status = "estoque_baixo"
            priority = 62
            action = "Avaliar reposição"
        elif margin_percent < 20 and cost > 0:
            status = "margem_baixa"
            priority = 55
            action = "Revisar margem"
        else:
            status = "saudavel"
            priority = 20
            action = "Sem ação urgente"

        items.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "brand": p.brand,
            "model": p.model,
            "year": p.year,
            "stock": stock,
            "price": round(price, 2),
            "cost": round(cost, 2),
            "margin_value": round(margin_value, 2),
            "margin_percent": round(margin_percent, 1),
            "age_days": age_days,
            "sold_30": sold_30,
            "sold_90": sold_90,
            "revenue_90": round(revenue_90, 2),
            "last_sale_at": last_sale_at,
            "status": status,
            "priority": priority,
            "action": action,
            "suggested_discount_percent": discount,
            "suggested_price": round(suggested_price, 2),
        })

    items.sort(key=lambda x: (x["priority"], x["age_days"]), reverse=True)

    return {
        "generated_at": now,
        "summary": {
            "products_analyzed": len(products),
            "low_stock": low_stock_count,
            "stale_120": stale_120_count,
            "stale_180": stale_180_count,
            "stock_sale_value": round(stock_sale_value, 2),
            "stock_cost_value": round(stock_cost_value, 2),
            "estimated_stock_margin": round(stock_sale_value - stock_cost_value, 2),
        },
        "items": items,
    }


@router.get("/radar")
def radar(db: Session = Depends(get_db), user = Depends(active_user)):
    now = datetime.utcnow()
    products = db.query(Product).filter(Product.company_id == user.company_id, Product.active == True).all()
    stale = sorted(
        [p for p in products if p.created_at and p.created_at <= now - timedelta(days=120) and int(p.stock or 0) > 0],
        key=lambda x: x.created_at
    )[:20]
    lost = (
        db.query(SearchEvent.query, func.count(SearchEvent.id).label("qty"))
        .filter(SearchEvent.company_id == user.company_id, SearchEvent.results_count == 0, SearchEvent.created_at >= now - timedelta(days=30))
        .group_by(SearchEvent.query)
        .order_by(func.count(SearchEvent.id).desc())
        .limit(12)
        .all()
    )
    return {
        "top_sellers": _top_products(db, user.company_id, 90, 12),
        "stale_products": [
            {
                "id": p.id, "sku": p.sku, "name": p.name, "stock": p.stock,
                "price": p.price, "days": (now - p.created_at).days if p.created_at else 0
            }
            for p in stale
        ],
        "lost_searches": [{"query": r.query, "count": int(r.qty)} for r in lost],
        "generated_at": now,
    }


@router.post("/search-event")
def search_event(payload: dict, db: Session = Depends(get_db), user = Depends(active_user)):
    q = str(payload.get("query") or "").strip()[:220]
    if len(q) < 2:
        return {"ok": True, "ignored": True}
    row = SearchEvent(
        company_id=user.company_id,
        query=q,
        results_count=max(0, int(payload.get("results_count") or 0)),
        source=str(payload.get("source") or "estoque")[:40],
    )
    db.add(row)
    db.commit()
    return {"ok": True}


@router.get("/pricing/{product_id}")
def pricing(product_id: int, db: Session = Depends(get_db), user = Depends(active_user)):
    p = db.query(Product).filter(Product.id == product_id, Product.company_id == user.company_id, Product.active == True).first()
    if not p:
        raise HTTPException(404, "Peça não encontrada")

    history = (
        db.query(SaleItem)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Product, Product.id == SaleItem.product_id)
        .filter(
            Sale.company_id == user.company_id,
            Product.name == p.name,
            Sale.created_at >= datetime.utcnow() - timedelta(days=365)
        ).all()
    )
    historical_prices = [float(x.unit_price or 0) for x in history if float(x.unit_price or 0) > 0]
    hist_avg = mean(historical_prices) if historical_prices else 0
    age = (datetime.utcnow() - p.created_at).days if p.created_at else 0
    current = float(p.price or 0)
    cost = float(p.cost or 0)
    floor = cost * 1.30 if cost > 0 else max(current * .70, 0)

    if hist_avg > 0:
        base = hist_avg * .65 + current * .35 if current > 0 else hist_avg
        reason = "histórico de vendas da própria empresa"
    else:
        base = current if current > 0 else max(cost * 1.6, 0)
        reason = "preço atual e custo cadastrado"

    discount = .10 if age >= 180 else (.05 if age >= 120 else 0)
    suggested = max(floor, base * (1 - discount))
    suggested = round(suggested / 5) * 5 if suggested >= 50 else round(suggested, 2)

    return {
        "product_id": p.id,
        "current_price": current,
        "suggested_price": round(suggested, 2),
        "minimum_price": round(floor, 2),
        "historical_average": round(hist_avg, 2),
        "sales_sample": len(historical_prices),
        "days_in_stock": age,
        "reason": f"Sugestão baseada em {reason}" + (f" e ajuste por {age} dias em estoque." if discount else "."),
        "channel_note": "O valor por canal pode ser ajustado depois para considerar taxas e frete."
    }


@router.post("/pricing/{product_id}/apply")
def apply_pricing(product_id: int, db: Session = Depends(get_db), user = Depends(active_user)):
    """Recalcula no servidor e aplica a sugestão ao preço local da peça."""
    result = pricing(product_id, db, user)
    p = db.query(Product).filter(
        Product.id == product_id,
        Product.company_id == user.company_id,
        Product.active == True
    ).first()
    if not p:
        raise HTTPException(404, "Peça não encontrada")
    old_price = float(p.price or 0)
    new_price = float(result["suggested_price"] or 0)
    if new_price <= 0:
        raise HTTPException(400, "Não foi possível calcular um preço válido para aplicar")
    p.price = new_price
    db.commit()
    db.refresh(p)
    return {
        "ok": True,
        "product_id": p.id,
        "old_price": old_price,
        "new_price": float(p.price or 0),
        "message": "Preço inteligente aplicado à peça. Use Sincronizar no estoque para enviar o novo valor aos canais conectados."
    }


@router.get("/dismantling/{vehicle_id}")
def dismantling(vehicle_id: int, db: Session = Depends(get_db), user = Depends(active_user)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.company_id == user.company_id).first()
    if not v:
        raise HTTPException(404, "Sucata não encontrada")

    terms = [
        ("Motor", 96), ("Câmbio", 94), ("Módulo", 90), ("Alternador", 86), ("Farol", 84),
        ("Compressor", 82), ("Lanterna", 80), ("Retrovisor", 76), ("Porta", 70), ("Banco", 62)
    ]
    all_items = (
        db.query(SaleItem, Product, Sale)
        .join(Product, Product.id == SaleItem.product_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.company_id == user.company_id)
        .all()
    )

    suggestions = []
    for label, base_score in terms:
        matches = []
        qty = 0
        for item, prod, sale in all_items:
            if label.lower() in (prod.name or "").lower():
                same_vehicle = (prod.brand or "").lower() == (v.brand or "").lower()
                price = float(item.unit_price or 0)
                if price > 0:
                    matches.append(price * (1.15 if same_vehicle else 1))
                qty += int(item.quantity or 0)
        avg_price = mean(matches) if matches else 0
        score = min(100, base_score + min(10, qty))
        priority = "Alta" if score >= 85 else ("Média" if score >= 70 else "Normal")
        suggestions.append({
            "piece": label, "score": score, "priority": priority,
            "historical_sales": qty, "estimated_price": round(avg_price, 2),
        })

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    linked_products = db.query(Product).filter(
        Product.company_id == user.company_id, Product.vehicle_id == v.id, Product.active == True
    ).all()
    sold_revenue = 0
    for p in linked_products:
        rows = db.query(SaleItem).filter(SaleItem.product_id == p.id).all()
        sold_revenue += sum(float(i.unit_price or 0) * int(i.quantity or 0) for i in rows)

    estimated_total = round(sum(float(x.get("estimated_price") or 0) for x in suggestions), 2)
    high_priority_count = sum(1 for x in suggestions if x.get("priority") == "Alta")
    return {
        "vehicle": {"id": v.id, "brand": v.brand, "model": v.model, "year": v.year, "plate": v.plate},
        "suggestions": suggestions,
        "linked_products": len(linked_products),
        "revenue_from_linked_parts": round(sold_revenue, 2),
        "estimated_total": estimated_total,
        "high_priority_count": high_priority_count,
        "generated_at": datetime.utcnow(),
        "note": "A prioridade usa o histórico da própria empresa e uma base operacional. Valores estimados só aparecem quando existe histórico de venda compatível."
    }


@router.get("/public/catalog/{company_id}")
def public_catalog(company_id: int, q: str = "", db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id, Company.active == True).first()
    if not company:
        raise HTTPException(404, "Loja não encontrada")
    query = db.query(Product).filter(
        Product.company_id == company_id,
        Product.active == True,
        Product.public_catalog == True,
        Product.stock > 0,
    )
    term = q.strip().lower()
    rows = query.order_by(Product.id.desc()).limit(120).all()
    if term:
        rows = [
            p for p in rows
            if term in " ".join([
                p.sku or "", p.name or "", p.brand or "", p.model or "",
                str(p.year or ""), p.compatibility or "", p.oem or ""
            ]).lower()
        ]
        db.add(SearchEvent(company_id=company_id, query=q[:220], results_count=len(rows), source="catalogo_publico"))
        db.commit()
    return {
        "company": {
            "id": company.id, "name": company.trade_name or company.legal_name or "Autopeças",
            "phone": company.phone or "", "city": company.city or "", "state": company.state or ""
        },
        "query": q,
        "products": [
            {
                "id": p.id, "sku": p.sku, "name": p.name, "brand": p.brand, "model": p.model,
                "year": p.year, "price": p.price, "stock": p.stock, "compatibility": p.compatibility,
                "quality_grade": getattr(p, "quality_grade", "B"), "warranty_days": getattr(p, "warranty_days", 90),
                "has_image": bool((p.image_urls or "").strip())
            }
            for p in rows
        ]
    }


def _warranty_sign(company_id: int, sale_id: int, product_id: int):
    raw = f"{company_id}:{sale_id}:{product_id}"
    sig = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    payload = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"{payload}.{sig}"


def _warranty_decode(token: str):
    try:
        payload, sig = token.split(".", 1)
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        company_id, sale_id, product_id = [int(x) for x in raw.split(":")]
        expected = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            raise ValueError("assinatura")
        return company_id, sale_id, product_id
    except Exception:
        raise HTTPException(400, "Código de garantia inválido")


class WarrantyIn(BaseModel):
    sale_id: int
    product_id: int


@router.post("/warranty-token")
def warranty_token(data: WarrantyIn, db: Session = Depends(get_db), user = Depends(active_user)):
    sale = db.query(Sale).filter(Sale.id == data.sale_id, Sale.company_id == user.company_id).first()
    product = db.query(Product).filter(Product.id == data.product_id, Product.company_id == user.company_id).first()
    if not sale or not product:
        raise HTTPException(404, "Venda ou peça não encontrada")
    item = db.query(SaleItem).filter(
        SaleItem.sale_id == sale.id, SaleItem.product_id == product.id, SaleItem.company_id == user.company_id
    ).first()
    if not item:
        raise HTTPException(400, "Esta peça não faz parte da venda informada")
    return {
        "token": _warranty_sign(user.company_id, sale.id, product.id),
        "warranty_days": int(getattr(product, "warranty_days", 90) or 0),
    }


@router.get("/public/warranty/{token}")
def public_warranty(token: str, db: Session = Depends(get_db)):
    company_id, sale_id, product_id = _warranty_decode(token)
    company = db.get(Company, company_id)
    sale = db.query(Sale).filter(Sale.id == sale_id, Sale.company_id == company_id).first()
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company_id).first()
    if not company or not sale or not product:
        raise HTTPException(404, "Garantia não encontrada")
    days = int(getattr(product, "warranty_days", 90) or 0)
    start = sale.created_at or datetime.utcnow()
    expires = start + timedelta(days=days)
    return {
        "company": company.trade_name or company.legal_name or "CDM",
        "sale_id": sale.id, "product": product.name, "sku": product.sku,
        "quality_grade": getattr(product, "quality_grade", "B"),
        "warranty_days": days, "purchased_at": start, "expires_at": expires,
        "active": days > 0 and datetime.utcnow() <= expires,
    }


class AssistantIn(BaseModel):
    message: str = Field(min_length=2, max_length=2500)


class ProductPhotoAnalysisIn(BaseModel):
    images: list[str] = Field(default_factory=list)
    vehicle_id: int | None = None
    context: dict = Field(default_factory=dict)


def _response_output_text(data: dict):
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    parts = []
    for item in data.get("output") or []:
        for c in item.get("content") or []:
            if c.get("type") == "output_text" and c.get("text"):
                parts.append(c["text"])
    return "\n".join(parts).strip()


def _json_from_ai_text(text: str):
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                pass
    return None


@router.post("/product-photo-analysis")
def product_photo_analysis(data: ProductPhotoAnalysisIn, db: Session = Depends(get_db), user = Depends(active_user)):
    load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=True)
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "").strip()
    if not key or not model:
        raise HTTPException(503, "IA por foto ainda não está configurada no servidor")

    images = []
    for value in (data.images or [])[:3]:
        img = str(value or "").strip()
        if img.startswith("data:image/") or img.startswith("https://") or img.startswith("http://"):
            images.append(img)
    if not images:
        raise HTTPException(400, "Envie pelo menos uma foto da peça")
    if sum(len(x) for x in images) > 8_000_000:
        raise HTTPException(413, "As fotos ficaram muito grandes. Envie até 3 fotos menores")

    vehicle_context = None
    if data.vehicle_id:
        v = db.query(Vehicle).filter(
            Vehicle.id == data.vehicle_id,
            Vehicle.company_id == user.company_id
        ).first()
        if v:
            vehicle_context = {
                "id": v.id,
                "marca": v.brand or "",
                "modelo": v.model or "",
                "ano": v.year,
                "placa": v.plate or "",
            }

    safe_context = {
        "veiculo_origem_selecionado": vehicle_context,
        "dados_ja_preenchidos": {
            "nome": str(data.context.get("name") or "")[:180],
            "marca": str(data.context.get("brand") or "")[:80],
            "modelo": str(data.context.get("model") or "")[:120],
            "ano": str(data.context.get("year") or "")[:10],
        },
        "grupos_existentes": [str(x)[:120] for x in (data.context.get("groups") or [])[:80]],
    }

    prompt = f'''\nVocê é o módulo Cadastro de Peças com IA do CDM Desmontes, um ERP brasileiro de desmontes e autopeças.
Analise as fotos de UMA peça automotiva e devolva SOMENTE um objeto JSON válido, sem markdown e sem texto antes/depois.

CONTEXTO DO CADASTRO:
{json.dumps(safe_context, ensure_ascii=False, default=str)}

REGRAS IMPORTANTES:
- Seja conservador. Foto sozinha pode não provar aplicação exata.
- Não invente código OEM, marca, modelo, ano ou aplicação. Se não estiver visível/confiável, use string vazia ou null.
- Se houver etiqueta, gravação ou código legível na peça, transcreva em "oem". Se não estiver legível, deixe vazio.
- "condition" deve ser exatamente: "used", "new" ou "reconditioned".
- "side" use "Esquerdo", "Direito", "Ambos" ou "".
- "position" use algo curto como "Dianteiro", "Traseiro", "Superior", "Inferior" ou "".
- Em "part_group", prefira um dos grupos existentes enviados no contexto quando houver correspondência clara.
- "compatibility" deve trazer apenas aplicações possíveis com cautela. Nunca prometa compatibilidade.
- "description" deve ser uma descrição profissional para anúncio em português do Brasil, sem afirmar funcionamento que a foto não comprova.
- "marketplace_title" deve ser um título curto e útil para anúncio.
- "keywords" deve ter no máximo 10 itens.
- "warnings" deve listar o que o usuário precisa conferir manualmente.
- "confidence" deve ser "alta", "media" ou "baixa".
- Se a imagem não parecer uma peça automotiva, deixe os campos técnicos vazios e explique em warnings.

FORMATO EXATO:
{{
  "name": "",
  "category": "",
  "part_group": "",
  "side": "",
  "position": "",
  "condition": "used",
  "oem": "",
  "brand": "",
  "model": "",
  "year": null,
  "compatibility": "",
  "description": "",
  "marketplace_title": "",
  "keywords": [],
  "quality_notes": "",
  "confidence": "baixa",
  "warnings": []
}}\n'''.strip()

    content = [{"type": "input_text", "text": prompt}]
    for img in images:
        content.append({"type": "input_image", "image_url": img, "detail": "auto"})

    payload = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": 1200,
        "store": False,
    }

    try:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code >= 400:
            raise HTTPException(502, f"A IA não conseguiu analisar a foto agora (status {r.status_code})")
        parsed = _json_from_ai_text(_response_output_text(r.json()))
        if not isinstance(parsed, dict):
            raise HTTPException(502, "A IA respondeu em um formato inesperado. Tente novamente")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Não foi possível conectar ao serviço de IA agora")

    allowed_condition = {"used", "new", "reconditioned"}
    condition = str(parsed.get("condition") or "used").strip().lower()
    if condition not in allowed_condition:
        condition = "used"

    year = parsed.get("year")
    try:
        year = int(year) if year not in (None, "") else None
    except Exception:
        year = None

    def txt(name, limit):
        return str(parsed.get(name) or "").strip()[:limit]

    keywords = parsed.get("keywords") if isinstance(parsed.get("keywords"), list) else []
    warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
    confidence = str(parsed.get("confidence") or "baixa").strip().lower()
    if confidence not in {"alta", "media", "baixa"}:
        confidence = "baixa"

    return {
        "name": txt("name", 180),
        "category": txt("category", 100),
        "part_group": txt("part_group", 100),
        "side": txt("side", 40),
        "position": txt("position", 60),
        "condition": condition,
        "oem": txt("oem", 100),
        "brand": txt("brand", 80),
        "model": txt("model", 120),
        "year": year,
        "compatibility": txt("compatibility", 2000),
        "description": txt("description", 4000),
        "marketplace_title": txt("marketplace_title", 180),
        "keywords": [str(x).strip()[:80] for x in keywords[:10] if str(x).strip()],
        "quality_notes": txt("quality_notes", 1200),
        "confidence": confidence,
        "warnings": [str(x).strip()[:240] for x in warnings[:6] if str(x).strip()],
        "photos_analyzed": len(images),
    }


def _local_answer(db: Session, company_id: int, message: str):
    q = message.lower()
    snap = _snapshot(db, company_id)
    tops = _top_products(db, company_id, 90, 5)

    if any(x in q for x in ["hoje", "vendi hoje", "faturamento hoje"]):
        return f"Hoje foram {snap['sales_today']} venda(s), totalizando {_money(snap['revenue_today'])}."
    if any(x in q for x in ["30 dias", "mês", "mes", "mensal"]):
        return f"Nos últimos 30 dias a empresa registrou {snap['sales_30d']} venda(s) e {_money(snap['revenue_30d'])} em faturamento."
    if "estoque" in q and any(x in q for x in ["baixo", "acabando", "zerado"]):
        return f"Há {snap['low_stock']} peça(s) com estoque de 1 unidade ou menos. O estoque total soma {snap['stock_qty']} unidade(s)."
    if any(x in q for x in ["parada", "encalhada", "120 dias"]):
        return f"Encontrei {snap['stale_count']} peça(s) com estoque e cadastro há pelo menos 120 dias. Abra o Radar de Oportunidades para ver a lista."
    if any(x in q for x in ["mais vende", "campeã", "campea", "top"]):
        if not tops:
            return "Ainda não há histórico suficiente de vendas para montar o ranking das peças."
        return "Peças com maior saída nos últimos 90 dias: " + "; ".join(
            f"{x['name']} ({x['quantity']} un.)" for x in tops
        ) + "."
    if "saldo" in q or "financeiro" in q:
        return f"O saldo financeiro acumulado registrado no CDM é {_money(snap['balance'])}."
    return (
        f"Resumo da empresa: {snap['products']} peça(s) cadastrada(s), {snap['stock_qty']} unidade(s) em estoque, "
        f"{snap['sales_30d']} venda(s) nos últimos 30 dias e faturamento de {_money(snap['revenue_30d'])}. "
        "Você pode perguntar sobre vendas de hoje, estoque baixo, peças paradas, saldo financeiro ou peças que mais vendem."
    )


def _ai_answer(db: Session, user: User, message: str):
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "").strip()
    if not key or not model:
        return None

    company = db.get(Company, user.company_id)
    snap = _snapshot(db, user.company_id)
    top = _top_products(db, user.company_id, 90, 8)
    recent_sales = db.query(Sale).filter(Sale.company_id == user.company_id).order_by(Sale.id.desc()).limit(15).all()
    context = {
        "empresa": company.trade_name if company else "Empresa",
        "resumo": snap,
        "mais_vendidos_90d": top,
        "ultimas_vendas": [
            {"id": s.id, "total": s.total, "canal": getattr(s, "source", "manual"), "data": str(s.created_at)}
            for s in recent_sales
        ]
    }
    instructions = (
        "Você é o Assistente CDM de um ERP brasileiro de desmontes e autopeças. "
        "Responda sempre em português do Brasil, de forma curta, prática e profissional. "
        "Use somente os dados da empresa enviados no contexto. Nunca invente vendas, preços, estoque ou documentos. "
        "Quando a informação não estiver no contexto, diga claramente que não há dados suficientes. "
        "Não execute exclusões, alterações financeiras, fiscais ou publicações; apenas oriente."
    )
    payload = {
        "model": model,
        "instructions": instructions,
        "input": f"CONTEXTO DA EMPRESA:\n{json.dumps(context, ensure_ascii=False, default=str)}\n\nPERGUNTA:\n{message}",
        "max_output_tokens": 500,
        "store": False,
    }
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code >= 400:
            return None
        data = r.json()
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()
        parts = []
        for item in data.get("output") or []:
            for c in item.get("content") or []:
                if c.get("type") == "output_text" and c.get("text"):
                    parts.append(c["text"])
        return "\n".join(parts).strip() or None
    except Exception:
        return None


@router.post("/assistant/chat")
def assistant_chat(data: AssistantIn, db: Session = Depends(get_db), user = Depends(active_user)):
    used, limit = _assistant_usage(db, user.company_id)
    if used >= limit:
        raise HTTPException(429, f"Limite mensal do Assistente CDM atingido ({limit} mensagens).")
    db.add(AssistantMessage(company_id=user.company_id, user_id=user.id, role="user", content=data.message))
    db.flush()
    answer = _ai_answer(db, user, data.message) or _local_answer(db, user.company_id, data.message)
    db.add(AssistantMessage(company_id=user.company_id, user_id=user.id, role="assistant", content=answer))
    db.commit()
    return {
        "answer": answer,
        "mode": "ia" if (os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")) else "inteligencia_local",
        "automatic_access": True,
    }


@router.get("/assistant/history")
def assistant_history(db: Session = Depends(get_db), user = Depends(active_user)):
    rows = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.company_id == user.company_id, AssistantMessage.user_id == user.id)
        .order_by(AssistantMessage.id.desc())
        .limit(60)
        .all()
    )
    rows.reverse()
    return [{"id": r.id, "role": r.role, "content": r.content, "created_at": r.created_at} for r in rows]


class EvidenceIn(BaseModel):
    sale_id: int
    product_id: int | None = None
    serial_number: str = ""
    condition_notes: str = ""
    photos: list[str] = Field(default_factory=list)


@router.get("/evidence")
def list_evidence(db: Session = Depends(get_db), user = Depends(active_user)):
    rows = db.query(SaleEvidence).filter(
        SaleEvidence.company_id == user.company_id
    ).order_by(SaleEvidence.id.desc()).limit(100).all()
    out = []
    for r in rows:
        try:
            photos = json.loads(r.photo_urls_json or "[]")
        except Exception:
            photos = []
        out.append({
            "id": r.id, "sale_id": r.sale_id, "product_id": r.product_id,
            "serial_number": r.serial_number, "condition_notes": r.condition_notes,
            "photos": photos, "packed_by": r.packed_by, "created_at": r.created_at
        })
    return out


@router.post("/evidence")
def create_evidence(data: EvidenceIn, db: Session = Depends(get_db), user = Depends(active_user)):
    sale = db.query(Sale).filter(Sale.id == data.sale_id, Sale.company_id == user.company_id).first()
    if not sale:
        raise HTTPException(404, "Venda não encontrada")
    if data.product_id:
        product = db.query(Product).filter(Product.id == data.product_id, Product.company_id == user.company_id).first()
        if not product:
            raise HTTPException(404, "Peça não encontrada")
        sold_item = db.query(SaleItem).filter(
            SaleItem.sale_id == sale.id,
            SaleItem.product_id == product.id,
            SaleItem.company_id == user.company_id
        ).first()
        if not sold_item:
            raise HTTPException(400, "A peça selecionada não pertence à venda informada")
    photos = data.photos[:4]
    if sum(len(x) for x in photos) > 6_000_000:
        raise HTTPException(413, "As fotos estão muito grandes. Use até 4 fotos menores.")
    row = SaleEvidence(
        company_id=user.company_id, sale_id=data.sale_id, product_id=data.product_id,
        serial_number=data.serial_number[:120], condition_notes=data.condition_notes[:3000],
        photo_urls_json=json.dumps(photos, ensure_ascii=False),
        packed_by=user.name or user.email,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "ok": True}


class ShippingCheckIn(BaseModel):
    sale_id: int
    sku: str


@router.get("/shipping-checks")
def shipping_checks(db: Session = Depends(get_db), user = Depends(active_user)):
    rows = db.query(ShippingCheck).filter(
        ShippingCheck.company_id == user.company_id
    ).order_by(ShippingCheck.id.desc()).limit(100).all()
    return [{
        "id": r.id,
        "sale_id": r.sale_id,
        "product_id": r.product_id,
        "sku_scanned": r.sku_scanned,
        "result": "Correto" if r.result == "ok" else "Divergente",
        "checked_by": r.checked_by,
        "created_at": r.created_at,
    } for r in rows]


@router.post("/shipping-check")
def shipping_check(data: ShippingCheckIn, db: Session = Depends(get_db), user = Depends(active_user)):
    sale = db.query(Sale).filter(Sale.id == data.sale_id, Sale.company_id == user.company_id).first()
    if not sale:
        raise HTTPException(404, "Venda não encontrada")
    sku = data.sku.strip().upper()
    items = db.query(SaleItem).filter(
        SaleItem.sale_id == sale.id, SaleItem.company_id == user.company_id
    ).all()
    matched = None
    for item in items:
        p = db.get(Product, item.product_id)
        if p and (p.sku or "").upper() == sku:
            matched = p
            break
    row = ShippingCheck(
        company_id=user.company_id, sale_id=sale.id,
        product_id=matched.id if matched else None, sku_scanned=sku,
        result="ok" if matched else "divergente", checked_by=user.name or user.email,
    )
    db.add(row)
    db.commit()
    return {
        "ok": bool(matched),
        "result": "Peça correta para este pedido." if matched else "Atenção: este SKU não pertence à venda informada.",
        "product": {"id": matched.id, "sku": matched.sku, "name": matched.name} if matched else None,
    }

