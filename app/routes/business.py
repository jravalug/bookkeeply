from flask import (
    abort,
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from app.forms import BusinessForm
from app.services import BusinessService, BusinessRulesService
from app.utils.slug_utils import get_business_by_slugs
from app.utils.file_utils import handle_logo_upload

bp = Blueprint(
    "business", __name__, url_prefix="/clients/<string:client_slug>/business"
)

business_service = BusinessService()
business_rules_service = BusinessRulesService()


@bp.route("/<string:business_slug>", methods=["GET", "POST"])
def detail_or_edit(client_slug, business_slug):
    """
    Muestra los detalles de un negocio y maneja su edición.
    """
    business = get_business_by_slugs(client_slug, business_slug)
    if not business:
        abort(404)
    edit = request.args.get("edit", False)
    form = BusinessForm(obj=business)

    if request.method == "GET":
        default_mode, default_activity = (
            business_rules_service.resolve_business_income_defaults(
                business.client, business
            )
        )
        if not business.income_entry_mode:
            form.income_entry_mode.data = default_mode
        if not business.default_income_activity:
            form.default_income_activity.data = default_activity

    if edit and form.validate_on_submit():
        previous_parent_state = business_rules_service.snapshot_parent_state(business)

        parent_business = business.parent_business if not business.is_general else None
        fiscal_values = business_rules_service.resolve_fiscal_values_from_form(
            form,
            parent_business=parent_business,
        )

        logo_path = handle_logo_upload(form.logo.data)
        update_kwargs = {
            "name": form.name.data,
            "description": form.description.data,
            "business_activity": business_rules_service.normalize_optional_text(
                form.business_activity.data
            ),
            "inventory_flow_sales_floor_enabled": form.inventory_flow_sales_floor_enabled.data,
            "inventory_flow_wip_enabled": form.inventory_flow_wip_enabled.data,
            "income_entry_mode": form.income_entry_mode.data,
            "default_income_activity": form.default_income_activity.data,
            **fiscal_values,
            "is_general": form.is_general.data,
        }
        if logo_path is not None:
            update_kwargs["logo"] = logo_path

        try:
            business_service.update_business(
                business=business,
                **update_kwargs,
            )
            flash("Negocio actualizado correctamente", "success")
        except RuntimeError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"Error inesperado: {str(e)}", "error")

        if previous_parent_state is not None:
            business_rules_service.sync_children_inherited_fields(
                business,
                previous_parent_state,
            )

        business_rules_service.sync_sales_summary_daily_income(business)

        return redirect(
            url_for(
                "business.detail_or_edit",
                client_slug=client_slug,
                business_slug=business.slug,
            )
        )

    return render_template(
        "business/detail_or_edit.html", business=business, form=form, edit=edit
    )


@bp.route("/<string:business_slug>/add-sub-business", methods=["GET", "POST"])
def add_sub_business(client_slug, business_slug):
    # Obtener el negocio general
    business = get_business_by_slugs(client_slug, business_slug)
    if not business:
        abort(404)

    if not business.is_general:
        flash("Este negocio no es un negocio general.", "danger")
        return redirect(url_for("main.index"))

    # Inicializar el formulario
    form = BusinessForm()

    default_mode, default_activity = (
        business_rules_service.resolve_business_income_defaults(
            business.client, business
        )
    )
    if request.method == "GET":
        form.business_activity.data = business.business_activity
        form.income_entry_mode.data = default_mode
        form.default_income_activity.data = default_activity

    if form.validate_on_submit():
        fiscal_values = business_rules_service.resolve_fiscal_values_from_form(
            form,
            parent_business=business,
        )

        new_sub_business = business_service.create_business(
            name=form.name.data,
            description=business.description,
            business_activity=business_rules_service.normalize_optional_text(
                form.business_activity.data
            )
            or business.business_activity,
            inventory_flow_sales_floor_enabled=form.inventory_flow_sales_floor_enabled.data,
            inventory_flow_wip_enabled=form.inventory_flow_wip_enabled.data,
            income_entry_mode=form.income_entry_mode.data or default_mode,
            default_income_activity=form.default_income_activity.data
            or default_activity,
            is_general=False,
            parent_business_id=business.id,
            client_id=business.client_id,
            **fiscal_values,
        )

        business_rules_service.sync_sales_summary_daily_income(new_sub_business)

        flash("Negocio específico agregado correctamente.", "success")
        if business.client:
            return redirect(
                url_for(
                    "client.client_dashboard",
                    client_slug=business.client.slug,
                    business_slug=business.slug,
                )
            )
        return redirect(url_for("client.list_clients"))

    return render_template(
        "business/add_sub_business.html", business=business, form=form
    )
