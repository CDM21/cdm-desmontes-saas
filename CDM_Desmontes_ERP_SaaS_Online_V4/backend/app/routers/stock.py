from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Product, Location, StockMovement
from ..deps import active_user
from ..admin import audit
from ..services.marketplaces import sync_marketplace_stock_for_product

router = APIRouter()


class LocationIn(BaseModel):
    warehouse: str
    aisle: str = ""
    shelf: str = ""
    bin: str = ""


class MoveIn(BaseModel):
    product_id: int
    location_id: int
    quantity: int = 0


@router.get("/locations")
def locations(db: Session = Depends(get_db), user=Depends(active_user)):
    return db.query(Location).filter(Location.company_id == user.company_id).all()


@router.post("/locations")
def create_location(data: LocationIn, db: Session = Depends(get_db), user=Depends(active_user)):
    row = Location(company_id=user.company_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/movements")
def movements(limit: int = 200, product_id: int | None = None, db: Session = Depends(get_db), user=Depends(active_user)):
    query=db.query(StockMovement).filter(StockMovement.company_id == user.company_id)
    if product_id is not None: query=query.filter(StockMovement.product_id==product_id)
    return query.order_by(StockMovement.id.desc()).limit(max(1,min(limit,1000))).all()


@router.post("/move")
def move(data: MoveIn, db: Session = Depends(get_db), user=Depends(active_user)):
    product = (
        db.query(Product)
        .filter(Product.id == data.product_id, Product.company_id == user.company_id)
        .with_for_update()
        .first()
    )
    location = db.query(Location).filter(
        Location.id == data.location_id,
        Location.company_id == user.company_id,
    ).first()
    if not product or not location:
        raise HTTPException(404, "Produto/local não encontrado")

    old_stock = int(product.stock or 0)
    product.location_id = location.id
    # Mantém compatibilidade com a V6: zero significa somente trocar a localização.
    if data.quantity:
        product.stock = max(0, int(data.quantity))

    new_stock = int(product.stock or 0)
    delta = new_stock - old_stock
    if delta:
        db.add(StockMovement(
            company_id=user.company_id,
            product_id=product.id,
            kind="adjustment",
            quantity_delta=delta,
            balance_after=new_stock,
            reference=f"Ajuste manual/local {location.id}",
        ))
    audit(db, user, "stock.move", "product", product.id, {
        "from": old_stock,
        "to": new_stock,
        "location_id": location.id,
    })
    db.commit()
    db.refresh(product)

    sync_result = []
    if delta:
        try:
            sync_result = sync_marketplace_stock_for_product(db, product, user.company_id)
        except Exception as exc:
            sync_result = [{"marketplace": "all", "ok": False, "error": str(exc)[:300]}]

    return {
        "ok": True,
        "product_id": product.id,
        "location_id": location.id,
        "stock": product.stock,
        "quantity_delta": delta,
        "marketplace_sync": sync_result,
    }
