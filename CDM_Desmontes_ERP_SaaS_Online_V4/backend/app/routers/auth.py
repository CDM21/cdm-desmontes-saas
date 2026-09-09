import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Company, Subscription
from ..security import verify_password, hash_password, create_token
from ..deps import current_user
from ..admin import is_platform_admin

router=APIRouter()


# Limite simples por IP para reduzir tentativas automatizadas de login/cadastro.
# Em produção com múltiplas instâncias, recomenda-se complementar com rate limit no proxy/WAF.
from collections import defaultdict, deque
from threading import Lock
import time
_RATE=defaultdict(deque)
_RATE_LOCK=Lock()

def _check_rate(request:Request, bucket:str):
    ip=(request.client.host if request.client else "unknown")
    key=f"{bucket}:{ip}"
    now=time.time(); window=300; limit=30 if bucket=="login" else 12
    with _RATE_LOCK:
        q=_RATE[key]
        while q and q[0] < now-window: q.popleft()
        if len(q)>=limit: raise HTTPException(429,"Muitas tentativas. Aguarde alguns minutos e tente novamente.")
        q.append(now)

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
        "is_platform_admin":is_platform_admin(user),
    }

@router.post("/login")
def login(data:Login, request:Request, db:Session=Depends(get_db)):
    _check_rate(request,"login")
    user=db.query(User).filter(User.email==data.email).first()
    if not user or not verify_password(data.password,user.password_hash):
        raise HTTPException(401,"E-mail ou senha inválidos")
    if not user.active: raise HTTPException(403,"Usuário desativado")
    company=db.get(Company,user.company_id)
    if not company or not company.active: raise HTTPException(403,"Empresa desativada")
    return session_payload(db,user)

@router.post("/register")
def register(data:Register, request:Request, db:Session=Depends(get_db)):
    _check_rate(request,"register")
    if len(data.password)<8: raise HTTPException(400,"A senha deve ter pelo menos 8 caracteres")
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
    return {"user":{"id":user.id,"name":user.name,"email":user.email,"role":user.role,"company_id":user.company_id},"company":company,"subscription":sub,"is_platform_admin":is_platform_admin(user)}

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
