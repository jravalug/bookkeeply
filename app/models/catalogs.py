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
