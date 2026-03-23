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
    is_htmx_request = request.headers.get("HX-Request") == "true"
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return redirect(url_for("client.list_clients"))

    form = InventoryItemForm()
    inline_message = None
    inline_message_type = None

    if form.validate_on_submit():
        try:
            inventory_service.create_item(name=form.name.data, unit=form.unit.data)
            inline_message = "Articulo de inventario agregado correctamente"
            inline_message_type = "success"
            flash(inline_message, "success")
            if not is_htmx_request:
                return redirect(
                    url_for(
                        "inventory.item_list",
                        client_slug=business.client.slug,
                        business_slug=business.slug,
                    )
                )
        except ValueError as exc:
            inline_message = str(exc)
            inline_message_type = "error"
            flash(inline_message, "danger")
    elif request.method == "POST":
        first_error = next(iter(form.errors.values()), ["Datos invalidos"])[0]
        inline_message = first_error
        inline_message_type = "error"

    inventory_items_list = inventory_service.get_all_items()

    template_context = {
        "business": business,
        "inventory_items": inventory_items_list,
        "form": form,
        "inline_message": inline_message,
        "inline_message_type": inline_message_type,
    }

    if is_htmx_request:
        return render_template(
            "inventory/partials/_item_panel.html", **template_context
        )

    return render_template(
        "inventory/item_list.html",
        **template_context,
    )


@bp.route("/<int:inventory_item_id>", methods=["POST"])
def item_update(client_slug, business_slug, inventory_item_id):
    is_htmx_request = request.headers.get("HX-Request") == "true"
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return redirect(url_for("client.list_clients"))

    inline_message = "Articulo de inventario actualizado correctamente"
    inline_message_type = "success"

    try:
        inventory_service.update_item(
            inventory_item_id=inventory_item_id,
            name=request.form["name"],
            unit=request.form["unit"],
        )
        flash(inline_message, "success")
    except ValueError as exc:
        inline_message = str(exc)
        inline_message_type = "error"
        flash(inline_message, "danger")

    if is_htmx_request:
        form = InventoryItemForm()
        inventory_items_list = inventory_service.get_all_items()
        return render_template(
            "inventory/partials/_item_panel.html",
            business=business,
            inventory_items=inventory_items_list,
            form=form,
            inline_message=inline_message,
            inline_message_type=inline_message_type,
        )

    return redirect(
        url_for(
            "inventory.item_list",
            client_slug=business.client.slug,
            business_slug=business.slug,
        )
    )


@bp.route("/accounting/manage", methods=["GET", "POST"])
def accounting_manage(client_slug, business_slug):
    is_htmx_request = request.headers.get("HX-Request") == "true"
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return redirect(url_for("client.list_clients"))

    inline_message = None
    inline_message_type = None

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        account_code = (request.form.get("account_code") or "").strip()
        actor = (request.form.get("actor") or "ui_user").strip()

        try:
            if action == "adopt":
                inventory_service.adopt_account_by_code(
                    business_id=business.id,
                    account_code=account_code,
                    actor=actor,
                    source="inventory_ui",
                )
                inline_message = "Cuenta adoptada correctamente"
                inline_message_type = "success"
                flash(inline_message, "success")
            elif action == "unadopt":
                inventory_service.unadopt_account_by_code(
                    business_id=business.id,
                    account_code=account_code,
                    actor=actor,
                    source="inventory_ui",
                )
                inline_message = "Cuenta desadoptada correctamente"
                inline_message_type = "success"
                flash(inline_message, "success")
            else:
                inline_message = "Accion no valida"
                inline_message_type = "error"
                flash("Accion no valida", "warning")
        except ValueError as exc:
            inline_message = str(exc)
            inline_message_type = "error"
            flash(str(exc), "danger")

        if not is_htmx_request:
            return redirect(
                url_for(
                    "inventory.accounting_manage",
                    client_slug=business.client.slug,
                    business_slug=business.slug,
                )
            )

    accounts = inventory_service.list_catalog_accounts()
    adoptions = inventory_service.list_account_adoptions(
        business_id=business.id,
        include_inactive=True,
    )
    adopted_by_code = {
        adoption.account.code: adoption
        for adoption in adoptions
        if adoption.account and adoption.is_active
    }
    audits = inventory_service.list_account_adoption_audits(business_id=business.id)[
        :30
    ]

    template_context = {
        "business": business,
        "accounts": accounts,
        "adopted_by_code": adopted_by_code,
        "audits": audits,
        "inline_message": inline_message,
        "inline_message_type": inline_message_type,
    }

    if is_htmx_request:
        return render_template(
            "inventory/partials/_accounting_manage_content.html",
            **template_context,
        )

    return render_template("inventory/accounting_manage.html", **template_context)


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
                    "adjustment_kind": movement.adjustment_kind,
                    "destination": movement.destination,
                    "lot_code": movement.lot_code,
                    "lot_date": (
                        movement.lot_date.isoformat() if movement.lot_date else None
                    ),
                    "lot_unit": movement.lot_unit,
                    "lot_conversion_factor": movement.lot_conversion_factor,
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "account_code": movement.account_code,
                    "supplier_name": movement.supplier_name,
                    "waste_reason": movement.waste_reason,
                    "waste_responsible": movement.waste_responsible,
                    "waste_evidence": movement.waste_evidence,
                    "waste_evidence_file_url": getattr(
                        movement, "waste_evidence_file_url", None
                    ),
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


