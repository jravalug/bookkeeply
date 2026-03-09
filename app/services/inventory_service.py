from app import db
from app.models import (
    ACAccount,
    Business,
    BusinessAccountAdoption,
    BusinessAccountAdoptionAudit,
    Inventory,
    InventoryItem,
    InventoryMovement,
    InventoryWipBalance,
    Supply,
)
from app.utils.slug_utils import get_business_by_slugs


class InventoryService:
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
    def create_item(name: str, unit: str):
        """Crea y persiste un nuevo item de inventario."""
        new_item = InventoryItem(name=name, unit=unit)
        db.session.add(new_item)
        db.session.commit()
        return new_item

    @staticmethod
    def update_item(inventory_item_id: int, name: str, unit: str):
        """Actualiza nombre y unidad de un item de inventario existente."""
        inventory_item = InventoryService._get_item_or_404(inventory_item_id)
        inventory_item.name = name
        inventory_item.unit = unit
        db.session.commit()
        return inventory_item

    @staticmethod
    def list_supplies(business_id: int, include_inactive: bool = False) -> list[Supply]:
        query = Supply.query.filter(Supply.business_id == business_id)
        if not include_inactive:
            query = query.filter(Supply.is_active.is_(True))
        return query.order_by(Supply.product_surtido.asc()).all()

    @staticmethod
    def create_supply(
        business_id: int,
        inventory_item_id: int,
        product_surtido: str,
        is_active: bool = True,
    ) -> Supply:
        inventory_item = InventoryService._get_item_or_404(inventory_item_id)

        normalized_surtido = (product_surtido or "").strip()
        if not normalized_surtido:
            raise ValueError("El surtido del insumo es obligatorio")

        existing_supply = Supply.query.filter(
            Supply.business_id == business_id,
            Supply.product_surtido == normalized_surtido,
        ).first()
        if existing_supply:
            raise ValueError("Ya existe un insumo con ese surtido en el negocio")

        new_supply = Supply(
            business_id=business_id,
            inventory_item_id=inventory_item.id,
            product_surtido=normalized_surtido,
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
        product_surtido: str,
        is_active: bool,
    ) -> Supply:
        supply = Supply.query.get_or_404(supply_id)
        if supply.business_id != business_id:
            raise ValueError("El insumo no pertenece al negocio")

        inventory_item = InventoryService._get_item_or_404(inventory_item_id)

        normalized_surtido = (product_surtido or "").strip()
        if not normalized_surtido:
            raise ValueError("El surtido del insumo es obligatorio")

        existing_supply = Supply.query.filter(
            Supply.business_id == business_id,
            Supply.product_surtido == normalized_surtido,
            Supply.id != supply.id,
        ).first()
        if existing_supply:
            raise ValueError("Ya existe un insumo con ese surtido en el negocio")

        supply.inventory_item_id = inventory_item.id
        supply.product_surtido = normalized_surtido
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

        delta = 0.0
        qty = float(quantity)
        if movement_type == "purchase":
            delta = qty
        elif movement_type in {"consumption", "transfer", "waste"}:
            delta = -qty
        elif movement_type == "adjustment":
            delta = qty

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
