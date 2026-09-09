from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user, active_user
from ..models import Customer,Supplier,Carrier,Seller,PartGroup,Location,TaxConfig,User
from ..security import hash_password

router=APIRouter()

class PartyIn(BaseModel):
    name:str
    cpf_cnpj:str=""
    phone:str=""
    email:str=""
    address:str=""
class CarrierIn(BaseModel):
    name:str
    cnpj:str=""
    phone:str=""
    email:str=""
class SellerIn(BaseModel):
    name:str
    email:str=""
    phone:str=""
    commission_rate:float=0
class PartGroupIn(BaseModel):
    name:str
    description:str=""
class LocationIn(BaseModel):
    warehouse:str
    aisle:str=""
    shelf:str=""
    bin:str=""
class TaxIn(BaseModel):
    regime:str="Simples Nacional"
    crt:str="1"
    cfop_default:str="5102"
    ncm_default:str=""
    csosn_default:str="102"
    notes:str=""
class UserIn(BaseModel):
    name:str
    email:str
    password:str
    role:str="user"

@router.get("/customers")
def customers(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Customer).filter(Customer.company_id==user.company_id).order_by(Customer.id.desc()).all()
@router.post("/customers")
def add_customer(data:PartyIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=Customer(company_id=user.company_id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row

@router.get("/suppliers")
def suppliers(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Supplier).filter(Supplier.company_id==user.company_id).order_by(Supplier.id.desc()).all()
@router.post("/suppliers")
def add_supplier(data:PartyIn,db:Session=Depends(get_db),user=Depends(active_user)):
    payload=data.model_dump();payload.pop("address",None);row=Supplier(company_id=user.company_id,**payload);db.add(row);db.commit();db.refresh(row);return row

@router.get("/carriers")
def carriers(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Carrier).filter(Carrier.company_id==user.company_id).order_by(Carrier.id.desc()).all()
@router.post("/carriers")
def add_carrier(data:CarrierIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=Carrier(company_id=user.company_id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row

@router.get("/sellers")
def sellers(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Seller).filter(Seller.company_id==user.company_id).order_by(Seller.id.desc()).all()
@router.post("/sellers")
def add_seller(data:SellerIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=Seller(company_id=user.company_id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row

@router.get("/part-groups")
def part_groups(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(PartGroup).filter(PartGroup.company_id==user.company_id).order_by(PartGroup.name).all()
@router.post("/part-groups")
def add_part_group(data:PartGroupIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=PartGroup(company_id=user.company_id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row

@router.get("/locations")
def locations(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Location).filter(Location.company_id==user.company_id).order_by(Location.id.desc()).all()
@router.post("/locations")
def add_location(data:LocationIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=Location(company_id=user.company_id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row

@router.get("/tax")
def tax(db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first()
    if not row:
        row=TaxConfig(company_id=user.company_id);db.add(row);db.commit();db.refresh(row)
    return row
@router.put("/tax")
def update_tax(data:TaxIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first()
    if not row: row=TaxConfig(company_id=user.company_id);db.add(row)
    for k,v in data.model_dump().items(): setattr(row,k,v)
    db.commit();db.refresh(row);return row

@router.get("/users")
def users(db:Session=Depends(get_db),user=Depends(active_user)):
    rows=db.query(User).filter(User.company_id==user.company_id).order_by(User.id.desc()).all()
    return [{"id":r.id,"name":r.name,"email":r.email,"role":r.role,"active":r.active} for r in rows]
@router.post("/users")
def add_user(data:UserIn,db:Session=Depends(get_db),user=Depends(active_user)):
    if user.role not in {"owner","admin"}: raise HTTPException(403,"Sem permissão")
    if db.query(User).filter(User.email==data.email.lower().strip()).first(): raise HTTPException(409,"E-mail já cadastrado")
    if len(data.password)<6: raise HTTPException(400,"Senha deve ter pelo menos 6 caracteres")
    row=User(company_id=user.company_id,name=data.name,email=data.email.lower().strip(),role=data.role,password_hash=hash_password(data.password));db.add(row);db.commit();db.refresh(row);return {"id":row.id,"name":row.name,"email":row.email,"role":row.role,"active":row.active}