@bp.route("/movement/waste-report", methods=["GET"])
def movement_waste_report(client_slug, business_slug):
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

    items = inventory_service.list_waste_report(
        business_id=business.id,
        start_date=start_date,
        end_date=end_date,
        inventory_item_id=request.args.get("inventory_item_id", type=int),
        waste_reason=request.args.get("waste_reason"),
    )

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "inventory_item_id": row["inventory_item_id"],
                    "inventory_item_name": row["inventory_item_name"],
                    "waste_reason": row["waste_reason"],
                    "events": row["events"],
                    "total_quantity": row["total_quantity"],
                    "total_amount": row["total_amount"],
                    "last_movement_date": (
                        row["last_movement_date"].isoformat()
                        if row["last_movement_date"]
                        else None
                    ),
                }
                for row in items
            ],
        }
    )


@bp.route("/cycle-count/list", methods=["GET"])
def cycle_count_list(client_slug, business_slug):
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

    counts = inventory_service.list_cycle_counts(
        business_id=business.id,
        location=request.args.get("location"),
        status=request.args.get("status"),
        inventory_item_id=request.args.get("inventory_item_id", type=int),
        start_date=start_date,
        end_date=end_date,
    )

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": row.id,
                    "business_id": row.business_id,
                    "inventory_item_id": row.inventory_item_id,
                    "inventory_item_name": (
                        row.inventory_item.name if row.inventory_item else None
                    ),
                    "location": row.location,
                    "theoretical_quantity": row.theoretical_quantity,
                    "counted_quantity": row.counted_quantity,
                    "difference_quantity": row.difference_quantity,
                    "proposed_adjustment_kind": row.proposed_adjustment_kind,
                    "status": row.status,
                    "actor": row.actor,
                    "counted_at": (
                        row.counted_at.isoformat() if row.counted_at else None
                    ),
                    "observation": row.observation,
                    "applied_movement_id": row.applied_movement_id,
                }
                for row in counts
            ],
        }
    )


@bp.route("/cycle-count/create", methods=["POST"])
def cycle_count_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    counted_at_raw = payload.get("counted_at")
    counted_at = None
    if counted_at_raw not in (None, ""):
        try:
            counted_at = datetime.fromisoformat(str(counted_at_raw))
        except ValueError:
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": "counted_at invalida. Use ISO 8601 (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)",
                    }
                ),
                400,
            )

    try:
        row = inventory_service.create_cycle_count(
            business_id=business.id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            location=str(payload.get("location", "warehouse")),
            counted_quantity=float(payload.get("counted_quantity", 0)),
            actor=str(payload.get("actor", "")),
            counted_at=counted_at,
            observation=payload.get("observation"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": row.id,
                    "inventory_item_id": row.inventory_item_id,
                    "location": row.location,
                    "theoretical_quantity": row.theoretical_quantity,
                    "counted_quantity": row.counted_quantity,
                    "difference_quantity": row.difference_quantity,
                    "proposed_adjustment_kind": row.proposed_adjustment_kind,
                    "status": row.status,
                    "actor": row.actor,
                    "counted_at": (
                        row.counted_at.isoformat() if row.counted_at else None
                    ),
                    "observation": row.observation,
                },
            }
        ),
        201,
    )


