from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from ..db import get_db
from ..models import Vehicle,VehiclePhoto,Dismantling,Product,SaleItem,Sale,VehicleExpense
from ..deps import current_user, active_user, require_roles

router=APIRouter()

MAX_VEHICLE_PHOTOS = 15

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


class VehiclePhotoIn(BaseModel):
    photo_data:str=""


class VehicleExpenseIn(BaseModel):
    category:str="Outros"
    description:str=""
    amount:float=0
    expense_date:str=""

@router.get("")
def list_vehicles(db:Session=Depends(get_db), user=Depends(active_user)):
    return db.query(Vehicle).filter(Vehicle.company_id==user.company_id).order_by(Vehicle.id.desc()).all()

@router.post("")
def create_vehicle(data:VehicleIn, db:Session=Depends(get_db), user=Depends(require_roles("owner","admin","manager","stock"))):
    payload=data.model_dump()
    payload["plate"]=(payload.get("plate") or "").strip().upper()
    payload["vin"]=(payload.get("vin") or "").strip().upper()
    payload["renavam"]=(payload.get("renavam") or "").strip()
    payload["brand"]=(payload.get("brand") or "").strip()
    payload["model"]=(payload.get("model") or "").strip()
    payload["fuel"]=(payload.get("fuel") or "").strip()
    payload["transmission"]=(payload.get("transmission") or "").strip()
    payload["color"]=(payload.get("color") or "").strip()
    payload["acquisition_value"]=round(float(payload.get("acquisition_value") or 0),2)
    payload["other_costs"]=round(float(payload.get("other_costs") or 0),2)

    if not payload["brand"]:
        raise HTTPException(400,"Selecione a marca do veículo")
    if not payload["model"]:
        raise HTTPException(400,"Selecione ou informe o modelo do veículo")
    year=payload.get("year")
    if year is not None and (int(year)<1971 or int(year)>datetime.utcnow().year+1):
        raise HTTPException(400,"Ano do veículo inválido")

    try:
        v=Vehicle(company_id=user.company_id,**payload)
        db.add(v)
        db.commit()
        db.refresh(v)
        return v
    except SQLAlchemyError as exc:
        db.rollback()
        message=str(getattr(exc,"orig",exc))
        if "other_costs" in message.lower() or "column" in message.lower():
            raise HTTPException(500,"O banco de dados do cadastro de sucatas precisa ser atualizado. Aguarde o novo deploy e tente novamente.")
        raise HTTPException(500,"Não foi possível salvar a sucata no banco de dados")


