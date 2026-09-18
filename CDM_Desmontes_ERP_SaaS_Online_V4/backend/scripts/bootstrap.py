import os
from datetime import datetime, timedelta

from app.db import Base, engine, SessionLocal
from app.models import User, Company, Subscription
from app.security import hash_password, password_policy_error

Base.metadata.create_all(bind=engine)
db=SessionLocal()
try:
    if db.query(User).count():
        print("Bootstrap ignorado: sistema já inicializado")
    else:
        if os.getenv("ALLOW_BOOTSTRAP","").strip().lower() not in {"1","true","yes","on"}:
            raise RuntimeError("ALLOW_BOOTSTRAP precisa estar habilitado explicitamente")

        email=(os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
        password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or ""

        if not email or "@" not in email:
            raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL não configurado corretamente")

        password_error=password_policy_error(password)
        if password_error:
            raise RuntimeError(f"BOOTSTRAP_ADMIN_PASSWORD insegura: {password_error}")

        company=Company(
            trade_name="CDM Desmontes",
            legal_name="CDM Desmontes",
            email=email,
            responsible_name="Administrador",
            state="RJ",
        )
        db.add(company); db.flush()

        db.add(User(
            company_id=company.id,
            email=email,
            name="Administrador",
            role="owner",
            password_hash=hash_password(password),
        ))
        db.add(Subscription(
            company_id=company.id,
            plan="mensal",
            status="active",
            provider="bootstrap",
            expires_at=datetime.utcnow()+timedelta(days=3650),
        ))
        db.commit()
        print("Bootstrap concluído")
finally:
    db.close()