@bp.route("/cycle-count/<int:cycle_count_id>/reconcile", methods=["POST"])
def cycle_count_reconcile(client_slug, business_slug, cycle_count_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        row = inventory_service.reconcile_cycle_count(
            business_id=business.id,
            cycle_count_id=cycle_count_id,
            account_code=str(payload.get("account_code", "")),
            actor=str(payload.get("actor", "")),
            notes=payload.get("notes"),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": row.id,
                "status": row.status,
                "applied_movement_id": row.applied_movement_id,
                "difference_quantity": row.difference_quantity,
                "proposed_adjustment_kind": row.proposed_adjustment_kind,
            },
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

    def _to_date(name):
        value = _raw(name)
        if value in (None, ""):
            return None
        return datetime.fromisoformat(str(value)).date()

    try:
        movement = inventory_service.create_movement(
            business_id=business.id,
            inventory_item_id=int(_raw("inventory_item_id")),
            movement_type=str(_raw("movement_type", "")),
            destination=_raw("destination"),
            adjustment_kind=_raw("adjustment_kind"),
            quantity=float(_raw("quantity", 0)),
            unit=str(_raw("unit", "")),
            inventory_id=_to_int("inventory_id"),
            unit_cost=_to_float("unit_cost"),
            total_cost=_to_float("total_cost"),
            account_code=_raw("account_code"),
            idempotency_key=_raw("idempotency_key"),
            reference_type=_raw("reference_type"),
            reference_id=_to_int("reference_id"),
            supplier_name=_raw("supplier_name"),
            waste_reason=_raw("waste_reason"),
            waste_responsible=_raw("waste_responsible"),
            waste_evidence=_raw("waste_evidence"),
            waste_evidence_file_url=_raw("waste_evidence_file_url"),
            lot_code=_raw("lot_code"),
            lot_date=_to_date("lot_date"),
            lot_unit=_raw("lot_unit"),
            lot_conversion_factor=_to_float("lot_conversion_factor"),
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
                    "adjustment_kind": movement.adjustment_kind,
                    "destination": movement.destination,
                    "lot_code": movement.lot_code,
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "account_code": movement.account_code,
                    "supplier_name": movement.supplier_name,
                    "waste_reason": movement.waste_reason,
                    "waste_responsible": movement.waste_responsible,
                    "waste_evidence": movement.waste_evidence,
                    "waste_evidence_file_url": getattr(
                        movement, "waste_evidence_file_url", None
                    ),
                    "lot_date": (
                        movement.lot_date.isoformat() if movement.lot_date else None
                    ),
                    "lot_unit": movement.lot_unit,
                    "lot_conversion_factor": movement.lot_conversion_factor,
                    "min_stock_alert": bool(
                        getattr(movement, "min_stock_alert", False)
                    ),
                    "min_stock_policy": getattr(movement, "min_stock_policy", "alert"),
                    "projected_stock": getattr(movement, "projected_stock", None),
                    "min_stock_threshold": getattr(
                        movement, "min_stock_threshold", None
                    ),
                },
            }
        ),
        201,
    )


