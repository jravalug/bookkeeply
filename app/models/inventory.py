from app.extensions import db


class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_item.id"), nullable=False
    )
    location = db.Column(
        db.String(20), nullable=True
    )  # "warehouse" (almacén) o "pantry" (despensa)
    quantity = db.Column(db.Float, nullable=False)  # Cantidad disponible
    unit = db.Column(
        db.String(20), nullable=False
    )  # Unidad de medida en que se compra (ej. lata, kg)
    conversion_factor = db.Column(
        db.Float, nullable=False
    )  # Factor de conversión (ej. 1 lata = 400 ml)
    purchase_price = db.Column(db.Float, nullable=False)  # Precio de compra
    date = db.Column(db.Date, nullable=False)  # Fecha de entrada al almacén

    # Foreign Keys
    invoice_id = db.Column(
        db.Integer, db.ForeignKey("invoice.id"), nullable=True
    )  # Referencia cruzada con la factura
    business_id = db.Column(
        db.Integer, db.ForeignKey("business.id"), nullable=False
    )  # Asociación con el negocio
    specific_business_id = db.Column(
        db.Integer, db.ForeignKey("business.id"), nullable=True
    )  # Negocio específico (opcional)

    # Relations
    business = db.relationship(
        "Business", foreign_keys=[business_id], backref="inventory"
    )
    specific_business = db.relationship(
        "Business", foreign_keys=[specific_business_id], backref="specific_inventory"
    )
    extractions = db.relationship("InventoryExtraction", back_populates="inventory")


class InventoryExtraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(
        db.Integer, db.ForeignKey("inventory.id"), nullable=False
    )  # Artículo extraído
    quantity = db.Column(db.Float, nullable=False)  # Cantidad extraída
    date = db.Column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )  # Fecha de la extracción
    reason = db.Column(
        db.Integer, db.ForeignKey("ac_element.id"), nullable=False
    )  # Motivo de la extracción (opcional)

    # Relaciones
    inventory = db.relationship("Inventory", back_populates="extractions")


class InventoryItem(db.Model):
    USAGE_TYPE_SALE_DIRECT = "sale_direct"
    USAGE_TYPE_PRODUCTION_INPUT = "production_input"
    USAGE_TYPE_MIXED = "mixed"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    unit = db.Column(
        db.String(20), nullable=False
    )  # Ejemplo: "kg", "litros", "unidades"
    usage_type = db.Column(
        db.String(30),
        nullable=False,
        default=USAGE_TYPE_MIXED,
        server_default=USAGE_TYPE_MIXED,
    )
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    stock = db.Column(db.Float, default=0.0)  # Cantidad disponible en inventario
    average_unit_cost = db.Column(
        db.Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )
    min_stock = db.Column(db.Float, nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    # Relación con ProductDetail
    products = db.relationship("ProductDetail", back_populates="raw_material")

    __table_args__ = (
        db.CheckConstraint(
            "usage_type IN ('sale_direct', 'production_input', 'mixed')",
            name="ck_inventory_item_usage_type",
        ),
    )


class InventoryUnitConversion(db.Model):
    __tablename__ = "inventory_unit_conversion"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        index=True,
    )
    from_unit = db.Column(db.String(20), nullable=False)
    to_unit = db.Column(db.String(20), nullable=False)
    factor = db.Column(db.Float, nullable=False)
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business", foreign_keys=[business_id], backref="inventory_unit_conversions"
    )
    inventory_item = db.relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        backref="unit_conversions",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "business_id",
            "inventory_item_id",
            "from_unit",
            "to_unit",
            name="uq_inventory_unit_conversion_business_item_units",
        ),
        db.CheckConstraint("factor > 0", name="ck_inventory_unit_conversion_factor"),
    )


