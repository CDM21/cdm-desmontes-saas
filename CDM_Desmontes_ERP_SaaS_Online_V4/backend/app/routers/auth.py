import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Company, Subscription
from ..security import verify_password, hash_password, create_token, password_policy_error, create_password_reset_token, decode_password_reset_token
from ..deps import current_user
from ..admin import is_platform_admin, audit
from ..mailer import send_password_reset_email

router=APIRouter()


# Proteção em memória contra tentativas automatizadas.
# Em produção com múltiplas instâncias, complementar com rate limit no proxy/WAF.
from collections import defaultdict, deque
from threading import Lock
import time
_RATE=defaultdict(deque)
_FAILED_LOGIN=defaultdict(deque)
_RATE_LOCK=Lock()

def _safe_delivery_error(exc):
    text=str(exc or "Erro SMTP desconhecido")
    secret=os.getenv("SMTP_PASSWORD","") or ""
    if secret:
        text=text.replace(secret,"***")
    return text[:500]

def _ip(request:Request):
    return request.client.host if request.client else "unknown"

def _trim_window(q, now, window):
    while q and q[0] < now-window:
        q.popleft()

def _check_rate(request:Request, bucket:str):
    ip=_ip(request)
    key=f"{bucket}:{ip}"
    now=time.time()
    window=300 if bucket=="login" else 900
    limit=20 if bucket=="login" else 6
    with _RATE_LOCK:
        q=_RATE[key]
        _trim_window(q,now,window)
        if len(q)>=limit:
            raise HTTPException(429,"Muitas tentativas. Aguarde alguns minutos e tente novamente.")
        q.append(now)

def _failed_key(request:Request,email:str):
    return f"{_ip(request)}:{email.lower().strip()[:180]}"

def _check_failed_logins(request:Request,email:str):
    key=_failed_key(request,email)
    now=time.time();window=900;limit=8
    with _RATE_LOCK:
        q=_FAILED_LOGIN[key]
        _trim_window(q,now,window)
        if len(q)>=limit:
            wait=max(1,int((window-(now-q[0]))/60)+1)
            raise HTTPException(429,f"Muitas senhas incorretas. Aguarde cerca de {wait} minuto(s) e tente novamente.")

def _record_failed_login(request:Request,email:str):
    key=_failed_key(request,email)
    now=time.time()
    with _RATE_LOCK:
        q=_FAILED_LOGIN[key]
        _trim_window(q,now,900)
        q.append(now)

def _clear_failed_logins(request:Request,email:str):
    key=_failed_key(request,email)
    with _RATE_LOCK:
        _FAILED_LOGIN.pop(key,None)

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

class ForgotPassword(BaseModel):
    email:str

class ResetPassword(BaseModel):
    token:str
    password:str


def session_payload(db:Session,user:User):
    company=db.get(Company,user.company_id)
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    return {
        "access_token":create_token(user.id,user.company_id,getattr(user,"token_version",0)),
        "user":{"id":user.id,"name":user.name,"email":user.email,"role":user.role,"company_id":user.company_id},
        "company":company,
        "subscription":sub,
        "is_platform_admin":is_platform_admin(user),
    }

@router.post("/login")
def login(data:Login, request:Request, db:Session=Depends(get_db)):
    _check_rate(request,"login")
    email=data.email.lower().strip()[:180]
    _check_failed_logins(request,email)
    user=db.query(User).filter(User.email==email).first()
    if not user or not verify_password(data.password,user.password_hash):
        _record_failed_login(request,email)
        raise HTTPException(401,"E-mail ou senha inválidos")
    _clear_failed_logins(request,email)
    if not user.active: raise HTTPException(403,"Usuário desativado")
    company=db.get(Company,user.company_id)
    if not company or not company.active: raise HTTPException(403,"Empresa desativada")
    user.last_login_at=datetime.utcnow()
    audit(db,user,"auth.login","user",str(user.id),{"ip":request.client.host if request.client else ""})
    db.commit();db.refresh(user)
    return session_payload(db,user)

@router.post("/register")
def register(data:Register, request:Request, db:Session=Depends(get_db)):
    _check_rate(request,"register")
    email=data.email.lower().strip()[:180]
    company_name=data.company_name.strip()[:180]
    name=data.name.strip()[:180]
    if not company_name: raise HTTPException(400,"Informe o nome da empresa")
    if not name: raise HTTPException(400,"Informe seu nome")
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400,"Informe um e-mail válido")
    password_error=password_policy_error(data.password)
    if password_error: raise HTTPException(400,password_error)
    if db.query(User).filter(User.email==email).first():
        raise HTTPException(409,"Já existe uma conta com este e-mail")
    company=Company(trade_name=company_name,legal_name=company_name,cnpj=data.cnpj.strip()[:30],phone=data.phone.strip()[:40],email=email,responsible_name=name)
    db.add(company); db.flush()
    user=User(company_id=company.id,email=email,name=name,role="owner",password_hash=hash_password(data.password))
    db.add(user)
    # O SaaS já nasce pronto para onboarding. O gateway de pagamento pode trocar trial -> active via webhook.
    sub=Subscription(company_id=company.id,plan="mensal-350",status="trial",provider="onboarding",expires_at=datetime.utcnow()+timedelta(days=7))
    db.add(sub); db.commit(); db.refresh(user)
    return session_payload(db,user)


