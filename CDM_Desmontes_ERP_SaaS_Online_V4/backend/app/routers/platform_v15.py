import os
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..admin import audit, require_platform_admin
from ..backup_service import offsite_config, restore_drill_offsite
from ..db import get_db
from ..deps import current_user
from ..models import AuditLog, Company, FiscalConfig, MarketplaceConnection, Product, Subscription, Vehicle
from ..services.marketplaces import MARKETPLACES, app_ready

router = APIRouter()


def _env(name, default=""):
    return str(os.getenv(name, default) or "").strip()


def _truthy(name):
    return _env(name).lower() in {"1", "true", "yes", "on"}


def _public_url():
    return (
        _env("PUBLIC_BASE_URL")
        or _env("RENDER_EXTERNAL_URL")
        or _env("FRONTEND_URL")
    ).rstrip("/")


def _custom_domain():
    url = _public_url().lower()
    return bool(url and "onrender.com" not in url and "localhost" not in url and "127.0.0.1" not in url)


def _email_ready():
    return bool(_env("SMTP_HOST") and _env("SMTP_FROM"))


def _check(key, label, done, detail, level="important", external=False, action=""):
    return {
        "key": key,
        "label": label,
        "done": bool(done),
        "status": "ready" if done else ("external" if external else "pending"),
        "detail": detail,
        "level": level,
        "external": bool(external),
        "action": action,
    }


@router.get("/ping")
def v15_ping():
    return {"ok": True, "version": "15.0", "name": "CDM V15 Geral"}


class RestoreDrillIn(BaseModel):
    key: str = ""


