from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from datetime import datetime
from app.forms import InventoryItemForm
from app.services import InventoryService

bp = Blueprint(
    "inventory",
    __name__,
    url_prefix="/clients/<string:client_slug>/business/<string:business_slug>/inventory",
)

inventory_service = InventoryService()


@bp.route("/item/list", methods=["GET", "POST"])
def item_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return redirect(url_for("client.list_clients"))

    form = InventoryItemForm()

    if form.validate_on_submit():
        inventory_service.create_item(name=form.name.data, unit=form.unit.data)

        flash("Articulo de inventario agregado correctamente", "success")
        return redirect(
            url_for(
                "inventory.item_list",
                client_slug=business.client.slug,
                business_slug=business.slug,
            )
        )

    inventory_items_list = inventory_service.get_all_items()

    return render_template(
        "inventory/item_list.html",
        business=business,
        inventory_items=inventory_items_list,
        form=form,
    )


@bp.route("/<int:inventory_item_id>", methods=["POST"])
def item_update(client_slug, business_slug, inventory_item_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return redirect(url_for("client.list_clients"))

    inventory_service.update_item(
        inventory_item_id=inventory_item_id,
        name=request.form["name"],
        unit=request.form["unit"],
    )
    flash("Articulo de inventario actualizado correctamente", "success")
    return redirect(
        url_for(
            "inventory.item_list",
            client_slug=business.client.slug,
            business_slug=business.slug,
        )
    )


@bp.route("/supply/list", methods=["GET"])
def supply_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    supplies = inventory_service.list_supplies(
        business_id=business.id,
        include_inactive=include_inactive,
    )
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": supply.id,
                    "business_id": supply.business_id,
                    "inventory_item_id": supply.inventory_item_id,
                    "inventory_item_name": supply.inventory_item.name,
                    "product_specific_id": supply.product_specific_id,
                    "product_specific_name": (
                        supply.product_specific.name
                        if supply.product_specific
                        else None
                    ),
                    "product_generic_name": (
                        supply.product_specific.generic.name
                        if supply.product_specific and supply.product_specific.generic
                        else None
                    ),
                    "product_variant": supply.product_variant,
                    "is_active": supply.is_active,
                }
                for supply in supplies
            ],
        }
    )


@bp.route("/supply/create", methods=["POST"])
def supply_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    try:
        supply = inventory_service.create_supply(
            business_id=business.id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            product_variant=str(payload.get("product_variant", "")),
            product_specific_id=(
                int(payload.get("product_specific_id"))
                if payload.get("product_specific_id") not in (None, "")
                else None
            ),
            is_active=str(payload.get("is_active", "true")).lower() == "true",
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": supply.id,
                    "business_id": supply.business_id,
                    "inventory_item_id": supply.inventory_item_id,
                    "product_specific_id": supply.product_specific_id,
                    "product_variant": supply.product_variant,
                    "is_active": supply.is_active,
                },
            }
        ),
        201,
    )


@bp.route("/supply/<int:supply_id>/update", methods=["POST"])
def supply_update(client_slug, business_slug, supply_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    try:
        supply = inventory_service.update_supply(
            business_id=business.id,
            supply_id=supply_id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            product_variant=str(payload.get("product_variant", "")),
            product_specific_id=(
                int(payload.get("product_specific_id"))
                if payload.get("product_specific_id") not in (None, "")
                else None
            ),
            is_active=str(payload.get("is_active", "true")).lower() == "true",
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": supply.id,
                "business_id": supply.business_id,
                "inventory_item_id": supply.inventory_item_id,
                "product_specific_id": supply.product_specific_id,
                "product_variant": supply.product_variant,
                "is_active": supply.is_active,
            },
        }
    )


@bp.route("/catalog/generic/list", methods=["GET"])
def catalog_generic_list(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    items = inventory_service.list_product_generics(include_inactive=include_inactive)
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "is_active": item.is_active,
                }
                for item in items
            ],
        }
    )


