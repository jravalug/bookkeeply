import re
import unicodedata
from datetime import UTC, datetime
from datetime import timedelta

from app import db
from app.models import (
    ACAccount,
    Business,
    BusinessAccountAdoption,
    BusinessAccountAdoptionAudit,
    Inventory,
    InventoryItem,
    InventoryProductGeneric,
    InventoryProductSpecific,
    InventorySalesFloorStock,
    InventoryMovement,
    InventoryWipBalance,
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
    ALLOWED_WIP_STATUSES = {
        InventoryWipBalance.STATUS_OPEN,
        InventoryWipBalance.STATUS_FINISHED,
        InventoryWipBalance.STATUS_WASTE,
    }

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
    def transfer_to_sales_floor(
        business_id: int,
        inventory_item_id: int,
        quantity: float,
        unit: str,
        account_code: str,
        lot_code: str | None = None,
        notes: str | None = None,
    ):
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
    def create_movement(
        business_id: int,
        inventory_item_id: int,
        movement_type: str,
        quantity: float,
        unit: str,
        destination: str | None = None,
        inventory_id: int | None = None,
        unit_cost: float | None = None,
        total_cost: float | None = None,
        account_code: str | None = None,
        idempotency_key: str | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
        lot_code: str | None = None,
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

        if idempotency_key:
            existing = InventoryMovement.query.filter_by(
                idempotency_key=idempotency_key
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

        qty = float(quantity)
        delta = InventoryService._movement_stock_delta(
            movement_type=movement_type, quantity=qty
        )

        new_stock = (inventory_item.stock or 0.0) + delta
        if new_stock < 0:
            raise ValueError("No hay existencia suficiente para realizar la salida")

        inventory_item.stock = new_stock

        movement = InventoryMovement(
            business_id=business_id,
            inventory_item_id=inventory_item.id,
            inventory_id=inventory_record.id if inventory_record else None,
            movement_type=movement_type,
            destination=destination,
            lot_code=normalized_lot_code,
            quantity=qty,
            unit=normalized_unit,
            unit_cost=unit_cost,
            total_cost=total_cost,
            account_code=normalized_account_code,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            document=document,
            notes=notes,
        )
        db.session.add(movement)
        db.session.commit()
        return movement

    @staticmethod
    def _movement_stock_delta(movement_type: str, quantity: float) -> float:
        if movement_type in {"purchase", "adjustment"}:
            return float(quantity)
        if movement_type in {"consumption", "transfer", "waste"}:
            return -float(quantity)
        return 0.0

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
    ):
        normalized_lot_code = (lot_code or "").strip()
        if not normalized_lot_code:
            raise ValueError("El lote es obligatorio para consultar tarjeta de estiba")

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
            delta = InventoryService._movement_stock_delta(
                movement_type=movement.movement_type,
                quantity=movement.quantity,
            )
            running_balance += delta
            items.append(
                {
                    "id": movement.id,
                    "movement_type": movement.movement_type,
                    "destination": movement.destination,
                    "lot_code": movement.lot_code,
                    "quantity": movement.quantity,
                    "delta": delta,
                    "running_balance": running_balance,
                    "unit": movement.unit,
                    "movement_date": movement.movement_date,
                    "account_code": movement.account_code,
                    "reference_type": movement.reference_type,
                    "reference_id": movement.reference_id,
                    "document": movement.document,
                    "notes": movement.notes,
                }
            )
        return items

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
        notes: str | None = None,
    ) -> InventoryWipBalance:
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

        wip_balance = InventoryWipBalance(
            business_id=business_id,
            inventory_item_id=inventory_item_id,
            source_inventory_id=source_inventory_id,
            quantity=float(quantity),
            remaining_quantity=float(quantity),
            unit=movement.unit,
            status=InventoryWipBalance.STATUS_OPEN,
            notes=notes,
        )
        db.session.add(wip_balance)
        db.session.commit()
        return wip_balance

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

        wip_balance.status = InventoryWipBalance.STATUS_FINISHED
        wip_balance.remaining_quantity = 0.0
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
    def reject_catalog_account_update():
        raise ValueError(
            "El nomenclador general es normativo y no permite editar codigo ni nombre"
        )

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
