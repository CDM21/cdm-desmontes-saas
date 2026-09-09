from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user
from ..models import Company, Subscription

router=APIRouter()

class CompanyIn(BaseModel):
    trade_name:str=""
    legal_name:str=""
    cnpj:str=""
    state_registration:str=""
    tax_regime:str="Simples Nacional"
    email:str=""
    phone:str=""
    responsible_name:str=""
    rg:str=""
    cpf:str=""
    issuing_agency:str=""
    cep:str=""
    state:str="RJ"
    city:str=""
    address:str=""
    number:str=""
    complement:str=""
    logo_url:str=""

@router.get("/me")
def get_company(db:Session=Depends(get_db), user=Depends(current_user)):
    company=db.get(Company,user.company_id)
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    return {"company":company,"subscription":sub}

@router.put("/me")
def update_company(data:CompanyIn, db:Session=Depends(get_db), user=Depends(current_user)):
    if user.role not in {"owner","admin"}: raise HTTPException(403,"Apenas administradores podem alterar a empresa")
    company=db.get(Company,user.company_id)
    if not company: raise HTTPException(404,"Empresa não encontrada")
    for k,v in data.model_dump().items(): setattr(company,k,v)
    db.commit(); db.refresh(company)
    return company
