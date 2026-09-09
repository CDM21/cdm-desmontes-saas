from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User
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
    return user