@bp.route("/purchase-receipt/create", methods=["POST"])
def purchase_receipt_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    receipt_date_raw = payload.get("receipt_date")
    try:
        receipt_date = datetime.fromisoformat(str(receipt_date_raw))
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "receipt_date invalida. Use ISO 8601 (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)",
                }
            ),
            400,
        )

    try:
        movement = inventory_service.create_purchase_receipt(
            business_id=business.id,
            inventory_item_id=int(payload.get("inventory_item_id")),
            quantity=float(payload.get("quantity", 0)),
            unit=str(payload.get("unit", "")),
            account_code=str(payload.get("account_code", "")),
            supplier_name=str(payload.get("supplier_name", "")),
            document=str(payload.get("document", "")),
            receipt_date=receipt_date,
            unit_cost=float(payload.get("unit_cost", 0)),
            total_cost=(
                float(payload.get("total_cost"))
                if payload.get("total_cost") not in (None, "")
                else None
            ),
            lot_code=payload.get("lot_code"),
            lot_date=(
                datetime.fromisoformat(str(payload.get("lot_date"))).date()
                if payload.get("lot_date") not in (None, "")
                else None
            ),
            lot_unit=(
                str(payload.get("lot_unit", ""))
                if payload.get("lot_unit") not in (None, "")
                else None
            ),
            lot_conversion_factor=(
                float(payload.get("lot_conversion_factor"))
                if payload.get("lot_conversion_factor") not in (None, "")
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
                    "id": movement.id,
                    "movement_type": movement.movement_type,
                    "inventory_item_id": movement.inventory_item_id,
                    "quantity": movement.quantity,
                    "unit": movement.unit,
                    "unit_cost": movement.unit_cost,
                    "total_cost": movement.total_cost,
                    "account_code": movement.account_code,
                    "supplier_name": movement.supplier_name,
                    "document": movement.document,
                    "lot_code": movement.lot_code,
                    "lot_date": (
                        movement.lot_date.isoformat() if movement.lot_date else None
                    ),
                    "lot_unit": movement.lot_unit,
                    "lot_conversion_factor": movement.lot_conversion_factor,
                    "movement_date": (
                        movement.movement_date.isoformat()
                        if movement.movement_date
                        else None
                    ),
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
    location = request.args.get("location")

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
            location=location,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "inventory_item_id": inventory_item_id,
                "lot_code": (lot_code or "").strip(),
                "location": (location or "").strip().lower() or None,
                "entries": [
                    {
                        "id": row["id"],
                        "movement_type": row["movement_type"],
                        "adjustment_kind": row.get("adjustment_kind"),
                        "destination": row["destination"],
                        "location": row.get("location"),
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
                        "supplier_name": row["supplier_name"],
                        "waste_reason": row["waste_reason"],
                        "waste_responsible": row["waste_responsible"],
                        "waste_evidence": row["waste_evidence"],
                        "waste_evidence_file_url": row.get("waste_evidence_file_url"),
                        "lot_date": (
                            row["lot_date"].isoformat() if row["lot_date"] else None
                        ),
                        "lot_unit": row["lot_unit"],
                        "lot_conversion_factor": row["lot_conversion_factor"],
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


@bp.route("/accounting/turnover-coverage", methods=["GET"])
def accounting_turnover_coverage(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    inventory_item_id = request.args.get("inventory_item_id", type=int)

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

    try:
        items = inventory_service.list_inventory_turnover_coverage(
            business_id=business.id,
            inventory_item_id=inventory_item_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "inventory_item_id": item["inventory_item_id"],
                    "inventory_item_name": item["inventory_item_name"],
                    "unit": item["unit"],
                    "period_start": (
                        item["period_start"].isoformat()
                        if item.get("period_start")
                        else None
                    ),
                    "period_end": (
                        item["period_end"].isoformat()
                        if item.get("period_end")
                        else None
                    ),
                    "period_days": item["period_days"],
                    "movement_count": item["movement_count"],
                    "opening_stock": item["opening_stock"],
                    "closing_stock": item["closing_stock"],
                    "inbound_quantity": item["inbound_quantity"],
                    "outbound_quantity": item["outbound_quantity"],
                    "average_stock": item["average_stock"],
                    "avg_daily_outbound": item["avg_daily_outbound"],
                    "turnover_ratio": item["turnover_ratio"],
                    "days_of_coverage": item["days_of_coverage"],
                    "min_stock": item["min_stock"],
                }
                for item in items
            ],
        }
    )


@bp.route("/accounting/stockout-risk", methods=["GET"])
def accounting_stockout_risk(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    inventory_item_id = request.args.get("inventory_item_id", type=int)

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

    try:
        items = inventory_service.list_stockout_risk_report(
            business_id=business.id,
            inventory_item_id=inventory_item_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "inventory_item_id": item["inventory_item_id"],
                    "inventory_item_name": item["inventory_item_name"],
                    "unit": item["unit"],
                    "closing_stock": item["closing_stock"],
                    "avg_daily_outbound": item["avg_daily_outbound"],
                    "days_of_coverage": item["days_of_coverage"],
                    "min_stock": item["min_stock"],
                    "stockout": item["stockout"],
                    "risk_of_stockout": item["risk_of_stockout"],
                    "min_stock_breach": item["min_stock_breach"],
                    "risk_level": item["risk_level"],
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


@bp.route("/alerts/preventive", methods=["GET"])
def preventive_alerts(client_slug, business_slug):
    try:
        inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    usage_type = request.args.get("usage_type")
    try:
        days_to_expiration = int(request.args.get("days_to_expiration", 7))
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "days_to_expiration debe ser un numero entero",
                }
            ),
            400,
        )

    try:
        alerts = inventory_service.list_inventory_preventive_alerts(
            days_to_expiration=days_to_expiration,
            usage_type=usage_type,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "inventory_item_id": item["inventory_item_id"],
                    "inventory_item_name": item["inventory_item_name"],
                    "usage_type": item["usage_type"],
                    "stock": item["stock"],
                    "min_stock": item["min_stock"],
                    "low_stock": item["low_stock"],
                    "expiration_date": (
                        item["expiration_date"].isoformat()
                        if item["expiration_date"]
                        else None
                    ),
                    "expired": item["expired"],
                    "expiring_soon": item["expiring_soon"],
                    "days_until_expiration": item["days_until_expiration"],
                }
                for item in alerts
            ],
        }
    )


