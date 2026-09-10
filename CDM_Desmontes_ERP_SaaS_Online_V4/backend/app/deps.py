from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Company
from .security import SECRET_KEY, ALGORITHM

bearer=HTTPBearer()

def current_user(credentials=Depends(bearer), db:Session=Depends(get_db)):
    try:
        payload=jwt.decode(credentials.credentials,SECRET_KEY,algorithms=[ALGORITHM])
        uid=int(payload["sub"])
    except (JWTError,KeyError,ValueError):
        raise HTTPException(401,"Credencial de acesso inválida")
    user=db.get(User,uid)
    if not user or not user.active: raise HTTPException(401,"Usuário inválido")
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
