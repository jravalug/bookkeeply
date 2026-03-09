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
                    "product_surtido": supply.product_surtido,
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
            product_surtido=str(payload.get("product_surtido", "")),
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
                    "product_surtido": supply.product_surtido,
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
            product_surtido=str(payload.get("product_surtido", "")),
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
                "product_surtido": supply.product_surtido,
                "is_active": supply.is_active,
            },
        }
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
    movements = inventory_service.list_movements(
        business_id=business.id,
        inventory_item_id=inventory_item_id,
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
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "account_code": movement.account_code,
                },
            }
        ),
        201,
    )


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
