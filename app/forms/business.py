from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FileField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Optional

from app.models import Business


class BusinessForm(FlaskForm):
    """Formulario para crear y editar negocios."""

    name = StringField(
        "Nombre",
        validators=[DataRequired(message="El nombre del negocio es obligatorio.")],
    )
    description = TextAreaField("Descripción", validators=[Optional()])
    business_activity = StringField("Actividad del negocio", validators=[Optional()])
    inventory_flow_sales_floor_enabled = BooleanField(
        "Habilitar flujo de exposicion",
        default=True,
        false_values=(False, "false", "", "n", "no", "0"),
    )
    inventory_flow_wip_enabled = BooleanField(
        "Habilitar flujo WIP",
        default=False,
        false_values=(False, "false", "", "n", "no", "0"),
    )
    income_entry_mode = SelectField(
        "Modo de ingresos",
        choices=[
            (Business.INCOME_MODE_DAILY, "Ingreso diario"),
            (Business.INCOME_MODE_DETAILED, "Ventas detalladas"),
        ],
        default=Business.INCOME_MODE_DAILY,
        validators=[Optional()],
    )
    default_income_activity = SelectField(
        "Actividad por defecto",
        choices=[
            (Business.INCOME_ACTIVITY_SALE, "Venta"),
            (Business.INCOME_ACTIVITY_SERVICE, "Servicio"),
        ],
        default=Business.INCOME_ACTIVITY_SALE,
        validators=[Optional()],
    )
    fiscal_street = StringField("Calle fiscal", validators=[Optional()])
    fiscal_number = StringField("Número fiscal", validators=[Optional()])
    fiscal_between_streets = StringField(
        "Entre calles (fiscal)", validators=[Optional()]
    )
    fiscal_apartment = StringField("Apto / Oficina fiscal", validators=[Optional()])
    fiscal_district = StringField("Reparto / Distrito fiscal", validators=[Optional()])
    fiscal_municipality = StringField("Municipio fiscal", validators=[Optional()])
    fiscal_province = StringField("Provincia fiscal", validators=[Optional()])
    fiscal_postal_code = StringField("Código postal fiscal", validators=[Optional()])
    is_general = BooleanField(
        "Negocio Principal",
        false_values=(
            False,
            "false",
            "",
            "n",
            "no",
            "0",
        ),  # Valores que se consideran False
        description="Marque esta casilla para convertir en negocio principal.",
    )
    logo = FileField("Logo", validators=[Optional()])  # Campo opcional
