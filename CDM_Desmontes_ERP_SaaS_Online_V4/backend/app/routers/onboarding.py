from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user
from ..models import Company, MarketplaceConnection, FiscalConfig, TaxConfig, Product, Subscription
from ..services.marketplaces import MARKETPLACES, app_ready
from ..subscriptions import subscription_is_active

router = APIRouter()


def _company_ok(c):
    return bool(c and (c.cnpj or c.cpf) and c.trade_name and c.city and c.state and c.address)


@router.get("")
def onboarding(db: Session = Depends(get_db), user=Depends(current_user)):
    company = db.get(Company, user.company_id)
    fiscal = db.query(FiscalConfig).filter(FiscalConfig.company_id == user.company_id).first()
    tax = db.query(TaxConfig).filter(TaxConfig.company_id == user.company_id).first()
    conns = {
        x.marketplace: x
        for x in db.query(MarketplaceConnection).filter(
            MarketplaceConnection.company_id == user.company_id
        ).all()
    }
    markets = []
    for m in MARKETPLACES:
        c = conns.get(m)
        markets.append({
            "id": m,
            "app_available": app_ready(m),
            "connected": bool(c and c.active),
            "status": c.status if c else "disconnected",
        })
    sub = db.query(Subscription).filter(Subscription.company_id == user.company_id).first()
    steps = [
        {"id": "company", "label": "Dados da empresa", "done": _company_ok(company), "tab": "company", "description": "CNPJ, endereço e contato da empresa."},
        {"id": "billing", "label": "Plano e cobrança", "done": subscription_is_active(sub), "tab": "subscription", "description": "Teste, mensalidade e implantação quando aplicável."},
        {"id": "fiscal", "label": "Nota fiscal", "done": bool(fiscal and fiscal.setup_status in {"ready", "configured"} and tax), "tab": "invoices", "description": "Certificado, tributação e ambiente fiscal."},
        {"id": "marketplaces", "label": "Canais de venda", "done": any(x["connected"] for x in markets), "tab": "marketplaces", "description": "Mercado Livre, Shopee e OLX em conexão guiada."},
        {"id": "first_product", "label": "Primeira peça", "done": db.query(Product).filter(Product.company_id == user.company_id).first() is not None, "tab": "product-create", "description": "Cadastre uma peça para começar a operar."},
    ]
    done = sum(1 for x in steps if x["done"])
    return {"steps": steps, "completed": done, "total": len(steps), "percent": round(done / len(steps) * 100), "marketplaces": markets, "ready": done == len(steps)}