@bp.route("/stock/position", methods=["GET"])
def stock_position(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    inventory_item_id = request.args.get("inventory_item_id", type=int)
    try:
        items = inventory_service.list_stock_position(
            business_id=business.id,
            inventory_item_id=inventory_item_id,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "inventory_item_id": item["inventory_item_id"],
                    "inventory_item_name": item["inventory_item_name"],
                    "unit": item["unit"],
                    "stock_available": item["stock_available"],
                    "stock_committed": item["stock_committed"],
                    "stock_virtual": item["stock_virtual"],
                    "stock_committed_sales_floor": item["stock_committed_sales_floor"],
                    "stock_committed_wip": item["stock_committed_wip"],
                }
                for item in items
            ],
        }
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
                    "produced_product_id": balance.produced_product_id,
                    "quantity": balance.quantity,
                    "remaining_quantity": balance.remaining_quantity,
                    "unit": balance.unit,
                    "status": balance.status,
                    "can_be_subproduct": balance.can_be_subproduct,
                    "finished_location": balance.finished_location,
                    "expiration_date": (
                        balance.expiration_date.isoformat()
                        if balance.expiration_date
                        else None
                    ),
                    "expiration_source": balance.expiration_source,
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
    expiration_date_raw = payload.get("expiration_date")
    expiration_date = None
    if expiration_date_raw not in (None, ""):
        try:
            expiration_date = datetime.strptime(
                str(expiration_date_raw), "%Y-%m-%d"
            ).date()
        except ValueError:
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": "expiration_date debe estar en formato YYYY-MM-DD",
                    }
                ),
                400,
            )

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
            expiration_date=expiration_date,
            can_be_subproduct=str(payload.get("can_be_subproduct", "false")).lower()
            == "true",
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
                    "can_be_subproduct": balance.can_be_subproduct,
                    "finished_location": balance.finished_location,
                    "expiration_date": (
                        balance.expiration_date.isoformat()
                        if balance.expiration_date
                        else None
                    ),
                    "expiration_source": balance.expiration_source,
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
            produced_product_id=(
                int(payload.get("produced_product_id"))
                if payload.get("produced_product_id") not in (None, "")
                else None
            ),
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
                "produced_product_id": balance.produced_product_id,
                "can_be_subproduct": balance.can_be_subproduct,
                "finished_location": balance.finished_location,
            },
        }
    )


@bp.route("/wip/<int:wip_balance_id>/mark-subproduct", methods=["POST"])
def wip_mark_subproduct(client_slug, business_slug, wip_balance_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        balance = inventory_service.mark_wip_as_subproduct(
            business_id=business.id,
            wip_balance_id=wip_balance_id,
            can_be_subproduct=str(payload.get("can_be_subproduct", "true")).lower()
            == "true",
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": balance.id,
                "can_be_subproduct": balance.can_be_subproduct,
                "status": balance.status,
            },
        }
    )


