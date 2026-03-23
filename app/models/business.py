import re
import unicodedata

from app.extensions import db


class Business(db.Model):
    """
    Modelo que representa un negocio en el sistema.

    Relaciones:
        - parent_business: Relación con el negocio padre (si existe).
        - sub_businesses: Relación con los negocios específicos asociados.
    """

    __tablename__ = "business"

    INCOME_MODE_DAILY = "daily_income"
    INCOME_MODE_DETAILED = "detailed_sales"

    INCOME_ACTIVITY_SALE = "sale"
    INCOME_ACTIVITY_SERVICE = "service"

    ACTIVITY_RETAIL = "retail"
    ACTIVITY_RESTAURANT = "restaurant"
    ACTIVITY_BAR = "bar"
    ACTIVITY_CAFETERIA = "cafeteria"
    ACTIVITY_BEAUTY = "beauty"
    ACTIVITY_RENTAL = "rental"
    ACTIVITY_SERVICE = "service"
    ACTIVITY_OTHER = "other"

    ACTIVITIES_WITH_WIP_BY_DEFAULT = {
        ACTIVITY_RESTAURANT,
        ACTIVITY_BAR,
        ACTIVITY_CAFETERIA,
    }

    # Campos principales
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(100), nullable=False, unique=True, comment="Nombre del negocio"
    )
    description = db.Column(
        db.String(255), nullable=True, comment="Descripción opcional del negocio"
    )
    logo = db.Column(db.String(255), nullable=True, comment="Ruta del archivo del logo")
    category = db.Column(
        db.String(50), nullable=True, comment="Campo legado (usar business_activity)"
    )
    business_activity = db.Column(
        db.String(120), nullable=True, comment="Actividad del negocio"
    )
    inventory_flow_sales_floor_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true(),
        comment="Habilita flujo de traslado a exposicion",
    )
    inventory_flow_wip_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
        comment="Habilita flujo de produccion en proceso (WIP)",
    )
    inventory_min_stock_policy = db.Column(
        db.String(20),
        nullable=False,
        default="alert",
        server_default="alert",
        comment="Politica al romper stock minimo: alert o block",
    )
    income_entry_mode = db.Column(
        db.String(30),
        nullable=False,
        default=INCOME_MODE_DAILY,
        comment="Modo de registro de ingresos del negocio",
    )
    default_income_activity = db.Column(
        db.String(20),
        nullable=False,
        default=INCOME_ACTIVITY_SALE,
        comment="Actividad por defecto para Daily Income",
    )
    address = db.Column(db.String(255), nullable=True, comment="Dirección del negocio")
    phone_number = db.Column(
        db.String(15), nullable=True, comment="Número de teléfono opcional"
    )
    email = db.Column(
        db.String(100), nullable=True, comment="Correo electrónico opcional"
    )
    website = db.Column(
        db.String(255), nullable=True, comment="URL del sitio web opcional"
    )
    tax_id = db.Column(
        db.String(20), nullable=True, comment="Número de identificación fiscal opcional"
    )
    fiscal_street = db.Column(db.String(120), nullable=True)
    fiscal_number = db.Column(db.String(30), nullable=True)
    fiscal_between_streets = db.Column(db.String(120), nullable=True)
    fiscal_apartment = db.Column(db.String(50), nullable=True)
    fiscal_district = db.Column(db.String(100), nullable=True)
    fiscal_municipality = db.Column(db.String(100), nullable=True)
    fiscal_province = db.Column(db.String(100), nullable=True)
    fiscal_postal_code = db.Column(db.String(20), nullable=True)
    currency = db.Column(
        db.String(10), default="CUP", comment="Tipo de moneda que opera el negocio"
    )
    is_general = db.Column(
        db.Boolean, default=False, comment="Indica si es un negocio general"
    )
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("clients.id"),
        nullable=True,
        comment="Cliente al que pertenece el negocio",
    )
    parent_business_id = db.Column(
        db.Integer, db.ForeignKey("business.id"), nullable=True, comment="Negocio padre"
    )
    created_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        comment="Fecha de creación del negocio",
    )
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
        comment="Fecha de actualización del negocio",
    )

    # Relaciones con otros modelos
    # Relación con el negocio padre (si existe)
    parent_business = db.relationship(
        "Business",
        remote_side=[id],
        backref=db.backref("sub_businesses", lazy="dynamic"),
        uselist=False,
    )
    # Relación con el cliente del negocio
    client = db.relationship(
        "Client",
        back_populates="businesses",
    )
    # Relación con los productos asociados al negocio
    products = db.relationship(
        "Product",
        backref=db.backref("business", lazy="select"),
        lazy="dynamic",
    )
    # Relación con las ventas asociadas al negocio
    sales = db.relationship(
        "Sale",
        back_populates="business",
        foreign_keys="[Sale.business_id]",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Business {self.name}>"

    @staticmethod
    def slugify(value: str | None) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", value)
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        lowered = ascii_value.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
        return slug

    @property
    def slug(self) -> str:
        return self.slugify(self.name)

    __table_args__ = (
        db.CheckConstraint(
            "income_entry_mode IN ('daily_income', 'detailed_sales')",
            name="business_income_entry_mode_allowed_values",
        ),
        db.CheckConstraint(
            "default_income_activity IN ('sale', 'service')",
            name="business_default_income_activity_allowed_values",
        ),
        db.CheckConstraint(
            "inventory_min_stock_policy IN ('alert', 'block')",
            name="business_inventory_min_stock_policy_allowed_values",
        ),
    )

    def parent_name(self):
        """
        Retorna el nombre del negocio general si es un negocio especifico
        Si no tiene un negocio padre, retorna None.
        """
        if self.parent_business:
            return self.parent_business.name
        return None