@bp.route("/catalog/generic/create", methods=["POST"])
def catalog_generic_create(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        item = inventory_service.create_product_generic(
            name=str(payload.get("name", ""))
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify({"ok": True, "item": {"id": item.id, "name": item.name}}), 201


@bp.route("/catalog/specific/list", methods=["GET"])
def catalog_specific_list(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    product_generic_id = request.args.get("product_generic_id", type=int)
    items = inventory_service.list_product_specifics(
        product_generic_id=product_generic_id,
        include_inactive=include_inactive,
    )
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": item.id,
                    "generic_id": item.generic_id,
                    "generic_name": item.generic.name if item.generic else None,
                    "name": item.name,
                    "is_active": item.is_active,
                }
                for item in items
            ],
        }
    )


@bp.route("/catalog/specific/create", methods=["POST"])
def catalog_specific_create(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        item = inventory_service.create_product_specific(
            product_generic_id=int(payload.get("product_generic_id")),
            name=str(payload.get("name", "")),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": item.id,
                    "generic_id": item.generic_id,
                    "name": item.name,
                },
            }
        ),
        201,
    )


@bp.route("/supply/<int:supply_id>/delete", methods=["POST"])
def supply_delete(client_slug, business_slug, supply_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    try:
        inventory_service.delete_supply(
            business_id=business.id,
            supply_id=supply_id,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify({"ok": True, "message": "Insumo eliminado correctamente"})


@bp.route("/movement/list", methods=["GET"])
def movement_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    start_date = None
    end_date = None

    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Formato de fecha invalido. Use ISO 8601 (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)",
                }
            ),
            400,
        )

    inventory_item_id = request.args.get("inventory_item_id", type=int)
    lot_code = request.args.get("lot_code")
    movements = inventory_service.list_movements(
        business_id=business.id,
        inventory_item_id=inventory_item_id,
        lot_code=lot_code,
        start_date=start_date,
        end_date=end_date,
    )
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": movement.id,
                    "business_id": movement.business_id,
                    "inventory_item_id": movement.inventory_item_id,
                    "movement_type": movement.movement_type,
                    "destination": movement.destination,
                    "lot_code": movement.lot_code,
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "account_code": movement.account_code,
                    "movement_date": (
                        movement.movement_date.isoformat()
                        if movement.movement_date
                        else None
                    ),
                }
                for movement in movements
            ],
        }
    )


@bp.route("/movement/create", methods=["POST"])
def movement_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    def _raw(name, default=None):
        if isinstance(payload, dict):
            return payload.get(name, default)
        return payload.get(name, default)

    def _to_int(name):
        value = _raw(name)
        if value in (None, ""):
            return None
        return int(value)

    def _to_float(name):
        value = _raw(name)
        if value in (None, ""):
            return None
        return float(value)

    try:
        movement = inventory_service.create_movement(
            business_id=business.id,
            inventory_item_id=int(_raw("inventory_item_id")),
            movement_type=str(_raw("movement_type", "")),
            destination=_raw("destination"),
            quantity=float(_raw("quantity", 0)),
            unit=str(_raw("unit", "")),
            inventory_id=_to_int("inventory_id"),
            unit_cost=_to_float("unit_cost"),
            total_cost=_to_float("total_cost"),
            account_code=_raw("account_code"),
            idempotency_key=_raw("idempotency_key"),
            reference_type=_raw("reference_type"),
            reference_id=_to_int("reference_id"),
            lot_code=_raw("lot_code"),
            document=_raw("document"),
            notes=_raw("notes"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": movement.id,
                    "movement_type": movement.movement_type,
                    "destination": movement.destination,
                    "lot_code": movement.lot_code,
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "account_code": movement.account_code,
                },
            }
        ),
        201,
    )


