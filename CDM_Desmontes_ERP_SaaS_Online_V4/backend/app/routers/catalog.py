from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import active_user
from ..models import Customer,Supplier,Carrier,Seller,PartGroup,Location,TaxConfig,User
from ..security import hash_password

router=APIRouter()

class PartyIn(BaseModel):
    name:str
    cpf_cnpj:str=""
    phone:str=""
    email:str=""
    address:str=""
class SupplierIn(BaseModel):
    name:str
    trade_name:str=""
    cpf_cnpj:str=""
    rg_ie:str=""
    mobile:str=""
    phone:str=""
    cep:str=""
    city:str=""
    state:str=""
    number:str=""
    address:str=""
    neighborhood:str=""
    complement:str=""
    ibge:str=""
    email:str=""
    active:bool=True
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
    code:str=""
    description:str=""
    max_quantity:int=0
    auto_generate:bool=False
    warehouse:str=""
    aisle:str=""
    shelf:str=""
    bin:str=""
    active:bool=True
class TaxIn(BaseModel):
    state:str="RJ"
    tax_profile:str="Simples Nacional"
    operation_nature:str="Venda de mercadoria"
    regime:str="Simples Nacional"
    crt:str="1"
    cfop_default:str="5102"
    ncm_default:str=""
    csosn_default:str="102"
    icms_cst:str=""
    icms_rate:float=0
    pis_cst:str="49"
    pis_rate:float=0
    cofins_cst:str="49"
    cofins_rate:float=0
    ipi_cst:str="53"
    ipi_rate:float=0
    ibs_cbs_notes:str=""
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
@router.put("/customers/{customer_id}")
def update_customer(customer_id:int,data:PartyIn,db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(Customer).filter(Customer.id==customer_id,Customer.company_id==user.company_id).first()
    if not row:
        raise HTTPException(404,"Cliente não encontrado")
    for k,v in data.model_dump().items():
        setattr(row,k,v)
    db.commit();db.refresh(row);return row

@router.get("/suppliers")
def suppliers(db:Session=Depends(get_db),user=Depends(active_user)):
    return db.query(Supplier).filter(Supplier.company_id==user.company_id).order_by(Supplier.id.desc()).all()
@router.post("/suppliers")
def add_supplier(data:SupplierIn,db:Session=Depends(get_db),user=Depends(active_user)):
    if not data.cpf_cnpj.strip(): raise HTTPException(400,"CPF / CNPJ é obrigatório")
    if not data.name.strip(): raise HTTPException(400,"Razão Social / Nome é obrigatório")
    row=Supplier(company_id=user.company_id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row
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
    payload=data.model_dump()
    if payload["auto_generate"] and not payload["code"]:
        last=db.query(Location).filter(Location.company_id==user.company_id).order_by(Location.id.desc()).first()
        payload["code"]=f"LOC-{((last.id if last else 0)+1):04d}"
    if not payload["description"].strip() and payload["warehouse"].strip(): payload["description"]=payload["warehouse"].strip()
    if not payload["warehouse"].strip(): payload["warehouse"]=payload["description"].strip() or payload["code"].strip()
    if not payload["code"].strip(): raise HTTPException(400,"Sigla é obrigatória")
    if not payload["description"].strip(): raise HTTPException(400,"Descrição é obrigatória")
    row=Location(company_id=user.company_id,**payload);db.add(row);db.commit();db.refresh(row);return row
@router.get("/tax")
def tax(db:Session=Depends(get_db),user=Depends(active_user)):
    row=db.query(TaxConfig).filter(TaxConfig.company_id==user.company_id).first()
    if not row: row=TaxConfig(company_id=user.company_id);db.add(row);db.commit();db.refresh(row)
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
    if len(data.password)<8: raise HTTPException(400,"Senha deve ter pelo menos 8 caracteres")
    row=User(company_id=user.company_id,name=data.name,email=data.email.lower().strip(),role=data.role,password_hash=hash_password(data.password));db.add(row);db.commit();db.refresh(row)
    return {"id":row.id,"name":row.name,"email":row.email,"role":row.role,"active":row.active}
