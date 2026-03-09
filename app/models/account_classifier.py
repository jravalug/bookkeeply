from app.extensions import db
from sqlalchemy import ForeignKeyConstraint, event, inspect


class ACAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(
        db.String(20), nullable=False, unique=True
    )  # Código de la cuenta (ej. 800)
    name = db.Column(
        db.String(100), nullable=False
    )  # Nombre de la cuenta (ej. Gastos de Operaciones)
    is_normative = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true(),
        index=True,
    )
    subaccounts = db.relationship("ACSubAccount", back_populates="account")


class ACSubAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_code = db.Column(
        db.String(20), db.ForeignKey("ac_account.code"), nullable=False
    )
    code = db.Column(db.String(20), nullable=False)  # Código de la partida (ej. 11000)
    name = db.Column(
        db.String(100), nullable=False
    )  # Nombre de la partida (ej. Materias Primas y Materiales)
    elements = db.relationship("ACElement", back_populates="subaccount")

    # Relación con la cuenta principal
    account = db.relationship("ACAccount", back_populates="subaccounts")

    __table_args__ = (
        db.UniqueConstraint(
            "code",
            "account_code",
            name="unique_ac_subaccount_code_per_ac_account_code",
        ),
    )


class ACElement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subaccount_code = db.Column(
        db.String(20), db.ForeignKey("ac_sub_account.code"), nullable=False
    )
    code = db.Column(db.String(20), nullable=False)  # Código del elemento (ej. 01)
    name = db.Column(
        db.String(100), nullable=False
    )  # Nombre del elemento (ej. Alimento)

    # Relación con la partida
    subaccount = db.relationship("ACSubAccount", back_populates="elements")
    # details = db.relationship("PurchaseDetail", back_populates="element")

    __table_args__ = (
        db.UniqueConstraint(
            "code",
            "subaccount_code",
            name="unique_ac_element_code_per_ac_subaccount_code",
        ),
    )


class BusinessAccountAdoption(db.Model):
    __tablename__ = "business_account_adoption"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("ac_account.id"),
        nullable=False,
        index=True,
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    adopted_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    removed_at = db.Column(db.DateTime, nullable=True)

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="adopted_accounts",
    )
    account = db.relationship(
        "ACAccount",
        foreign_keys=[account_id],
        backref="adoptions",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "business_id",
            "account_id",
            name="uq_business_account_adoption_business_account",
        ),
        db.UniqueConstraint(
            "business_id",
            "id",
            name="uq_business_account_adoption_business_id_id",
        ),
    )


class BusinessAccountAdoptionAudit(db.Model):
    __tablename__ = "business_account_adoption_audit"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    account_id = db.Column(
        db.Integer,
        db.ForeignKey("ac_account.id"),
        nullable=False,
        index=True,
    )
    action = db.Column(db.String(30), nullable=False, index=True)
    actor = db.Column(db.String(120), nullable=True)
    source = db.Column(db.String(50), nullable=True)
    previous_is_active = db.Column(db.Boolean, nullable=True)
    new_is_active = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="account_adoption_audits",
    )
    account = db.relationship(
        "ACAccount",
        foreign_keys=[account_id],
        backref="adoption_audits",
    )


class BusinessSubAccount(db.Model):
    __tablename__ = "business_sub_account"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    business_account_adoption_id = db.Column(
        db.Integer,
        db.ForeignKey("business_account_adoption.id"),
        nullable=False,
        index=True,
    )
    template_subaccount_id = db.Column(
        db.Integer,
        db.ForeignKey("ac_sub_account.id"),
        nullable=True,
        index=True,
    )
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
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
        "Business",
        foreign_keys=[business_id],
        backref="business_subaccounts",
    )
    adoption = db.relationship(
        "BusinessAccountAdoption",
        foreign_keys=[business_account_adoption_id],
        backref="business_subaccounts",
    )
    template_subaccount = db.relationship(
        "ACSubAccount",
        foreign_keys=[template_subaccount_id],
        backref="business_subaccount_overrides",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "business_account_adoption_id"],
            [
                "business_account_adoption.business_id",
                "business_account_adoption.id",
            ],
            name="fk_business_sub_account_adoption_same_business",
        ),
        db.UniqueConstraint(
            "business_id",
            "code",
            name="uq_business_sub_account_business_code",
        ),
    )


class BusinessSubAccountAudit(db.Model):
    __tablename__ = "business_sub_account_audit"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=False,
        index=True,
    )
    business_sub_account_id = db.Column(
        db.Integer,
        db.ForeignKey("business_sub_account.id"),
        nullable=True,
        index=True,
    )
    business_account_adoption_id = db.Column(
        db.Integer,
        db.ForeignKey("business_account_adoption.id"),
        nullable=False,
        index=True,
    )
    action = db.Column(db.String(30), nullable=False, index=True)
    actor = db.Column(db.String(120), nullable=True)
    source = db.Column(db.String(50), nullable=True)
    previous_code = db.Column(db.String(20), nullable=True)
    new_code = db.Column(db.String(20), nullable=True)
    previous_name = db.Column(db.String(100), nullable=True)
    new_name = db.Column(db.String(100), nullable=True)
    previous_is_active = db.Column(db.Boolean, nullable=True)
    new_is_active = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )

    business = db.relationship(
        "Business",
        foreign_keys=[business_id],
        backref="subaccount_audits",
    )
    subaccount = db.relationship(
        "BusinessSubAccount",
        foreign_keys=[business_sub_account_id],
        backref="audits",
    )
    adoption = db.relationship(
        "BusinessAccountAdoption",
        foreign_keys=[business_account_adoption_id],
        backref="subaccount_audits",
    )


@event.listens_for(ACAccount, "before_update")
def block_ac_account_normative_updates(mapper, connection, target):
    state = inspect(target)
    if target.is_normative and (
        state.attrs.code.history.has_changes() or state.attrs.name.history.has_changes()
    ):
        raise ValueError(
            "El nomenclador general es normativo y no permite editar codigo ni nombre de cuenta"
        )
