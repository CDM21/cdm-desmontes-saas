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
        raise HTTPException(401,"Token inválido")
    user=db.get(User,uid)
    if not user or not user.active: raise HTTPException(401,"Usuário inválido")
    company=db.get(Company,user.company_id)
    if not company or not company.active: raise HTTPException(403,"Empresa desativada")
    return user


def active_user(user=Depends(current_user), db:Session=Depends(get_db)):
    """Usuário autenticado com assinatura vigente para módulos operacionais."""
    from datetime import datetime
    from .models import Subscription
    sub=db.query(Subscription).filter(Subscription.company_id==user.company_id).first()
    valid=bool(sub and sub.status in {"active","trial"} and (not sub.expires_at or sub.expires_at>=datetime.utcnow()))
    if not valid:
        raise HTTPException(402,"Sua assinatura do CDM está inativa. Regularize o plano para continuar usando os módulos operacionais.")
    return user