class InventoryProductGeneric(db.Model):
    __tablename__ = "inventory_product_generic"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class InventoryProductSpecific(db.Model):
    __tablename__ = "inventory_product_specific"

    id = db.Column(db.Integer, primary_key=True)
    generic_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_product_generic.id"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    generic = db.relationship(
        "InventoryProductGeneric",
        foreign_keys=[generic_id],
        backref="specifics",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "generic_id",
            "name",
            name="uq_inventory_product_specific_generic_name",
        ),
    )


class Supply(db.Model):
    __tablename__ = "supply"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        index=True,
    )
    product_specific_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_product_specific.id"),
        nullable=True,
        index=True,
    )
    product_variant = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business", foreign_keys=[business_id], backref="supplies"
    )
    inventory_item = db.relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        backref="supply_links",
    )
    product_specific = db.relationship(
        "InventoryProductSpecific",
        foreign_keys=[product_specific_id],
        backref="supplies",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "business_id",
            "product_variant",
            name="uq_supply_business_product_variant",
        ),
    )


class InventoryMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        index=True,
    )
    inventory_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory.id"),
        nullable=True,
        index=True,
    )
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    adjustment_kind = db.Column(db.String(20), nullable=True, index=True)
    destination = db.Column(db.String(30), nullable=True, index=True)
    lot_code = db.Column(db.String(80), nullable=True, index=True)
    lot_date = db.Column(db.Date, nullable=True)
    lot_unit = db.Column(db.String(20), nullable=True)
    lot_conversion_factor = db.Column(db.Float, nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    unit_cost = db.Column(db.Float, nullable=True)
    total_cost = db.Column(db.Float, nullable=True)
    account_code = db.Column(db.String(20), nullable=True, index=True)
    idempotency_key = db.Column(db.String(120), nullable=True, unique=True)
    reference_type = db.Column(db.String(40), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    supplier_name = db.Column(db.String(160), nullable=True)
    waste_reason = db.Column(db.String(40), nullable=True)
    waste_responsible = db.Column(db.String(120), nullable=True)
    waste_evidence = db.Column(db.Text, nullable=True)
    waste_evidence_file_url = db.Column(db.String(255), nullable=True)
    document = db.Column(db.String(80), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    movement_date = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="inventory_movements",
    )
    inventory_item = db.relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        backref="movements",
    )
    inventory = db.relationship(
        "Inventory",
        foreign_keys=[inventory_id],
        backref="movements",
    )


class InventoryWipBalance(db.Model):
    __tablename__ = "inventory_wip_balance"

    STATUS_OPEN = "open"
    STATUS_FINISHED = "finished"
    STATUS_WASTE = "waste"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        index=True,
    )
    source_inventory_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory.id"),
        nullable=True,
        index=True,
    )
    produced_product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=True,
        index=True,
    )
    quantity = db.Column(db.Float, nullable=False)
    remaining_quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, index=True)
    can_be_subproduct = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )
    finished_location = db.Column(
        db.String(30),
        nullable=False,
        default="finished_goods",
        server_default="finished_goods",
    )
    expiration_date = db.Column(db.Date, nullable=True)
    expiration_source = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="inventory_wip_balances",
    )
    inventory_item = db.relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        backref="wip_balances",
    )
    source_inventory = db.relationship(
        "Inventory",
        foreign_keys=[source_inventory_id],
        backref="wip_balances",
    )
    produced_product = db.relationship(
        "Product",
        foreign_keys=[produced_product_id],
        backref="wip_outputs",
    )

    __table_args__ = (
        db.CheckConstraint(
            "finished_location IN ('finished_goods', 'sales_floor')",
            name="ck_inventory_wip_balance_finished_location",
        ),
    )


class InventorySalesFloorStock(db.Model):
    __tablename__ = "inventory_sales_floor_stock"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        index=True,
    )
    current_quantity = db.Column(db.Float, nullable=False, default=0.0)
    min_quantity = db.Column(db.Float, nullable=False, default=0.0)
    max_quantity = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="sales_floor_stocks",
    )
    inventory_item = db.relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        backref="sales_floor_stocks",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "business_id",
            "inventory_item_id",
            name="uq_sales_floor_stock_business_item",
        ),
    )


