import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db import Base, engine
from sqlalchemy import inspect, text
from .routers import auth, vehicles, products, sales, finance, stock, marketplaces, company, catalog, billing, vehicle_catalog, admin

Base.metadata.create_all(bind=engine)


def ensure_v7_schema():
    """Migração leve para instalações V4/V5/V6 já existentes no Render."""
    product_additions={
        "publish_mercadolivre":"BOOLEAN DEFAULT TRUE",
        "publish_shopee":"BOOLEAN DEFAULT TRUE",
        "publish_olx":"BOOLEAN DEFAULT TRUE",
        "ml_has_warranty":"BOOLEAN DEFAULT FALSE",
        "ml_warranty_text":"VARCHAR(180) DEFAULT ''",
        "ml_shipping_mode":"VARCHAR(60) DEFAULT ''",
        "ml_free_shipping":"BOOLEAN DEFAULT FALSE",
        "ml_local_pickup":"BOOLEAN DEFAULT TRUE",
        "ml_attributes_json":"TEXT DEFAULT '{}'",
        "ml_store_id":"VARCHAR(80) DEFAULT ''",
        "ml_network_node_id":"VARCHAR(120) DEFAULT ''",
    }
    sale_additions={
        "source":"VARCHAR(40) DEFAULT 'manual'",
        "external_order_id":"VARCHAR(180) DEFAULT ''",
    }
    try:
        inspector=inspect(engine)
        with engine.begin() as conn:
            current={c["name"] for c in inspector.get_columns("products")}
            for name,ddl in product_additions.items():
                if name not in current: conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {ddl}"))
            current_sales={c["name"] for c in inspector.get_columns("sales")}
            for name,ddl in sale_additions.items():
                if name not in current_sales: conn.execute(text(f"ALTER TABLE sales ADD COLUMN {name} {ddl}"))
    except Exception as exc:
        print("V7 schema warning:",exc)

ensure_v7_schema()

app = FastAPI(title="CDM Desmontes ERP API", version="7.0.0")

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
app.include_router(marketplaces.router, prefix="/api/marketplaces", tags=["Marketplaces"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin SaaS"])

@app.get("/api/health")
def health():
    return {"status":"ok","service":"cdm-desmontes-erp","version":"7.0.0"}

frontend_dist = Path(os.getenv("FRONTEND_DIST", "/app/frontend_dist"))
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
