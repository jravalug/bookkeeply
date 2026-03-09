from app.extensions import db


class Product(db.Model):
    """
    Modelo que representa un producto en el sistema.
    """

    # === Información Básica ===
    id = db.Column(db.Integer, primary_key=True, comment="ID único del producto.")
    name = db.Column(db.String(100), nullable=False, comment="Nombre del producto.")
    description = db.Column(
        db.Text, nullable=True, comment="Descripción detallada del producto."
    )
    category = db.Column(
        db.String(50),
        nullable=True,
        comment="Categoría del producto (comida, bebida, ropa, herramientas, etc.).",
    )
    sku = db.Column(
        db.String(50),
        nullable=True,
        unique=True,
        comment="Código único del producto (SKU - Stock Keeping Unit).",
    )
    barcode = db.Column(
        db.String(50),
        nullable=True,
        comment="Código de barras del producto (opcional).",
    )

    # === Precios y Costos ===
    price = db.Column(db.Float, nullable=False, comment="Precio de venta del producto.")
    cost_price = db.Column(
        db.Float,
        nullable=True,
        comment="Costo unitario del producto (útil para calcular márgenes de ganancia).",
    )

    # === Instrucciones y Unidad ===
    instructions = db.Column(
        db.Text,
        nullable=True,
        comment="Instrucciones de elaboración o uso del producto.",
    )
    unit = db.Column(
        db.String(20),
        nullable=True,
        comment="Unidad de medida (kilogramos, litros, unidades, etc.).",
    )

    # === Estado y Disponibilidad ===
    is_active = db.Column(
        db.Boolean,
        default=True,
        comment="Indica si el producto está activo (disponible para la venta).",
    )
    min_stock = db.Column(
        db.Float,
        nullable=True,
        comment="Stock mínimo antes de emitir una alerta.",
    )

    # === Preparación por Lotes ===
    is_batch_prepared = db.Column(
        db.Boolean,
        default=False,
        comment="Indica si el producto se prepara por lotes.",
    )
    batch_size = db.Column(
        db.Integer,
        nullable=True,
        default=1,
        comment="Número de raciones o unidades por lote.",
    )

    # === Reglas de inventario/WIP ===
    can_be_subproduct = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
        comment="Permite tratar el producto terminado como subproducto en WIP.",
    )
    goes_to_sales_floor = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
        comment="Si es true, la produccion terminada va directo a exposicion.",
    )

    # === Relaciones ===
    # ID del negocio al que pertenece el producto.
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
    )
    # Detalles de ventas asociadas.
    sale_details = db.relationship(
        "SaleDetail",
        back_populates="product",
    )
    # Materias primas asociadas al producto.
    raw_materials = db.relationship(
        "ProductDetail",
        back_populates="product",
    )


class ProductDetail(db.Model):
    """
    Modelo que representa la relación entre un producto y sus materias primas.
    """

    # === Atributos Principales ===
    id = db.Column(db.Integer, primary_key=True, comment="ID único de la relación.")
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False,
        comment="ID del producto asociado.",
    )
    raw_material_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_item.id"),
        nullable=False,
        comment="ID de la materia prima asociada.",
    )
    quantity = db.Column(
        db.Float,
        nullable=False,
        comment="Cantidad de materia prima necesaria para el producto.",
    )

    # === Relaciones ===
    # Producto al que pertenece esta relación.
    product = db.relationship(
        "Product",
        back_populates="raw_materials",
    )
    # Materia prima asociada a este producto.
    raw_material = db.relationship(
        "InventoryItem",
        back_populates="products",
    )
