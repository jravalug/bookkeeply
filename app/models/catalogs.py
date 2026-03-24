import enum
from app.extensions import db


class EconomicActivity(db.Model):
    """
    Catálogo de actividades económicas.
    """

    __tablename__ = "catalogs_economic_activities"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(
        db.String(20),
        unique=True,
        index=True,
        nullable=False,
        comment="Código de la actividad económica (ej. 4217, L)",
    )  # Agregado campo code
    name = db.Column(
        db.String(120), nullable=False, comment="Nombre de la actividad económica"
    )
    description = db.Column(
        db.String(255),
        nullable=True,
        comment="Descripción opcional de la actividad económica",
    )

    def __repr__(self):
        return f"<EconomicActivity {self.name}>"


class BusinessType(db.Model):
    """
    Catálogo de tipos de negocio.
    """

    __tablename__ = "catalogs_business_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        comment="Nombre del tipo de negocio",
    )
    description = db.Column(
        db.String(255), nullable=True, comment="Descripción opcional"
    )

    def __repr__(self):
        return f"<BusinessType {self.name}>"


class AccountLevelEnum(enum.Enum):
    """
    Enum que representa los niveles del catálogo de cuentas contables.
    """

    ACCOUNT = "account"
    SUBACCOUNT = "subaccount"
    ELEMENT = "element"
    SUBELEMENT = "subelement"


class AccountClassifier(db.Model):
    """
    Clasificador jerárquico de cuentas contables (cuenta, subcuenta, elemento, subelemento).

    Permite representar cualquier nivel del nomenclador contable mediante la relación padre-hijo.
    El campo 'level' indica el nivel: 'account', 'subaccount', 'element', 'subelement'.

    Atributos:
        - id: Identificador único.
        - code: Código único de la cuenta/subcuenta/elemento/subelemento.
        - name: Nombre de la cuenta/subcuenta/elemento/subelemento.
        - parent_id: Referencia al nodo padre (nullable para cuentas raíz).
        - level: Nivel del clasificador ('account', 'subaccount', 'element', 'subelement').
        - is_normative: Indica si es parte del nomenclador normativo general.
        - description: Descripción opcional.
        - is_active: Indica si está activo en el clasificador.
    Relaciones:
        - parent: Nodo padre en la jerarquía.
        - children: Nodos hijos (subcuentas, elementos, subelementos).
    """

    __tablename__ = "catalogs_account_classifier"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(
        db.Integer, db.ForeignKey("catalogs_account_classifier.id"), nullable=True
    )
    level = db.Column(
        db.Enum(AccountLevelEnum, name="account_level_enum"),
        nullable=False,
        index=True,
        comment="Nivel del clasificador: 'account', 'subaccount', 'element', 'subelement'.",
    )
    description = db.Column(db.String(255), nullable=True)
    is_normative = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    parent = db.relationship(
        "AccountClassifier",
        remote_side=[id],
        backref=db.backref("children", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<AccountClassifier {self.code} - {self.name} ({self.level})>"

    __table_args__ = (
        db.UniqueConstraint(
            "parent_id", "code", name="uq_account_classifier_parent_code"
        ),
        db.CheckConstraint(
            "level IN ('account', 'subaccount', 'element', 'subelement')",
            name="account_classifier_level_allowed_values",
        ),
    )
