from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Vehicle,Dismantling,Product,SaleItem,Sale
from ..deps import current_user, active_user

router=APIRouter()

class VehicleIn(BaseModel):
    plate:str=""
    vin:str=""
    renavam:str=""
    brand:str=""
    model:str=""
    year:int|None=None
    fuel:str=""
    transmission:str=""
    color:str=""
    acquisition_value:float=0
    other_costs:float=0

@router.get("")
def list_vehicles(db:Session=Depends(get_db), user=Depends(active_user)):
    return db.query(Vehicle).filter(Vehicle.company_id==user.company_id).order_by(Vehicle.id.desc()).all()

@router.post("")
def create_vehicle(data:VehicleIn, db:Session=Depends(get_db), user=Depends(active_user)):
    v=Vehicle(company_id=user.company_id,**data.model_dump()); db.add(v); db.commit(); db.refresh(v); return v


@router.put("/{vehicle_id}")
def update_vehicle(vehicle_id:int,data:VehicleIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not row:
        raise HTTPException(404,"Veículo não encontrado")
    for k,v in data.model_dump().items():
        setattr(row,k,v)
    db.commit();db.refresh(row);return row


@router.get("/{vehicle_id}/overview")
def vehicle_overview(vehicle_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    v=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not v:
        raise HTTPException(404,"Veículo não encontrado")

    products=db.query(Product).filter(
        Product.company_id==user.company_id,
        Product.vehicle_id==vehicle_id
    ).order_by(Product.id.desc()).all()

    product_ids=[p.id for p in products]
    sales_by_product={}
    if product_ids:
        rows=db.query(SaleItem,Sale).join(Sale,Sale.id==SaleItem.sale_id).filter(
            SaleItem.company_id==user.company_id,
            Sale.company_id==user.company_id,
            SaleItem.product_id.in_(product_ids),
            Sale.status.notin_(["canceled","cancelled","rejected"])
        ).all()
        for item,sale in rows:
            info=sales_by_product.setdefault(item.product_id,{"qty":0,"revenue":0.0})
            info["qty"]+=int(item.quantity or 0)
            info["revenue"]+=float(item.unit_price or 0)*int(item.quantity or 0)

    part_rows=[]
    revenue=0.0
    sold_qty=0
    stock_qty=0
    stock_value=0.0
    skus_in_stock=0
    registered_units=0

    for p in products:
        sale_info=sales_by_product.get(p.id,{"qty":0,"revenue":0.0})
        p_sold=int(sale_info["qty"])
        p_revenue=round(float(sale_info["revenue"]),2)
        p_stock=max(0,int(p.stock or 0))
        p_price=float(p.price or 0)

        revenue+=p_revenue
        sold_qty+=p_sold
        stock_qty+=p_stock
        stock_value+=p_stock*p_price
        registered_units+=p_stock+p_sold
        if p_stock>0:
            skus_in_stock+=1

        part_rows.append({
            "id":p.id,
            "sku":p.sku or "",
            "name":p.name or "",
            "stock":p_stock,
            "sold_qty":p_sold,
            "price":round(p_price,2),
            "revenue":p_revenue,
            "estimated_stock_value":round(p_stock*p_price,2),
            "active":bool(p.active),
        })

    acquisition=float(v.acquisition_value or 0)
    other=float(v.other_costs or 0)
    invested=acquisition+other
    revenue=round(revenue,2)
    stock_value=round(stock_value,2)
    potential_total=round(revenue+stock_value,2)
    realized_result=round(revenue-invested,2)
    potential_profit=round(potential_total-invested,2)
    recovery_percent=round((revenue/invested*100),1) if invested>0 else 0.0

    dismantling=db.query(Dismantling).filter(
        Dismantling.company_id==user.company_id,
        Dismantling.vehicle_id==vehicle_id
    ).order_by(Dismantling.id.desc()).first()

    status_labels={
        "received":"Recebido",
        "dismantling":"Em desmontagem",
        "available":"Disponível",
        "sold":"Vendido",
        "completed":"Concluído",
        "finished":"Finalizado",
    }
    dismantling_labels={
        "pending":"Pendente",
        "in_progress":"Em andamento",
        "completed":"Concluído",
        "finished":"Finalizado",
    }

    return {
        "vehicle":{
            "id":v.id,"plate":v.plate or "","brand":v.brand or "","model":v.model or "",
            "year":v.year,"fuel":v.fuel or "","transmission":v.transmission or "",
            "color":v.color or "","vin":v.vin or "","renavam":v.renavam or "",
            "status":v.status or "received",
            "status_label":status_labels.get(v.status or "received",v.status or "Recebido"),
        },
        "investment":{
            "acquisition_value":round(acquisition,2),
            "other_costs":round(other,2),
            "total_invested":round(invested,2),
        },
        "parts":{
            "registered_skus":len(products),
            "registered_units":registered_units,
            "sold_qty":sold_qty,
            "stock_qty":stock_qty,
            "skus_in_stock":skus_in_stock,
        },
        "result":{
            "revenue":revenue,
            "realized_result":realized_result,
            "estimated_stock_value":stock_value,
            "potential_total":potential_total,
            "potential_profit":potential_profit,
            "recovery_percent":recovery_percent,
        },
        "dismantling":{
            "status":dismantling.status if dismantling else "pending",
            "status_label":dismantling_labels.get(dismantling.status if dismantling else "pending",dismantling.status if dismantling else "Pendente"),
        },
        "products":part_rows,
    }

@router.get("/{vehicle_id}")
def get_vehicle(vehicle_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    v=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not v: raise HTTPException(404,"Veículo não encontrado")
    return v

@router.post("/{vehicle_id}/dismantling")
def start_dismantling(vehicle_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    v=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not v: raise HTTPException(404,"Veículo não encontrado")
    v.status="dismantling"
    d=Dismantling(company_id=user.company_id,vehicle_id=vehicle_id,status="in_progress")
    db.add(d); db.commit(); db.refresh(d); return d
