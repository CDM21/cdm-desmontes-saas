from datetime import datetime, timedelta, timezone
import os
import uuid
from dotenv import load_dotenv
load_dotenv()
from jose import jwt
from passlib.context import CryptContext

DEFAULT_SECRET_KEY="CHANGE_THIS_SECRET_IN_PRODUCTION"
SECRET_KEY=os.getenv("SECRET_KEY",DEFAULT_SECRET_KEY)
ALGORITHM="HS256"
TOKEN_HOURS=max(1,min(int(os.getenv("TOKEN_HOURS","12")),168))
pwd=CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(value):
    return pwd.hash(value)

def verify_password(value, hashed):
    return pwd.verify(value, hashed)

def password_policy_error(value:str):
    value=str(value or "")
    if len(value)<10:
        return "A senha deve ter pelo menos 10 caracteres"
    if len(value)>128:
        return "A senha deve ter no máximo 128 caracteres"
    groups=sum([
        any(c.islower() for c in value),
        any(c.isupper() for c in value),
        any(c.isdigit() for c in value),
        any(not c.isalnum() for c in value),
    ])
    if groups<3:
        return "Use uma senha com pelo menos 3 tipos: maiúsculas, minúsculas, números e símbolos"
    return ""

def secret_key_status():
    raw=str(SECRET_KEY or "")
    default=raw==DEFAULT_SECRET_KEY
    return {
        "configured":bool(raw and not default),
        "strong":bool(raw and not default and len(raw)>=32),
        "length":len(raw),
        "using_default":default,
        "token_hours":TOKEN_HOURS,
    }

def create_token(user_id, company_id=None, token_version=0):
    now=datetime.now(timezone.utc)
    exp=now+timedelta(hours=TOKEN_HOURS)
    return jwt.encode({
        "sub":str(user_id),"company_id":company_id,"ver":int(token_version or 0),
        "type":"access","iat":now,"exp":exp,"jti":uuid.uuid4().hex
    },SECRET_KEY,algorithm=ALGORITHM)

def create_oauth_state(company_id:int, marketplace:str):
    exp=datetime.now(timezone.utc)+timedelta(minutes=15)
    return jwt.encode({"company_id":company_id,"marketplace":marketplace,"purpose":"marketplace_oauth","exp":exp},SECRET_KEY,algorithm=ALGORITHM)

def decode_oauth_state(token:str):
    return jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])

def create_password_reset_token(user_id:int, token_version=0):
    now=datetime.now(timezone.utc)
    exp=now+timedelta(minutes=30)
    return jwt.encode({
        "sub":str(user_id),"ver":int(token_version or 0),
        "purpose":"password_reset","iat":now,"exp":exp,"jti":uuid.uuid4().hex
    },SECRET_KEY,algorithm=ALGORITHM)

def decode_password_reset_token(token:str):
    data=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
    if data.get("purpose")!="password_reset":
        raise ValueError("Token inválido")
    return data
