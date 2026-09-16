from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, UniqueConstraint
from datetime import datetime
from .db import Base


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    trade_name = Column(String(180), default="")
    legal_name = Column(String(220), default="")
    cnpj = Column(String(30), default="", index=True)
    state_registration = Column(String(40), default="")
    tax_regime = Column(String(80), default="Simples Nacional")
    email = Column(String(180), default="")
    phone = Column(String(40), default="")
    responsible_name = Column(String(180), default="")
    rg = Column(String(40), default="")
    cpf = Column(String(30), default="")
    issuing_agency = Column(String(40), default="")
    cep = Column(String(20), default="")
    state = Column(String(10), default="RJ")
    city = Column(String(120), default="")
    address = Column(String(220), default="")
    number = Column(String(40), default="")
    complement = Column(String(120), default="")
    logo_url = Column(String(500), default="")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, index=True)
    plan = Column(String(60), default="mensal")
    status = Column(String(30), default="trial")  # trial/active/past_due/canceled/inactive
    provider = Column(String(60), default="manual")
    external_subscription_id = Column(String(180), default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    email = Column(String(180), unique=True, index=True)
    password_hash = Column(String(255))
    name = Column(String(120))
    role = Column(String(40), default="admin")
    active = Column(Boolean, default=True)
    token_version = Column(Integer, default=0)
    last_login_at = Column(DateTime, nullable=True)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    plate = Column(String(20), index=True)
    vin = Column(String(80), index=True)
    renavam = Column(String(40))
    brand = Column(String(80))
    model = Column(String(120))
    year = Column(Integer)
    fuel = Column(String(30))
    transmission = Column(String(30))
    color = Column(String(40))
    acquisition_value = Column(Float, default=0)
    other_costs = Column(Float, default=0)
    status = Column(String(30), default="received")
    created_at = Column(DateTime, default=datetime.utcnow)


class VehicleExpense(Base):
    __tablename__ = "vehicle_expenses"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=False)
    category = Column(String(80), default="Outros")
    description = Column(String(255), default="")
    amount = Column(Float, default=0)
    expense_date = Column(String(20), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Dismantling(Base):
    __tablename__ = "dismantlings"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    status = Column(String(30), default="pending")
    notes = Column(Text, default="")
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    code = Column(String(40), default="", index=True)
    description = Column(String(180), default="")
    max_quantity = Column(Integer, default=0)
    auto_generate = Column(Boolean, default=False)
    warehouse = Column(String(80), default="")
    aisle = Column(String(40), default="")
    shelf = Column(String(40), default="")
    bin = Column(String(40), default="")
    active = Column(Boolean, default=True)



class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    sku = Column(String(80), index=True)
    name = Column(String(180), index=True)
    category = Column(String(100))
    part_group = Column(String(100), default="")
    brand = Column(String(80))
    model = Column(String(120))
    year = Column(Integer)
    oem = Column(String(100))
    condition = Column(String(50), default="used")
    side = Column(String(40))
    position = Column(String(60))
    cost = Column(Float, default=0)
    price = Column(Float, default=0)
    stock = Column(Integer, default=0)
    location_id = Column(Integer, ForeignKey("locations.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    active = Column(Boolean, default=True)
    description = Column(Text, default="")
    compatibility = Column(Text, default="")
    image_urls = Column(Text, default="")  # one URL per line
    weight = Column(Float, default=1)
    package_length = Column(Float, default=20)
    package_width = Column(Float, default=20)
    package_height = Column(Float, default=20)
    ml_category_id = Column(String(60), default="")
    ml_listing_type = Column(String(60), default="gold_special")
    shopee_category_id = Column(String(60), default="")
    shopee_logistic_id = Column(String(60), default="")
    shopee_image_ids = Column(Text, default="")
    olx_category_id = Column(String(60), default="")
    publish_mercadolivre = Column(Boolean, default=True)
    publish_shopee = Column(Boolean, default=True)
    publish_olx = Column(Boolean, default=True)
    ml_has_warranty = Column(Boolean, default=False)
    ml_warranty_text = Column(String(180), default="")
    ml_shipping_mode = Column(String(60), default="")
    ml_free_shipping = Column(Boolean, default=False)
    ml_local_pickup = Column(Boolean, default=True)
    ml_attributes_json = Column(Text, default="{}")
    ml_store_id = Column(String(80), default="")
    ml_network_node_id = Column(String(120), default="")
    quality_grade = Column(String(10), default="B")
    quality_notes = Column(Text, default="")
    warranty_days = Column(Integer, default=90)
    public_catalog = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_company_sku"),)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    name = Column(String(180))
    cpf_cnpj = Column(String(30))
    phone = Column(String(40))
    email = Column(String(180))
    address = Column(String(255))


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    name = Column(String(180), default="")
    trade_name = Column(String(180), default="")
    cpf_cnpj = Column(String(30), default="", index=True)
    rg_ie = Column(String(50), default="")
    mobile = Column(String(40), default="")
    phone = Column(String(40), default="")
    cep = Column(String(20), default="")
    city = Column(String(120), default="")
    state = Column(String(10), default="")
    number = Column(String(40), default="")
    address = Column(String(220), default="")
    neighborhood = Column(String(120), default="")
    complement = Column(String(160), default="")
    ibge = Column(String(30), default="")
    email = Column(String(180), default="")
    active = Column(Boolean, default=True)



class Carrier(Base):
    __tablename__ = "carriers"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    name = Column(String(180))
    cnpj = Column(String(30), default="")
    phone = Column(String(40), default="")
    email = Column(String(180), default="")


class Seller(Base):
    __tablename__ = "sellers"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    name = Column(String(180))
    email = Column(String(180), default="")
    phone = Column(String(40), default="")
    commission_rate = Column(Float, default=0)
    active = Column(Boolean, default=True)


class PartGroup(Base):
    __tablename__ = "part_groups"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    name = Column(String(120))
    description = Column(Text, default="")


class TaxConfig(Base):
    __tablename__ = "tax_configs"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, index=True, nullable=False)
    state = Column(String(10), default="RJ")
    tax_profile = Column(String(80), default="Simples Nacional")
    operation_nature = Column(String(180), default="Venda de mercadoria")
    regime = Column(String(80), default="Simples Nacional")
    crt = Column(String(20), default="1")
    cfop_default = Column(String(20), default="5102")
    ncm_default = Column(String(20), default="")
    csosn_default = Column(String(20), default="102")
    icms_cst = Column(String(20), default="")
    icms_rate = Column(Float, default=0)
    pis_cst = Column(String(20), default="49")
    pis_rate = Column(Float, default=0)
    cofins_cst = Column(String(20), default="49")
    cofins_rate = Column(Float, default=0)
    ipi_cst = Column(String(20), default="53")
    ipi_rate = Column(Float, default=0)
    ibs_cbs_notes = Column(Text, default="")
    notes = Column(Text, default="")



class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    total = Column(Float, default=0)
    payment_method = Column(String(40))
    status = Column(String(30), default="paid")
    source = Column(String(40), default="manual")
    external_order_id = Column(String(180), default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    unit_price = Column(Float)


class FinancialEntry(Base):
    __tablename__ = "financial_entries"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    kind = Column(String(20)) # income/expense
    description = Column(String(255))
    amount = Column(Float)
    status = Column(String(30), default="paid")
    due_date = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketplaceConnection(Base):
    __tablename__ = "marketplace_connections"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    marketplace = Column(String(40), index=True)
    account_name = Column(String(180), default="")
    external_account_id = Column(String(120), default="")
    access_token_enc = Column(Text, default="")
    refresh_token_enc = Column(Text, default="")
    token_expires_at = Column(DateTime, nullable=True)
    metadata_json = Column(Text, default="{}")
    active = Column(Boolean, default=False)
    status = Column(String(30), default="disconnected")
    last_error = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("company_id", "marketplace", name="uq_company_marketplace"),)


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    marketplace = Column(String(40), index=True)
    external_id = Column(String(180), default="")
    status = Column(String(30), default="pending")
    error_message = Column(Text, default="")
    published_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("company_id", "product_id", "marketplace", name="uq_company_product_marketplace"),)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    kind = Column(String(30), default="sale")  # sale/adjustment/marketplace
    quantity_delta = Column(Integer, default=0)
    balance_after = Column(Integer, default=0)
    reference = Column(String(180), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketplaceOrderEvent(Base):
    __tablename__ = "marketplace_order_events"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    marketplace = Column(String(40), index=True, nullable=False)
    external_order_id = Column(String(180), index=True, nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    payload_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("company_id", "marketplace", "external_order_id", name="uq_marketplace_order_event"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    action = Column(String(100), index=True)
    entity = Column(String(80), default="")
    entity_id = Column(String(100), default="")
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    kind = Column(String(40), default="info")
    title = Column(String(180), default="")
    message = Column(Text, default="")
    source = Column(String(40), default="system")
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True, index=True)
    amount = Column(Float, default=0)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class FiscalDocument(Base):
    __tablename__ = "fiscal_documents"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    series = Column(String(20), default="1")
    number = Column(String(30), default="")
    operation_type = Column(String(40), default="saida")
    purpose = Column(String(60), default="normal")
    operation_nature = Column(String(180), default="Venda de mercadoria")
    referenced_key = Column(String(60), default="")
    order_number = Column(String(80), default="")
    intermediary_indicator = Column(String(80), default="sem_intermediador")
    recipient = Column(String(220), default="")
    recipient_ie = Column(String(60), default="")
    sections_json = Column(Text, default="{}")
    status = Column(String(40), default="rascunho")
    provider_response = Column(Text, default="")
    access_key = Column(String(60), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String(20), default="user")
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SaleEvidence(Base):
    __tablename__ = "sale_evidences"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    serial_number = Column(String(120), default="")
    condition_notes = Column(Text, default="")
    photo_urls_json = Column(Text, default="[]")
    packed_by = Column(String(120), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ShippingCheck(Base):
    __tablename__ = "shipping_checks"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku_scanned = Column(String(120), default="")
    result = Column(String(30), default="ok")
    checked_by = Column(String(120), default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SearchEvent(Base):
    __tablename__ = "search_events"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True, nullable=False)
    query = Column(String(220), default="", index=True)
    results_count = Column(Integer, default=0)
    source = Column(String(40), default="estoque")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
