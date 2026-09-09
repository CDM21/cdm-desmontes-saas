import json
import os
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import AuditLog, User


def platform_admin_emails():
    return {x.strip().lower() for x in os.getenv("PLATFORM_ADMIN_EMAILS", "").split(",") if x.strip()}


def is_platform_admin(user: User) -> bool:
    return bool(user and user.email and user.email.lower() in platform_admin_emails())


def require_platform_admin(user: User):
    if not is_platform_admin(user):
        raise HTTPException(403, "Acesso exclusivo do administrador da plataforma CDM")
    return user


def audit(db: Session, user: User | None, action: str, entity: str = "", entity_id: str = "", details: dict | None = None, company_id: int | None = None):
    row = AuditLog(
        company_id=company_id if company_id is not None else getattr(user, "company_id", None),
        user_id=getattr(user, "id", None),
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        details_json=json.dumps(details or {}, ensure_ascii=False)[:8000],
    )
    db.add(row)
    return row
