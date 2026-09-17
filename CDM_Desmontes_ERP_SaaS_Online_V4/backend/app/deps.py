from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Company
from .security import SECRET_KEY, ALGORITHM
from .admin import is_platform_admin

bearer=HTTPBearer()

def current_user(credentials=Depends(bearer), db:Session=Depends(get_db)):
    try:
        payload=jwt.decode(credentials.credentials,SECRET_KEY,algorithms=[ALGORITHM])
        uid=int(payload["sub"])
    except (JWTError,KeyError,ValueError):
        raise HTTPException(401,"Credencial de acesso inválida")
    user=db.get(User,uid)
    if not user or not user.active: raise HTTPException(401,"Usuário inválido")
    if payload.get("type","access")!="access": raise HTTPException(401,"Tipo de sessão inválido")
    token_company=payload.get("company_id")
    if token_company is not None and int(token_company)!=int(user.company_id):
        raise HTTPException(401,"Sessão não pertence a esta empresa")
    if int(payload.get("ver",0) or 0)!=int(getattr(user,"token_version",0) or 0):
        raise HTTPException(401,"Sessão expirada. Entre novamente.")
    company=db.get(Company,user.company_id)
    if not company or not company.active: raise HTTPException(403,"Empresa desativada")
    return user


def active_user(user=Depends(current_user), db:Session=Depends(get_db)):
    """Usuário autenticado com assinatura vigente para módulos operacionais."""
    from .subscriptions import subscription_for, subscription_is_active
    sub=subscription_for(db,user.company_id)
    if not subscription_is_active(sub):
        raise HTTPException(402,"Sua assinatura do CDM está inativa. Regularize o plano para continuar usando os módulos operacionais.")
    return user


ROLE_NAMES={"owner","admin","manager","stock","cashier","user"}

def require_roles(*roles):
    allowed=set(roles)
    def check(user=Depends(active_user)):
        if user.role not in allowed:
            raise HTTPException(403,"Seu perfil não tem permissão para esta operação")
        return user
    return check
