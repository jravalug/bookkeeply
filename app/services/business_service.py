from app.models import Business
from app.extensions import db


class BusinessService:
    def __init__(self):
        """Inicializa el servicio de negocios."""

    @staticmethod
    def _validate_required_fields(data: dict, required_fields: list[str]) -> None:
        """Valida que los campos obligatorios estén presentes en los datos."""
        for field in required_fields:
            if field not in data:
                raise ValueError(
                    f"El campo '{field}' es obligatorio para crear un negocio."
                )

    @staticmethod
    def _apply_business_updates(business: Business, data: dict) -> None:
        """Aplica cambios validados al modelo `Business` recibido."""
        for key, value in data.items():
            if not hasattr(business, key):
                raise ValueError(
                    f"El campo '{key}' no es válido para el modelo Business."
                )
            setattr(business, key, value)

    @staticmethod
    def _normalize_business_activity(value):
        normalized = (value or "").strip().lower()
        return normalized or None

    @staticmethod
    def _coerce_optional_bool(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        return normalized in {"1", "true", "yes", "on", "si", "s"}

    @staticmethod
    def _resolve_inventory_flow_defaults(activity: str | None):
        enable_sales_floor = True
        enable_wip = activity in Business.ACTIVITIES_WITH_WIP_BY_DEFAULT
        return enable_sales_floor, enable_wip

    @staticmethod
    def _apply_inventory_flow_rules(
        kwargs: dict, current_business: Business | None = None
    ):
        normalized_activity = BusinessService._normalize_business_activity(
            kwargs.get("business_activity")
            if "business_activity" in kwargs
            else (current_business.business_activity if current_business else None)
        )

        if "business_activity" in kwargs:
            kwargs["business_activity"] = normalized_activity

        explicit_sales_floor = BusinessService._coerce_optional_bool(
            kwargs.get("inventory_flow_sales_floor_enabled")
        )
        explicit_wip = BusinessService._coerce_optional_bool(
            kwargs.get("inventory_flow_wip_enabled")
        )

        default_sales_floor, default_wip = (
            BusinessService._resolve_inventory_flow_defaults(normalized_activity)
        )

        if explicit_sales_floor is not None:
            kwargs["inventory_flow_sales_floor_enabled"] = explicit_sales_floor
        elif "inventory_flow_sales_floor_enabled" not in kwargs:
            kwargs["inventory_flow_sales_floor_enabled"] = default_sales_floor

        if explicit_wip is not None:
            kwargs["inventory_flow_wip_enabled"] = explicit_wip
        elif "inventory_flow_wip_enabled" not in kwargs:
            kwargs["inventory_flow_wip_enabled"] = default_wip

        return kwargs

    def create_business(self, **kwargs):
        """
        Crea un nuevo negocio en la base de datos.

        :param kwargs: Campos y valores para crear el negocio (por ejemplo, name, description, logo, etc.).
        :return: El objeto Business recién creado.
        """
        try:
            self._validate_required_fields(kwargs, ["name"])
            kwargs = self._apply_inventory_flow_rules(kwargs)
            new_business = Business(**kwargs)
            db.session.add(new_business)
            db.session.commit()
            return new_business

        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Error al crear el negocio: {e}")

    def update_business(self, business, **kwargs):
        """
        Actualiza un negocio existente en la base de datos.

        :param business: Objeto `Business` a actualizar.
        :param kwargs: Campos y valores para actualizar el negocio (por ejemplo, name, description, logo, etc.).
        :return: El objeto `Business` actualizado.
        """
        try:
            kwargs = self._apply_inventory_flow_rules(kwargs, current_business=business)
            self._apply_business_updates(business, kwargs)
            db.session.commit()
            return business

        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Error al actualizar el negocio: {e}")

    def get_parent_filters(self, business: Business):
        """
        Devuelve los filtros necesarios para consultar ventas u otros datos relacionados con un negocio.

        :param business: Objeto `Business` para el cual se generan los filtros.
        :return: Un diccionario con los filtros aplicables.
        """
        filters = {
            "business_id": (
                business.id if business.is_general else business.parent_business_id
            )
        }
        if not business.is_general:
            filters["specific_business_id"] = business.id
        return filters

    @staticmethod
    def get_businesses_api_data():
        """Serializa negocios para respuestas simples de API."""
        businesses = Business.query.all()
        return [
            {
                "id": business.id,
                "name": business.name,
                "description": business.description,
            }
            for business in businesses
        ]
