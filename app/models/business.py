from datetime import datetime, timezone
import re
import unicodedata

from app.extensions import db
from sqlalchemy import event


class Business(db.Model):
    """
    Modelo que representa un negocio (empresa o sucursal) en el sistema.

    Atributos principales:
        - Identidad y descripción del negocio.
        - Clasificación, actividad y régimen contable.
        - Políticas de inventario.
        - Información de contacto y ubicación.
        - Fiscalidad y moneda.
        - Jerarquía (matriz/sucursal) y relación con cliente.
        - Estado y auditoría.

    Relaciones:
        - main_business: Negocio principal (si es sucursal).
        - branches: Sucursales asociadas (si es matriz).
        - business_type: Tipo de negocio (catálogo).
        - client: Cliente propietario del negocio.
        - products: Productos asociados.
        - sales: Ventas asociadas.
        - creator/updater: Usuarios que crearon/actualizaron el registro.
    """

    __tablename__ = "business"

    REGIME_FISCAL = "fiscal"
    REGIME_FINANCIAL = "financial"

    INCOME_MODE_SALE = "sale"
    INCOME_MODE_SERVICE = "service"

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_SUSPENDED = "suspended"
    STATUS_DELETED = "deleted"

    # 1. Identidad y Descripción
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment="Nombre del negocio")
    logo = db.Column(db.String(255), nullable=True, comment="Ruta del archivo del logo")
    description = db.Column(
        db.String(255), nullable=True, comment="Descripción opcional del negocio"
    )

    # 2. Clasificación y Actividad
    business_type_id = db.Column(
        db.Integer,
        db.ForeignKey("catalogs_business_types.id"),
        nullable=False,
        comment="Tipo de negocio",
    )
    income_mode = db.Column(
        db.String(30),
        nullable=False,
        default=INCOME_MODE_SALE,
        comment="Modo de registro de ingresos: Ventas o Servicios",
    )
    accounting_regime = db.Column(
        db.String(20),
        nullable=False,
        default=REGIME_FISCAL,
        comment="Régimen contable del negocio: Fiscal o Financiero",
    )
    regime_changed_at = db.Column(db.DateTime, nullable=True)
    regime_change_reason = db.Column(db.String(255), nullable=True)
    last_regime_evaluation_year = db.Column(db.Integer, nullable=True)
    last_regime_evaluated_at = db.Column(db.DateTime, nullable=True)

    # 3. Inventario y Políticas
    inventory_flow_sales_floor_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
        comment="Habilita flujo de traslado a exposicion",
    )
    inventory_flow_wip_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
        comment="Habilita flujo de produccion en proceso (WIP)",
    )

    # 4. Contacto y Ubicación
    phone_number = db.Column(
        db.String(15), nullable=True, comment="Número de teléfono opcional"
    )
    email = db.Column(
        db.String(100), nullable=True, comment="Correo electrónico opcional"
    )
    website = db.Column(
        db.String(255), nullable=True, comment="URL del sitio web opcional"
    )
    addr_street = db.Column(
        db.String(120),
        nullable=False,
        comment="Calle de la dirección del negocio",
    )
    addr_number = db.Column(
        db.String(30), nullable=False, comment="Número de la dirección del negocio"
    )
    addr_between_streets = db.Column(
        db.String(120),
        nullable=False,
        comment="Entre calles de la dirección del negocio",
    )
    addr_apartment = db.Column(
        db.String(50), nullable=True, comment="Apartamento de la dirección del negocio"
    )
    addr_district = db.Column(
        db.String(100), nullable=True, comment="Distrito de la dirección del negocio"
    )
    addr_municipality = db.Column(
        db.String(100), nullable=False, comment="Municipio de la dirección del negocio"
    )
    addr_province = db.Column(
        db.String(100), nullable=False, comment="Provincia de la dirección del negocio"
    )
    addr_postal_code = db.Column(
        db.String(20),
        nullable=True,
        comment="Código postal de la dirección del negocio",
    )

    # 5. Fiscalidad y Moneda
    tax_id = db.Column(
        db.String(20), nullable=True, comment="Número de identificación fiscal opcional"
    )
    currency = db.Column(
        db.String(10), default="CUP", comment="Tipo de moneda que opera el negocio"
    )

    # 6. Jerarquía y Relación
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("clients.id"),
        nullable=False,
        comment="Cliente al que pertenece el negocio",
    )
    is_branch = db.Column(
        db.Boolean, default=False, comment="Indica si es una sucursal"
    )
    main_business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=True,
        comment="Negocio principal",
    )

    # 7. Estado y Auditoría
    status = db.Column(
        db.String(20),
        nullable=False,
        default=STATUS_ACTIVE,
        comment="Estado del negocio: active, inactive, suspended, deleted, etc.",
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        comment="Fecha de creación del negocio",
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        comment="Fecha de actualización del negocio",
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        comment="Usuario que creó el negocio",
    )
    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        comment="Usuario que actualizó el negocio",
    )

    # Relaciones con otros modelos

    # Relación con el cliente del negocio
    client = db.relationship(
        "Client",
        back_populates="businesses",
    )
    # Relación con el negocio padre (si existe)
    main_business = db.relationship(
        "Business",
        remote_side=[id],
        backref=db.backref("branches", lazy="dynamic"),
        uselist=False,
    )
    # Relación con el tipo de negocio
    business_type = db.relationship(
        "BusinessType",
        backref=db.backref("businesses", lazy="dynamic"),
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
    # Relacion con el usuario que creó y actualizó el negocio
    creator = db.relationship(
        "User", foreign_keys=[created_by], backref="businesses_created"
    )
    updater = db.relationship(
        "User", foreign_keys=[updated_by], backref="businesses_updated"
    )

    def __repr__(self):
        return f"<Business {self.name}>"

    @staticmethod
    def slugify(value: str | None) -> str:
        """
        Convierte un texto en un slug ASCII en minúsculas, apto para URLs.
        Elimina acentos y caracteres especiales.
        """
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
            "accounting_regime IN ('fiscal', 'financial')",
            name="business_accounting_regime_allowed_values",
        ),
        db.CheckConstraint(
            "income_mode IN ('sale', 'service')",
            name="business_income_mode_allowed_values",
        ),
        db.UniqueConstraint("name", "client_id", name="uq_business_name_per_client"),
    )

    def main_business_name(self):
        """
        Devuelve el nombre del negocio principal si la instancia es una sucursal.
        Retorna None si no aplica.
        """
        if self.is_branch and self.main_business:
            return self.main_business.name
        return None

    @event.listens_for("Business", "before_insert")
    @event.listens_for("Business", "before_update")
    def check_branch_business(mapper, connection, target):
        """
        Valida la integridad de la relación sucursal/matriz antes de insertar o actualizar:
        - Si 'is_branch' es True, 'main_business_id' debe estar definido.
        - Si 'is_branch' es False, 'main_business_id' debe ser None.
        Lanza ValueError si la relación es inconsistente.
        """
        if target.is_branch and not target.main_business_id:
            raise ValueError("Una sucursal debe tener un negocio principal.")
        if not target.is_branch and target.main_business_id is not None:
            raise ValueError(
                "Un negocio principal no puede tener un negocio principal asignado."
            )