@bp.route("/movement/stowage-card", methods=["GET"])
def movement_stowage_card(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    inventory_item_id = request.args.get("inventory_item_id", type=int)
    lot_code = request.args.get("lot_code")

    if inventory_item_id is None:
        return (
            jsonify({"ok": False, "message": "inventory_item_id es obligatorio"}),
            400,
        )

    try:
        card_items = inventory_service.list_stowage_card(
            business_id=business.id,
            inventory_item_id=inventory_item_id,
            lot_code=lot_code or "",
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "inventory_item_id": inventory_item_id,
                "lot_code": (lot_code or "").strip(),
                "entries": [
                    {
                        "id": row["id"],
                        "movement_type": row["movement_type"],
                        "destination": row["destination"],
                        "lot_code": row["lot_code"],
                        "quantity": row["quantity"],
                        "delta": row["delta"],
                        "running_balance": row["running_balance"],
                        "unit": row["unit"],
                        "movement_date": (
                            row["movement_date"].isoformat()
                            if row["movement_date"]
                            else None
                        ),
                        "account_code": row["account_code"],
                        "reference_type": row["reference_type"],
                        "reference_id": row["reference_id"],
                        "document": row["document"],
                        "notes": row["notes"],
                    }
                    for row in card_items
                ],
            },
        }
    )


@bp.route("/sales-floor/list", methods=["GET"])
def sales_floor_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    items = inventory_service.list_sales_floor_stocks(business_id=business.id)
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": item.id,
                    "business_id": item.business_id,
                    "inventory_item_id": item.inventory_item_id,
                    "inventory_item_name": (
                        item.inventory_item.name if item.inventory_item else None
                    ),
                    "current_quantity": item.current_quantity,
                    "min_quantity": item.min_quantity,
                    "max_quantity": item.max_quantity,
                }
                for item in items
            ],
        }
    )


@bp.route("/sales-floor/configure", methods=["POST"])
def sales_floor_configure(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        item = inventory_service.configure_sales_floor_stock(
            business_id=business.id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            min_quantity=float(payload.get("min_quantity", 0)),
            max_quantity=float(payload.get("max_quantity", 0)),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": item.id,
                "business_id": item.business_id,
                "inventory_item_id": item.inventory_item_id,
                "current_quantity": item.current_quantity,
                "min_quantity": item.min_quantity,
                "max_quantity": item.max_quantity,
            },
        }
    )


@bp.route("/sales-floor/transfer", methods=["POST"])
def sales_floor_transfer(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        movement, stock = inventory_service.transfer_to_sales_floor(
            business_id=business.id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            quantity=float(payload.get("quantity", 0)),
            unit=str(payload.get("unit", "")),
            account_code=str(payload.get("account_code", "")),
            lot_code=payload.get("lot_code"),
            notes=payload.get("notes"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "movement_id": movement.id,
                    "movement_type": movement.movement_type,
                    "destination": movement.destination,
                    "inventory_item_id": movement.inventory_item_id,
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "lot_code": movement.lot_code,
                    "sales_floor_current_quantity": stock.current_quantity,
                },
            }
        ),
        201,
    )


@bp.route("/sales-floor/alerts", methods=["GET"])
def sales_floor_alerts(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    items = inventory_service.list_sales_floor_alerts(business_id=business.id)
    return jsonify({"ok": True, "items": items})


@bp.route("/wip/list", methods=["GET"])
def wip_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    status = request.args.get("status")
    inventory_item_id = request.args.get("inventory_item_id", type=int)

    try:
        balances = inventory_service.list_wip_balances(
            business_id=business.id,
            status=status,
            inventory_item_id=inventory_item_id,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": balance.id,
                    "business_id": balance.business_id,
                    "inventory_item_id": balance.inventory_item_id,
                    "quantity": balance.quantity,
                    "remaining_quantity": balance.remaining_quantity,
                    "unit": balance.unit,
                    "status": balance.status,
                    "notes": balance.notes,
                }
                for balance in balances
            ],
        }
    )


@bp.route("/wip/create", methods=["POST"])
def wip_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    source_inventory_id = payload.get("source_inventory_id")
    try:
        balance = inventory_service.create_wip_balance(
            business_id=business.id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            quantity=float(payload.get("quantity", 0)),
            unit=str(payload.get("unit", "")),
            account_code=str(payload.get("account_code", "")),
            source_inventory_id=(
                int(source_inventory_id)
                if source_inventory_id not in (None, "")
                else None
            ),
            notes=payload.get("notes"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": balance.id,
                    "inventory_item_id": balance.inventory_item_id,
                    "quantity": balance.quantity,
                    "remaining_quantity": balance.remaining_quantity,
                    "unit": balance.unit,
                    "status": balance.status,
                },
            }
        ),
        201,
    )


