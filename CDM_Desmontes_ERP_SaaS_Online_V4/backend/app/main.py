import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db import Base, engine
from sqlalchemy import inspect, text
from .routers import auth, vehicles, products, sales, finance, stock, marketplaces, company, catalog, billing, vehicle_catalog, admin, notifications, fiscal, intelligence, platform_v14

Base.metadata.create_all(bind=engine)


def ensure_v8_schema():
    """Migração leve para instalações V4/V5/V6/V7 já existentes no Render."""
    additions={
        "users":{"token_version":"INTEGER DEFAULT 0","last_login_at":"TIMESTAMP NULL"},
        "vehicles":{
            "plate":"VARCHAR(20) DEFAULT ''",
            "vin":"VARCHAR(80) DEFAULT ''",
            "renavam":"VARCHAR(40) DEFAULT ''",
            "brand":"VARCHAR(80) DEFAULT ''",
            "model":"VARCHAR(120) DEFAULT ''",
            "year":"INTEGER NULL",
            "fuel":"VARCHAR(30) DEFAULT ''",
            "transmission":"VARCHAR(30) DEFAULT ''",
            "color":"VARCHAR(40) DEFAULT ''",
            "acquisition_value":"FLOAT DEFAULT 0",
            "other_costs":"FLOAT DEFAULT 0",
            "status":"VARCHAR(30) DEFAULT 'received'",
            "created_at":"TIMESTAMP NULL"
        },
        "products":{"publish_mercadolivre":"BOOLEAN DEFAULT TRUE","publish_shopee":"BOOLEAN DEFAULT TRUE","publish_olx":"BOOLEAN DEFAULT TRUE","ml_has_warranty":"BOOLEAN DEFAULT FALSE","ml_warranty_text":"VARCHAR(180) DEFAULT ''","ml_shipping_mode":"VARCHAR(60) DEFAULT ''","ml_free_shipping":"BOOLEAN DEFAULT FALSE","ml_local_pickup":"BOOLEAN DEFAULT TRUE","ml_attributes_json":"TEXT DEFAULT '{}'","ml_store_id":"VARCHAR(80) DEFAULT ''","ml_network_node_id":"VARCHAR(120) DEFAULT ''","quality_grade":"VARCHAR(10) DEFAULT 'B'","quality_notes":"TEXT DEFAULT ''","warranty_days":"INTEGER DEFAULT 90","public_catalog":"BOOLEAN DEFAULT TRUE"},
        "sales":{"source":"VARCHAR(40) DEFAULT 'manual'","external_order_id":"VARCHAR(180) DEFAULT ''"},
        "locations":{"code":"VARCHAR(40) DEFAULT ''","description":"VARCHAR(180) DEFAULT ''","max_quantity":"INTEGER DEFAULT 0","auto_generate":"BOOLEAN DEFAULT FALSE","active":"BOOLEAN DEFAULT TRUE"},
        "suppliers":{"trade_name":"VARCHAR(180) DEFAULT ''","rg_ie":"VARCHAR(50) DEFAULT ''","mobile":"VARCHAR(40) DEFAULT ''","cep":"VARCHAR(20) DEFAULT ''","city":"VARCHAR(120) DEFAULT ''","state":"VARCHAR(10) DEFAULT ''","number":"VARCHAR(40) DEFAULT ''","address":"VARCHAR(220) DEFAULT ''","neighborhood":"VARCHAR(120) DEFAULT ''","complement":"VARCHAR(160) DEFAULT ''","ibge":"VARCHAR(30) DEFAULT ''","active":"BOOLEAN DEFAULT TRUE"},
        "tax_configs":{"state":"VARCHAR(10) DEFAULT 'RJ'","tax_profile":"VARCHAR(80) DEFAULT 'Simples Nacional'","operation_nature":"VARCHAR(180) DEFAULT 'Venda de mercadoria'","icms_cst":"VARCHAR(20) DEFAULT ''","icms_rate":"FLOAT DEFAULT 0","pis_cst":"VARCHAR(20) DEFAULT '49'","pis_rate":"FLOAT DEFAULT 0","cofins_cst":"VARCHAR(20) DEFAULT '49'","cofins_rate":"FLOAT DEFAULT 0","ipi_cst":"VARCHAR(20) DEFAULT '53'","ipi_rate":"FLOAT DEFAULT 0","ibs_cbs_notes":"TEXT DEFAULT ''"}
    }
    try:
        inspector=inspect(engine);tables=set(inspector.get_table_names())
        with engine.begin() as conn:
            for table,cols in additions.items():
                if table not in tables: continue
                current={c["name"] for c in inspector.get_columns(table)}
                for name,ddl in cols.items():
                    if name not in current: conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    except Exception as exc: print("V8 schema warning:",exc)

ensure_v8_schema()


app = FastAPI(title="CDM Desmontes ERP API", version="14.0.0")

frontend_url = (os.getenv("FRONTEND_URL") or os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:5173").rstrip("/")
origins = {"http://localhost:5173", "http://127.0.0.1:5173", frontend_url}
extra_origins = os.getenv("CORS_ORIGINS", "")
for origin in extra_origins.split(","):
    if origin.strip(): origins.add(origin.strip().rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    if request.url.scheme=="https" or os.getenv("RENDER"):
        response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = response.headers.get("Cache-Control","no-store") if request.url.path.startswith("/api/") else response.headers.get("Cache-Control","public, max-age=300")
    return response

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(company.router, prefix="/api/company", tags=["Empresa"])
app.include_router(billing.router, prefix="/api/billing", tags=["Assinatura"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["Cadastros"])
app.include_router(vehicle_catalog.router, prefix="/api/vehicle-catalog", tags=["Catálogo automotivo"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["Veículos"])
app.include_router(products.router, prefix="/api/products", tags=["Peças"])
app.include_router(stock.router, prefix="/api/stock", tags=["Estoque"])
app.include_router(sales.router, prefix="/api/sales", tags=["Vendas"])
app.include_router(finance.router, prefix="/api/finance", tags=["Financeiro"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notificações"])
app.include_router(fiscal.router, prefix="/api/fiscal", tags=["Fiscal"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Inteligência CDM"])
app.include_router(platform_v14.router, prefix="/api/v14", tags=["CDM V14"])
app.include_router(marketplaces.router, prefix="/api/marketplaces", tags=["Marketplaces"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin SaaS"])

@app.get("/api/health")
def health():
    return {"status":"ok","service":"cdm-desmontes-erp","version":"14.0.0"}

frontend_dist = Path(os.getenv("FRONTEND_DIST", "/app/frontend_dist"))
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
