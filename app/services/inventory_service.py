import re
import unicodedata
from datetime import UTC, date, datetime
from datetime import timedelta
from sqlalchemy import or_

from app import db
from app.models import (
    ACAccount,
    Business,
    BusinessAccountAdoption,
    BusinessAccountAdoptionAudit,
    BusinessSubAccount,
    BusinessSubAccountAudit,
    Inventory,
    InventoryItem,
    InventoryUnitConversion,
    InventoryProductGeneric,
    InventoryProductSpecific,
    InventorySalesFloorStock,
    InventoryMovement,
    InventoryLedgerEntry,
    InventoryWipBalance,
    InventorySaleCostBreakdown,
    InventoryCycleCount,
    Product,
    Sale,
    SaleDetail,
    Supply,
)
from app.utils.slug_utils import get_business_by_slugs


class InventoryService:
    ALLOWED_ITEM_UNITS = {
        "g",
        "kg",
        "ml",
        "l",
        "unit",
    }
    ALLOWED_ITEM_USAGE_TYPES = {
        InventoryItem.USAGE_TYPE_SALE_DIRECT,
        InventoryItem.USAGE_TYPE_PRODUCTION_INPUT,
        InventoryItem.USAGE_TYPE_MIXED,
    }
    ALLOWED_MOVEMENT_TYPES = {
        "purchase",
        "consumption",
        "transfer",
        "adjustment",
        "waste",
        "wip_close",
    }
    ALLOWED_DESTINATIONS = {"sales_floor", "wip", "finished_goods"}
    ALLOWED_STOWAGE_LOCATIONS = {"warehouse", "sales_floor", "wip", "finished_goods"}
    ALLOWED_VALUATION_METHODS = {"fifo", "fefo", "manual"}
    ALLOWED_WIP_STATUSES = {
        InventoryWipBalance.STATUS_OPEN,
        InventoryWipBalance.STATUS_FINISHED,
        InventoryWipBalance.STATUS_WASTE,
    }
    ALLOWED_ADJUSTMENT_KINDS = {"positive", "negative"}
    ALLOWED_WASTE_REASONS = {"rotura", "deterioro", "caducidad", "otros"}
    ALLOWED_MIN_STOCK_POLICIES = {"alert", "block"}
    ALLOWED_WASTE_EVIDENCE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".pdf",
    }
    ALLOWED_CYCLE_COUNT_LOCATIONS = {"warehouse"}
    WASTE_EXPENSE_ACCOUNT_CODE = "800"
    AUTO_IDEMPOTENT_REFERENCE_TYPES = {
        "sale",
        "sale_line",
        "sale_product",
        "sale_consumption",
        "venta",
    }
    SALE_CONSUMPTION_REFERENCE_TYPES = {
        "sale_inventory_line",
        "sale",
        "sale_line",
        "sale_product",
        "sale_consumption",
        "venta",
    }
    INVENTORY_SYNC_QUANTITY_EPSILON = 1e-6
    UNIT_PRECISION_RULES = {
        "g": 2,
        "ml": 2,
    }

    @staticmethod
    def _parse_bool(value, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "si", "s"}

    @staticmethod
    def _get_or_create_sales_floor_stock(
        business_id: int,
        inventory_item_id: int,
    ) -> InventorySalesFloorStock:
        stock = InventorySalesFloorStock.query.filter_by(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
        ).first()
        if stock:
            return stock

        stock = InventorySalesFloorStock(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            current_quantity=0.0,
            min_quantity=0.0,
            max_quantity=0.0,
        )
        db.session.add(stock)
        db.session.commit()
        return stock

    @staticmethod
    def list_sales_floor_stocks(business_id: int) -> list[InventorySalesFloorStock]:
        return (
            InventorySalesFloorStock.query.filter(
                InventorySalesFloorStock.business_id == business_id
            )
            .order_by(InventorySalesFloorStock.inventory_item_id.asc())
            .all()
        )

    @staticmethod
    def configure_sales_floor_stock(
        business_id: int,
        inventory_item_id: int,
        min_quantity: float,
        max_quantity: float,
    ) -> InventorySalesFloorStock:
        if min_quantity is None or max_quantity is None:
            raise ValueError("Los umbrales min/max son obligatorios")

        min_value = float(min_quantity)
        max_value = float(max_quantity)
        if min_value < 0 or max_value < 0:
            raise ValueError("Los umbrales min/max no pueden ser negativos")
        if max_value < min_value:
            raise ValueError("El maximo debe ser mayor o igual que el minimo")

        InventoryService._get_item_or_404(inventory_item_id)
        stock = InventoryService._get_or_create_sales_floor_stock(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
        )
        stock.min_quantity = min_value
        stock.max_quantity = max_value
        db.session.commit()
        return stock

    @staticmethod
    def _resolve_business_inventory_flows(business_id: int) -> tuple[bool, bool]:
        business = Business.query.get_or_404(business_id)
        return (
            bool(getattr(business, "inventory_flow_sales_floor_enabled", True)),
            bool(getattr(business, "inventory_flow_wip_enabled", False)),
        )

    @staticmethod
    def _validate_item_usage_for_destination(
        inventory_item: InventoryItem,
        destination: str,
    ) -> None:
        usage_type = (getattr(inventory_item, "usage_type", "") or "").strip().lower()
        if not usage_type:
            return

        if (
            destination == "sales_floor"
            and usage_type == InventoryItem.USAGE_TYPE_PRODUCTION_INPUT
        ):
            raise ValueError(
                "El item es solo de produccion y no es compatible con exposicion/venta directa"
            )

        if destination == "wip" and usage_type == InventoryItem.USAGE_TYPE_SALE_DIRECT:
            raise ValueError(
                "El item es solo de venta directa y no es compatible con flujo WIP"
            )

    @staticmethod
    def transfer_to_sales_floor(
        business_id: int,
        inventory_item_id: int,
        quantity: float,
        unit: str,
        account_code: str,
        lot_code: str | None = None,
        notes: str | None = None,
    ):
        sales_floor_enabled, _ = InventoryService._resolve_business_inventory_flows(
            business_id
        )
        if not sales_floor_enabled:
            raise ValueError("El negocio no tiene habilitado el flujo de exposicion")

        inventory_item = InventoryService._get_item_or_404(inventory_item_id)
        InventoryService._validate_item_usage_for_destination(
            inventory_item=inventory_item,
            destination="sales_floor",
        )

        movement = InventoryService.create_movement(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            movement_type="transfer",
            destination="sales_floor",
            quantity=quantity,
            unit=unit,
            account_code=account_code,
            lot_code=lot_code,
            notes=notes,
        )

        stock = InventoryService._get_or_create_sales_floor_stock(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
        )
        stock.current_quantity = float(stock.current_quantity or 0.0) + float(quantity)
        db.session.commit()
        return movement, stock

    @staticmethod
    def _calculate_sales_floor_average_7_days(
        business_id: int,
        inventory_item_id: int,
    ) -> float:
        cutoff = datetime.now(UTC) - timedelta(days=7)
        rows = InventoryMovement.query.filter(
            InventoryMovement.business_id == business_id,
            InventoryMovement.inventory_item_id == inventory_item_id,
            InventoryMovement.destination == "sales_floor",
            InventoryMovement.movement_date >= cutoff,
        ).all()
        if not rows:
            return 0.0

        total = sum(float(row.quantity or 0.0) for row in rows)
        return total / 7.0

    @staticmethod
    def list_sales_floor_alerts(business_id: int):
        stocks = InventoryService.list_sales_floor_stocks(business_id=business_id)
        alerts = []
        for stock in stocks:
            current = float(stock.current_quantity or 0.0)
            min_q = float(stock.min_quantity or 0.0)
            max_q = float(stock.max_quantity or 0.0)
            avg_7_days = InventoryService._calculate_sales_floor_average_7_days(
                business_id=business_id,
                inventory_item_id=stock.inventory_item_id,
            )
            suggestion_to_max = max(0.0, max_q - current)
            suggestion_by_avg_7_days = max(0.0, (avg_7_days * 7.0) - current)

            alerts.append(
                {
                    "inventory_item_id": stock.inventory_item_id,
                    "inventory_item_name": (
                        stock.inventory_item.name if stock.inventory_item else None
                    ),
                    "current_quantity": current,
                    "min_quantity": min_q,
                    "max_quantity": max_q,
                    "low_stock": current <= min_q,
                    "stockout": current <= 0,
                    "over_stock": current > max_q if max_q > 0 else False,
                    "suggestion_to_max": round(suggestion_to_max, 2),
                    "suggestion_by_avg_7_days": round(suggestion_by_avg_7_days, 2),
                    "avg_7_days": round(avg_7_days, 4),
                }
            )

        return alerts

    @staticmethod
    def list_stock_position(
        business_id: int,
        inventory_item_id: int | None = None,
    ) -> list[dict]:
        normalized_item_id = None
        if inventory_item_id is not None:
            normalized_item_id = int(inventory_item_id)
            if normalized_item_id <= 0:
                raise ValueError("inventory_item_id debe ser un entero positivo")

        movements_query = InventoryMovement.query.filter(
            InventoryMovement.business_id == business_id
        )
        sales_floor_query = InventorySalesFloorStock.query.filter(
            InventorySalesFloorStock.business_id == business_id
        )
        wip_query = InventoryWipBalance.query.filter(
            InventoryWipBalance.business_id == business_id,
            InventoryWipBalance.status == InventoryWipBalance.STATUS_OPEN,
        )

        if normalized_item_id is not None:
            movements_query = movements_query.filter(
                InventoryMovement.inventory_item_id == normalized_item_id
            )
            sales_floor_query = sales_floor_query.filter(
                InventorySalesFloorStock.inventory_item_id == normalized_item_id
            )
            wip_query = wip_query.filter(
                InventoryWipBalance.inventory_item_id == normalized_item_id
            )

        movement_rows = movements_query.all()
        sales_floor_rows = sales_floor_query.all()
        wip_rows = wip_query.all()

        item_ids = {
            int(row.inventory_item_id)
            for row in movement_rows
            if getattr(row, "inventory_item_id", None) is not None
        }
        item_ids.update(
            int(row.inventory_item_id)
            for row in sales_floor_rows
            if getattr(row, "inventory_item_id", None) is not None
        )
        item_ids.update(
            int(row.inventory_item_id)
            for row in wip_rows
            if getattr(row, "inventory_item_id", None) is not None
        )

        if normalized_item_id is not None:
            item_ids.add(normalized_item_id)

        if not item_ids:
            return []

        items = (
            InventoryItem.query.filter(InventoryItem.id.in_(item_ids))
            .order_by(InventoryItem.name.asc())
            .all()
        )

        sales_floor_by_item: dict[int, float] = {}
        for row in sales_floor_rows:
            row_item_id = int(getattr(row, "inventory_item_id", 0) or 0)
            if row_item_id <= 0:
                continue
            sales_floor_by_item[row_item_id] = sales_floor_by_item.get(
                row_item_id, 0.0
            ) + float(getattr(row, "current_quantity", 0.0) or 0.0)

        wip_by_item: dict[int, float] = {}
        for row in wip_rows:
            row_item_id = int(getattr(row, "inventory_item_id", 0) or 0)
            if row_item_id <= 0:
                continue
            wip_by_item[row_item_id] = wip_by_item.get(row_item_id, 0.0) + float(
                getattr(row, "remaining_quantity", 0.0) or 0.0
            )

        result = []
        for item in items:
            available_stock = float(getattr(item, "stock", 0.0) or 0.0)
            committed_sales_floor = float(sales_floor_by_item.get(item.id, 0.0))
            committed_wip = float(wip_by_item.get(item.id, 0.0))
            committed_stock = committed_sales_floor + committed_wip
            virtual_stock = available_stock + committed_stock

            result.append(
                {
                    "inventory_item_id": item.id,
                    "inventory_item_name": getattr(item, "name", None),
                    "unit": getattr(item, "unit", None),
                    "stock_available": round(available_stock, 4),
                    "stock_committed": round(committed_stock, 4),
                    "stock_virtual": round(virtual_stock, 4),
                    "stock_committed_sales_floor": round(committed_sales_floor, 4),
                    "stock_committed_wip": round(committed_wip, 4),
                }
            )

        return result

    @staticmethod
    def _resolve_report_period(
        start_date=None, end_date=None
    ) -> tuple[datetime, datetime, int]:
        now = datetime.now(UTC)
        resolved_end = end_date or now
        resolved_start = start_date or (resolved_end - timedelta(days=29))
        if resolved_start > resolved_end:
            raise ValueError("start_date no puede ser mayor que end_date")

        total_days = max(1, (resolved_end.date() - resolved_start.date()).days + 1)
        return resolved_start, resolved_end, total_days

    @staticmethod
    def list_inventory_turnover_coverage(
        business_id: int,
        inventory_item_id: int | None = None,
        start_date=None,
        end_date=None,
    ) -> list[dict]:
        resolved_start, resolved_end, period_days = (
            InventoryService._resolve_report_period(
                start_date=start_date,
                end_date=end_date,
            )
        )

        movements = InventoryService.list_movements(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            start_date=resolved_start,
            end_date=resolved_end,
        )

        movement_stats_by_item: dict[int, dict] = {}
        for movement in movements:
            item_id = int(getattr(movement, "inventory_item_id", 0) or 0)
            if item_id <= 0:
                continue

            movement_type = (
                (getattr(movement, "movement_type", "") or "").strip().lower()
            )
            adjustment_kind = (
                getattr(movement, "adjustment_kind", "") or ""
            ).strip().lower() or None
            quantity = float(getattr(movement, "quantity", 0.0) or 0.0)
            delta = InventoryService._movement_stock_delta(
                movement_type=movement_type,
                quantity=quantity,
                adjustment_kind=adjustment_kind,
            )

            if item_id not in movement_stats_by_item:
                movement_stats_by_item[item_id] = {
                    "inbound_quantity": 0.0,
                    "outbound_quantity": 0.0,
                    "net_delta": 0.0,
                    "movement_count": 0,
                }

            stats = movement_stats_by_item[item_id]
            stats["movement_count"] += 1
            stats["net_delta"] = round(float(stats["net_delta"]) + float(delta), 4)
            if delta > 0:
                stats["inbound_quantity"] = round(
                    float(stats["inbound_quantity"]) + float(delta),
                    4,
                )
            elif delta < 0:
                stats["outbound_quantity"] = round(
                    float(stats["outbound_quantity"]) + abs(float(delta)),
                    4,
                )

        item_ids = set(movement_stats_by_item.keys())
        if inventory_item_id is not None:
            normalized_item_id = int(inventory_item_id)
            if normalized_item_id <= 0:
                raise ValueError("inventory_item_id debe ser un entero positivo")
            item_ids.add(normalized_item_id)

        if not item_ids:
            return []

        items = (
            InventoryItem.query.filter(InventoryItem.id.in_(item_ids))
            .order_by(InventoryItem.name.asc())
            .all()
        )

        rows = []
        for item in items:
            stats = movement_stats_by_item.get(int(item.id), None) or {
                "inbound_quantity": 0.0,
                "outbound_quantity": 0.0,
                "net_delta": 0.0,
                "movement_count": 0,
            }

            current_stock = round(float(getattr(item, "stock", 0.0) or 0.0), 4)
            net_delta = float(stats["net_delta"])
            opening_stock = round(current_stock - net_delta, 4)
            average_stock = round((opening_stock + current_stock) / 2.0, 4)
            outbound_quantity = round(float(stats["outbound_quantity"]), 4)
            inbound_quantity = round(float(stats["inbound_quantity"]), 4)
            avg_daily_outbound = round(outbound_quantity / float(period_days), 4)

            turnover_ratio = None
            if average_stock > 0:
                turnover_ratio = round(outbound_quantity / average_stock, 4)

            days_of_coverage = None
            if avg_daily_outbound > 0:
                days_of_coverage = round(current_stock / avg_daily_outbound, 2)

            rows.append(
                {
                    "inventory_item_id": int(item.id),
                    "inventory_item_name": getattr(item, "name", None),
                    "unit": getattr(item, "unit", None),
                    "period_start": resolved_start,
                    "period_end": resolved_end,
                    "period_days": period_days,
                    "movement_count": int(stats["movement_count"]),
                    "opening_stock": opening_stock,
                    "closing_stock": current_stock,
                    "inbound_quantity": inbound_quantity,
                    "outbound_quantity": outbound_quantity,
                    "average_stock": average_stock,
                    "avg_daily_outbound": avg_daily_outbound,
                    "turnover_ratio": turnover_ratio,
                    "days_of_coverage": days_of_coverage,
                    "min_stock": (
                        float(getattr(item, "min_stock", 0.0))
                        if getattr(item, "min_stock", None) not in (None, "")
                        else None
                    ),
                }
            )

        return rows

    @staticmethod
    def list_stockout_risk_report(
        business_id: int,
        inventory_item_id: int | None = None,
        start_date=None,
        end_date=None,
    ) -> list[dict]:
        base_rows = InventoryService.list_inventory_turnover_coverage(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            start_date=start_date,
            end_date=end_date,
        )

        items = []
        for row in base_rows:
            closing_stock = float(row.get("closing_stock", 0.0) or 0.0)
            days_of_coverage = row.get("days_of_coverage", None)
            min_stock = row.get("min_stock", None)

            stockout = closing_stock <= 0
            min_stock_breach = min_stock is not None and float(closing_stock) <= float(
                min_stock
            )

            if stockout:
                risk_level = "critical"
            elif days_of_coverage is None:
                risk_level = "no_data"
            elif float(days_of_coverage) <= 3:
                risk_level = "high"
            elif float(days_of_coverage) <= 7:
                risk_level = "medium"
            elif float(days_of_coverage) <= 14:
                risk_level = "low"
            else:
                risk_level = "stable"

            risk_of_stockout = stockout or (
                days_of_coverage is not None and float(days_of_coverage) <= 7
            )

            if not stockout and not risk_of_stockout and not min_stock_breach:
                continue

            risk_row = dict(row)
            risk_row.update(
                {
                    "stockout": stockout,
                    "risk_of_stockout": risk_of_stockout,
                    "min_stock_breach": min_stock_breach,
                    "risk_level": risk_level,
                }
            )
            items.append(risk_row)

        return items

    @staticmethod
    def list_inventory_preventive_alerts(
        days_to_expiration: int = 7,
        usage_type: str | None = None,
    ):
        normalized_days = int(days_to_expiration)
        if normalized_days < 0:
            raise ValueError("days_to_expiration no puede ser negativo")

        normalized_usage_type = (usage_type or "").strip().lower() or None
        if (
            normalized_usage_type
            and normalized_usage_type not in InventoryService.ALLOWED_ITEM_USAGE_TYPES
        ):
            raise ValueError("Tipo de uso no permitido para alertas preventivas")

        today = date.today()
        cutoff = today + timedelta(days=normalized_days)

        query = InventoryItem.query.filter(InventoryItem.is_active.is_(True))
        if normalized_usage_type:
            query = query.filter(InventoryItem.usage_type == normalized_usage_type)

        items = query.order_by(InventoryItem.name.asc()).all()

        alerts = []
        for item in items:
            stock_value = float(item.stock or 0.0)
            min_stock_value = (
                float(item.min_stock) if item.min_stock not in (None, "") else None
            )

            low_stock = min_stock_value is not None and stock_value <= min_stock_value

            expiration = item.expiration_date
            expired = bool(expiration and expiration < today)
            expiring_soon = bool(expiration and today <= expiration <= cutoff)
            days_until_expiration = (
                (expiration - today).days if expiration is not None else None
            )

            if not low_stock and not expiring_soon and not expired:
                continue

            alerts.append(
                {
                    "inventory_item_id": item.id,
                    "inventory_item_name": item.name,
                    "usage_type": item.usage_type,
                    "stock": stock_value,
                    "min_stock": min_stock_value,
                    "low_stock": low_stock,
                    "expiration_date": expiration,
                    "expired": expired,
                    "expiring_soon": expiring_soon,
                    "days_until_expiration": days_until_expiration,
                }
            )

        return alerts

    @staticmethod
    def resolve_business(client_slug: str, business_slug: str) -> Business:
        """Resuelve y valida el negocio a partir de slugs de cliente y negocio."""
        business = get_business_by_slugs(client_slug, business_slug)
        if not business:
            raise ValueError("Negocio no encontrado")
        return business

    @staticmethod
    def _get_item_or_404(inventory_item_id: int) -> InventoryItem:
        """Obtiene un item de inventario o lanza 404 si no existe."""
        return InventoryItem.query.get_or_404(inventory_item_id)

    @staticmethod
    def _resolve_business_min_stock_policy(business_id: int) -> str:
        business = Business.query.get_or_404(business_id)
        policy = (business.inventory_min_stock_policy or "alert").strip().lower()
        if policy not in InventoryService.ALLOWED_MIN_STOCK_POLICIES:
            return "alert"
        return policy

    @staticmethod
    def get_all_items() -> list[InventoryItem]:
        """Devuelve todos los items de inventario ordenados por nombre."""
        return InventoryItem.query.order_by(InventoryItem.name).all()

    @staticmethod
    def _normalize_item_name(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        collapsed = re.sub(r"\s+", " ", ascii_value).strip().lower()
        return collapsed

    @staticmethod
    def _validate_unit(unit: str) -> str:
        normalized_unit = (unit or "").strip().lower()
        if normalized_unit not in InventoryService.ALLOWED_ITEM_UNITS:
            allowed_units = ", ".join(sorted(InventoryService.ALLOWED_ITEM_UNITS))
            raise ValueError(f"Unidad no permitida. Use una de: {allowed_units}")
        return normalized_unit

    @staticmethod
    def _validate_usage_type(usage_type: str | None) -> str:
        normalized_usage_type = (
            (usage_type or InventoryItem.USAGE_TYPE_MIXED).strip().lower()
        )
        if normalized_usage_type not in InventoryService.ALLOWED_ITEM_USAGE_TYPES:
            raise ValueError("Tipo de uso no permitido para item de inventario")
        return normalized_usage_type

    @staticmethod
    def _validate_item_name_uniqueness(name: str, current_item_id: int | None = None):
        normalized_name = InventoryService._normalize_item_name(name)
        if not normalized_name:
            raise ValueError("El nombre del item es obligatorio")

        query = InventoryItem.query
        if current_item_id is not None:
            query = query.filter(InventoryItem.id != current_item_id)

        for item in query.all():
            if InventoryService._normalize_item_name(item.name) == normalized_name:
                raise ValueError(
                    "Ya existe un item con ese nombre normalizado (acentos/espacios/case)"
                )

        return (name or "").strip()

    @staticmethod
    def create_item(
        name: str,
        unit: str,
        usage_type: str = InventoryItem.USAGE_TYPE_MIXED,
        is_active: bool = True,
    ):
        """Crea y persiste un nuevo item de inventario."""
        normalized_name = InventoryService._validate_item_name_uniqueness(name=name)
        normalized_unit = InventoryService._validate_unit(unit)
        normalized_usage_type = InventoryService._validate_usage_type(usage_type)

        new_item = InventoryItem(
            name=normalized_name,
            unit=normalized_unit,
            usage_type=normalized_usage_type,
            is_active=bool(is_active),
        )
        db.session.add(new_item)
        db.session.commit()
        return new_item

    @staticmethod
    def update_item(
        inventory_item_id: int,
        name: str,
        unit: str,
        usage_type: str | None = None,
        is_active: bool | None = None,
    ):
        """Actualiza nombre y unidad de un item de inventario existente."""
        inventory_item = InventoryService._get_item_or_404(inventory_item_id)
        normalized_name = InventoryService._validate_item_name_uniqueness(
            name=name,
            current_item_id=inventory_item.id,
        )
        normalized_unit = InventoryService._validate_unit(unit)
        inventory_item.name = normalized_name
        inventory_item.unit = normalized_unit
        if usage_type is not None:
            inventory_item.usage_type = InventoryService._validate_usage_type(
                usage_type
            )
        if is_active is not None:
            inventory_item.is_active = bool(is_active)
        db.session.commit()
        return inventory_item

    @staticmethod
    def list_supplies(business_id: int, include_inactive: bool = False) -> list[Supply]:
        query = Supply.query.filter(Supply.business_id == business_id)
        if not include_inactive:
            query = query.filter(Supply.is_active.is_(True))
        return query.order_by(Supply.product_variant.asc()).all()

    @staticmethod
    def list_product_generics(
        include_inactive: bool = False,
    ) -> list[InventoryProductGeneric]:
        query = InventoryProductGeneric.query
        if not include_inactive:
            query = query.filter(InventoryProductGeneric.is_active.is_(True))
        return query.order_by(InventoryProductGeneric.name.asc()).all()

    @staticmethod
    def create_product_generic(name: str) -> InventoryProductGeneric:
        normalized_name = (name or "").strip()
        if not normalized_name:
            raise ValueError("El producto generico es obligatorio")

        existing = InventoryProductGeneric.query.filter(
            db.func.lower(InventoryProductGeneric.name) == normalized_name.lower()
        ).first()
        if existing:
            raise ValueError("Ya existe ese producto generico")

        generic = InventoryProductGeneric(name=normalized_name, is_active=True)
        db.session.add(generic)
        db.session.commit()
        return generic

    @staticmethod
    def list_product_specifics(
        product_generic_id: int | None = None,
        include_inactive: bool = False,
    ) -> list[InventoryProductSpecific]:
        query = InventoryProductSpecific.query
        if product_generic_id is not None:
            query = query.filter(
                InventoryProductSpecific.generic_id == product_generic_id
            )
        if not include_inactive:
            query = query.filter(InventoryProductSpecific.is_active.is_(True))
        return query.order_by(InventoryProductSpecific.name.asc()).all()

    @staticmethod
    def create_product_specific(
        product_generic_id: int,
        name: str,
    ) -> InventoryProductSpecific:
        generic = InventoryProductGeneric.query.get_or_404(product_generic_id)

        normalized_name = (name or "").strip()
        if not normalized_name:
            raise ValueError("El producto especifico es obligatorio")

        existing = InventoryProductSpecific.query.filter(
            InventoryProductSpecific.generic_id == generic.id,
            db.func.lower(InventoryProductSpecific.name) == normalized_name.lower(),
        ).first()
        if existing:
            raise ValueError("Ya existe ese producto especifico para el generico")

        specific = InventoryProductSpecific(
            generic_id=generic.id,
            name=normalized_name,
            is_active=True,
        )
        db.session.add(specific)
        db.session.commit()
        return specific

    @staticmethod
    def create_supply(
        business_id: int,
        inventory_item_id: int,
        product_variant: str,
        product_specific_id: int | None = None,
        is_active: bool = True,
    ) -> Supply:
        inventory_item = InventoryService._get_item_or_404(inventory_item_id)

        product_specific = None
        if product_specific_id is not None:
            product_specific = InventoryProductSpecific.query.get_or_404(
                product_specific_id
            )

        normalized_variant = (product_variant or "").strip()
        if not normalized_variant:
            raise ValueError("La variante del insumo es obligatoria")

        existing_supply = Supply.query.filter(
            Supply.business_id == business_id,
            Supply.product_variant == normalized_variant,
        ).first()
        if existing_supply:
            raise ValueError("Ya existe un insumo con esa variante en el negocio")

        new_supply = Supply(
            business_id=business_id,
            inventory_item_id=inventory_item.id,
            product_specific_id=product_specific.id if product_specific else None,
            product_variant=normalized_variant,
            is_active=bool(is_active),
        )
        db.session.add(new_supply)
        db.session.commit()
        return new_supply

    @staticmethod
    def update_supply(
        business_id: int,
        supply_id: int,
        inventory_item_id: int,
        product_variant: str,
        product_specific_id: int | None,
        is_active: bool,
    ) -> Supply:
        supply = Supply.query.get_or_404(supply_id)
        if supply.business_id != business_id:
            raise ValueError("El insumo no pertenece al negocio")

        inventory_item = InventoryService._get_item_or_404(inventory_item_id)

        product_specific = None
        if product_specific_id is not None:
            product_specific = InventoryProductSpecific.query.get_or_404(
                product_specific_id
            )

        normalized_variant = (product_variant or "").strip()
        if not normalized_variant:
            raise ValueError("La variante del insumo es obligatoria")

        existing_supply = Supply.query.filter(
            Supply.business_id == business_id,
            Supply.product_variant == normalized_variant,
            Supply.id != supply.id,
        ).first()
        if existing_supply:
            raise ValueError("Ya existe un insumo con esa variante en el negocio")

        supply.inventory_item_id = inventory_item.id
        supply.product_specific_id = product_specific.id if product_specific else None
        supply.product_variant = normalized_variant
        supply.is_active = bool(is_active)
        db.session.commit()
        return supply

    @staticmethod
    def delete_supply(business_id: int, supply_id: int):
        supply = Supply.query.get_or_404(supply_id)
        if supply.business_id != business_id:
            raise ValueError("El insumo no pertenece al negocio")

        db.session.delete(supply)
        db.session.commit()

    @staticmethod
    def list_movements(
        business_id: int,
        inventory_item_id: int | None = None,
        lot_code: str | None = None,
        start_date=None,
        end_date=None,
    ) -> list[InventoryMovement]:
        query = InventoryMovement.query.filter(
            InventoryMovement.business_id == business_id
        )
        if inventory_item_id is not None:
            query = query.filter(
                InventoryMovement.inventory_item_id == inventory_item_id
            )
        normalized_lot_code = (lot_code or "").strip() or None
        if normalized_lot_code:
            query = query.filter(InventoryMovement.lot_code == normalized_lot_code)
        if start_date is not None:
            query = query.filter(InventoryMovement.movement_date >= start_date)
        if end_date is not None:
            query = query.filter(InventoryMovement.movement_date <= end_date)

        return query.order_by(InventoryMovement.movement_date.desc()).all()

    @staticmethod
    def list_waste_report(
        business_id: int,
        start_date=None,
        end_date=None,
        inventory_item_id: int | None = None,
        waste_reason: str | None = None,
    ):
        query = InventoryMovement.query.filter(
            InventoryMovement.business_id == business_id,
            InventoryMovement.movement_type == "waste",
        )

        if inventory_item_id is not None:
            query = query.filter(
                InventoryMovement.inventory_item_id == inventory_item_id
            )

        normalized_waste_reason = (waste_reason or "").strip().lower() or None
        if normalized_waste_reason:
            query = query.filter(
                InventoryMovement.waste_reason == normalized_waste_reason
            )

        if start_date is not None:
            query = query.filter(InventoryMovement.movement_date >= start_date)
        if end_date is not None:
            query = query.filter(InventoryMovement.movement_date <= end_date)

        movements = query.order_by(InventoryMovement.movement_date.desc()).all()

        rows_by_key: dict[tuple[int, str], dict] = {}
        for movement in movements:
            reason = (
                (getattr(movement, "waste_reason", None) or "otros").strip().lower()
            )
            key = (movement.inventory_item_id, reason)

            if key not in rows_by_key:
                item_name = None
                if getattr(movement, "inventory_item", None):
                    item_name = movement.inventory_item.name
                rows_by_key[key] = {
                    "inventory_item_id": movement.inventory_item_id,
                    "inventory_item_name": item_name,
                    "waste_reason": reason,
                    "events": 0,
                    "total_quantity": 0.0,
                    "total_amount": 0.0,
                    "last_movement_date": None,
                }

            row = rows_by_key[key]
            row["events"] += 1
            row["total_quantity"] += float(movement.quantity or 0.0)
            row["total_amount"] += InventoryService._resolve_movement_amount(movement)
            movement_date = getattr(movement, "movement_date", None)
            if movement_date and (
                row["last_movement_date"] is None
                or movement_date > row["last_movement_date"]
            ):
                row["last_movement_date"] = movement_date

        items = []
        for row in sorted(
            rows_by_key.values(),
            key=lambda value: (
                value["inventory_item_name"] or "",
                value["waste_reason"],
            ),
        ):
            row["total_quantity"] = round(row["total_quantity"], 4)
            row["total_amount"] = round(row["total_amount"], 2)
            items.append(row)
        return items

    @staticmethod
    def create_movement(
        business_id: int,
        inventory_item_id: int,
        movement_type: str,
        quantity: float,
        unit: str,
        destination: str | None = None,
        adjustment_kind: str | None = None,
        inventory_id: int | None = None,
        unit_cost: float | None = None,
        total_cost: float | None = None,
        account_code: str | None = None,
        idempotency_key: str | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
        supplier_name: str | None = None,
        waste_reason: str | None = None,
        waste_responsible: str | None = None,
        waste_evidence: str | None = None,
        waste_evidence_file_url: str | None = None,
        lot_code: str | None = None,
        lot_date: date | None = None,
        lot_unit: str | None = None,
        lot_conversion_factor: float | None = None,
        movement_date: datetime | None = None,
        document: str | None = None,
        notes: str | None = None,
    ) -> InventoryMovement:
        movement_type = (movement_type or "").strip().lower()
        if movement_type not in InventoryService.ALLOWED_MOVEMENT_TYPES:
            raise ValueError("Tipo de movimiento no permitido")

        if quantity is None or float(quantity) <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")

        normalized_unit = (unit or "").strip()
        if not normalized_unit:
            raise ValueError("La unidad es obligatoria")

        if destination:
            destination = destination.strip().lower()
            if destination not in InventoryService.ALLOWED_DESTINATIONS:
                raise ValueError("Destino de movimiento no permitido")

        normalized_document = (document or "").strip() or None
        if movement_type == "purchase" and not normalized_document:
            raise ValueError(
                "El documento es obligatorio para registrar entradas de compra"
            )

        normalized_supplier_name = (supplier_name or "").strip() or None
        normalized_notes = (notes or "").strip() or None

        normalized_adjustment_kind = (adjustment_kind or "").strip().lower() or None
        if movement_type == "adjustment":
            if (
                normalized_adjustment_kind
                not in InventoryService.ALLOWED_ADJUSTMENT_KINDS
            ):
                raise ValueError("El tipo de ajuste debe ser 'positive' o 'negative'")
            if not normalized_notes:
                raise ValueError("El motivo es obligatorio para registrar ajustes")
        else:
            normalized_adjustment_kind = None

        normalized_waste_reason = (waste_reason or "").strip().lower() or None
        normalized_waste_responsible = (waste_responsible or "").strip() or None
        normalized_waste_evidence = (waste_evidence or "").strip() or None
        normalized_waste_evidence_file_url = (
            waste_evidence_file_url or ""
        ).strip() or None
        if movement_type == "waste":
            if normalized_waste_reason not in InventoryService.ALLOWED_WASTE_REASONS:
                raise ValueError(
                    "La causa de merma debe ser: rotura, deterioro, caducidad u otros"
                )
            if not normalized_waste_responsible:
                raise ValueError("El responsable es obligatorio para registrar mermas")
            if normalized_waste_evidence_file_url:
                lowered_file_url = normalized_waste_evidence_file_url.lower()
                if not any(
                    lowered_file_url.endswith(ext)
                    for ext in InventoryService.ALLOWED_WASTE_EVIDENCE_EXTENSIONS
                ):
                    raise ValueError(
                        "La evidencia de merma debe ser una imagen o PDF valido"
                    )
        else:
            normalized_waste_reason = None
            normalized_waste_responsible = None
            normalized_waste_evidence = None
            normalized_waste_evidence_file_url = None

        normalized_account_code = (account_code or "").strip() or None
        if not normalized_account_code:
            raise ValueError(
                "La cuenta contable es obligatoria para registrar el movimiento"
            )
        if normalized_account_code:
            InventoryService.validate_account_is_adopted(
                business_id=business_id,
                account_code=normalized_account_code,
            )

        resolved_idempotency_key = InventoryService._resolve_movement_idempotency_key(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            movement_type=movement_type,
            destination=destination,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
        )

        if resolved_idempotency_key:
            existing = InventoryMovement.query.filter_by(
                idempotency_key=resolved_idempotency_key
            ).first()
            if existing:
                return existing

        inventory_item = InventoryService._get_item_or_404(inventory_item_id)

        inventory_record = None
        if inventory_id is not None:
            inventory_record = Inventory.query.get_or_404(inventory_id)
            if inventory_record.business_id != business_id:
                raise ValueError("El inventario seleccionado no pertenece al negocio")

        normalized_lot_code = (lot_code or "").strip() or None
        if movement_type == "purchase" and not normalized_lot_code:
            normalized_lot_code = InventoryService._generate_auto_lot_code(
                business_id=business_id,
                inventory_item_id=inventory_item_id,
            )

        normalized_lot_unit = (lot_unit or "").strip() or None
        normalized_lot_conversion_factor = (
            float(lot_conversion_factor)
            if lot_conversion_factor not in (None, "")
            else None
        )
        if normalized_lot_conversion_factor is not None:
            if normalized_lot_conversion_factor <= 0:
                raise ValueError(
                    "El factor de conversion del lote debe ser mayor que cero"
                )
            if not normalized_lot_unit:
                raise ValueError(
                    "La unidad del lote es obligatoria cuando hay factor de conversion"
                )
        if normalized_lot_unit and normalized_lot_conversion_factor is None:
            raise ValueError(
                "El factor de conversion del lote es obligatorio cuando se indica unidad de lote"
            )

        requested_quantity = float(quantity)
        requested_unit = normalized_unit.strip().lower()
        qty, normalized_unit, applied_conversion_factor, non_exact_conversion = (
            InventoryService._resolve_quantity_in_item_base_unit(
                business_id=business_id,
                inventory_item=inventory_item,
                quantity=requested_quantity,
                unit=requested_unit,
            )
        )

        if non_exact_conversion and not normalized_notes:
            raise ValueError(
                "El motivo es obligatorio cuando la conversion de unidades no es exacta"
            )

        if (
            unit_cost not in (None, "")
            and requested_unit
            != (getattr(inventory_item, "unit", None) or "").strip().lower()
            and applied_conversion_factor is not None
        ):
            requested_total_cost = float(unit_cost) * requested_quantity
            unit_cost = requested_total_cost / qty if qty > 0 else unit_cost

        delta = InventoryService._movement_stock_delta(
            movement_type=movement_type,
            quantity=qty,
            adjustment_kind=normalized_adjustment_kind,
        )
        selected_valuation_method = "manual"

        previous_stock = float(inventory_item.stock or 0.0)
        new_stock = previous_stock + delta
        if new_stock < 0:
            raise ValueError("No hay existencia suficiente para realizar la salida")

        min_stock_value = getattr(inventory_item, "min_stock", None)
        min_stock_threshold = (
            float(min_stock_value) if min_stock_value not in (None, "") else None
        )
        min_stock_breach = (
            delta < 0
            and min_stock_threshold is not None
            and new_stock < min_stock_threshold
        )
        min_stock_policy = "alert"
        if min_stock_breach:
            min_stock_policy = InventoryService._resolve_business_min_stock_policy(
                business_id=business_id
            )
            if min_stock_policy == "block":
                raise ValueError(
                    "Operacion bloqueada: el movimiento deja el stock por debajo del minimo configurado"
                )

        selected_lot_context = None
        if delta < 0 and inventory_id is None and not normalized_lot_code:
            selected_lot_context = InventoryService._select_outgoing_lot_context(
                business_id=business_id,
                inventory_item_id=inventory_item.id,
            )
            if selected_lot_context:
                normalized_lot_code = selected_lot_context.get("lot_code")
                if lot_date is None:
                    lot_date = selected_lot_context.get("lot_date")
                if inventory_record is None and selected_lot_context.get(
                    "inventory_id"
                ):
                    inventory_record = Inventory.query.get(
                        selected_lot_context.get("inventory_id")
                    )
                selected_valuation_method = selected_lot_context.get(
                    "valuation_method", "fifo"
                )
            else:
                selected_valuation_method = "fifo"
        elif delta < 0:
            selected_valuation_method = "fefo" if lot_date is not None else "fifo"

        if delta > 0:
            InventoryService._recalculate_average_unit_cost(
                inventory_item=inventory_item,
                previous_stock=previous_stock,
                entry_quantity=qty,
                entry_unit_cost=InventoryService._resolve_entry_unit_cost(
                    quantity=qty,
                    unit_cost=unit_cost,
                    total_cost=total_cost,
                ),
            )

        inventory_item.stock = new_stock

        movement = InventoryMovement(
            business_id=business_id,
            inventory_item_id=inventory_item.id,
            inventory_id=inventory_record.id if inventory_record else None,
            movement_type=movement_type,
            adjustment_kind=normalized_adjustment_kind,
            destination=destination,
            lot_code=normalized_lot_code,
            lot_date=lot_date,
            lot_unit=normalized_lot_unit,
            lot_conversion_factor=normalized_lot_conversion_factor,
            quantity=qty,
            unit=normalized_unit,
            unit_cost=unit_cost,
            total_cost=total_cost,
            account_code=normalized_account_code,
            idempotency_key=resolved_idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            supplier_name=normalized_supplier_name,
            waste_reason=normalized_waste_reason,
            waste_responsible=normalized_waste_responsible,
            waste_evidence=normalized_waste_evidence,
            waste_evidence_file_url=normalized_waste_evidence_file_url,
            document=normalized_document,
            notes=normalized_notes,
        )
        if movement_date is not None:
            movement.movement_date = movement_date
        movement.min_stock_alert = bool(min_stock_breach)
        movement.min_stock_policy = min_stock_policy
        movement.projected_stock = new_stock
        movement.min_stock_threshold = min_stock_threshold
        db.session.add(movement)
        db.session.commit()
        InventoryService.register_inventory_ledger_for_movement(
            movement,
            valuation_method=selected_valuation_method,
        )
        return movement

    @staticmethod
    def _build_lot_balances_for_item(
        business_id: int,
        inventory_item_id: int,
    ) -> list[dict]:
        movements = (
            InventoryMovement.query.filter(
                InventoryMovement.business_id == business_id,
                InventoryMovement.inventory_item_id == inventory_item_id,
            )
            .order_by(InventoryMovement.movement_date.asc(), InventoryMovement.id.asc())
            .all()
        )

        balances: dict[str, dict] = {}
        for movement in movements:
            movement_lot_code = (getattr(movement, "lot_code", None) or "").strip()
            key = movement_lot_code or "__NO_LOT__"
            adjustment_kind = (
                getattr(movement, "adjustment_kind", "") or ""
            ).strip().lower() or None
            delta = InventoryService._movement_stock_delta(
                movement_type=(getattr(movement, "movement_type", "") or "")
                .strip()
                .lower(),
                quantity=float(getattr(movement, "quantity", 0.0) or 0.0),
                adjustment_kind=adjustment_kind,
            )

            if key not in balances:
                balances[key] = {
                    "lot_code": movement_lot_code or None,
                    "lot_date": getattr(movement, "lot_date", None),
                    "inventory_id": getattr(movement, "inventory_id", None),
                    "first_movement_date": getattr(movement, "movement_date", None),
                    "first_movement_id": getattr(movement, "id", None),
                    "balance": 0.0,
                }

            bucket = balances[key]
            bucket["balance"] += float(delta)

            if bucket.get("lot_date") is None and getattr(movement, "lot_date", None):
                bucket["lot_date"] = getattr(movement, "lot_date", None)
            if bucket.get("inventory_id") is None and getattr(
                movement, "inventory_id", None
            ):
                bucket["inventory_id"] = getattr(movement, "inventory_id", None)

        return [
            bucket
            for bucket in balances.values()
            if float(bucket["balance"] or 0.0) > 0
        ]

    @staticmethod
    def _select_outgoing_lot_context(
        business_id: int,
        inventory_item_id: int,
    ) -> dict | None:
        lot_balances = InventoryService._build_lot_balances_for_item(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
        )
        if not lot_balances:
            return None

        has_expiration_lot = any(
            bucket.get("lot_date") is not None for bucket in lot_balances
        )
        if has_expiration_lot:
            ordered = sorted(
                lot_balances,
                key=lambda bucket: (
                    bucket.get("lot_date") is None,
                    bucket.get("lot_date"),
                    bucket.get("first_movement_date") is None,
                    bucket.get("first_movement_date"),
                    bucket.get("first_movement_id") or 0,
                ),
            )
            selected = ordered[0]
            return {
                "lot_code": selected.get("lot_code"),
                "lot_date": selected.get("lot_date"),
                "inventory_id": selected.get("inventory_id"),
                "valuation_method": "fefo",
            }

        ordered = sorted(
            lot_balances,
            key=lambda bucket: (
                bucket.get("first_movement_date") is None,
                bucket.get("first_movement_date"),
                bucket.get("first_movement_id") or 0,
            ),
        )
        selected = ordered[0]
        return {
            "lot_code": selected.get("lot_code"),
            "lot_date": selected.get("lot_date"),
            "inventory_id": selected.get("inventory_id"),
            "valuation_method": "fifo",
        }

    @staticmethod
    def _round_quantity_by_unit(unit: str, quantity: float) -> float:
        normalized_unit = (unit or "").strip().lower()
        precision = InventoryService.UNIT_PRECISION_RULES.get(normalized_unit, 4)
        return round(float(quantity), precision)

    @staticmethod
    def _resolve_quantity_in_item_base_unit(
        business_id: int,
        inventory_item: InventoryItem,
        quantity: float,
        unit: str,
    ) -> tuple[float, str, float | None, bool]:
        item_unit = (getattr(inventory_item, "unit", None) or "").strip().lower()
        requested_unit = (unit or "").strip().lower()

        if not item_unit:
            item_unit = requested_unit

        if requested_unit == item_unit:
            return (
                InventoryService._round_quantity_by_unit(item_unit, quantity),
                item_unit,
                None,
                False,
            )

        conversion = InventoryUnitConversion.query.filter_by(
            business_id=business_id,
            inventory_item_id=inventory_item.id,
            from_unit=requested_unit,
            to_unit=item_unit,
            is_active=True,
        ).first()
        if not conversion:
            raise ValueError(
                "No existe conversion configurada para la unidad indicada en este item"
            )

        converted_quantity = float(quantity) * float(conversion.factor)
        rounded_quantity = InventoryService._round_quantity_by_unit(
            item_unit, converted_quantity
        )
        has_non_exact_conversion = (
            abs(float(converted_quantity) - float(rounded_quantity))
            > InventoryService.INVENTORY_SYNC_QUANTITY_EPSILON
        )
        return (
            rounded_quantity,
            item_unit,
            float(conversion.factor),
            has_non_exact_conversion,
        )

    @staticmethod
    def _resolve_movement_idempotency_key(
        business_id: int,
        inventory_item_id: int,
        movement_type: str,
        destination: str | None,
        idempotency_key: str | None,
        reference_type: str | None,
        reference_id: int | None,
    ) -> str | None:
        normalized_key = (idempotency_key or "").strip() or None
        if normalized_key:
            return normalized_key

        normalized_reference_type = (reference_type or "").strip().lower() or None
        if (
            normalized_reference_type
            not in InventoryService.AUTO_IDEMPOTENT_REFERENCE_TYPES
        ):
            return None
        if reference_id is None:
            return None

        normalized_destination = (destination or "").strip().lower() or "none"
        return (
            f"auto:{normalized_reference_type}:{business_id}:{reference_id}:"
            f"{inventory_item_id}:{movement_type}:{normalized_destination}"
        )

    @staticmethod
    def list_cycle_counts(
        business_id: int,
        location: str | None = None,
        status: str | None = None,
        inventory_item_id: int | None = None,
        start_date=None,
        end_date=None,
    ) -> list[InventoryCycleCount]:
        query = InventoryCycleCount.query.filter(
            InventoryCycleCount.business_id == business_id
        )

        normalized_location = (location or "").strip().lower() or None
        if normalized_location:
            query = query.filter(InventoryCycleCount.location == normalized_location)

        normalized_status = (status or "").strip().lower() or None
        if normalized_status:
            query = query.filter(InventoryCycleCount.status == normalized_status)

        if inventory_item_id is not None:
            query = query.filter(
                InventoryCycleCount.inventory_item_id == inventory_item_id
            )

        if start_date is not None:
            query = query.filter(InventoryCycleCount.counted_at >= start_date)
        if end_date is not None:
            query = query.filter(InventoryCycleCount.counted_at <= end_date)

        return query.order_by(InventoryCycleCount.counted_at.desc()).all()

    @staticmethod
    def _resolve_theoretical_quantity_for_cycle_count(
        business_id: int,
        inventory_item_id: int,
        location: str,
    ) -> float:
        _ = business_id
        if location == "warehouse":
            item = InventoryService._get_item_or_404(inventory_item_id)
            return float(item.stock or 0.0)

        raise ValueError("Ubicacion no soportada para conteo ciclico")

    @staticmethod
    def create_cycle_count(
        business_id: int,
        inventory_item_id: int,
        location: str,
        counted_quantity: float,
        actor: str,
        counted_at: datetime | None = None,
        observation: str | None = None,
    ) -> InventoryCycleCount:
        normalized_location = (location or "").strip().lower() or "warehouse"
        if normalized_location not in InventoryService.ALLOWED_CYCLE_COUNT_LOCATIONS:
            raise ValueError("Ubicacion no permitida para conteo ciclico")

        normalized_actor = (actor or "").strip()
        if not normalized_actor:
            raise ValueError("El usuario del conteo es obligatorio")

        counted_value = float(counted_quantity)
        if counted_value < 0:
            raise ValueError("La cantidad contada no puede ser negativa")

        theoretical_quantity = (
            InventoryService._resolve_theoretical_quantity_for_cycle_count(
                business_id=business_id,
                inventory_item_id=inventory_item_id,
                location=normalized_location,
            )
        )

        difference = counted_value - theoretical_quantity
        proposed_adjustment_kind = None
        if difference > 0:
            proposed_adjustment_kind = "positive"
        elif difference < 0:
            proposed_adjustment_kind = "negative"

        pending_status = getattr(InventoryCycleCount, "STATUS_PENDING", "pending")
        if not isinstance(pending_status, str) or not pending_status.strip():
            pending_status = "pending"

        count = InventoryCycleCount(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            location=normalized_location,
            theoretical_quantity=theoretical_quantity,
            counted_quantity=counted_value,
            difference_quantity=difference,
            proposed_adjustment_kind=proposed_adjustment_kind,
            status=pending_status,
            actor=normalized_actor,
            observation=(observation or "").strip() or None,
        )
        if counted_at is not None:
            count.counted_at = counted_at

        db.session.add(count)
        db.session.commit()
        return count

    @staticmethod
    def reconcile_cycle_count(
        business_id: int,
        cycle_count_id: int,
        account_code: str,
        actor: str,
        notes: str | None = None,
    ) -> InventoryCycleCount:
        pending_status = getattr(InventoryCycleCount, "STATUS_PENDING", "pending")
        if not isinstance(pending_status, str) or not pending_status.strip():
            pending_status = "pending"

        applied_status = getattr(InventoryCycleCount, "STATUS_APPLIED", "applied")
        if not isinstance(applied_status, str) or not applied_status.strip():
            applied_status = "applied"

        count = InventoryCycleCount.query.get_or_404(cycle_count_id)
        if count.business_id != business_id:
            raise ValueError("El conteo no pertenece al negocio")
        if count.status != pending_status:
            raise ValueError("El conteo ya fue conciliado")

        normalized_account_code = (account_code or "").strip()
        if not normalized_account_code:
            raise ValueError("La cuenta contable es obligatoria para conciliar")

        if count.location not in InventoryService.ALLOWED_CYCLE_COUNT_LOCATIONS:
            raise ValueError("Ubicacion no soportada para conciliacion en esta etapa")

        diff = float(count.difference_quantity or 0.0)
        movement = None
        if diff != 0:
            movement_notes = (notes or "").strip() or (
                f"Conciliacion de conteo ciclico #{count.id} por {actor}"
            )
            movement = InventoryService.create_movement(
                business_id=business_id,
                inventory_item_id=count.inventory_item_id,
                movement_type="adjustment",
                adjustment_kind=("positive" if diff > 0 else "negative"),
                quantity=abs(diff),
                unit=count.inventory_item.unit,
                account_code=normalized_account_code,
                reference_type="cycle_count",
                reference_id=count.id,
                notes=movement_notes,
            )

        count.status = applied_status
        count.applied_movement_id = movement.id if movement else None
        db.session.commit()
        return count

    @staticmethod
    def create_purchase_receipt(
        business_id: int,
        inventory_item_id: int,
        quantity: float,
        unit: str,
        account_code: str,
        supplier_name: str,
        document: str,
        receipt_date: datetime,
        unit_cost: float,
        total_cost: float | None = None,
        lot_code: str | None = None,
        lot_date: date | None = None,
        lot_unit: str | None = None,
        lot_conversion_factor: float | None = None,
        notes: str | None = None,
    ) -> InventoryMovement:
        normalized_supplier_name = (supplier_name or "").strip()
        if not normalized_supplier_name:
            raise ValueError("El proveedor es obligatorio en la recepcion de compra")

        normalized_document = (document or "").strip()
        if not normalized_document:
            raise ValueError("El documento es obligatorio en la recepcion de compra")

        if receipt_date is None:
            raise ValueError("La fecha de recepcion es obligatoria")

        normalized_unit_cost = float(unit_cost)
        if normalized_unit_cost <= 0:
            raise ValueError("El costo unitario debe ser mayor que cero")

        normalized_total_cost = (
            float(total_cost)
            if total_cost is not None
            else float(quantity) * normalized_unit_cost
        )

        return InventoryService.create_movement(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            movement_type="purchase",
            destination=None,
            quantity=quantity,
            unit=unit,
            unit_cost=normalized_unit_cost,
            total_cost=normalized_total_cost,
            account_code=account_code,
            reference_type="purchase_receipt",
            supplier_name=normalized_supplier_name,
            lot_code=lot_code,
            lot_date=lot_date,
            lot_unit=lot_unit,
            lot_conversion_factor=lot_conversion_factor,
            movement_date=receipt_date,
            document=normalized_document,
            notes=notes,
        )

    @staticmethod
    def _resolve_movement_amount(movement: InventoryMovement) -> float:
        if movement.total_cost is not None:
            return max(0.0, float(movement.total_cost))
        if movement.unit_cost is not None:
            return max(0.0, float(movement.unit_cost) * float(movement.quantity or 0.0))
        return 0.0

    @staticmethod
    def _resolve_inventory_ledger_flow(
        movement_type: str,
        destination: str | None,
        adjustment_kind: str | None = None,
    ) -> tuple[str, str]:
        destination_norm = (destination or "").strip().lower() or None
        if movement_type == "purchase":
            return "supplier", "warehouse"
        if movement_type == "consumption":
            return "warehouse", "consumption"
        if movement_type == "waste":
            if destination_norm == "finished_goods":
                return "finished_goods", "waste_finished_goods"
            return "warehouse", "waste_raw_materials"
        if movement_type == "transfer":
            return "warehouse", destination_norm or "warehouse"
        if movement_type == "wip_close":
            return "wip", destination_norm or "finished_goods"
        if movement_type == "adjustment":
            if adjustment_kind == "negative":
                return "warehouse", "adjustment_negative"
            return "adjustment_positive", "warehouse"
        return "unknown", destination_norm or "unknown"

    @staticmethod
    def register_inventory_ledger_for_movement(
        movement: InventoryMovement,
        valuation_method: str | None = None,
    ) -> InventoryLedgerEntry:
        adjustment_kind = (
            getattr(movement, "adjustment_kind", "") or ""
        ).strip().lower() or None
        source_bucket, destination_bucket = (
            InventoryService._resolve_inventory_ledger_flow(
                movement_type=(movement.movement_type or "").strip().lower(),
                destination=movement.destination,
                adjustment_kind=adjustment_kind,
            )
        )

        account_code = (movement.account_code or "").strip() or None
        source_account_code = account_code
        destination_account_code = account_code

        if movement.movement_type == "purchase":
            source_account_code = None
        elif movement.movement_type == "consumption":
            destination_account_code = None
        elif movement.movement_type == "waste":
            destination_account_code = InventoryService.WASTE_EXPENSE_ACCOUNT_CODE

        resolved_valuation_method = (valuation_method or "").strip().lower() or (
            "fefo" if (movement.lot_code or "").strip() else "fifo"
        )
        if resolved_valuation_method not in InventoryService.ALLOWED_VALUATION_METHODS:
            resolved_valuation_method = "manual"
        amount = InventoryService._resolve_movement_amount(movement)

        entry = InventoryLedgerEntry.query.filter_by(movement_id=movement.id).first()
        if not entry:
            entry = InventoryLedgerEntry(
                business_id=movement.business_id,
                movement_id=movement.id,
            )
            db.session.add(entry)

        entry.movement_type = movement.movement_type
        entry.destination = movement.destination
        entry.source_bucket = source_bucket
        entry.destination_bucket = destination_bucket
        entry.source_account_code = source_account_code
        entry.destination_account_code = destination_account_code
        entry.quantity = float(movement.quantity or 0.0)
        entry.unit = movement.unit
        entry.unit_cost = movement.unit_cost
        entry.amount = amount
        entry.valuation_method = resolved_valuation_method
        entry.document = movement.document
        entry.reference_type = movement.reference_type
        entry.reference_id = movement.reference_id
        db.session.commit()
        return entry

    @staticmethod
    def _resolve_waste_expense_account_code(
        movement_type: str,
    ) -> str | None:
        if movement_type == "waste":
            return InventoryService.WASTE_EXPENSE_ACCOUNT_CODE
        return None

    @staticmethod
    def list_inventory_ledger_entries(
        business_id: int,
        account_code: str | None = None,
    ) -> list[InventoryLedgerEntry]:
        query = InventoryLedgerEntry.query.filter(
            InventoryLedgerEntry.business_id == business_id
        )
        normalized_code = (account_code or "").strip()
        if normalized_code:
            query = query.filter(
                or_(
                    InventoryLedgerEntry.source_account_code == normalized_code,
                    InventoryLedgerEntry.destination_account_code == normalized_code,
                )
            )

        return query.order_by(InventoryLedgerEntry.created_at.desc()).all()

    @staticmethod
    def list_valued_kardex(
        business_id: int,
        inventory_item_id: int | None = None,
        start_date=None,
        end_date=None,
    ) -> list[dict]:
        movements = InventoryService.list_movements(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            start_date=start_date,
            end_date=end_date,
        )
        ordered_movements = sorted(
            movements,
            key=lambda row: (
                getattr(row, "movement_date", None) or datetime.min,
                int(getattr(row, "id", 0) or 0),
            ),
        )

        item_ids = {
            int(getattr(row, "inventory_item_id", 0) or 0)
            for row in ordered_movements
            if int(getattr(row, "inventory_item_id", 0) or 0) > 0
        }
        item_names_by_id: dict[int, str] = {}
        if item_ids:
            item_rows = InventoryItem.query.filter(InventoryItem.id.in_(item_ids)).all()
            item_names_by_id = {
                int(item.id): str(getattr(item, "name", "") or "") for item in item_rows
            }

        running_stock_by_item: dict[int, float] = {}
        running_value_by_item: dict[int, float] = {}
        rows = []

        for movement in ordered_movements:
            row_item_id = int(getattr(movement, "inventory_item_id", 0) or 0)
            if row_item_id <= 0:
                continue

            movement_type = (
                (getattr(movement, "movement_type", "") or "").strip().lower()
            )
            adjustment_kind = (
                getattr(movement, "adjustment_kind", "") or ""
            ).strip().lower() or None
            quantity = float(getattr(movement, "quantity", 0.0) or 0.0)
            delta_quantity = InventoryService._movement_stock_delta(
                movement_type=movement_type,
                quantity=quantity,
                adjustment_kind=adjustment_kind,
            )
            amount = InventoryService._resolve_movement_amount(movement)
            sign = 1.0 if delta_quantity > 0 else (-1.0 if delta_quantity < 0 else 0.0)
            delta_value = round(amount * sign, 4)

            running_stock = round(
                float(running_stock_by_item.get(row_item_id, 0.0))
                + float(delta_quantity),
                4,
            )
            running_value = round(
                float(running_value_by_item.get(row_item_id, 0.0)) + float(delta_value),
                4,
            )
            running_stock_by_item[row_item_id] = running_stock
            running_value_by_item[row_item_id] = running_value

            rows.append(
                {
                    "movement_id": getattr(movement, "id", None),
                    "movement_date": getattr(movement, "movement_date", None),
                    "inventory_item_id": row_item_id,
                    "inventory_item_name": item_names_by_id.get(row_item_id, ""),
                    "movement_type": movement_type,
                    "adjustment_kind": adjustment_kind,
                    "quantity": round(quantity, 4),
                    "delta_quantity": round(float(delta_quantity), 4),
                    "unit": getattr(movement, "unit", None),
                    "unit_cost": getattr(movement, "unit_cost", None),
                    "total_cost": getattr(movement, "total_cost", None),
                    "amount": round(float(amount), 4),
                    "delta_value": delta_value,
                    "running_stock": running_stock,
                    "running_value": running_value,
                    "account_code": getattr(movement, "account_code", None),
                    "reference_type": getattr(movement, "reference_type", None),
                    "reference_id": getattr(movement, "reference_id", None),
                    "document": getattr(movement, "document", None),
                }
            )

        return rows

    @staticmethod
    def summarize_sale_consumption_cost_report(
        business_id: int,
        sale_id: int | None = None,
        start_date=None,
        end_date=None,
    ) -> list[dict]:
        movements = InventoryService.list_movements(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
        )

        scoped_movements = []
        line_reference_ids: set[int] = set()
        for movement in movements:
            reference_type = (
                (getattr(movement, "reference_type", "") or "").strip().lower()
            )
            if reference_type not in InventoryService.SALE_CONSUMPTION_REFERENCE_TYPES:
                continue

            reference_id = getattr(movement, "reference_id", None)
            if reference_type == "sale_inventory_line" and reference_id is not None:
                line_reference_ids.add(int(reference_id))

            scoped_movements.append(movement)

        sale_id_by_line_id: dict[int, int] = {}
        if line_reference_ids:
            details = SaleDetail.query.filter(
                SaleDetail.id.in_(line_reference_ids)
            ).all()
            sale_id_by_line_id = {
                int(detail.id): int(getattr(detail, "sale_id", 0) or 0)
                for detail in details
                if int(getattr(detail, "sale_id", 0) or 0) > 0
            }

        rows_by_sale: dict[int, dict] = {}
        for movement in scoped_movements:
            reference_type = (
                (getattr(movement, "reference_type", "") or "").strip().lower()
            )
            reference_id = getattr(movement, "reference_id", None)

            resolved_sale_id = None
            if reference_type == "sale_inventory_line":
                if reference_id is None:
                    continue
                resolved_sale_id = sale_id_by_line_id.get(int(reference_id))
            else:
                if reference_id is not None:
                    resolved_sale_id = int(reference_id)

            if not resolved_sale_id:
                continue
            if sale_id is not None and int(sale_id) != int(resolved_sale_id):
                continue

            if resolved_sale_id not in rows_by_sale:
                rows_by_sale[resolved_sale_id] = {
                    "sale_id": int(resolved_sale_id),
                    "movement_count": 0,
                    "consumption_quantity": 0.0,
                    "consumption_cost": 0.0,
                    "reversal_cost": 0.0,
                    "net_consumption_cost": 0.0,
                }

            row = rows_by_sale[resolved_sale_id]
            movement_type = (
                (getattr(movement, "movement_type", "") or "").strip().lower()
            )
            adjustment_kind = (
                getattr(movement, "adjustment_kind", "") or ""
            ).strip().lower() or None
            quantity = float(getattr(movement, "quantity", 0.0) or 0.0)
            delta_quantity = InventoryService._movement_stock_delta(
                movement_type=movement_type,
                quantity=quantity,
                adjustment_kind=adjustment_kind,
            )
            amount = float(InventoryService._resolve_movement_amount(movement) or 0.0)

            row["movement_count"] += 1
            if delta_quantity < 0:
                row["consumption_quantity"] = round(
                    float(row["consumption_quantity"]) + abs(float(delta_quantity)),
                    4,
                )
                row["consumption_cost"] = round(
                    float(row["consumption_cost"]) + amount,
                    4,
                )
            elif delta_quantity > 0:
                row["reversal_cost"] = round(
                    float(row["reversal_cost"]) + amount,
                    4,
                )

            row["net_consumption_cost"] = round(
                float(row["consumption_cost"]) - float(row["reversal_cost"]),
                4,
            )

        if not rows_by_sale:
            return []

        sales = Sale.query.filter(Sale.id.in_(set(rows_by_sale.keys()))).all()
        sales_by_id = {int(sale.id): sale for sale in sales}

        rows = []
        for row_sale_id in sorted(rows_by_sale.keys()):
            row = rows_by_sale[row_sale_id]
            sale_row = sales_by_id.get(row_sale_id)
            row["sale_number"] = getattr(sale_row, "sale_number", None)
            row["sale_date"] = getattr(sale_row, "date", None)
            rows.append(row)

        return rows

    @staticmethod
    def summarize_inventory_account_reconciliation(business_id: int):
        ledger_entries = InventoryService.list_inventory_ledger_entries(
            business_id=business_id
        )
        movements = InventoryService.list_movements(business_id=business_id)

        rows_by_account: dict[str, dict] = {}

        def _ensure_row(account_code: str):
            if account_code not in rows_by_account:
                rows_by_account[account_code] = {
                    "account_code": account_code,
                    "ledger_in": 0.0,
                    "ledger_out": 0.0,
                    "ledger_balance": 0.0,
                    "operational_in": 0.0,
                    "operational_out": 0.0,
                    "operational_balance": 0.0,
                    "difference": 0.0,
                }
            return rows_by_account[account_code]

        for entry in ledger_entries:
            if entry.destination_account_code:
                row = _ensure_row(entry.destination_account_code)
                row["ledger_in"] += float(entry.amount or 0.0)
            if entry.source_account_code:
                row = _ensure_row(entry.source_account_code)
                row["ledger_out"] += float(entry.amount or 0.0)

        for movement in movements:
            account_code = (movement.account_code or "").strip()
            if not account_code:
                continue

            row = _ensure_row(account_code)
            amount = InventoryService._resolve_movement_amount(movement)
            movement_type = (movement.movement_type or "").strip().lower()
            if movement_type in {"purchase", "adjustment", "wip_close"}:
                if movement_type == "adjustment":
                    adjustment_kind = (movement.adjustment_kind or "").strip().lower()
                    if adjustment_kind == "negative":
                        row["operational_out"] += amount
                    else:
                        row["operational_in"] += amount
                else:
                    row["operational_in"] += amount
            elif movement_type in {"consumption", "transfer", "waste"}:
                row["operational_out"] += amount

            expense_account_code = InventoryService._resolve_waste_expense_account_code(
                movement_type=movement_type
            )
            if expense_account_code:
                expense_row = _ensure_row(expense_account_code)
                expense_row["operational_in"] += amount

        items = []
        for account_code, row in sorted(
            rows_by_account.items(), key=lambda pair: pair[0]
        ):
            row["ledger_balance"] = round(row["ledger_in"] - row["ledger_out"], 2)
            row["operational_balance"] = round(
                row["operational_in"] - row["operational_out"],
                2,
            )
            row["difference"] = round(
                row["ledger_balance"] - row["operational_balance"],
                2,
            )
            row["ledger_in"] = round(row["ledger_in"], 2)
            row["ledger_out"] = round(row["ledger_out"], 2)
            row["operational_in"] = round(row["operational_in"], 2)
            row["operational_out"] = round(row["operational_out"], 2)
            items.append(row)
        return items

    @staticmethod
    def _build_stock_rebuild_snapshot(
        business_id: int,
        inventory_item_id: int | None = None,
        tolerance: float = 0.0001,
    ) -> dict:
        business = Business.query.get(business_id)
        if not business:
            raise ValueError("Negocio no encontrado")

        normalized_item_id = None
        if inventory_item_id is not None:
            normalized_item_id = int(inventory_item_id)
            if normalized_item_id <= 0:
                raise ValueError("inventory_item_id debe ser un entero positivo")

        movements = InventoryService.list_movements(
            business_id=business_id,
            inventory_item_id=normalized_item_id,
        )
        ordered_movements = sorted(
            movements,
            key=lambda movement: (
                getattr(movement, "movement_date", None) or datetime.min,
                int(getattr(movement, "id", 0) or 0),
            ),
        )

        expected_stock_by_item: dict[int, float] = {}
        negative_balance_issues: list[dict] = []
        referenced_item_ids: set[int] = set()

        for movement in ordered_movements:
            item_id = int(getattr(movement, "inventory_item_id", 0) or 0)
            if item_id <= 0:
                continue

            referenced_item_ids.add(item_id)
            movement_type = (
                (getattr(movement, "movement_type", "") or "").strip().lower()
            )
            adjustment_kind = (
                getattr(movement, "adjustment_kind", "") or ""
            ).strip().lower() or None
            quantity = float(getattr(movement, "quantity", 0.0) or 0.0)
            delta = InventoryService._movement_stock_delta(
                movement_type=movement_type,
                quantity=quantity,
                adjustment_kind=adjustment_kind,
            )
            running_balance = float(expected_stock_by_item.get(item_id, 0.0)) + delta
            expected_stock_by_item[item_id] = running_balance

            if running_balance < (-1 * abs(float(tolerance or 0.0001))):
                negative_balance_issues.append(
                    {
                        "movement_id": getattr(movement, "id", None),
                        "inventory_item_id": item_id,
                        "movement_type": movement_type,
                        "movement_date": getattr(movement, "movement_date", None),
                        "running_balance": round(running_balance, 4),
                    }
                )

        if normalized_item_id is not None:
            referenced_item_ids.add(normalized_item_id)

        if referenced_item_ids:
            items = (
                InventoryItem.query.filter(InventoryItem.id.in_(referenced_item_ids))
                .order_by(InventoryItem.name.asc())
                .all()
            )
        else:
            items = []

        items_by_id = {int(item.id): item for item in items}
        missing_inventory_item_ids = sorted(
            item_id for item_id in referenced_item_ids if item_id not in items_by_id
        )

        mismatches = []
        for item_id in sorted(items_by_id):
            item = items_by_id[item_id]
            expected_stock = round(float(expected_stock_by_item.get(item_id, 0.0)), 4)
            current_stock = round(float(getattr(item, "stock", 0.0) or 0.0), 4)
            difference = round(expected_stock - current_stock, 4)
            if abs(difference) <= abs(float(tolerance or 0.0001)):
                continue

            mismatches.append(
                {
                    "inventory_item_id": item_id,
                    "inventory_item_name": getattr(item, "name", None),
                    "current_stock": current_stock,
                    "expected_stock": expected_stock,
                    "difference": difference,
                }
            )

        return {
            "business_id": business_id,
            "inventory_item_id": normalized_item_id,
            "movement_count": len(ordered_movements),
            "item_count": len(items_by_id),
            "mismatch_count": len(mismatches),
            "negative_balance_issue_count": len(negative_balance_issues),
            "missing_item_count": len(missing_inventory_item_ids),
            "mismatches": mismatches,
            "negative_balance_issues": negative_balance_issues,
            "missing_inventory_item_ids": missing_inventory_item_ids,
        }

    @staticmethod
    def validate_stock_consistency_from_history(
        business_id: int,
        inventory_item_id: int | None = None,
        tolerance: float = 0.0001,
    ) -> dict:
        snapshot = InventoryService._build_stock_rebuild_snapshot(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            tolerance=tolerance,
        )
        snapshot["is_consistent"] = (
            snapshot["mismatch_count"] == 0
            and snapshot["negative_balance_issue_count"] == 0
            and snapshot["missing_item_count"] == 0
        )
        return snapshot

    @staticmethod
    def rebuild_stock_from_history(
        business_id: int,
        inventory_item_id: int | None = None,
        commit: bool = True,
        tolerance: float = 0.0001,
    ) -> dict:
        snapshot = InventoryService._build_stock_rebuild_snapshot(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            tolerance=tolerance,
        )

        updates = []
        for mismatch in snapshot["mismatches"]:
            if commit:
                item = InventoryItem.query.get(mismatch["inventory_item_id"])
                if not item:
                    continue
                item.stock = mismatch["expected_stock"]
            updates.append(
                {
                    "inventory_item_id": mismatch["inventory_item_id"],
                    "inventory_item_name": mismatch["inventory_item_name"],
                    "previous_stock": mismatch["current_stock"],
                    "new_stock": mismatch["expected_stock"],
                }
            )

        if commit and updates:
            db.session.commit()

        snapshot["commit_applied"] = bool(commit and updates)
        snapshot["updated_count"] = len(updates)
        snapshot["updates"] = updates
        snapshot["is_consistent_after_rebuild"] = (
            snapshot["negative_balance_issue_count"] == 0
            and snapshot["missing_item_count"] == 0
            and (snapshot["mismatch_count"] - len(updates) == 0)
        )
        return snapshot

    @staticmethod
    def upsert_sale_cost_breakdown(
        business_id: int,
        sale_id: int,
        production_cost: float,
        merchandise_cost: float,
        actor: str | None = None,
        source: str | None = "inventory_api",
        production_account_code: str = "1586",
        merchandise_account_code: str = "1587",
        notes: str | None = None,
    ) -> InventorySaleCostBreakdown:
        _ = actor, source
        sale = Sale.query.get_or_404(sale_id)
        if sale.business_id != business_id:
            raise ValueError("La venta no pertenece al negocio")

        production_amount = float(production_cost)
        merchandise_amount = float(merchandise_cost)
        if production_amount < 0 or merchandise_amount < 0:
            raise ValueError("Los costos de desglose no pueden ser negativos")

        production_code = (production_account_code or "").strip() or "1586"
        merchandise_code = (merchandise_account_code or "").strip() or "1587"

        breakdown = InventorySaleCostBreakdown.query.filter_by(sale_id=sale_id).first()
        if not breakdown:
            breakdown = InventorySaleCostBreakdown(
                business_id=business_id,
                sale_id=sale_id,
            )
            db.session.add(breakdown)

        breakdown.production_account_code = production_code
        breakdown.merchandise_account_code = merchandise_code
        breakdown.production_cost = production_amount
        breakdown.merchandise_cost = merchandise_amount
        breakdown.notes = notes
        db.session.commit()
        return breakdown

    @staticmethod
    def list_sale_cost_breakdowns(
        business_id: int,
        sale_id: int | None = None,
    ) -> list[InventorySaleCostBreakdown]:
        query = InventorySaleCostBreakdown.query.filter(
            InventorySaleCostBreakdown.business_id == business_id
        )
        if sale_id is not None:
            query = query.filter(InventorySaleCostBreakdown.sale_id == sale_id)
        return query.order_by(InventorySaleCostBreakdown.created_at.desc()).all()

    @staticmethod
    def _movement_stock_delta(
        movement_type: str,
        quantity: float,
        adjustment_kind: str | None = None,
    ) -> float:
        if movement_type in {"purchase", "adjustment"}:
            if movement_type == "adjustment" and adjustment_kind == "negative":
                return -float(quantity)
            return float(quantity)
        if movement_type in {"consumption", "transfer", "waste"}:
            return -float(quantity)
        return 0.0

    @staticmethod
    def _resolve_entry_unit_cost(
        quantity: float,
        unit_cost: float | None,
        total_cost: float | None,
    ) -> float | None:
        qty = float(quantity or 0.0)
        if qty <= 0:
            return None

        if total_cost not in (None, ""):
            total = float(total_cost)
            if total > 0:
                return total / qty

        if unit_cost not in (None, ""):
            resolved_unit_cost = float(unit_cost)
            if resolved_unit_cost > 0:
                return resolved_unit_cost

        return None

    @staticmethod
    def _recalculate_average_unit_cost(
        inventory_item: InventoryItem,
        previous_stock: float,
        entry_quantity: float,
        entry_unit_cost: float | None,
    ) -> None:
        if entry_quantity <= 0 or entry_unit_cost is None:
            return

        previous_stock_value = float(previous_stock or 0.0)
        previous_average_cost = float(inventory_item.average_unit_cost or 0.0)
        resulting_stock = previous_stock_value + float(entry_quantity)
        if resulting_stock <= 0:
            return

        weighted_total = (previous_stock_value * previous_average_cost) + (
            float(entry_quantity) * float(entry_unit_cost)
        )
        inventory_item.average_unit_cost = weighted_total / resulting_stock

    @staticmethod
    def _generate_auto_lot_code(business_id: int, inventory_item_id: int) -> str:
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"AUTO-{today}-{inventory_item_id}-"
        count = InventoryMovement.query.filter(
            InventoryMovement.business_id == business_id,
            InventoryMovement.inventory_item_id == inventory_item_id,
            InventoryMovement.lot_code.like(f"{prefix}%"),
        ).count()
        return f"{prefix}{count + 1:03d}"

    @staticmethod
    def list_stowage_card(
        business_id: int,
        inventory_item_id: int,
        lot_code: str,
        location: str | None = None,
    ):
        normalized_lot_code = (lot_code or "").strip()
        if not normalized_lot_code:
            raise ValueError("El lote es obligatorio para consultar tarjeta de estiba")

        normalized_location = (location or "").strip().lower() or None
        if (
            normalized_location
            and normalized_location not in InventoryService.ALLOWED_STOWAGE_LOCATIONS
        ):
            raise ValueError("Ubicacion no permitida para tarjeta de estiba")

        movements = (
            InventoryMovement.query.filter(
                InventoryMovement.business_id == business_id,
                InventoryMovement.inventory_item_id == inventory_item_id,
                InventoryMovement.lot_code == normalized_lot_code,
            )
            .order_by(InventoryMovement.movement_date.asc(), InventoryMovement.id.asc())
            .all()
        )

        running_balance = 0.0
        items = []
        for movement in movements:
            adjustment_kind = (
                getattr(movement, "adjustment_kind", "") or ""
            ).strip().lower() or None
            movement_type = (
                (getattr(movement, "movement_type", "") or "").strip().lower()
            )
            delta = InventoryService._movement_stock_delta(
                movement_type=movement_type,
                quantity=movement.quantity,
                adjustment_kind=adjustment_kind,
            )

            resolved_location = InventoryService._resolve_movement_location_for_stowage(
                movement=movement,
            )
            if normalized_location:
                delta = InventoryService._resolve_stowage_location_delta(
                    movement=movement,
                    location=normalized_location,
                )
                resolved_location = normalized_location

            if normalized_location and abs(float(delta)) <= 0:
                continue

            running_balance += delta
            items.append(
                {
                    "id": movement.id,
                    "movement_type": movement_type,
                    "adjustment_kind": adjustment_kind,
                    "destination": movement.destination,
                    "location": resolved_location,
                    "lot_code": movement.lot_code,
                    "quantity": movement.quantity,
                    "delta": delta,
                    "running_balance": running_balance,
                    "unit": movement.unit,
                    "movement_date": movement.movement_date,
                    "account_code": movement.account_code,
                    "supplier_name": movement.supplier_name,
                    "waste_reason": getattr(movement, "waste_reason", None),
                    "waste_responsible": getattr(movement, "waste_responsible", None),
                    "waste_evidence": getattr(movement, "waste_evidence", None),
                    "waste_evidence_file_url": getattr(
                        movement, "waste_evidence_file_url", None
                    ),
                    "reference_type": movement.reference_type,
                    "reference_id": movement.reference_id,
                    "document": movement.document,
                    "lot_date": movement.lot_date,
                    "lot_unit": movement.lot_unit,
                    "lot_conversion_factor": movement.lot_conversion_factor,
                    "notes": movement.notes,
                }
            )
        return items

    @staticmethod
    def _resolve_movement_location_for_stowage(movement) -> str:
        movement_type = (getattr(movement, "movement_type", "") or "").strip().lower()
        destination = (
            getattr(movement, "destination", "") or ""
        ).strip().lower() or None

        if movement_type == "wip_close":
            return destination or "finished_goods"
        if movement_type in {"transfer", "waste"} and destination:
            return destination
        return "warehouse"

    @staticmethod
    def _resolve_stowage_location_delta(movement, location: str) -> float:
        movement_type = (getattr(movement, "movement_type", "") or "").strip().lower()
        destination = (
            getattr(movement, "destination", "") or ""
        ).strip().lower() or None
        adjustment_kind = (
            getattr(movement, "adjustment_kind", "") or ""
        ).strip().lower() or None
        quantity = float(getattr(movement, "quantity", 0.0) or 0.0)

        if location == "warehouse":
            if movement_type == "purchase":
                return quantity
            if movement_type == "adjustment":
                return -quantity if adjustment_kind == "negative" else quantity
            if movement_type in {"consumption", "transfer"}:
                return -quantity
            if movement_type == "waste" and (destination in {None, "", "warehouse"}):
                return -quantity
            return 0.0

        if location == "wip":
            if movement_type == "transfer" and destination == "wip":
                return quantity
            if movement_type == "wip_close":
                return -quantity
            if movement_type == "waste" and destination == "wip":
                return -quantity
            return 0.0

        if location == "finished_goods":
            if movement_type == "wip_close" and destination == "finished_goods":
                return quantity
            if movement_type == "waste" and destination == "finished_goods":
                return -quantity
            return 0.0

        if location == "sales_floor":
            if movement_type == "transfer" and destination == "sales_floor":
                return quantity
            return 0.0

        return 0.0

    @staticmethod
    def list_wip_balances(
        business_id: int,
        status: str | None = None,
        inventory_item_id: int | None = None,
    ) -> list[InventoryWipBalance]:
        query = InventoryWipBalance.query.filter(
            InventoryWipBalance.business_id == business_id
        )
        if status:
            normalized_status = status.strip().lower()
            if normalized_status not in InventoryService.ALLOWED_WIP_STATUSES:
                raise ValueError("Estado WIP no permitido")
            query = query.filter(InventoryWipBalance.status == normalized_status)
        if inventory_item_id is not None:
            query = query.filter(
                InventoryWipBalance.inventory_item_id == inventory_item_id
            )

        return query.order_by(InventoryWipBalance.created_at.desc()).all()

    @staticmethod
    def create_wip_balance(
        business_id: int,
        inventory_item_id: int,
        quantity: float,
        unit: str,
        account_code: str,
        source_inventory_id: int | None = None,
        expiration_date: date | None = None,
        can_be_subproduct: bool = False,
        notes: str | None = None,
    ) -> InventoryWipBalance:
        _, wip_enabled = InventoryService._resolve_business_inventory_flows(business_id)
        if not wip_enabled:
            raise ValueError("El negocio no tiene habilitado el flujo WIP")

        inventory_item = InventoryService._get_item_or_404(inventory_item_id)
        InventoryService._validate_item_usage_for_destination(
            inventory_item=inventory_item,
            destination="wip",
        )

        movement = InventoryService.create_movement(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            movement_type="transfer",
            destination="wip",
            quantity=quantity,
            unit=unit,
            inventory_id=source_inventory_id,
            account_code=account_code,
            notes=notes,
        )

        resolved_expiration_date, expiration_source = (
            InventoryService._resolve_wip_expiration_reference(
                source_inventory_id=source_inventory_id,
                explicit_expiration_date=expiration_date,
            )
        )

        wip_balance = InventoryWipBalance(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            source_inventory_id=source_inventory_id,
            quantity=float(quantity),
            remaining_quantity=float(quantity),
            unit=movement.unit,
            status=InventoryWipBalance.STATUS_OPEN,
            can_be_subproduct=bool(can_be_subproduct),
            finished_location="finished_goods",
            expiration_date=resolved_expiration_date,
            expiration_source=expiration_source,
            notes=notes,
        )
        db.session.add(wip_balance)
        db.session.commit()
        return wip_balance

    @staticmethod
    def _resolve_wip_expiration_reference(
        source_inventory_id: int | None,
        explicit_expiration_date: date | None,
    ) -> tuple[date | None, str | None]:
        if explicit_expiration_date is not None:
            return explicit_expiration_date, "manual"

        if source_inventory_id is None:
            return None, None

        source_lot_movement = (
            InventoryMovement.query.filter(
                InventoryMovement.inventory_id == source_inventory_id,
                InventoryMovement.lot_date.isnot(None),
            )
            .order_by(
                InventoryMovement.movement_date.desc(), InventoryMovement.id.desc()
            )
            .first()
        )
        if source_lot_movement and source_lot_movement.lot_date is not None:
            return source_lot_movement.lot_date, "inventory_lot"

        return None, None

    @staticmethod
    def mark_wip_as_subproduct(
        business_id: int,
        wip_balance_id: int,
        can_be_subproduct: bool,
    ) -> InventoryWipBalance:
        wip_balance = InventoryWipBalance.query.get_or_404(wip_balance_id)
        if wip_balance.business_id != business_id:
            raise ValueError("El balance WIP no pertenece al negocio")

        wip_balance.can_be_subproduct = bool(can_be_subproduct)
        db.session.commit()
        return wip_balance

    @staticmethod
    def consume_wip_subproduct_for_recipe(
        business_id: int,
        wip_balance_id: int,
        consumed_quantity: float,
    ) -> InventoryWipBalance:
        wip_balance = InventoryWipBalance.query.get_or_404(wip_balance_id)
        if wip_balance.business_id != business_id:
            raise ValueError("El balance WIP no pertenece al negocio")
        if not wip_balance.can_be_subproduct:
            raise ValueError("El balance WIP no esta marcado como subproducto")

        return InventoryService.consume_wip_balance(
            business_id=business_id,
            wip_balance_id=wip_balance_id,
            consumed_quantity=consumed_quantity,
        )

    @staticmethod
    def consume_wip_balance(
        business_id: int,
        wip_balance_id: int,
        consumed_quantity: float,
    ) -> InventoryWipBalance:
        wip_balance = InventoryWipBalance.query.get_or_404(wip_balance_id)
        if wip_balance.business_id != business_id:
            raise ValueError("El balance WIP no pertenece al negocio")
        if wip_balance.status != InventoryWipBalance.STATUS_OPEN:
            raise ValueError("Solo se puede consumir balance WIP en estado abierto")
        if consumed_quantity is None or float(consumed_quantity) <= 0:
            raise ValueError("La cantidad consumida debe ser mayor que cero")

        new_remaining = float(wip_balance.remaining_quantity) - float(consumed_quantity)
        if new_remaining < 0:
            raise ValueError("La cantidad consumida excede el remanente en WIP")

        wip_balance.remaining_quantity = new_remaining
        if new_remaining == 0:
            wip_balance.status = InventoryWipBalance.STATUS_FINISHED

        db.session.commit()
        return wip_balance

    @staticmethod
    def finish_wip_balance(
        business_id: int,
        wip_balance_id: int,
        account_code: str,
        produced_product_id: int | None = None,
        notes: str | None = None,
    ) -> InventoryWipBalance:
        wip_balance = InventoryWipBalance.query.get_or_404(wip_balance_id)
        if wip_balance.business_id != business_id:
            raise ValueError("El balance WIP no pertenece al negocio")
        if wip_balance.status != InventoryWipBalance.STATUS_OPEN:
            raise ValueError("Solo se puede cerrar balance WIP en estado abierto")

        close_quantity = float(wip_balance.remaining_quantity or 0.0)
        if close_quantity <= 0:
            raise ValueError("El balance WIP no tiene remanente para cerrar")

        # Registro contable del pase WIP -> producto terminado; no altera stock de insumo.
        InventoryService.create_movement(
            business_id=business_id,
            inventory_item_id=wip_balance.inventory_item_id,
            movement_type="wip_close",
            destination="finished_goods",
            quantity=close_quantity,
            unit=wip_balance.unit,
            account_code=account_code,
            reference_type="wip_balance",
            reference_id=wip_balance.id,
            notes=notes,
        )

        produced_product = None
        if produced_product_id is not None:
            produced_product = Product.query.get_or_404(produced_product_id)
            if produced_product.business_id != business_id:
                raise ValueError("El producto terminado no pertenece al negocio")

        finished_location = "finished_goods"
        if produced_product and produced_product.goes_to_sales_floor:
            sales_floor_stock = InventoryService._get_or_create_sales_floor_stock(
                business_id=business_id,
                inventory_item_id=wip_balance.inventory_item_id,
            )
            sales_floor_stock.current_quantity = (
                float(sales_floor_stock.current_quantity or 0.0) + close_quantity
            )
            finished_location = "sales_floor"

        wip_balance.status = InventoryWipBalance.STATUS_FINISHED
        wip_balance.remaining_quantity = 0.0
        wip_balance.produced_product_id = (
            produced_product.id if produced_product else None
        )
        if produced_product and produced_product.can_be_subproduct:
            wip_balance.can_be_subproduct = True
        wip_balance.finished_location = finished_location
        if notes is not None:
            wip_balance.notes = notes
        db.session.commit()
        return wip_balance

    @staticmethod
    def mark_wip_waste(
        business_id: int,
        wip_balance_id: int,
        notes: str | None = None,
    ) -> InventoryWipBalance:
        wip_balance = InventoryWipBalance.query.get_or_404(wip_balance_id)
        if wip_balance.business_id != business_id:
            raise ValueError("El balance WIP no pertenece al negocio")
        if wip_balance.status != InventoryWipBalance.STATUS_OPEN:
            raise ValueError("Solo se puede marcar merma en balance WIP abierto")

        wip_balance.status = InventoryWipBalance.STATUS_WASTE
        wip_balance.remaining_quantity = 0.0
        if notes is not None:
            wip_balance.notes = notes
        db.session.commit()
        return wip_balance

    @staticmethod
    def list_account_adoptions(
        business_id: int,
        include_inactive: bool = False,
    ) -> list[BusinessAccountAdoption]:
        query = BusinessAccountAdoption.query.filter(
            BusinessAccountAdoption.business_id == business_id
        )
        if not include_inactive:
            query = query.filter(BusinessAccountAdoption.is_active.is_(True))

        return query.order_by(BusinessAccountAdoption.adopted_at.desc()).all()

    @staticmethod
    def list_account_adoption_audits(
        business_id: int,
        account_code: str | None = None,
    ) -> list[BusinessAccountAdoptionAudit]:
        query = BusinessAccountAdoptionAudit.query.filter(
            BusinessAccountAdoptionAudit.business_id == business_id
        )
        if account_code:
            normalized_code = account_code.strip()
            account = ACAccount.query.filter_by(code=normalized_code).first()
            if account:
                query = query.filter(
                    BusinessAccountAdoptionAudit.account_id == account.id
                )
            else:
                return []

        return query.order_by(BusinessAccountAdoptionAudit.created_at.desc()).all()

    @staticmethod
    def list_catalog_accounts() -> list[ACAccount]:
        return ACAccount.query.order_by(ACAccount.code.asc()).all()

    @staticmethod
    def update_catalog_account(
        account_code: str,
        new_code: str,
        new_name: str,
    ) -> ACAccount:
        normalized_code = (account_code or "").strip()
        target_code = (new_code or "").strip()
        target_name = (new_name or "").strip()

        if not normalized_code:
            raise ValueError("El codigo de cuenta es obligatorio")
        if not target_code:
            raise ValueError("El nuevo codigo de cuenta es obligatorio")
        if not target_name:
            raise ValueError("El nuevo nombre de cuenta es obligatorio")

        account = ACAccount.query.filter_by(code=normalized_code).first()
        if not account:
            raise ValueError("La cuenta indicada no existe en el nomenclador general")

        if account.is_normative:
            raise ValueError(
                "El nomenclador general es normativo y no permite editar codigo ni nombre"
            )

        duplicate = ACAccount.query.filter(
            ACAccount.code == target_code,
            ACAccount.id != account.id,
        ).first()
        if duplicate:
            raise ValueError("Ya existe otra cuenta con el codigo indicado")

        account.code = target_code
        account.name = target_name
        db.session.commit()
        return account

    @staticmethod
    def adopt_account_by_code(
        business_id: int,
        account_code: str,
        actor: str | None = None,
        source: str | None = "inventory_api",
    ) -> BusinessAccountAdoption:
        normalized_code = (account_code or "").strip()
        if not normalized_code:
            raise ValueError("El codigo de cuenta es obligatorio")

        account = ACAccount.query.filter_by(code=normalized_code).first()
        if not account:
            raise ValueError("La cuenta indicada no existe en el nomenclador general")

        adoption = BusinessAccountAdoption.query.filter_by(
            business_id=business_id,
            account_id=account.id,
        ).first()

        if adoption and adoption.is_active:
            InventoryService._log_account_adoption_event(
                business_id=business_id,
                account_id=account.id,
                action="adopt_noop",
                previous_is_active=True,
                new_is_active=True,
                actor=actor,
                source=source,
            )
            return adoption

        if adoption and not adoption.is_active:
            previous_is_active = adoption.is_active
            adoption.is_active = True
            adoption.removed_at = None
            db.session.commit()
            InventoryService._log_account_adoption_event(
                business_id=business_id,
                account_id=account.id,
                action="reactivate",
                previous_is_active=previous_is_active,
                new_is_active=True,
                actor=actor,
                source=source,
            )
            return adoption

        adoption = BusinessAccountAdoption(
            business_id=business_id,
            account_id=account.id,
            is_active=True,
        )
        db.session.add(adoption)
        db.session.commit()
        InventoryService._log_account_adoption_event(
            business_id=business_id,
            account_id=account.id,
            action="adopt",
            previous_is_active=None,
            new_is_active=True,
            actor=actor,
            source=source,
        )
        return adoption

    @staticmethod
    def unadopt_account_by_code(
        business_id: int,
        account_code: str,
        actor: str | None = None,
        source: str | None = "inventory_api",
    ) -> BusinessAccountAdoption:
        normalized_code = (account_code or "").strip()
        if not normalized_code:
            raise ValueError("El codigo de cuenta es obligatorio")

        account = ACAccount.query.filter_by(code=normalized_code).first()
        if not account:
            raise ValueError("La cuenta indicada no existe en el nomenclador general")

        adoption = BusinessAccountAdoption.query.filter_by(
            business_id=business_id,
            account_id=account.id,
        ).first()
        if not adoption or not adoption.is_active:
            raise ValueError("La cuenta no esta adoptada en este negocio")

        movements_in_use = InventoryMovement.query.filter_by(
            business_id=business_id,
            account_code=normalized_code,
        ).first()
        if movements_in_use:
            raise ValueError(
                "No se puede desadoptar la cuenta porque ya tiene movimientos contables asociados"
            )

        active_subaccount = BusinessSubAccount.query.filter_by(
            business_id=business_id,
            business_account_adoption_id=adoption.id,
            is_active=True,
        ).first()
        if active_subaccount:
            raise ValueError(
                "No se puede desadoptar la cuenta porque tiene subcuentas activas asociadas"
            )

        previous_is_active = adoption.is_active
        adoption.is_active = False
        adoption.removed_at = db.func.current_timestamp()
        db.session.commit()
        InventoryService._log_account_adoption_event(
            business_id=business_id,
            account_id=account.id,
            action="unadopt",
            previous_is_active=previous_is_active,
            new_is_active=False,
            actor=actor,
            source=source,
        )
        return adoption

    @staticmethod
    def validate_account_is_adopted(business_id: int, account_code: str) -> ACAccount:
        normalized_code = (account_code or "").strip()
        if not normalized_code:
            raise ValueError("El codigo de cuenta es obligatorio")

        account = ACAccount.query.filter_by(code=normalized_code).first()
        if not account:
            raise ValueError("La cuenta indicada no existe en el nomenclador general")

        adoption = BusinessAccountAdoption.query.filter_by(
            business_id=business_id,
            account_id=account.id,
            is_active=True,
        ).first()
        if not adoption:
            raise ValueError("La cuenta no esta adoptada en este negocio")

        return account

    @staticmethod
    def _get_active_adoption_or_fail(
        business_id: int,
        account_code: str,
    ) -> BusinessAccountAdoption:
        account = InventoryService.validate_account_is_adopted(
            business_id=business_id,
            account_code=account_code,
        )
        adoption = BusinessAccountAdoption.query.filter_by(
            business_id=business_id,
            account_id=account.id,
            is_active=True,
        ).first()
        if not adoption:
            raise ValueError("La cuenta no esta adoptada en este negocio")
        return adoption

    @staticmethod
    def list_business_subaccounts(
        business_id: int,
        include_inactive: bool = False,
        account_code: str | None = None,
    ) -> list[BusinessSubAccount]:
        query = BusinessSubAccount.query.filter(
            BusinessSubAccount.business_id == business_id
        )
        if not include_inactive:
            query = query.filter(BusinessSubAccount.is_active.is_(True))

        normalized_code = (account_code or "").strip()
        if normalized_code:
            adoption = InventoryService._get_active_adoption_or_fail(
                business_id=business_id,
                account_code=normalized_code,
            )
            query = query.filter(
                BusinessSubAccount.business_account_adoption_id == adoption.id
            )

        return query.order_by(BusinessSubAccount.code.asc()).all()

    @staticmethod
    def create_business_subaccount(
        business_id: int,
        account_code: str,
        code: str,
        name: str,
        actor: str | None = None,
        source: str | None = "inventory_api",
        template_subaccount_id: int | None = None,
    ) -> BusinessSubAccount:
        normalized_sub_code = (code or "").strip()
        normalized_sub_name = (name or "").strip()
        if not normalized_sub_code:
            raise ValueError("El codigo de subcuenta es obligatorio")
        if not normalized_sub_name:
            raise ValueError("El nombre de subcuenta es obligatorio")

        adoption = InventoryService._get_active_adoption_or_fail(
            business_id=business_id,
            account_code=account_code,
        )

        duplicate = BusinessSubAccount.query.filter_by(
            business_id=business_id,
            code=normalized_sub_code,
        ).first()
        if duplicate:
            raise ValueError("Ya existe una subcuenta con ese codigo en el negocio")

        subaccount = BusinessSubAccount(
            business_id=business_id,
            business_account_adoption_id=adoption.id,
            template_subaccount_id=template_subaccount_id,
            code=normalized_sub_code,
            name=normalized_sub_name,
            is_active=True,
        )
        db.session.add(subaccount)
        db.session.commit()

        InventoryService._log_business_subaccount_event(
            business_id=business_id,
            business_sub_account_id=subaccount.id,
            business_account_adoption_id=adoption.id,
            action="create",
            actor=actor,
            source=source,
            previous_code=None,
            new_code=subaccount.code,
            previous_name=None,
            new_name=subaccount.name,
            previous_is_active=None,
            new_is_active=subaccount.is_active,
        )
        return subaccount

    @staticmethod
    def update_business_subaccount(
        business_id: int,
        business_sub_account_id: int,
        code: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
        actor: str | None = None,
        source: str | None = "inventory_api",
    ) -> BusinessSubAccount:
        subaccount = BusinessSubAccount.query.get_or_404(business_sub_account_id)
        if subaccount.business_id != business_id:
            raise ValueError("La subcuenta no pertenece al negocio")

        previous_code = subaccount.code
        previous_name = subaccount.name
        previous_is_active = subaccount.is_active

        if code is not None:
            normalized_code = code.strip()
            if not normalized_code:
                raise ValueError("El codigo de subcuenta es obligatorio")
            duplicate = BusinessSubAccount.query.filter(
                BusinessSubAccount.business_id == business_id,
                BusinessSubAccount.code == normalized_code,
                BusinessSubAccount.id != subaccount.id,
            ).first()
            if duplicate:
                raise ValueError("Ya existe una subcuenta con ese codigo en el negocio")
            subaccount.code = normalized_code

        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise ValueError("El nombre de subcuenta es obligatorio")
            subaccount.name = normalized_name

        if is_active is not None:
            subaccount.is_active = bool(is_active)

        db.session.commit()

        InventoryService._log_business_subaccount_event(
            business_id=business_id,
            business_sub_account_id=subaccount.id,
            business_account_adoption_id=subaccount.business_account_adoption_id,
            action="update",
            actor=actor,
            source=source,
            previous_code=previous_code,
            new_code=subaccount.code,
            previous_name=previous_name,
            new_name=subaccount.name,
            previous_is_active=previous_is_active,
            new_is_active=subaccount.is_active,
        )
        return subaccount

    @staticmethod
    def _log_business_subaccount_event(
        business_id: int,
        business_sub_account_id: int | None,
        business_account_adoption_id: int,
        action: str,
        actor: str | None,
        source: str | None,
        previous_code: str | None,
        new_code: str | None,
        previous_name: str | None,
        new_name: str | None,
        previous_is_active,
        new_is_active,
    ):
        audit = BusinessSubAccountAudit(
            business_id=business_id,
            business_sub_account_id=business_sub_account_id,
            business_account_adoption_id=business_account_adoption_id,
            action=action,
            actor=(actor or "").strip() or None,
            source=(source or "").strip() or None,
            previous_code=previous_code,
            new_code=new_code,
            previous_name=previous_name,
            new_name=new_name,
            previous_is_active=previous_is_active,
            new_is_active=new_is_active,
        )
        db.session.add(audit)
        db.session.commit()

    @staticmethod
    def _log_account_adoption_event(
        business_id: int,
        account_id: int,
        action: str,
        previous_is_active,
        new_is_active,
        actor: str | None,
        source: str | None,
    ):
        audit = BusinessAccountAdoptionAudit(
            business_id=business_id,
            account_id=account_id,
            action=action,
            actor=(actor or "").strip() or None,
            source=(source or "").strip() or None,
            previous_is_active=previous_is_active,
            new_is_active=new_is_active,
        )
        db.session.add(audit)
        db.session.commit()