@router.post("/admin/backup-restore-drill")
def backup_restore_drill(
    data: RestoreDrillIn,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    require_platform_admin(user)
    try:
        result = restore_drill_offsite(data.key)
        audit(
            db,
            user,
            "backup.restore_drill.success",
            "database",
            "",
            {
                "tables": result.get("tables"),
                "rows": result.get("rows"),
                "sha256": result.get("sha256"),
            },
        )
        db.commit()
        return {"ok": True, **result}
    except Exception as exc:
        audit(
            db,
            user,
            "backup.restore_drill.error",
            "database",
            "",
            {"error": str(exc)[:1000]},
        )
        db.commit()
        raise HTTPException(503, f"Teste de restauração não concluído: {str(exc)[:300]}")


@router.get("/admin/launch-readiness")
def launch_readiness(
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    require_platform_admin(user)

    started = time.perf_counter()
    database_online = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_online = False
    db_latency = round((time.perf_counter() - started) * 1000, 1)

    try:
        from .billing import _mercadopago_health
        mp = _mercadopago_health(force=False)
    except Exception:
        mp = {
            "valid": False,
            "ready": False,
            "webhook_configured": False,
            "message": "Diagnóstico do Mercado Pago indisponível.",
        }

    backup_cfg = offsite_config()
    last_backup = (
        db.query(AuditLog)
        .filter(
            AuditLog.action.in_(
                [
                    "backup.offsite.cron",
                    "backup.offsite.success",
                    "backup.offsite.automatic",
                    "backup.download",
                ]
            )
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    last_restore = (
        db.query(AuditLog)
        .filter(AuditLog.action == "backup.restore_drill.success")
        .order_by(AuditLog.id.desc())
        .first()
    )

    focus_ready = bool(_env("FOCUS_MASTER_TOKEN"))
    fiscal_total = db.query(FiscalConfig).count()
    fiscal_ready = (
        db.query(FiscalConfig)
        .filter(FiscalConfig.setup_status == "ready")
        .count()
    )

    active_connections = (
        db.query(MarketplaceConnection)
        .filter(MarketplaceConnection.active.is_(True))
        .all()
    )
    active_by_market = {}
    for row in active_connections:
        active_by_market[row.marketplace] = active_by_market.get(row.marketplace, 0) + 1

    marketplaces = []
    for market in MARKETPLACES:
        marketplaces.append(
            {
                "id": market,
                "app_available": bool(app_ready(market)),
                "active_connections": int(active_by_market.get(market, 0)),
            }
        )

    try:
        founder_count = int(
            db.execute(text("SELECT COUNT(*) FROM founder_program")).scalar() or 0
        )
    except Exception:
        founder_count = 0

    companies = db.query(Company).count()
    subscriptions = db.query(Subscription).count()
    active_subscriptions = (
        db.query(Subscription)
        .filter(Subscription.status == "active")
        .count()
    )

    critical = [
        _check(
            "database",
            "Banco de dados online",
            database_online,
            f"Resposta do banco em {db_latency} ms.",
            "critical",
        ),
        _check(
            "database_persistent",
            "Banco persistente para produção",
            _truthy("CDM_DATABASE_PERSISTENT"),
            "Marque CDM_DATABASE_PERSISTENT=true somente depois de migrar o banco do plano temporário/free.",
            "critical",
            action="Migrar o Postgres do Render para um plano persistente antes de liberar clientes.",
        ),
        _check(
            "mercadopago",
            "Mercado Pago validado",
            bool(mp.get("valid")),
            mp.get("message") or "Validação da API de pagamentos.",
            "critical",
        ),
        _check(
            "mercadopago_webhook",
            "Webhook de cobrança protegido",
            bool(mp.get("webhook_configured")),
            "Confirmações de pagamento precisam chegar assinadas ao CDM.",
            "critical",
        ),
        _check(
            "backup_offsite",
            "Backup externo configurado",
            bool(backup_cfg.get("configured")),
            "Cópia externa independente do servidor principal.",
            "critical",
        ),
        _check(
            "backup_recent",
            "Backup recente disponível",
            bool(last_backup),
            (
                f"Último registro: {last_backup.created_at.isoformat()}"
                if last_backup and last_backup.created_at
                else "Nenhum backup confirmado pelo monitoramento."
            ),
            "critical",
        ),
        _check(
            "restore_drill",
            "Restauração testada",
            bool(last_restore),
            (
                f"Último teste: {last_restore.created_at.isoformat()}"
                if last_restore and last_restore.created_at
                else "Execute o teste isolado de restauração pelo Portal do Dono."
            ),
            "critical",
            action="Clique em “Testar restauração” no Centro de Lançamento.",
        ),
    ]

    operations = [
        _check(
            "focus",
            "Emissor NF-e disponível",
            focus_ready,
            "Token mestre da Focus NFe configurado no servidor." if focus_ready else "A conta integradora Focus NFe ainda precisa ser conectada.",
            "critical",
            external=not focus_ready,
            action="Configurar FOCUS_MASTER_TOKEN e concluir uma emissão em homologação.",
        ),
        _check(
            "fiscal_companies",
            "Fiscal validado por empresa",
            bool(fiscal_ready),
            f"{fiscal_ready} empresa(s) pronta(s) de {fiscal_total} configuração(ões) fiscal(is).",
            "critical",
            action="Concluir CNPJ, tributação, certificado A1 e teste final na aba NF-e.",
        ),
        _check(
            "otx",
            "OTX / documento de transporte",
            _truthy("CDM_OTX_READY"),
            "Integração de transporte só deve ser marcada como pronta após definir o provedor e concluir um teste real.",
            "critical",
            external=not _truthy("CDM_OTX_READY"),
            action="Definir o provedor/fluxo OTX e só então configurar CDM_OTX_READY=true.",
        ),
        _check(
            "mercadolivre",
            "Mercado Livre conectado",
            int(active_by_market.get("mercadolivre", 0)) > 0,
            f"{int(active_by_market.get('mercadolivre', 0))} conexão(ões) ativa(s).",
            "important",
        ),
        _check(
            "shopee",
            "Shopee pronta",
            bool(app_ready("shopee")) and int(active_by_market.get("shopee", 0)) > 0,
            "Depende da aprovação/onboarding da Shopee Open Platform quando ainda não houver credenciais/conexão.",
            "important",
            external=not bool(app_ready("shopee")),
        ),
        _check(
            "olx",
            "OLX pronta",
            bool(app_ready("olx")) and int(active_by_market.get("olx", 0)) > 0,
            "Depende de credenciais e homologação do integrador OLX quando ainda não estiver conectado.",
            "important",
            external=not bool(app_ready("olx")),
        ),
    ]

    commercial = [
        _check(
            "password_recovery",
            "Recuperação de senha por e-mail",
            _email_ready(),
            "Fluxo de recuperação já está no CDM; o envio fica ativo quando SMTP_HOST e SMTP_FROM estiverem configurados.",
            "important",
            external=not _email_ready(),
            action="Configurar SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD e SMTP_FROM.",
        ),
        _check(
            "custom_domain",
            "Domínio profissional",
            _custom_domain(),
            _public_url() or "URL pública não detectada.",
            "recommended",
            external=not _custom_domain(),
            action="Conectar um domínio próprio ao Render antes do lançamento comercial.",
        ),
        _check(
            "terms",
            "Termos de Uso publicados",
            bool(_env("CDM_TERMS_URL")),
            _env("CDM_TERMS_URL") or "URL dos Termos de Uso ainda não cadastrada.",
            "important",
            external=not bool(_env("CDM_TERMS_URL")),
        ),
        _check(
            "privacy",
            "Política de Privacidade publicada",
            bool(_env("CDM_PRIVACY_URL")),
            _env("CDM_PRIVACY_URL") or "URL da Política de Privacidade ainda não cadastrada.",
            "important",
            external=not bool(_env("CDM_PRIVACY_URL")),
        ),
    ]

    all_checks = critical + operations + commercial
    critical_ready = all(x["done"] for x in critical)
    core_ready = all(x["done"] for x in critical + operations if x["key"] not in {"shopee", "olx"})
    done = sum(1 for x in all_checks if x["done"])

    return {
        "version": "15.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "done": done,
            "total": len(all_checks),
            "percent": round(done / len(all_checks) * 100) if all_checks else 0,
            "critical_ready": critical_ready,
            "core_ready": core_ready,
            "external_pending": sum(1 for x in all_checks if not x["done"] and x["external"]),
        },
        "usage": {
            "companies": companies,
            "subscriptions": subscriptions,
            "active_subscriptions": active_subscriptions,
            "founders": founder_count,
            "products": db.query(Product).count(),
            "vehicles": db.query(Vehicle).count(),
        },
        "payments": mp,
        "backup": {
            "configured": bool(backup_cfg.get("configured")),
            "automatic_enabled": bool(backup_cfg.get("automatic_enabled")),
            "last_backup_at": last_backup.created_at if last_backup else None,
            "last_restore_drill_at": last_restore.created_at if last_restore else None,
        },
        "fiscal": {
            "focus_configured": focus_ready,
            "configs": fiscal_total,
            "ready": fiscal_ready,
        },
        "marketplaces": marketplaces,
        "sections": [
            {"id": "critical", "label": "Base para produção", "checks": critical},
            {"id": "operations", "label": "Fiscal e integrações", "checks": operations},
            {"id": "commercial", "label": "Lançamento comercial", "checks": commercial},
        ],
    }