@bp.route("/wip/<int:wip_balance_id>/consume", methods=["POST"])
def wip_consume(client_slug, business_slug, wip_balance_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        balance = inventory_service.consume_wip_balance(
            business_id=business.id,
            wip_balance_id=wip_balance_id,
            consumed_quantity=float(payload.get("consumed_quantity", 0)),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": balance.id,
                "remaining_quantity": balance.remaining_quantity,
                "status": balance.status,
            },
        }
    )


@bp.route("/wip/<int:wip_balance_id>/finish", methods=["POST"])
def wip_finish(client_slug, business_slug, wip_balance_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        balance = inventory_service.finish_wip_balance(
            business_id=business.id,
            wip_balance_id=wip_balance_id,
            account_code=payload.get("account_code"),
            notes=payload.get("notes"),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": balance.id,
                "remaining_quantity": balance.remaining_quantity,
                "status": balance.status,
            },
        }
    )


@bp.route("/wip/<int:wip_balance_id>/waste", methods=["POST"])
def wip_waste(client_slug, business_slug, wip_balance_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        balance = inventory_service.mark_wip_waste(
            business_id=business.id,
            wip_balance_id=wip_balance_id,
            notes=payload.get("notes"),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": balance.id,
                "remaining_quantity": balance.remaining_quantity,
                "status": balance.status,
            },
        }
    )


@bp.route("/account-adoption/list", methods=["GET"])
def account_adoption_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    adoptions = inventory_service.list_account_adoptions(
        business_id=business.id,
        include_inactive=include_inactive,
    )

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": adoption.id,
                    "business_id": adoption.business_id,
                    "account_id": adoption.account_id,
                    "account_code": adoption.account.code,
                    "account_name": adoption.account.name,
                    "is_active": adoption.is_active,
                    "adopted_at": (
                        adoption.adopted_at.isoformat() if adoption.adopted_at else None
                    ),
                    "removed_at": (
                        adoption.removed_at.isoformat() if adoption.removed_at else None
                    ),
                }
                for adoption in adoptions
            ],
        }
    )


@bp.route("/account-adoption/adopt", methods=["POST"])
def account_adoption_adopt(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    try:
        adoption = inventory_service.adopt_account_by_code(
            business_id=business.id,
            account_code=str(payload.get("account_code", "")),
            actor=str(payload.get("actor", "") or ""),
            source="inventory_api",
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": adoption.id,
                    "account_code": adoption.account.code,
                    "account_name": adoption.account.name,
                    "is_active": adoption.is_active,
                },
            }
        ),
        201,
    )


@bp.route("/account-adoption/unadopt", methods=["POST"])
def account_adoption_unadopt(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    try:
        adoption = inventory_service.unadopt_account_by_code(
            business_id=business.id,
            account_code=str(payload.get("account_code", "")),
            actor=str(payload.get("actor", "") or ""),
            source="inventory_api",
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": adoption.id,
                "account_code": adoption.account.code,
                "account_name": adoption.account.name,
                "is_active": adoption.is_active,
            },
        }
    )


@bp.route("/account-catalog/list", methods=["GET"])
def account_catalog_list(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    accounts = inventory_service.list_catalog_accounts()
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": account.id,
                    "code": account.code,
                    "name": account.name,
                }
                for account in accounts
            ],
        }
    )


@bp.route("/account-catalog/update", methods=["POST"])
def account_catalog_update(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    try:
        inventory_service.reject_catalog_account_update()
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify({"ok": True})


@bp.route("/account-adoption/audit-list", methods=["GET"])
def account_adoption_audit_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    account_code = request.args.get("account_code")
    audits = inventory_service.list_account_adoption_audits(
        business_id=business.id,
        account_code=account_code,
    )

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": audit.id,
                    "account_code": audit.account.code,
                    "account_name": audit.account.name,
                    "action": audit.action,
                    "actor": audit.actor,
                    "source": audit.source,
                    "previous_is_active": audit.previous_is_active,
                    "new_is_active": audit.new_is_active,
                    "created_at": (
                        audit.created_at.isoformat() if audit.created_at else None
                    ),
                }
                for audit in audits
            ],
        }
    )
