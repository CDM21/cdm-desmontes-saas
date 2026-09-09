from datetime import datetime, timedelta
from app.db import Base, engine, SessionLocal
from app.models import User, Company, Subscription
from app.security import hash_password

Base.metadata.create_all(bind=engine)
db=SessionLocal()
try:
    if not db.query(User).count():
        company=Company(trade_name="CDM Desmontes",legal_name="CDM Desmontes",email="admin@autodesmonte.local",responsible_name="Administrador",state="RJ")
        db.add(company);db.flush()
        db.add(User(company_id=company.id,email="admin@autodesmonte.local",name="Administrador",role="owner",password_hash=hash_password("admin123")))
        db.add(Subscription(company_id=company.id,plan="mensal",status="active",provider="bootstrap",expires_at=datetime.utcnow()+timedelta(days=3650)))
        db.commit()
    print("Bootstrap concluído")
finally:
    db.close()
