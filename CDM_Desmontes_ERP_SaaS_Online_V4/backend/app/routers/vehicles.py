from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Vehicle,Dismantling
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