class InventoryLedgerEntry(db.Model):
    __tablename__ = "inventory_ledger_entry"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    movement_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_movement.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    destination = db.Column(db.String(30), nullable=True, index=True)
    source_bucket = db.Column(db.String(30), nullable=False)
    destination_bucket = db.Column(db.String(30), nullable=False)
    source_account_code = db.Column(db.String(20), nullable=True, index=True)
    destination_account_code = db.Column(db.String(20), nullable=True, index=True)
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    unit = db.Column(db.String(20), nullable=False)
    unit_cost = db.Column(db.Float, nullable=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    valuation_method = db.Column(
        db.String(20),
        nullable=False,
        default="fifo",
        server_default="fifo",
    )
    document = db.Column(db.String(80), nullable=True)
    reference_type = db.Column(db.String(40), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="inventory_ledger_entries",
    )
    movement = db.relationship(
        "InventoryMovement",
        foreign_keys=[movement_id],
        backref="ledger_entry",
    )

    __table_args__ = (
        db.CheckConstraint("amount >= 0", name="ck_inventory_ledger_entry_amount"),
        db.CheckConstraint(
            "valuation_method IN ('fifo', 'fefo', 'manual')",
            name="ck_inventory_ledger_entry_valuation_method",
        ),
    )


class InventorySaleCostBreakdown(db.Model):
    __tablename__ = "inventory_sale_cost_breakdown"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sale.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    production_account_code = db.Column(
        db.String(20),
        nullable=False,
        default="1586",
        server_default="1586",
    )
    merchandise_account_code = db.Column(
        db.String(20),
        nullable=False,
        default="1587",
        server_default="1587",
    )
    production_cost = db.Column(db.Float, nullable=False, default=0.0)
    merchandise_cost = db.Column(db.Float, nullable=False, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="sale_cost_breakdowns",
    )
    sale = db.relationship(
        "Sale",
        foreign_keys=[sale_id],
        backref="cost_breakdown",
    )

    __table_args__ = (
        db.CheckConstraint(
            "production_cost >= 0",
            name="ck_inventory_sale_cost_breakdown_production_cost",
        ),
        db.CheckConstraint(
            "merchandise_cost >= 0",
            name="ck_inventory_sale_cost_breakdown_merchandise_cost",
        ),
    )


class InventoryCycleCount(db.Model):
    __tablename__ = "inventory_cycle_count"

    STATUS_PENDING = "pending"
    STATUS_APPLIED = "applied"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        index=True,
    )
    location = db.Column(db.String(30), nullable=False, default="warehouse")
    theoretical_quantity = db.Column(db.Float, nullable=False, default=0.0)
    counted_quantity = db.Column(db.Float, nullable=False, default=0.0)
    difference_quantity = db.Column(db.Float, nullable=False, default=0.0)
    proposed_adjustment_kind = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    actor = db.Column(db.String(120), nullable=False)
    counted_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    observation = db.Column(db.Text, nullable=True)
    applied_movement_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_movement.id"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="inventory_cycle_counts",
    )
    inventory_item = db.relationship(
        "InventoryItem",
        foreign_keys=[inventory_item_id],
        backref="cycle_counts",
    )
    applied_movement = db.relationship(
        "InventoryMovement",
        foreign_keys=[applied_movement_id],
        backref="cycle_count_reconciliation",
    )

    __table_args__ = (
        db.CheckConstraint(
            "location IN ('warehouse')",
            name="ck_inventory_cycle_count_location",
        ),
        db.CheckConstraint(
            "status IN ('pending', 'applied')",
            name="ck_inventory_cycle_count_status",
        ),
        db.CheckConstraint(
            "proposed_adjustment_kind IS NULL OR proposed_adjustment_kind IN ('positive', 'negative')",
            name="ck_inventory_cycle_count_proposed_adjustment_kind",
        ),
    )