@bp.route("/wip/<int:wip_balance_id>/consume-subproduct", methods=["POST"])
def wip_consume_subproduct(client_slug, business_slug, wip_balance_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        balance = inventory_service.consume_wip_subproduct_for_recipe(
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
                "can_be_subproduct": balance.can_be_subproduct,
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
                    "is_normative": account.is_normative,
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

    payload = request.get_json(silent=True) or request.form
    try:
        account = inventory_service.update_catalog_account(
            account_code=str(payload.get("account_code", "")),
            new_code=str(payload.get("new_code", "")),
            new_name=str(payload.get("new_name", "")),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": account.id,
                "code": account.code,
                "name": account.name,
                "is_normative": account.is_normative,
            },
        }
    )


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


@bp.route("/account-subaccount/list", methods=["GET"])
def account_subaccount_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    account_code = request.args.get("account_code")
    try:
        subaccounts = inventory_service.list_business_subaccounts(
            business_id=business.id,
            include_inactive=include_inactive,
            account_code=account_code,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": subaccount.id,
                    "business_id": subaccount.business_id,
                    "business_account_adoption_id": subaccount.business_account_adoption_id,
                    "account_code": subaccount.adoption.account.code,
                    "account_name": subaccount.adoption.account.name,
                    "code": subaccount.code,
                    "name": subaccount.name,
                    "is_active": subaccount.is_active,
                }
                for subaccount in subaccounts
            ],
        }
    )


@bp.route("/account-subaccount/create", methods=["POST"])
def account_subaccount_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        subaccount = inventory_service.create_business_subaccount(
            business_id=business.id,
            account_code=str(payload.get("account_code", "")),
            code=str(payload.get("code", "")),
            name=str(payload.get("name", "")),
            actor=str(payload.get("actor", "") or ""),
            source="inventory_api",
            template_subaccount_id=(
                int(payload.get("template_subaccount_id"))
                if payload.get("template_subaccount_id") not in (None, "")
                else None
            ),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return (
        jsonify(
            {
                "ok": True,
                "item": {
                    "id": subaccount.id,
                    "business_account_adoption_id": subaccount.business_account_adoption_id,
                    "code": subaccount.code,
                    "name": subaccount.name,
                    "is_active": subaccount.is_active,
                },
            }
        ),
        201,
    )


@bp.route("/account-subaccount/<int:business_sub_account_id>/update", methods=["POST"])
def account_subaccount_update(client_slug, business_slug, business_sub_account_id):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form

    try:
        subaccount = inventory_service.update_business_subaccount(
            business_id=business.id,
            business_sub_account_id=business_sub_account_id,
            code=(str(payload.get("code", "")) if "code" in payload else None),
            name=(str(payload.get("name", "")) if "name" in payload else None),
            is_active=(
                str(payload.get("is_active", "false")).lower() == "true"
                if "is_active" in payload
                else None
            ),
            actor=str(payload.get("actor", "") or ""),
            source="inventory_api",
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": subaccount.id,
                "business_account_adoption_id": subaccount.business_account_adoption_id,
                "code": subaccount.code,
                "name": subaccount.name,
                "is_active": subaccount.is_active,
            },
        }
    )


@bp.route("/accounting/ledger/list", methods=["GET"])
def accounting_ledger_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    account_code = request.args.get("account_code")
    entries = inventory_service.list_inventory_ledger_entries(
        business_id=business.id,
        account_code=account_code,
    )
    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": entry.id,
                    "movement_id": entry.movement_id,
                    "movement_type": entry.movement_type,
                    "destination": entry.destination,
                    "source_bucket": entry.source_bucket,
                    "destination_bucket": entry.destination_bucket,
                    "source_account_code": entry.source_account_code,
                    "destination_account_code": entry.destination_account_code,
                    "quantity": entry.quantity,
                    "unit": entry.unit,
                    "unit_cost": entry.unit_cost,
                    "amount": entry.amount,
                    "valuation_method": entry.valuation_method,
                    "document": entry.document,
                    "reference_type": entry.reference_type,
                    "reference_id": entry.reference_id,
                    "created_at": (
                        entry.created_at.isoformat() if entry.created_at else None
                    ),
                }
                for entry in entries
            ],
        }
    )


