from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import Subscription, User


def subscription_for(db: Session, company_id: int):
    return db.query(Subscription).filter(Subscription.company_id == company_id).first()


def subscription_is_active(sub: Subscription | None) -> bool:
    if not sub:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if sub.status in {"active", "trial"}:
        return not sub.expires_at or sub.expires_at >= now
    if sub.status == "pending" and sub.expires_at:
        return sub.expires_at >= now
    return False

def require_active_subscription(user: User, db: Session):
    sub = subscription_for(db, user.company_id)
    if not subscription_is_active(sub):
        raise HTTPException(402, "Sua assinatura precisa estar ativa para usar integrações e automações.")
    return sub
