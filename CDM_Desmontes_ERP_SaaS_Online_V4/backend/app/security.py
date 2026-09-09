from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
load_dotenv()
from jose import jwt
from passlib.context import CryptContext

SECRET_KEY=os.getenv("SECRET_KEY","CHANGE_THIS_SECRET_IN_PRODUCTION")
ALGORITHM="HS256"
pwd=CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(value):
    return pwd.hash(value)

def verify_password(value, hashed):
    return pwd.verify(value, hashed)

def create_token(user_id):
    exp=datetime.now(timezone.utc)+timedelta(hours=24)
    return jwt.encode({"sub":str(user_id),"exp":exp},SECRET_KEY,algorithm=ALGORITHM)

def create_oauth_state(company_id:int, marketplace:str):
    exp=datetime.now(timezone.utc)+timedelta(minutes=15)
    return jwt.encode({"company_id":company_id,"marketplace":marketplace,"purpose":"marketplace_oauth","exp":exp},SECRET_KEY,algorithm=ALGORITHM)

def decode_oauth_state(token:str):
    return jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