@bp.route("/accounting/reconciliation", methods=["GET"])
def accounting_reconciliation(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    items = inventory_service.summarize_inventory_account_reconciliation(
        business_id=business.id
    )
    return jsonify({"ok": True, "items": items})


@bp.route("/accounting/mixed-sale/create", methods=["POST"])
def accounting_mixed_sale_create(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    payload = request.get_json(silent=True) or request.form
    try:
        breakdown = inventory_service.upsert_sale_cost_breakdown(
            business_id=business.id,
            sale_id=int(payload.get("sale_id")),
            production_cost=float(payload.get("production_cost", 0)),
            merchandise_cost=float(payload.get("merchandise_cost", 0)),
            actor=str(payload.get("actor", "") or ""),
            source="inventory_api",
            production_account_code=str(payload.get("production_account_code", "1586")),
            merchandise_account_code=str(
                payload.get("merchandise_account_code", "1587")
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
                    "id": breakdown.id,
                    "sale_id": breakdown.sale_id,
                    "production_account_code": breakdown.production_account_code,
                    "merchandise_account_code": breakdown.merchandise_account_code,
                    "production_cost": breakdown.production_cost,
                    "merchandise_cost": breakdown.merchandise_cost,
                },
            }
        ),
        201,
    )


@bp.route("/accounting/mixed-sale/list", methods=["GET"])
def accounting_mixed_sale_list(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    sale_id = request.args.get("sale_id", type=int)
    items = inventory_service.list_sale_cost_breakdowns(
        business_id=business.id,
        sale_id=sale_id,
    )

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": item.id,
                    "sale_id": item.sale_id,
                    "production_account_code": item.production_account_code,
                    "merchandise_account_code": item.merchandise_account_code,
                    "production_cost": item.production_cost,
                    "merchandise_cost": item.merchandise_cost,
                    "notes": item.notes,
                }
                for item in items
            ],
        }
    )


@bp.route("/accounting/kardex-valued", methods=["GET"])
def accounting_kardex_valued(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    inventory_item_id = request.args.get("inventory_item_id", type=int)

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

    try:
        items = inventory_service.list_valued_kardex(
            business_id=business.id,
            inventory_item_id=inventory_item_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "movement_id": item["movement_id"],
                    "movement_date": (
                        item["movement_date"].isoformat()
                        if item.get("movement_date")
                        else None
                    ),
                    "inventory_item_id": item["inventory_item_id"],
                    "inventory_item_name": item["inventory_item_name"],
                    "movement_type": item["movement_type"],
                    "adjustment_kind": item["adjustment_kind"],
                    "quantity": item["quantity"],
                    "delta_quantity": item["delta_quantity"],
                    "unit": item["unit"],
                    "unit_cost": item["unit_cost"],
                    "total_cost": item["total_cost"],
                    "amount": item["amount"],
                    "delta_value": item["delta_value"],
                    "running_stock": item["running_stock"],
                    "running_value": item["running_value"],
                    "account_code": item["account_code"],
                    "reference_type": item["reference_type"],
                    "reference_id": item["reference_id"],
                    "document": item["document"],
                }
                for item in items
            ],
        }
    )


@bp.route("/accounting/sale-consumption-cost", methods=["GET"])
def accounting_sale_consumption_cost(client_slug, business_slug):
    try:
        business = inventory_service.resolve_business(client_slug, business_slug)
    except ValueError:
        return jsonify({"ok": False, "message": "Negocio no encontrado"}), 404

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    sale_id = request.args.get("sale_id", type=int)

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

    try:
        items = inventory_service.summarize_sale_consumption_cost_report(
            business_id=business.id,
            sale_id=sale_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "sale_id": item["sale_id"],
                    "sale_number": item["sale_number"],
                    "sale_date": (
                        item["sale_date"].isoformat() if item.get("sale_date") else None
                    ),
                    "movement_count": item["movement_count"],
                    "consumption_quantity": item["consumption_quantity"],
                    "consumption_cost": item["consumption_cost"],
                    "reversal_cost": item["reversal_cost"],
                    "net_consumption_cost": item["net_consumption_cost"],
                }
                for item in items
            ],
        }
    )
