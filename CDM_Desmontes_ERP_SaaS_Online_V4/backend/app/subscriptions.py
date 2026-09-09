from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import Subscription, User


def subscription_for(db: Session, company_id: int):
    return db.query(Subscription).filter(Subscription.company_id == company_id).first()


def subscription_is_active(sub: Subscription | None) -> bool:
    if not sub or sub.status not in {"active", "trial"}:
        return False
    if sub.expires_at:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if sub.expires_at < now:
            return False
    return True


def require_active_subscription(user: User, db: Session):
    sub = subscription_for(db, user.company_id)
    if not subscription_is_active(sub):
        raise HTTPException(402, "Sua assinatura precisa estar ativa para usar integrações e automações.")
    return sub
