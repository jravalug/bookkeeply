from datetime import datetime, timezone
import re
import unicodedata

from app.extensions import db


# Tabla de asociación muchos-a-muchos entre Client y EconomicActivity
client_economic_activities = db.Table(
    "client_economic_activities",
    db.Column("client_id", db.Integer, db.ForeignKey("clients.id"), primary_key=True),
    db.Column(
        "economic_activity_id",
        db.Integer,
        db.ForeignKey("catalogs_economic_activities.id"),
        primary_key=True,
    ),
    db.Column("approved_at", db.DateTime, default=db.func.current_timestamp()),
)


class Client(db.Model):
    """
    Modelo que representa un cliente (persona natural o jurídica) en el sistema.

    Atributos:
        - id: Identificador único.
        - name: Nombre del cliente (único).
        - dni: Documento de identidad (único).
        - street, number, between_streets, apartment, district, municipality, province, postal_code:
            Dirección legal del cliente.
        - phone_number: Teléfono de contacto.
        - email_address: Correo electrónico de contacto.
        - nit: Número de identificación tributaria (único).
        - management_type: Tipo de gestión ('tcp' o 'mipyme').
        - main_economic_activity_id: Actividad económica principal (catálogo).
        - fiscal_account_number: Número de cuenta fiscal.
        - fiscal_account_card_number: Número de tarjeta asociada a la cuenta fiscal.
        - status: Estado del cliente (activo, inactivo, suspendido, eliminado).
        - created_at, updated_at: Fechas de creación y actualización.
        - created_by, updated_by: Usuarios responsables de la creación/actualización.

    Relaciones:
        - creator: Usuario que creó el cliente.
        - updater: Usuario que actualizó el cliente.
        - businesses: Negocios asociados a este cliente.
        - main_economic_activity: Actividad económica principal (catálogo).
        - economic_activities: Actividades económicas asociadas (muchos-a-muchos, catálogo).
    """

    __tablename__ = "clients"

    TYPE_TCP = "tcp"
    TYPE_MIPYME = "mipyme"

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_SUSPENDED = "suspended"
    STATUS_DELETED = "deleted"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    dni = db.Column(db.String(30), nullable=False, unique=True)

    # Legal address fields
    street = db.Column(db.String(120), nullable=False)
    number = db.Column(db.String(30), nullable=False)
    between_streets = db.Column(db.String(120), nullable=False)
    apartment = db.Column(db.String(50), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    municipality = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=True)

    # Phone and email fields
    phone_number = db.Column(db.String(30), nullable=True)
    email_address = db.Column(db.String(120), nullable=True)

    # Fiscal information
    nit = db.Column(db.String(30), nullable=False, unique=True)
    management_type = db.Column(db.String(20), nullable=False, default=TYPE_TCP)
    main_economic_activity_id = db.Column(
        db.Integer,
        db.ForeignKey("catalogs_economic_activities.id"),
        nullable=True,
        comment="Actividad económica principal del cliente",
    )
    fiscal_account_number = db.Column(db.String(50), nullable=True)
    fiscal_account_card_number = db.Column(db.String(30), nullable=True)

    status = db.Column(
        db.String(20),
        nullable=False,
        default=STATUS_ACTIVE,
        comment="Estado del cliente: active, inactive, suspended, deleted, etc.",
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        comment="Fecha de creación del cliente",
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        comment="Fecha de actualización del cliente",
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        comment="Usuario que creó el cliente",
    )
    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        comment="Usuario que actualizó el cliente",
    )
    creator = db.relationship(
        "User", foreign_keys=[created_by], backref="clients_created"
    )
    updater = db.relationship(
        "User", foreign_keys=[updated_by], backref="clients_updated"
    )

    businesses = db.relationship(
        "Business",
        back_populates="client",
        lazy="dynamic",
    )

    main_economic_activity = db.relationship(
        "EconomicActivity",
        foreign_keys=[main_economic_activity_id],
        post_update=True,
        backref="clients_with_main_economic_activity",
    )

    # Relación muchos-a-muchos con actividades económicas
    economic_activities = db.relationship(
        "EconomicActivity",
        secondary=client_economic_activities,
        backref="clients",
        lazy="dynamic",
    )

    __table_args__ = (
        db.UniqueConstraint("dni", name="uq_client_dni"),
        db.UniqueConstraint("nit", name="uq_client_nit"),
        db.CheckConstraint(
            "management_type IN ('tcp', 'mipyme')",
            name="client_management_type_allowed_values",
        ),
        db.CheckConstraint(
            "status IN ('active', 'inactive', 'suspended', 'deleted')",
            name="client_status_allowed_values",
        ),
    )

    def __repr__(self):
        return f"<Client {self.name}>"

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
