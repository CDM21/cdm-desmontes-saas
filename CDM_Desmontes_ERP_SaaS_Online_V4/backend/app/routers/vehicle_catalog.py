from fastapi import APIRouter, Query
from ..vehicle_catalog import brands, models_for

router = APIRouter()

@router.get("/brands")
def list_brands():
    return {"brands": brands()}

@router.get("/models")
def list_models(brand: str = Query(default="")):
    return {"brand": brand, "models": models_for(brand)}

@router.get("/years")
def list_years():
    from datetime import datetime
    current = datetime.utcnow().year + 1
    return {"years": list(range(current, 1970, -1))}
