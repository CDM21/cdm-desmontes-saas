import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Company, Subscription
from ..security import verify_password, hash_password, create_token
from ..deps import current_user

router=APIRouter()

class Login(BaseModel):
    email:str
    password:str

class Register(BaseModel):
    company_name:str
    name:str
    email:str
    password:str
    cnpj:str=""
    phone:str=""


def session_payload(db:Session,user:User):
    company=db.get(Company,user.company_id)
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    return {
        "access_token":create_token(user.id),
        "user":{"id":user.id,"name":user.name,"email":user.email,"role":user.role,"company_id":user.company_id},
        "company":company,
        "subscription":sub,
    }

@router.post("/login")
def login(data:Login, db:Session=Depends(get_db)):
    user=db.query(User).filter(User.email==data.email).first()
    if not user or not verify_password(data.password,user.password_hash):
        raise HTTPException(401,"E-mail ou senha inválidos")
    if not user.active: raise HTTPException(403,"Usuário desativado")
    company=db.get(Company,user.company_id)
    if not company or not company.active: raise HTTPException(403,"Empresa desativada")
    return session_payload(db,user)

@router.post("/register")
def register(data:Register, db:Session=Depends(get_db)):
    if len(data.password)<6: raise HTTPException(400,"A senha deve ter pelo menos 6 caracteres")
    if db.query(User).filter(User.email==data.email.lower().strip()).first():
        raise HTTPException(409,"Já existe uma conta com este e-mail")
    company=Company(trade_name=data.company_name.strip(),legal_name=data.company_name.strip(),cnpj=data.cnpj.strip(),phone=data.phone.strip(),email=data.email.lower().strip(),responsible_name=data.name.strip())
    db.add(company); db.flush()
    user=User(company_id=company.id,email=data.email.lower().strip(),name=data.name.strip(),role="owner",password_hash=hash_password(data.password))
    db.add(user)
    # O SaaS já nasce pronto para onboarding. O gateway de pagamento pode trocar trial -> active via webhook.
    sub=Subscription(company_id=company.id,plan="mensal-350",status="trial",provider="onboarding",expires_at=datetime.utcnow()+timedelta(days=7))
    db.add(sub); db.commit(); db.refresh(user)
    return session_payload(db,user)

@router.get("/me")
def me(user=Depends(current_user), db:Session=Depends(get_db)):
    company=db.get(Company,user.company_id)
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    return {"user":{"id":user.id,"name":user.name,"email":user.email,"role":user.role,"company_id":user.company_id},"company":company,"subscription":sub}

@router.post("/bootstrap")
def bootstrap(db:Session=Depends(get_db)):
    if os.getenv("ALLOW_BOOTSTRAP","").lower() not in {"1","true","yes"}: raise HTTPException(403,"Bootstrap desativado em produção")
    if db.query(User).count(): return {"message":"Já inicializado"}
    company=Company(trade_name="CDM Desmontes",legal_name="CDM Desmontes",email="admin@autodesmonte.local",responsible_name="Administrador",state="RJ")
    db.add(company); db.flush()
    u=User(company_id=company.id,email="admin@autodesmonte.local",name="Administrador",role="owner",password_hash=hash_password("admin123"))
    db.add(u)
    db.add(Subscription(company_id=company.id,plan="mensal",status="active",provider="bootstrap",expires_at=datetime.utcnow()+timedelta(days=3650)))
    db.commit()
    return {"message":"Administrador criado"}