@router.post("/forgot-password")
def forgot_password(data:ForgotPassword, request:Request, db:Session=Depends(get_db)):
    _check_rate(request,"register")
    email=data.email.lower().strip()[:180]
    user=db.query(User).filter(User.email==email).first()
    if user and user.active:
        token=create_password_reset_token(user.id,getattr(user,"token_version",0))
        base=(os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("FRONTEND_URL") or "").rstrip("/")
        if base:
            link=f"{base}/?reset_token={token}"
            try:
                sent=send_password_reset_email(user.email,user.name,link)
                if sent:
                    audit(db,user,"auth.password_reset_requested","user",str(user.id),{"delivery":"sent"})
                else:
                    audit(db,user,"auth.password_reset_delivery_unavailable","user",str(user.id),{"delivery":"smtp_not_configured"})
                db.commit()
            except Exception as exc:
                audit(db,user,"auth.password_reset_delivery_error","user",str(user.id),{"delivery":"smtp_error","error":_safe_delivery_error(exc)})
                db.commit()
    return {"ok":True,"message":"Se o e-mail estiver cadastrado, as instruções serão enviadas."}

@router.post("/reset-password")
def reset_password(data:ResetPassword, request:Request, db:Session=Depends(get_db)):
    _check_rate(request,"register")
    try:
        payload=decode_password_reset_token(data.token)
        user_id=int(payload.get("sub"))
    except Exception:
        raise HTTPException(400,"Link de recuperação inválido ou expirado")
    user=db.get(User,user_id)
    if not user or not user.active:
        raise HTTPException(400,"Link de recuperação inválido ou expirado")
    if int(payload.get("ver") or 0)!=int(getattr(user,"token_version",0) or 0):
        raise HTTPException(400,"Este link de recuperação já foi utilizado ou expirou")
    password_error=password_policy_error(data.password)
    if password_error:
        raise HTTPException(400,password_error)
    user.password_hash=hash_password(data.password)
    user.token_version=int(getattr(user,"token_version",0) or 0)+1
    audit(db,user,"auth.password_reset","user",str(user.id),{})
    db.commit()
    return {"ok":True,"message":"Senha alterada com sucesso"}

@router.get("/me")
def me(user=Depends(current_user), db:Session=Depends(get_db)):
    company=db.get(Company,user.company_id)
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    return {"user":{"id":user.id,"name":user.name,"email":user.email,"role":user.role,"company_id":user.company_id},"company":company,"subscription":sub,"is_platform_admin":is_platform_admin(user)}


@router.post("/logout")
def logout_current(user=Depends(current_user),db:Session=Depends(get_db)):
    user.token_version=int(getattr(user,"token_version",0) or 0)+1
    audit(db,user,"auth.logout","user",str(user.id),{})
    db.commit()
    return {"ok":True}

@router.post("/bootstrap")
def bootstrap(db:Session=Depends(get_db)):
    if os.getenv("ALLOW_BOOTSTRAP","").strip().lower() not in {"1","true","yes","on"}:
        raise HTTPException(403,"Inicialização administrativa desativada em produção")
    if db.query(User).count():
        return {"message":"Já inicializado"}

    bootstrap_email=(os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    bootstrap_password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or ""
    if not bootstrap_email or "@" not in bootstrap_email:
        raise HTTPException(503,"BOOTSTRAP_ADMIN_EMAIL não configurado corretamente")
    password_error=password_policy_error(bootstrap_password)
    if password_error:
        raise HTTPException(503,f"BOOTSTRAP_ADMIN_PASSWORD insegura: {password_error}")

    company=Company(
        trade_name="CDM Desmontes",
        legal_name="CDM Desmontes",
        email=bootstrap_email,
        responsible_name="Administrador",
        state="RJ",
    )
    db.add(company); db.flush()
    u=User(
        company_id=company.id,
        email=bootstrap_email,
        name="Administrador",
        role="owner",
        password_hash=hash_password(bootstrap_password),
    )
    db.add(u)
    db.add(Subscription(
        company_id=company.id,
        plan="mensal",
        status="active",
        provider="bootstrap",
        expires_at=datetime.utcnow()+timedelta(days=3650),
    ))
    db.commit()
    return {"message":"Administrador criado"}