@router.put("/{vehicle_id}/photo")
def save_vehicle_photo(vehicle_id:int,data:VehiclePhotoIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
    row=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not row:
        raise HTTPException(404,"Veiculo nao encontrado")
    photo=(data.photo_data or "").strip()
    if photo:
        allowed=("data:image/jpeg;base64,","data:image/jpg;base64,","data:image/png;base64,","data:image/webp;base64,")
        if not photo.lower().startswith(allowed):
            raise HTTPException(400,"Formato de foto invalido. Use JPG, PNG ou WEBP")
        if len(photo)>1500000:
            raise HTTPException(400,"A foto ficou muito grande. Escolha outra imagem.")
    row.photo_data=photo
    db.commit()
    db.refresh(row)
    return {"ok":True,"vehicle_id":row.id,"has_photo":bool(row.photo_data)}


def _clean_vehicle_photo(photo_data:str):
    photo=(photo_data or "").strip()
    if not photo:
        raise HTTPException(400,"Foto vazia")
    allowed=("data:image/jpeg;base64,","data:image/jpg;base64,","data:image/png;base64,","data:image/webp;base64,")
    if not photo.lower().startswith(allowed):
        raise HTTPException(400,"Formato de foto invalido. Use JPG, PNG ou WEBP")
    if len(photo)>1500000:
        raise HTTPException(400,"A foto ficou muito grande. Escolha outra imagem.")
    return photo


@router.get("/{vehicle_id}/photos")
def list_vehicle_photos(vehicle_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    vehicle=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not vehicle:
        raise HTTPException(404,"Veiculo nao encontrado")
    rows=db.query(VehiclePhoto).filter(
        VehiclePhoto.vehicle_id==vehicle_id,
        VehiclePhoto.company_id==user.company_id
    ).order_by(VehiclePhoto.position.asc(),VehiclePhoto.id.asc()).all()
    if not rows and vehicle.photo_data:
        return [{"id":0,"photo_data":vehicle.photo_data,"position":0,"is_primary":True,"legacy":True}]
    return [{
        "id":row.id,
        "photo_data":row.photo_data,
        "position":row.position,
        "is_primary":bool(vehicle.photo_data and row.photo_data==vehicle.photo_data),
        "legacy":False
    } for row in rows]


@router.post("/{vehicle_id}/photos")
def add_vehicle_gallery_photo(vehicle_id:int,data:VehiclePhotoIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
    vehicle=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not vehicle:
        raise HTTPException(404,"Veiculo nao encontrado")
    count=db.query(VehiclePhoto).filter(
        VehiclePhoto.vehicle_id==vehicle_id,
        VehiclePhoto.company_id==user.company_id
    ).count()
    if count>=MAX_VEHICLE_PHOTOS:
        raise HTTPException(400,f"Limite de {MAX_VEHICLE_PHOTOS} fotos por sucata atingido")
    photo=_clean_vehicle_photo(data.photo_data)
    row=VehiclePhoto(
        company_id=user.company_id,
        vehicle_id=vehicle_id,
        photo_data=photo,
        position=count
    )
    db.add(row)
    if not vehicle.photo_data:
        vehicle.photo_data=photo
    db.commit()
    db.refresh(row)
    return {
        "id":row.id,
        "photo_data":row.photo_data,
        "position":row.position,
        "is_primary":bool(vehicle.photo_data==row.photo_data)
    }


@router.delete("/{vehicle_id}/photos/{photo_id}")
def delete_vehicle_gallery_photo(vehicle_id:int,photo_id:int,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
    vehicle=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not vehicle:
        raise HTTPException(404,"Veiculo nao encontrado")
    row=db.query(VehiclePhoto).filter(
        VehiclePhoto.id==photo_id,
        VehiclePhoto.vehicle_id==vehicle_id,
        VehiclePhoto.company_id==user.company_id
    ).first()
    if not row:
        raise HTTPException(404,"Foto nao encontrada")
    was_primary=bool(vehicle.photo_data and vehicle.photo_data==row.photo_data)
    db.delete(row)
    db.flush()
    if was_primary:
        next_row=db.query(VehiclePhoto).filter(
            VehiclePhoto.vehicle_id==vehicle_id,
            VehiclePhoto.company_id==user.company_id,
            VehiclePhoto.id!=photo_id
        ).order_by(VehiclePhoto.position.asc(),VehiclePhoto.id.asc()).first()
        vehicle.photo_data=next_row.photo_data if next_row else ""
    db.commit()
    return {"ok":True}


@router.put("/{vehicle_id}/photos/{photo_id}/primary")
def set_vehicle_primary_photo(vehicle_id:int,photo_id:int,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
    vehicle=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not vehicle:
        raise HTTPException(404,"Veiculo nao encontrado")
    row=db.query(VehiclePhoto).filter(
        VehiclePhoto.id==photo_id,
        VehiclePhoto.vehicle_id==vehicle_id,
        VehiclePhoto.company_id==user.company_id
    ).first()
    if not row:
        raise HTTPException(404,"Foto nao encontrada")
    vehicle.photo_data=row.photo_data
    db.commit()
    return {"ok":True,"photo_id":row.id}


@router.put("/{vehicle_id}")
def update_vehicle(vehicle_id:int,data:VehicleIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager","stock"))):
    row=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not row:
        raise HTTPException(404,"Veículo não encontrado")
    for k,v in data.model_dump().items():
        setattr(row,k,v)
    db.commit();db.refresh(row);return row



@router.get("/{vehicle_id}/expenses")
def vehicle_expenses(vehicle_id:int,db:Session=Depends(get_db),user=Depends(active_user)):
    v=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not v:
        raise HTTPException(404,"Veículo não encontrado")
    return db.query(VehicleExpense).filter(
        VehicleExpense.company_id==user.company_id,
        VehicleExpense.vehicle_id==vehicle_id
    ).order_by(VehicleExpense.id.desc()).all()


@router.post("/{vehicle_id}/expenses")
def add_vehicle_expense(vehicle_id:int,data:VehicleExpenseIn,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager"))):
    v=db.query(Vehicle).filter(Vehicle.id==vehicle_id,Vehicle.company_id==user.company_id).first()
    if not v:
        raise HTTPException(404,"Veículo não encontrado")
    amount=round(float(data.amount or 0),2)
    if amount<=0:
        raise HTTPException(400,"Informe um valor de despesa maior que zero")
    row=VehicleExpense(
        company_id=user.company_id,
        vehicle_id=vehicle_id,
        category=(data.category or "Outros").strip() or "Outros",
        description=(data.description or "").strip(),
        amount=amount,
        expense_date=(data.expense_date or "").strip(),
    )
    db.add(row);db.commit();db.refresh(row);return row


@router.delete("/{vehicle_id}/expenses/{expense_id}")
def delete_vehicle_expense(vehicle_id:int,expense_id:int,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","manager"))):
    row=db.query(VehicleExpense).filter(
        VehicleExpense.id==expense_id,
        VehicleExpense.vehicle_id==vehicle_id,
        VehicleExpense.company_id==user.company_id
    ).first()
    if not row:
        raise HTTPException(404,"Despesa não encontrada")
    db.delete(row);db.commit()
    return {"ok":True}


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

    expenses=db.query(VehicleExpense).filter(
        VehicleExpense.company_id==user.company_id,
        VehicleExpense.vehicle_id==vehicle_id
    ).order_by(VehicleExpense.id.desc()).all()
    expenses_total=round(sum(float(x.amount or 0) for x in expenses),2)

    acquisition=float(v.acquisition_value or 0)
    other=float(v.other_costs or 0)
    invested=acquisition+other+expenses_total
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
            "vehicle_expenses":expenses_total,
            "total_additional_costs":round(other+expenses_total,2),
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
        "expenses":[{
            "id":x.id,
            "category":x.category or "Outros",
            "description":x.description or "",
            "amount":round(float(x.amount or 0),2),
            "expense_date":x.expense_date or "",
            "created_at":x.created_at.isoformat() if x.created_at else None,
        } for x in expenses],
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
