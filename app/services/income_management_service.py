from typing import Dict, Optional
from datetime import date, datetime
from collections import defaultdict

from sqlalchemy import desc, func, inspect, text
from sqlalchemy.orm import joinedload
from dateutil.relativedelta import relativedelta

from app import db
from app.forms import (
    IncomeForm,
    IncomeDetailForm,
    UpdateIncomeDetailForm,
    RemoveIncomeDetailForm,
)
from app.models import (
    Sale,
    Product,
    SaleDetail,
    DailyIncome,
    IncomeEvent,
    CollectionReceipt,
    InventoryItem,
    InventoryMovement,
)
from app.models.business import Business
from app.repositories.income_repository import IncomeRepository
from app.services.business_service import BusinessService
from app.services.income_posting_service import IncomePostingService
from app.services.cash_flow_service import CashFlowService
from app.services.inventory_service import InventoryService
from app.utils.slug_utils import get_business_by_slugs
from app.utils.income_utils import calculate_month_totals, group_sales_by_month


class IncomeManagementService:
    """
    Servicio para manejar las operaciones relacionadas con ingresos detallados.
    """

    MONTH_NAMES = (
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    )

    ALLOWED_PAYMENT_METHODS = {"cash", "transfer", "check"}
    TRANSFER_LIKE_METHODS = {"transfer", "check"}
    DEBTOR_TYPES = {"natural", "legal"}
    INVENTORY_SALE_LINE_REFERENCE_TYPE = "sale_inventory_line"
    INVENTORY_SYNC_QUANTITY_EPSILON = 1e-6

    def __init__(self):
        """Inicializa dependencias del servicio de ventas."""
        self.repository = IncomeRepository()
        self.business_service = BusinessService()

    # Métodos principales para operaciones CRUD de income

    def get_income(self, income_id, business_id):
        """Obtiene los detalles completos de un ingreso con sus relaciones."""
        return (
            Sale.query.options(joinedload(Sale.products).joinedload(SaleDetail.product))
            .filter(Sale.id == income_id, Sale.business_id == business_id)
            .first_or_404()
        )

    def get_sale(self, sale_id, business_id):
        """Alias temporal para compatibilidad retroactiva."""
        return self.get_income(sale_id, business_id)

    def resolve_business_and_filters(self, client_slug: str, business_slug: str):
        """Resuelve negocio por slugs y devuelve filtros de consulta asociados."""
        business = get_business_by_slugs(client_slug, business_slug)
        if not business:
            raise ValueError("Negocio no encontrado")

        filters = self.business_service.get_parent_filters(business=business)
        return business, filters

    def resolve_income_scope(
        self,
        client_slug: str,
        business_slug: str,
        income_id: int,
    ):
        """Resuelve negocio, filtros e ingreso concreto dentro del alcance válido."""
        business, filters = self.resolve_business_and_filters(
            client_slug, business_slug
        )
        income = self.get_income(income_id, filters["business_id"])
        return business, filters, income

    def resolve_sale_scope(self, client_slug: str, business_slug: str, sale_id: int):
        """Alias temporal para compatibilidad retroactiva."""
        return self.resolve_income_scope(client_slug, business_slug, sale_id)

    @staticmethod
    def get_incomes_api_data(business_id: int):
        """Devuelve ingresos serializados para consumo de endpoints API."""
        sales = Sale.query.filter_by(business_id=business_id).all()
        return [
            {
                "id": sale.id,
                "date": sale.date.strftime("%Y-%m-%d"),
                "total": sum(
                    (
                        sale_product.total_price
                        if sale_product.total_price is not None
                        else (sale_product.quantity or 0)
                        * (
                            (sale_product.product.price if sale_product.product else 0)
                            or 0
                        )
                    )
                    for sale_product in sale.products
                ),
            }
            for sale in sales
        ]

    def get_sales_api_data(self, business_id: int):
        """Alias temporal para compatibilidad retroactiva."""
        return self.get_incomes_api_data(business_id)

    def get_available_products(self, business_id):
        """Obtiene los productos disponibles para un negocio"""
        return (
            Product.query.filter_by(business_id=business_id)
            .order_by(Product.name.asc())
            .all()
        )

    def get_income_details(self, income_id):
        """Obtiene los productos de un ingreso específico."""
        return SaleDetail.query.filter_by(sale_id=income_id).join(Product).all()

    def get_sale_details(self, sale_id):
        """Alias temporal para compatibilidad retroactiva."""
        return self.get_income_details(sale_id)

    def get_income_detail_for_income(
        self, income_id: int, sale_detail_id: int
    ) -> SaleDetail:
        """Obtiene un detalle validando que pertenezca al ingreso indicado."""
        return SaleDetail.query.filter_by(
            id=sale_detail_id, sale_id=income_id
        ).first_or_404()

    def get_sale_detail_for_sale(self, sale_id: int, sale_detail_id: int) -> SaleDetail:
        """Alias temporal para compatibilidad retroactiva."""
        return self.get_income_detail_for_income(sale_id, sale_detail_id)

    def handle_remove_product_form(self, income: Sale, sale_detail_id: int) -> Product:
        """Procesa formulario para remover un producto de un ingreso."""
        sale_detail = self.get_income_detail_for_income(
            income_id=income.id,
            sale_detail_id=sale_detail_id,
        )
        return self.remove_product_from_income(income=income, sale_detail=sale_detail)

    def handle_add_product_form(
        self,
        income: Sale,
        product_id: int,
        quantity: int,
        discount: float,
    ) -> SaleDetail:
        """Procesa formulario para agregar un producto a un ingreso."""
        return self.add_product_to_income(
            income=income,
            product_id=product_id,
            quantity=quantity,
            discount=discount,
        )

    def handle_update_product_form(
        self,
        income: Sale,
        sale_detail_id: int,
        quantity: int,
        discount: float,
    ) -> SaleDetail:
        """Procesa formulario para actualizar cantidad/descuento de un producto vendido."""
        sale_detail = self.get_income_detail_for_income(
            income_id=income.id,
            sale_detail_id=sale_detail_id,
        )
        return self.update_income_detail(
            income=income,
            sale_detail=sale_detail,
            quantity=quantity,
            discount=discount,
        )

    @staticmethod
    def parse_month_range(month_param: str | None):
        """Resuelve mes seleccionado y su rango de fechas opcional."""
        selected_month = month_param if month_param else None
        date_range = None
        if not month_param:
            return selected_month, date_range

        selected = datetime.strptime(month_param, "%Y-%m").date()
        start_date = selected.replace(day=1)
        end_date = start_date + relativedelta(months=1, days=-1)
        return selected_month, (start_date, end_date)

    @staticmethod
    def build_months_display(months: list[str]):
        """Convierte meses `YYYY-MM` a etiquetas legibles para UI."""
        months_display = []
        for month in months:
            try:
                dt = datetime.strptime(month, "%Y-%m").date()
                label = f"{IncomeManagementService.MONTH_NAMES[dt.month - 1]} {dt.year}"
            except Exception:
                label = month
            months_display.append((month, label))
        return months_display

    @staticmethod
    def _resolve_month_navigation(selected_month: str | None, months: list[str]):
        """Calcula navegación de mes anterior/siguiente para la vista."""
        prev_month = None
        next_month = None
        display_month_name = "Todos"

        if not selected_month or selected_month not in months:
            return prev_month, next_month, display_month_name

        try:
            idx = months.index(selected_month)
            if idx + 1 < len(months):
                prev_month = months[idx + 1]
            if idx - 1 >= 0:
                next_month = months[idx - 1]
            display_month_name = IncomeManagementService.build_months_display(
                [selected_month]
            )[0][1]
        except Exception:
            display_month_name = selected_month

        return prev_month, next_month, display_month_name

    @staticmethod
    def _aggregate_daily_sales(sales_by_months: dict):
        """Consolida ventas diarias provenientes de múltiples meses."""
        daily_sales = {}
        for _, dates in sales_by_months.items():
            for date_key, data in dates.items():
                if date_key in daily_sales:
                    daily_sales[date_key]["total_products"] += data.get(
                        "total_products", 0
                    )
                    daily_sales[date_key]["total_income"] += data.get("total_income", 0)
                    daily_sales[date_key]["sales"].extend(data.get("sales", []))
                else:
                    daily_sales[date_key] = {
                        "total_products": data.get("total_products", 0),
                        "total_income": data.get("total_income", 0),
                        "sales": list(data.get("sales", [])),
                    }
        return daily_sales

    @staticmethod
    def _load_daily_income_context(business_id: int, date_range):
        """Carga ingresos diarios con y sin filtro mensual para el contexto."""
        daily_query = DailyIncome.query.filter_by(business_id=business_id)

        try:
            all_daily_income_unfiltered = daily_query.order_by(
                DailyIncome.date.desc(), DailyIncome.id.desc()
            ).all()
        except Exception as exc:
            if not IncomeManagementService._is_missing_daily_income_column_error(exc):
                raise

            IncomeManagementService._ensure_daily_income_compatibility_columns()
            all_daily_income_unfiltered = daily_query.order_by(
                DailyIncome.date.desc(), DailyIncome.id.desc()
            ).all()

        months = sorted(
            {
                income.date.strftime("%Y-%m")
                for income in all_daily_income_unfiltered
                if income.date
            },
            reverse=True,
        )

        if date_range:
            all_daily_income = (
                daily_query.filter(
                    DailyIncome.date.between(date_range[0], date_range[1])
                )
                .order_by(DailyIncome.date.desc(), DailyIncome.id.desc())
                .all()
            )
        else:
            all_daily_income = all_daily_income_unfiltered

        return all_daily_income_unfiltered, all_daily_income, months

    @staticmethod
    def _is_missing_daily_income_column_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "no such column" in message and "daily_income.payment_method" in message
        ) or (
            "has no column named payment_method" in message
            and "daily_income" in message
        )

    @staticmethod
    def _ensure_daily_income_compatibility_columns() -> None:
        inspector = inspect(db.engine)
        existing_columns = {
            column["name"] for column in inspector.get_columns("daily_income")
        }

        column_defs = {
            "payment_method": "VARCHAR(20) NOT NULL DEFAULT 'cash'",
            "debtor_type": "VARCHAR(20)",
            "debtor_natural_full_name": "VARCHAR(150)",
            "debtor_natural_identity_number": "VARCHAR(50)",
            "debtor_natural_bank_account": "VARCHAR(80)",
            "debtor_legal_entity_name": "VARCHAR(200)",
            "debtor_legal_reeup_code": "VARCHAR(50)",
            "debtor_legal_address": "VARCHAR(255)",
            "debtor_legal_credit_branch": "VARCHAR(120)",
            "debtor_legal_bank_account": "VARCHAR(80)",
            "debtor_legal_contract_number": "VARCHAR(80)",
        }

        missing_columns = [
            (name, ddl)
            for name, ddl in column_defs.items()
            if name not in existing_columns
        ]
        if not missing_columns:
            return

        db.session.rollback()
        with db.engine.begin() as connection:
            for column_name, ddl in missing_columns:
                connection.execute(
                    text(f"ALTER TABLE daily_income ADD COLUMN {column_name} {ddl}")
                )

    @staticmethod
    def _load_sales_context(filters: dict, date_range):
        """Carga ventas con y sin filtro mensual para el contexto de listado."""
        all_sales_unfiltered = (
            Sale.query.options(joinedload(Sale.products))
            .filter_by(**filters)
            .order_by(Sale.date.desc())
            .all()
        )
        sales_by_months_unfiltered = group_sales_by_month(all_sales_unfiltered)
        months = sorted(list(sales_by_months_unfiltered.keys()), reverse=True)

        if date_range:
            all_sales = (
                Sale.query.options(joinedload(Sale.products))
                .filter_by(**filters)
                .filter(Sale.date.between(date_range[0], date_range[1]))
                .order_by(Sale.date.desc())
                .all()
            )
        else:
            all_sales = all_sales_unfiltered

        return all_sales_unfiltered, all_sales, months

    def create_daily_income(self, business: Business, form) -> DailyIncome:
        """Registra un ingreso diario manual para el negocio indicado."""
        payment_method = (
            getattr(form, "payment_method", None) and form.payment_method.data
        ) or ""
        payment_method = (payment_method or "").strip().lower()

        if payment_method not in self.ALLOWED_PAYMENT_METHODS:
            raise ValueError("Método de pago no válido. Usa: cash, transfer o check.")

        if payment_method in self.TRANSFER_LIKE_METHODS:
            resolved_cash_location = DailyIncome.LOCATION_BANK
        elif payment_method == "cash":
            resolved_cash_location = DailyIncome.LOCATION_CASH
        else:
            resolved_cash_location = form.cash_location.data

        debtor_data = self._resolve_debtor_invoice_data(
            form=form,
            payment_method=payment_method,
        )

        income_type = (
            DailyIncome.TYPE_NON_TAXABLE
            if form.mark_non_taxable.data
            else DailyIncome.TYPE_INCOME_OBTAINED
        )
        new_income = DailyIncome(
            business_id=business.id,
            date=form.date.data,
            income_type=income_type,
            activity=form.activity.data,
            amount=float(form.amount.data or 0),
            description=(form.description.data or "").strip() or None,
            payment_method=payment_method,
            cash_location=resolved_cash_location,
            source=DailyIncome.SOURCE_MANUAL,
            **debtor_data,
        )
        db.session.add(new_income)
        if inspect(db.session.get_bind()).has_table("income_event"):
            payment_channel = (
                IncomeEvent.CHANNEL_BANK_TRANSFER
                if resolved_cash_location == DailyIncome.LOCATION_BANK
                else IncomeEvent.CHANNEL_CASH
            )
            collection_status = (
                IncomeEvent.STATUS_PENDING
                if payment_channel == IncomeEvent.CHANNEL_BANK_TRANSFER
                else IncomeEvent.STATUS_IMMEDIATE
            )
            collected_date = (
                None
                if collection_status == IncomeEvent.STATUS_PENDING
                else form.date.data
            )
            income_event = IncomeEvent(
                business_id=business.id,
                event_date=form.date.data,
                amount=float(form.amount.data or 0),
                origin_type=IncomeEvent.ORIGIN_MANUAL,
                payment_channel=payment_channel,
                collection_status=collection_status,
                collected_date=collected_date,
                description=(form.description.data or "").strip() or None,
                source_ref=f"daily_income:manual:{form.date.data}",
            )
            db.session.add(income_event)
            db.session.flush()
            IncomePostingService().post_event(income_event, commit=False)
            CashFlowService().record_income_event_inflow(
                income_event=income_event,
                commit=False,
            )
        db.session.commit()
        return new_income

    @staticmethod
    def get_pending_income_events(business_id: int) -> list[IncomeEvent]:
        """Devuelve ingresos pendientes por acreditar para un negocio."""
        return (
            IncomeEvent.query.filter_by(
                business_id=business_id,
                collection_status=IncomeEvent.STATUS_PENDING,
            )
            .order_by(IncomeEvent.event_date.asc(), IncomeEvent.id.asc())
            .all()
        )

    @staticmethod
    def _parse_collected_date(collected_date_value) -> date:
        if not collected_date_value:
            return datetime.today().date()

        if isinstance(collected_date_value, date):
            return collected_date_value

        return datetime.strptime(str(collected_date_value), "%Y-%m-%d").date()

    def reconcile_income_event(
        self,
        business_id: int,
        income_event_id: int,
        bank_operation_number: str,
        collected_date_value=None,
        reconciled_by: str | None = None,
        bank_name: str | None = None,
    ) -> IncomeEvent:
        """Concilia un ingreso pendiente y aplica posting contable según régimen."""
        operation_number = (bank_operation_number or "").strip()
        if not operation_number:
            raise ValueError("El número de operación bancaria es obligatorio.")

        income_event = IncomeEvent.query.filter_by(
            id=income_event_id,
            business_id=business_id,
        ).first()
        if not income_event:
            raise ValueError("Ingreso pendiente no encontrado.")

        if income_event.collection_status != IncomeEvent.STATUS_PENDING:
            raise ValueError("Solo se pueden conciliar ingresos pendientes.")

        collected_date = self._parse_collected_date(collected_date_value)

        income_event.collection_status = IncomeEvent.STATUS_COLLECTED
        income_event.collected_date = collected_date
        income_event.bank_operation_number = operation_number
        income_event.reconciled_by = (reconciled_by or "").strip() or None
        income_event.reconciled_at = datetime.utcnow()

        receipt = CollectionReceipt.query.filter_by(
            income_event_id=income_event.id
        ).first()
        if not receipt:
            receipt = CollectionReceipt(
                income_event_id=income_event.id,
                bank_operation_number=operation_number,
                collected_date=collected_date,
                bank_name=(bank_name or "").strip() or None,
                reconciled_by=income_event.reconciled_by,
            )
            db.session.add(receipt)
        else:
            receipt.bank_operation_number = operation_number
            receipt.collected_date = collected_date
            receipt.bank_name = (bank_name or "").strip() or None
            receipt.reconciled_by = income_event.reconciled_by

        IncomePostingService().post_event(income_event, commit=False)
        CashFlowService().record_income_event_inflow(
            income_event=income_event,
            commit=False,
        )
        db.session.commit()

        return income_event

    @staticmethod
    def build_income_summaries(daily_sales: dict):
        """Construye resúmenes por ingreso agrupando productos y totales."""
        income_summaries = {}
        for _, data in daily_sales.items():
            for sale in data.get("sales", []):
                summary = {}
                for sale_detail in getattr(sale, "products", []):
                    try:
                        product_name = (
                            sale_detail.product.name
                            if sale_detail.product
                            else f"#{sale_detail.product_id}"
                        )
                    except Exception:
                        product_name = f"#{sale_detail.product_id}"

                    if product_name in summary:
                        summary[product_name]["quantity"] += sale_detail.quantity or 0
                        summary[product_name]["total_price"] += (
                            sale_detail.total_price or 0
                        )
                    else:
                        summary[product_name] = {
                            "quantity": sale_detail.quantity or 0,
                            "total_price": sale_detail.total_price or 0,
                            "unit_price": sale_detail.unit_price or 0,
                        }

                income_summaries[sale.id] = [
                    {
                        "name": key,
                        "quantity": value["quantity"],
                        "total_price": value["total_price"],
                        "unit_price": value["unit_price"],
                    }
                    for key, value in summary.items()
                ]
        return income_summaries

    def build_sale_summaries(self, daily_sales: dict):
        """Alias temporal para compatibilidad retroactiva."""
        return self.build_income_summaries(daily_sales)

    def build_income_list_context(
        self,
        business: Business,
        filters: dict,
        month_param: str | None,
    ):
        """Arma el contexto completo de la vista de listado de ingresos."""
        is_daily_mode = business.income_entry_mode == Business.INCOME_MODE_DAILY
        all_sales_unfiltered = []
        all_daily_income_unfiltered = []
        months = []

        selected_month, date_range = self.parse_month_range(month_param)
        all_sales = []
        all_daily_income = []

        if is_daily_mode:
            (
                all_daily_income_unfiltered,
                all_daily_income,
                months,
            ) = self._load_daily_income_context(
                business_id=business.id,
                date_range=date_range,
            )
        else:
            all_sales_unfiltered, all_sales, months = self._load_sales_context(
                filters=filters,
                date_range=date_range,
            )

        months_display = self.build_months_display(months)

        sales_by_months = group_sales_by_month(all_sales) if not is_daily_mode else {}
        month_totals = (
            calculate_month_totals(sales_by_months) if not is_daily_mode else {}
        )

        daily_income_by_month = defaultdict(float)
        if is_daily_mode:
            for income in all_daily_income_unfiltered:
                if income.date:
                    daily_income_by_month[income.date.strftime("%Y-%m")] += float(
                        income.amount or 0
                    )

        daily_sales = (
            self._aggregate_daily_sales(sales_by_months) if not is_daily_mode else {}
        )

        daily_sales_sorted = sorted(
            daily_sales.items(), key=lambda item: item[0], reverse=True
        )
        income_summaries = (
            self.build_income_summaries(daily_sales) if not is_daily_mode else {}
        )

        prev_month, next_month, display_month_name = self._resolve_month_navigation(
            selected_month=selected_month,
            months=months,
        )

        current_total = (
            sum(float(item.amount or 0) for item in all_daily_income)
            if is_daily_mode
            else (
                month_totals.get(selected_month, 0)
                if selected_month
                else sum(month_totals.values())
            )
        )

        return {
            "is_daily_mode": is_daily_mode,
            "sales_by_months": sales_by_months,
            "month_totals": month_totals,
            "daily_income_by_month": daily_income_by_month,
            "all_daily_income": all_daily_income,
            "months": months,
            "months_display": months_display,
            "all_sales": all_sales,
            "current_total": current_total,
            "selected_month": selected_month,
            "daily_sales_sorted": daily_sales_sorted,
            "prev_month": prev_month,
            "next_month": next_month,
            "display_month_name": display_month_name,
            "income_summaries": income_summaries,
            "sale_summaries": income_summaries,
        }

    def build_sales_list_context(
        self,
        business: Business,
        filters: dict,
        month_param: str | None,
    ):
        """Alias temporal para compatibilidad retroactiva."""
        return self.build_income_list_context(business, filters, month_param)

    def build_income_details_context(self, income: Sale, filters: dict):
        """Prepara formularios y detalles requeridos por la vista de un ingreso."""
        add_product_form = IncomeDetailForm(prefix="add_product")
        update_product_form = UpdateIncomeDetailForm(prefix="update_product")
        remove_product_form = RemoveIncomeDetailForm(prefix="remove_product")
        update_sale_form = IncomeForm(
            parent_business_id=filters["business_id"],
            obj=income,
            prefix="update_sale",
        )
        add_sale_form = IncomeForm(
            parent_business_id=filters["business_id"],
            prefix="add_sale",
        )

        add_product_form.set_product_choices(
            self.get_available_products(filters["business_id"])
        )

        sale_details = self.get_income_details(income.id)

        return {
            "add_product_form": add_product_form,
            "update_product_form": update_product_form,
            "remove_product_form": remove_product_form,
            "update_sale_form": update_sale_form,
            "add_sale_form": add_sale_form,
            "sale_details": sale_details,
            "income_details": sale_details,
        }

    def build_sale_details_context(self, sale: Sale, filters: dict):
        """Alias temporal para compatibilidad retroactiva."""
        return self.build_income_details_context(sale, filters)

    @staticmethod
    def _clean_text(value):
        return (value or "").strip() or None

    def _resolve_debtor_invoice_data(
        self, form: IncomeForm, payment_method: str
    ) -> dict:
        debtor_fields = {
            "debtor_type": None,
            "debtor_natural_full_name": None,
            "debtor_natural_identity_number": None,
            "debtor_natural_bank_account": None,
            "debtor_legal_entity_name": None,
            "debtor_legal_reeup_code": None,
            "debtor_legal_address": None,
            "debtor_legal_credit_branch": None,
            "debtor_legal_bank_account": None,
            "debtor_legal_contract_number": None,
        }

        if payment_method not in self.TRANSFER_LIKE_METHODS:
            return debtor_fields

        debtor_type = self._clean_text(
            getattr(form, "debtor_type", None) and form.debtor_type.data
        )
        if debtor_type:
            debtor_type = debtor_type.lower()

        if debtor_type not in self.DEBTOR_TYPES:
            raise ValueError(
                "Debe seleccionar tipo de deudor (natural/legal) para pagos por transferencia o check."
            )

        debtor_fields["debtor_type"] = debtor_type

        if debtor_type == "natural":
            debtor_fields["debtor_natural_full_name"] = self._clean_text(
                getattr(form, "debtor_natural_full_name", None)
                and form.debtor_natural_full_name.data
            )
            debtor_fields["debtor_natural_identity_number"] = self._clean_text(
                getattr(form, "debtor_natural_identity_number", None)
                and form.debtor_natural_identity_number.data
            )
            debtor_fields["debtor_natural_bank_account"] = self._clean_text(
                getattr(form, "debtor_natural_bank_account", None)
                and form.debtor_natural_bank_account.data
            )

            missing_fields = [
                field_name
                for field_name in [
                    "debtor_natural_full_name",
                    "debtor_natural_identity_number",
                    "debtor_natural_bank_account",
                ]
                if not debtor_fields[field_name]
            ]
            if missing_fields:
                raise ValueError(
                    "Para persona natural debe completar: nombre y apellidos, carnet/NIT y cuenta bancaria."
                )

        if debtor_type == "legal":
            debtor_fields["debtor_legal_entity_name"] = self._clean_text(
                getattr(form, "debtor_legal_entity_name", None)
                and form.debtor_legal_entity_name.data
            )
            debtor_fields["debtor_legal_reeup_code"] = self._clean_text(
                getattr(form, "debtor_legal_reeup_code", None)
                and form.debtor_legal_reeup_code.data
            )
            debtor_fields["debtor_legal_address"] = self._clean_text(
                getattr(form, "debtor_legal_address", None)
                and form.debtor_legal_address.data
            )
            debtor_fields["debtor_legal_credit_branch"] = self._clean_text(
                getattr(form, "debtor_legal_credit_branch", None)
                and form.debtor_legal_credit_branch.data
            )
            debtor_fields["debtor_legal_bank_account"] = self._clean_text(
                getattr(form, "debtor_legal_bank_account", None)
                and form.debtor_legal_bank_account.data
            )
            debtor_fields["debtor_legal_contract_number"] = self._clean_text(
                getattr(form, "debtor_legal_contract_number", None)
                and form.debtor_legal_contract_number.data
            )

            missing_fields = [
                field_name
                for field_name in [
                    "debtor_legal_entity_name",
                    "debtor_legal_reeup_code",
                    "debtor_legal_address",
                    "debtor_legal_credit_branch",
                    "debtor_legal_bank_account",
                    "debtor_legal_contract_number",
                ]
                if not debtor_fields[field_name]
            ]
            if missing_fields:
                raise ValueError(
                    "Para persona jurídica debe completar: entidad, REEUP, dirección, sucursal de crédito, cuenta y contrato."
                )

        return debtor_fields

    def add_income(self, business: Business, form: IncomeForm) -> Sale:
        """
        Crea una nueva venta asociada a un negocio.


        Args:
            business (Business): Id del negocio al que pertenece la venta.
            form (IncomeForm): Campos y valores para crear el ingreso.

        Returns:
            Sale: El objeto Venta recién generado.
        """
        business_filter = self.business_service.get_parent_filters(business)

        if business.is_general:
            specific_business_id = form.specific_business_id.data
        else:
            specific_business_id = business_filter["specific_business_id"]

        # Convertir el formulario en un diccionario
        payment_method = (form.payment_method.data or "").strip().lower()
        if payment_method not in self.ALLOWED_PAYMENT_METHODS:
            raise ValueError("Método de pago no válido. Usa: cash, transfer o check.")
        debtor_data = self._resolve_debtor_invoice_data(
            form=form,
            payment_method=payment_method,
        )

        data = {
            "sale_number": form.sale_number.data,
            "date": form.date.data,
            "payment_method": payment_method,
            "status": form.status.data,
            "excluded": form.excluded.data,
            "discount": form.discount.data or 0,
            "tax": form.tax.data or 0,
            "subtotal_amount": 0,
            "total_amount": 0,
            "specific_business_id": specific_business_id,
            **debtor_data,
        }
        income = self.repository.add_sale(business_filter["business_id"], **data)
        self._sync_inventory_for_sale(income)
        return income

    def add_sale(self, business: Business, form: IncomeForm) -> Sale:
        """Alias temporal para compatibilidad retroactiva."""
        return self.add_income(business, form)

    def update_income(self, income: Sale, form: IncomeForm):
        """
        Actualiza una venta existente con los datos proporcionados en el formulario.

        Args:
            sale (Sale): Instancia de Sale a actualizar
            form (IncomeForm): Formulario con los nuevos datos validados

        Returns:
            Sale: Instancia actualizada de Sale
        """
        # Convertir el formulario en un diccionario
        payment_method = (form.payment_method.data or "").strip().lower()
        if payment_method not in self.ALLOWED_PAYMENT_METHODS:
            raise ValueError("Método de pago no válido. Usa: cash, transfer o check.")
        debtor_data = self._resolve_debtor_invoice_data(
            form=form,
            payment_method=payment_method,
        )

        data = {
            "sale_number": form.sale_number.data,
            "date": form.date.data,
            "payment_method": payment_method,
            "status": form.status.data,
            "excluded": form.excluded.data,
            "discount": form.discount.data or 0,
            "tax": form.tax.data or 0,
            "specific_business_id": form.specific_business_id.data,
            **debtor_data,
        }

        updated_income = self.repository.update_sale(income, **data)
        self._sync_inventory_for_sale(updated_income)
        return updated_income

    def update_sale(self, sale: Sale, form: IncomeForm):
        """Alias temporal para compatibilidad retroactiva."""
        return self.update_income(sale, form)

    def add_product_to_income(
        self, income: Sale, product_id: int, quantity: int, discount: float
    ) -> SaleDetail:
        """
        Agrega un producto a una venta existente

        Args:
            sale (Sale): Instancia de Sale a actualizar
            product_id (int): Id del producto
            quantity (int): Cantidad del producto
            discount (float): Descuento aplicado al producto en la venta
        Returns:
            SaleDetail: El objeto SaleDetail actualizado.
        """
        product = Product.query.get_or_404(product_id)

        sale_detail = self.repository.add_sale_detail(
            sale_id=income.id,
            product_id=product_id,
            quantity=quantity,
            unit_price=product.price,
            discount=discount or 0.0,
            total_price=self._calculate_income_detail_total(
                product.price, quantity, discount
            ),
        )
        self._sync_inventory_for_sale_detail(income, sale_detail)
        return sale_detail

    def add_product_to_sale(
        self, sale: Sale, product_id: int, quantity: int, discount: float
    ) -> SaleDetail:
        """Alias temporal para compatibilidad retroactiva."""
        return self.add_product_to_income(sale, product_id, quantity, discount)

    def update_income_detail(
        self,
        income: Sale,
        sale_detail: SaleDetail,
        quantity: int,
        discount: float,
    ) -> SaleDetail:
        """
        Actualiza un producto en una venta

        Args:
            sale (Sale): Instancia de Sale a actualizar
            sale_detail (SaleDetail): El objeto SaleDetail a actualizar
            quantity (int): Cantidad del producto
            discount (float): Descuento aplicado al producto en la venta

        Returns:
            SaleDetail: El objeto SaleDetail actualizado.
        """
        if sale_detail.unit_price and sale_detail.unit_price > 0:
            unit_price = sale_detail.unit_price
        else:
            unit_price = sale_detail.product.price

        updated_detail = self.repository.update_sale_detail(
            sale_id=income.id,
            sale_detail_id=sale_detail.id,
            quantity=quantity,
            unit_price=unit_price,
            discount=discount or 0.0,
            total_price=self._calculate_income_detail_total(
                unit_price, quantity, discount
            ),
        )
        self._sync_inventory_for_sale_detail(income, updated_detail)
        return updated_detail

    def update_sale_detail(
        self,
        sale: Sale,
        sale_detail: SaleDetail,
        quantity: int,
        discount: float,
    ) -> SaleDetail:
        """Alias temporal para compatibilidad retroactiva."""
        return self.update_income_detail(sale, sale_detail, quantity, discount)

    def remove_product_from_income(
        self, income: Sale, sale_detail: SaleDetail
    ) -> Product:
        """
        Elimina un producto de una venta

        Args:
            sale (Sale): Instancia de Sale a actualizar
            sale_detail (SaleDetail): El objeto SaleDetail a eliminar
        Returns:
            Product: El objeto Product que se eliminó de la venta.
        """
        self._sync_inventory_for_sale_detail(
            sale=income,
            sale_detail=sale_detail,
            force_reset=True,
        )
        removed_product = Product.query.get_or_404(sale_detail.product_id)
        self.repository.remove_sale_detail(income.id, sale_detail.id)
        return removed_product

    def _sale_should_apply_inventory_consumption(self, sale: Sale) -> bool:
        status = (getattr(sale, "status", "") or "").strip().lower()
        is_excluded = bool(getattr(sale, "excluded", False))
        return status == "completed" and not is_excluded

    def _resolve_inventory_account_code_for_sale(self, sale: Sale) -> str:
        adoptions = InventoryService.list_account_adoptions(
            business_id=sale.business_id,
            include_inactive=False,
        )
        for adoption in adoptions:
            code = (
                getattr(getattr(adoption, "account", None), "code", "") or ""
            ).strip()
            if code:
                return code

        raise ValueError(
            "No hay cuentas contables adoptadas para sincronizar consumo de inventario"
        )

    def _build_desired_consumption_by_item_for_sale_detail(
        self,
        sale: Sale,
        sale_detail: SaleDetail,
    ) -> dict[int, float]:
        desired: dict[int, float] = {}
        sold_quantity = float(getattr(sale_detail, "quantity", 0.0) or 0.0)
        if sold_quantity <= 0:
            return desired

        self._validate_sale_detail_recipe_integrity_for_inventory_sync(sale_detail)

        product = getattr(sale_detail, "product", None)

        for recipe_line in getattr(product, "raw_materials", []) or []:
            item_id, quantity_per_sale_unit = (
                self._resolve_recipe_line_consumption_in_item_base_unit(
                    sale=sale,
                    sale_detail=sale_detail,
                    recipe_line=recipe_line,
                )
            )

            desired[item_id] = round(
                float(desired.get(item_id, 0.0))
                + (sold_quantity * float(quantity_per_sale_unit)),
                4,
            )

        return desired

    def _resolve_recipe_line_consumption_in_item_base_unit(
        self,
        sale: Sale,
        sale_detail: SaleDetail,
        recipe_line,
    ) -> tuple[int, float]:
        raw_material = getattr(recipe_line, "raw_material", None)
        raw_material_id = getattr(recipe_line, "raw_material_id", None)
        if raw_material_id is None and raw_material is not None:
            raw_material_id = getattr(raw_material, "id", None)
        if raw_material_id is None:
            raise ValueError("Linea de receta sin materia prima asociada")

        if raw_material is None:
            raw_material = InventoryItem.query.get(raw_material_id)
        if raw_material is None:
            raise ValueError(
                f"Materia prima inexistente en receta (inventory_item_id={raw_material_id})"
            )

        product = getattr(sale_detail, "product", None)
        product_name = (
            getattr(product, "name", None) or f"#{getattr(product, 'id', 'N/A')}"
        ).strip()
        detail_id = getattr(sale_detail, "id", None)

        quantity_per_unit = float(getattr(recipe_line, "quantity", 0.0) or 0.0)
        if quantity_per_unit <= 0:
            raise ValueError(
                f"Receta incompleta para producto '{product_name}': la cantidad por unidad de una materia prima debe ser mayor que cero"
            )

        batch_size = float(getattr(product, "batch_size", 0.0) or 0.0)
        is_batch_prepared = bool(getattr(product, "is_batch_prepared", False))
        effective_quantity_per_sale_unit = quantity_per_unit
        if is_batch_prepared and batch_size > 0:
            effective_quantity_per_sale_unit = quantity_per_unit / batch_size

        recipe_unit = (
            getattr(recipe_line, "unit_base_insumo", None)
            or getattr(recipe_line, "unit", None)
            or getattr(raw_material, "unit", None)
            or ""
        )
        recipe_unit = str(recipe_unit).strip().lower()
        if not recipe_unit:
            raise ValueError(
                f"Receta incompleta para producto '{product_name}': la unidad de consumo de materia prima es obligatoria"
            )

        try:
            resolved_quantity, _, _, _ = (
                InventoryService._resolve_quantity_in_item_base_unit(
                    business_id=sale.business_id,
                    inventory_item=raw_material,
                    quantity=effective_quantity_per_sale_unit,
                    unit=recipe_unit,
                )
            )
        except ValueError as exc:
            raise ValueError(
                f"No se pudo resolver conversion de unidad en receta para '{product_name}' "
                f"(detalle #{detail_id}, materia_prima_id={raw_material_id}): {exc}"
            ) from exc

        return int(raw_material_id), float(resolved_quantity)

    def _validate_sale_detail_recipe_integrity_for_inventory_sync(
        self,
        sale_detail: SaleDetail,
    ) -> None:
        detail_id = getattr(sale_detail, "id", None)
        product = getattr(sale_detail, "product", None)
        if not product:
            raise ValueError(
                f"Receta incompleta en detalle #{detail_id}: no hay producto asociado"
            )

        product_name = (
            getattr(product, "name", None) or f"#{getattr(product, 'id', 'N/A')}"
        ).strip()
        raw_materials = list(getattr(product, "raw_materials", []) or [])
        if not raw_materials:
            raise ValueError(
                f"Receta incompleta para producto '{product_name}': no tiene materias primas configuradas"
            )

        for recipe_line in raw_materials:
            quantity_per_unit = float(getattr(recipe_line, "quantity", 0.0) or 0.0)
            if quantity_per_unit <= 0:
                raise ValueError(
                    f"Receta incompleta para producto '{product_name}': la cantidad por unidad de una materia prima debe ser mayor que cero"
                )

            raw_material = getattr(recipe_line, "raw_material", None)
            raw_material_id = getattr(recipe_line, "raw_material_id", None)
            if raw_material_id is None and raw_material is not None:
                raw_material_id = getattr(raw_material, "id", None)

            if raw_material_id is None:
                raise ValueError(
                    f"Receta incompleta para producto '{product_name}': existe una linea sin materia prima asociada"
                )

            if raw_material is None:
                existing_item = InventoryItem.query.get(raw_material_id)
                if existing_item is None:
                    raise ValueError(
                        f"Materia prima inexistente en receta de '{product_name}' (inventory_item_id={raw_material_id})"
                    )

    def _validate_sale_recipe_integrity_for_inventory_sync(self, sale: Sale) -> None:
        errors: list[str] = []
        for sale_detail in getattr(sale, "products", []) or []:
            try:
                self._validate_sale_detail_recipe_integrity_for_inventory_sync(
                    sale_detail
                )
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            raise ValueError("; ".join(errors))

    def _calculate_synced_consumption_by_item_for_sale_detail(
        self,
        sale: Sale,
        sale_detail: SaleDetail,
    ) -> dict[int, float]:
        rows = (
            InventoryMovement.query.filter(
                InventoryMovement.business_id == sale.business_id,
                InventoryMovement.reference_type
                == self.INVENTORY_SALE_LINE_REFERENCE_TYPE,
                InventoryMovement.reference_id == sale_detail.id,
            )
            .order_by(InventoryMovement.id.asc())
            .all()
        )

        synced: dict[int, float] = {}
        for row in rows:
            item_id = int(getattr(row, "inventory_item_id", 0) or 0)
            if item_id <= 0:
                continue
            delta = InventoryService._movement_stock_delta(
                movement_type=(getattr(row, "movement_type", "") or "").strip().lower(),
                quantity=float(getattr(row, "quantity", 0.0) or 0.0),
                adjustment_kind=(getattr(row, "adjustment_kind", "") or "")
                .strip()
                .lower()
                or None,
            )
            synced[item_id] = round(
                float(synced.get(item_id, 0.0)) + (-float(delta)), 4
            )

        return synced

    def _sync_inventory_for_sale(self, sale: Sale) -> None:
        if self._sale_should_apply_inventory_consumption(sale):
            self._validate_sale_recipe_integrity_for_inventory_sync(sale)

        for sale_detail in getattr(sale, "products", []) or []:
            self._sync_inventory_for_sale_detail(sale=sale, sale_detail=sale_detail)

    def _sync_inventory_for_sale_detail(
        self,
        sale: Sale,
        sale_detail: SaleDetail,
        force_reset: bool = False,
    ) -> None:
        desired_consumption_by_item: dict[int, float] = {}
        if not force_reset and self._sale_should_apply_inventory_consumption(sale):
            desired_consumption_by_item = (
                self._build_desired_consumption_by_item_for_sale_detail(
                    sale=sale,
                    sale_detail=sale_detail,
                )
            )

        synced_consumption_by_item = (
            self._calculate_synced_consumption_by_item_for_sale_detail(
                sale=sale,
                sale_detail=sale_detail,
            )
        )

        item_ids = sorted(
            set(desired_consumption_by_item.keys())
            | set(synced_consumption_by_item.keys())
        )
        if not item_ids:
            return

        item_rows = InventoryItem.query.filter(InventoryItem.id.in_(item_ids)).all()
        items_by_id = {int(item.id): item for item in item_rows}

        operations = []
        for item_id in item_ids:
            desired = float(desired_consumption_by_item.get(item_id, 0.0) or 0.0)
            synced = float(synced_consumption_by_item.get(item_id, 0.0) or 0.0)
            delta = round(desired - synced, 4)
            if abs(delta) <= self.INVENTORY_SYNC_QUANTITY_EPSILON:
                continue

            item = items_by_id.get(item_id)
            if item is None:
                raise ValueError(
                    f"Materia prima inexistente para sincronizacion de inventario (id={item_id})"
                )

            operations.append(
                {
                    "item": item,
                    "item_id": item_id,
                    "delta": delta,
                    "desired": desired,
                }
            )

        if not operations:
            return

        account_code = self._resolve_inventory_account_code_for_sale(sale)

        for operation in operations:
            item = operation["item"]
            item_id = operation["item_id"]
            delta = operation["delta"]
            desired = operation["desired"]
            base_idempotency_key = (
                f"sale-line-sync:{sale.id}:{sale_detail.id}:{item_id}:{desired:.4f}"
            )

            if delta > 0:
                InventoryService.create_movement(
                    business_id=sale.business_id,
                    inventory_item_id=item_id,
                    movement_type="consumption",
                    quantity=round(delta, 4),
                    unit=(getattr(item, "unit", "") or "").strip().lower(),
                    account_code=account_code,
                    idempotency_key=f"{base_idempotency_key}:consume",
                    reference_type=self.INVENTORY_SALE_LINE_REFERENCE_TYPE,
                    reference_id=sale_detail.id,
                    notes=f"Consumo automatico por venta #{sale.id} detalle #{sale_detail.id}",
                )
            else:
                InventoryService.create_movement(
                    business_id=sale.business_id,
                    inventory_item_id=item_id,
                    movement_type="adjustment",
                    adjustment_kind="positive",
                    quantity=round(abs(delta), 4),
                    unit=(getattr(item, "unit", "") or "").strip().lower(),
                    account_code=account_code,
                    idempotency_key=f"{base_idempotency_key}:restore",
                    reference_type=self.INVENTORY_SALE_LINE_REFERENCE_TYPE,
                    reference_id=sale_detail.id,
                    notes=f"Reversa automatica por venta #{sale.id} detalle #{sale_detail.id}",
                )

    def remove_product_from_sale(self, sale: Sale, sale_detail: SaleDetail) -> Product:
        """Alias temporal para compatibilidad retroactiva."""
        return self.remove_product_from_income(sale, sale_detail)

    # Helper methods
    def _calculate_income_detail_total(
        self, unit_price: float, quantity: int, discount: float
    ) -> float:
        """
        Calcula el total por producto considerando descuentos

        Args:
            unit_price (float): Precio unitario del producto
            quantity (int): Cantidad del producto
            discount (float): Descuento aplicado al producto

        Returns:
            float: Total por producto
        """
        return round(unit_price * quantity * (1 - (discount or 0.0)), 2)

    def _calculate_sale_detail_total(
        self, unit_price: float, quantity: int, discount: float
    ) -> float:
        """Alias temporal para compatibilidad retroactiva."""
        return self._calculate_income_detail_total(unit_price, quantity, discount)

    @staticmethod
    def generate_monthly_income_totals(
        business_id: int,
        specific_business_id: Optional[int] = None,  # Parámetro opcional
    ) -> Dict[str, float]:
        """
        Genera totales mensuales de ventas para un negocio.

        Args:
            business_id (int): Id del negocio
            specific_business_id (int): Id del negocio específico

        Returns:
            Dict[str, float]: Ventas mensuales para el negocio.
        """
        try:
            # Construir la consulta base
            query = db.session.query(
                func.strftime("%Y-%m", Sale.date).label("month"),
                func.sum(Sale.total_amount).label("total"),
            ).filter(Sale.business_id == business_id)

            # Aplicar filtro de sub negocio si existe
            if specific_business_id is not None:
                query = query.filter(Sale.specific_business_id == specific_business_id)

            # Agrupar y ordenar
            return (
                query.group_by(func.strftime("%Y-%m", Sale.date))
                .order_by(desc(func.strftime("%Y-%m", Sale.date)))
                .all()
            )

        except Exception as e:
            raise RuntimeError(f"Error generando totales mensuales: {str(e)}")

    @staticmethod
    def generate_monthly_totals_sales(
        business_id: int,
        specific_business_id: Optional[int] = None,
    ) -> Dict[str, float]:
        """Alias temporal para compatibilidad retroactiva."""
        return IncomeManagementService.generate_monthly_income_totals(
            business_id=business_id,
            specific_business_id=specific_business_id,
        )
