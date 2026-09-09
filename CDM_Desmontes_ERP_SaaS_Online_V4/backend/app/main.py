import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .db import Base, engine
from .routers import auth, vehicles, products, sales, finance, stock, marketplaces, company, catalog, billing, vehicle_catalog

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CDM Desmontes ERP API", version="5.0.0")

frontend_url = (os.getenv("FRONTEND_URL") or os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:5173").rstrip("/")
origins = {"http://localhost:5173", "http://127.0.0.1:5173", frontend_url}
extra_origins = os.getenv("CORS_ORIGINS", "")
for origin in extra_origins.split(","):
    if origin.strip():
        origins.add(origin.strip().rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/health")
def health():
    return {"status":"ok","service":"cdm-desmontes-erp","version":"5.0.0"}

# Em produção, o Docker copia o build do React para FRONTEND_DIST e o FastAPI
# serve o sistema inteiro no mesmo domínio HTTPS. Em desenvolvimento local,
# o Vite continua rodando na porta 5173 normalmente.
frontend_dist = Path(os.getenv("FRONTEND_DIST", "/app/frontend_dist"))
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
