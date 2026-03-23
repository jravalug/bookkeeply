import json
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from app.forms import MonthForm
from app.services import IncomeReportService
from app.utils import (
    generate_excel_sales_by_date,
    generate_excel_ipv,
    generate_excel_inventory_consumption,
)
from flask import jsonify


bp = Blueprint(
    "report",
    __name__,
    url_prefix="/clients/<string:client_slug>/business/<string:business_slug>/report",
)

sales_service = IncomeReportService()


def _redirect_clients_list():
    return redirect(url_for("client.list_clients"))


def _resolve_business_scope_or_redirect(client_slug, business_slug):
    try:
        business, business_filters = sales_service.resolve_business_scope(
            client_slug,
            business_slug,
        )
        return business, business_filters, None
    except ValueError:
        return None, None, _redirect_clients_list()


def _redirect_report(endpoint, business):
    return redirect(
        url_for(
            endpoint,
            client_slug=business.client.slug,
            business_slug=business.slug,
        )
    )


@bp.route("/monthly-sales-by-product", methods=["GET", "POST"])
def monthly_sales_by_produc(client_slug, business_slug):
    business, business_filters, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    daily_sales = []
    selected_month = None

    if request.method == "POST":
        # Obtener el mes seleccionado desde el formulario
        selected_month = request.form.get("month")

        if not selected_month:
            flash("Por favor, selecciona un mes.", "error")
            return render_template(
                "report/monthly_sales_by_product.html",
                business=business,
                daily_sales=daily_sales,
                selected_month=selected_month,
            )

        try:
            daily_sales = sales_service.get_monthly_sales_by_product_data(
                selected_month,
                business_filters["business_id"],
                business_filters.get("specific_business_id"),
            )

        except ValueError:
            # Manejar errores si el formato del mes es incorrecto
            flash("Por favor, selecciona un mes válido.", "error")

    # logging.basicConfig(level=logging.DEBUG)
    # logging.debug("Datos generados para el reporte: %s", daily_sales)

    return render_template(
        "report/monthly_sales_by_product.html",
        business=business,
        daily_sales=daily_sales,
        daily_sales_json=json.dumps(daily_sales),
        selected_month=selected_month,
    )


@bp.route("/monthly-sales-by-date", methods=["GET", "POST"])
def monthly_sales_by_date(client_slug, business_slug):
    """Endpoint para obtener las ventas mensuales agrupadas por día."""

    business, business_filters, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    form = MonthForm()

    # Inicializar variables

    daily_sales = []
    formated_daily_sales = []
    selected_month = None

    def redirect_to_monthly_sales_by_date():
        return _redirect_report("report.monthly_sales_by_date", business)

    if form.validate_on_submit():
        month_str = form.month.data

        try:
            daily_sales, formated_daily_sales = sales_service.get_daily_sales(
                month_str,
                business_filters["business_id"],
                business_filters.get("specific_business_id"),
            )

        except ValueError as e:
            flash(f"Error en el formato del mes: {e}", "error")
            return redirect_to_monthly_sales_by_date()

        except Exception as e:
            flash("Ocurrió un error inesperado.", "error")
            return redirect_to_monthly_sales_by_date()

        month_totals = sales_service.get_monthly_totals(daily_sales)

        return render_template(
            "report/monthly_sales_by_date.html",
            business=business,
            form=form,
            daily_sales=formated_daily_sales,
            daily_sales_json=json.dumps(formated_daily_sales),
            month_totals=month_totals,
            selected_month=month_str,
        )

    return render_template(
        "report/monthly_sales_by_date.html",
        business=business,
        form=form,
        daily_sales=[],
        selected_month=selected_month,
    )


@bp.route("/export-to-excel/sales-by-date", methods=["POST"])
def export_to_excel_sales_by_day(client_slug, business_slug):
    business, _, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response
    # Recuperar los datos del reporte mensual
    month = request.form.get("selected_month")
    daily_sales_json = request.form.get("daily_sales_export")
    try:
        data = sales_service.parse_json_payload(
            daily_sales_json,
            require_non_empty=True,
        )
    except ValueError as e:
        flash(str(e), "error")
        return _redirect_report("report.monthly_sales_by_date", business)

    try:
        # Generar el reporte en MS Excel
        excel_file = generate_excel_sales_by_date(business, data, month)
    except Exception as e:
        flash("Ocurrio un error al tratar de generar el reporte en MS Excel.", "error")
        return _redirect_report("report.monthly_sales_by_date", business)

    # Enviar el archivo como respuesta
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"RMV_{business.name}_{month}.xlsx",
    )


@bp.route("/export-to-excel/sales-by-product", methods=["POST"])
def export_to_excel_sales_by_product(client_slug, business_slug):
    business, _, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    try:
        data = sales_service.parse_json_payload(
            request.form.get("daily_sales_export", "[]"),
            require_non_empty=True,
        )
        month = request.form.get("selected_month", "_")
    except ValueError as e:
        flash(str(e), "error")
        return _redirect_report("report.monthly_sales_by_produc", business)
    try:
        excel_file = sales_service.generate_excel_sales_by_product(data)
    except Exception:
        flash("No se pudo generar el archivo de exportación.", "error")
        return _redirect_report("report.monthly_sales_by_produc", business)

    # Enviar el archivo como respuesta
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"RMVxProductos_{business.name}_{month}.xlsx",
    )


@bp.route("/export-to-excel/sales-by-product-by-date", methods=["POST"])
def export_to_excel_sales_by_product_by_date(client_slug, business_slug):
    business, _, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    try:
        data = sales_service.parse_json_payload(
            request.form.get("daily_sales_export", "[]"),
            require_non_empty=True,
        )
        month = request.form.get("selected_month", "_")
    except ValueError as e:
        flash(str(e), "error")
        return _redirect_report("report.monthly_sales_by_produc", business)
    try:
        excel_file = sales_service.generate_excel_sales_by_product_by_date(data)
    except Exception:
        flash("No se pudo generar el archivo de exportación.", "error")
        return _redirect_report("report.monthly_sales_by_produc", business)

    # Enviar el archivo como respuesta
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"RMVxProductos_Diario_{business.name}_{month}.xlsx",
    )


@bp.route("/ipv-report", methods=["GET", "POST"])
def ipv_report(client_slug, business_slug):
    business, business_filters, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    daily_sales = []
    selected_month = None

    if request.method == "POST":
        month_str = request.form.get("month")
        if not month_str:
            flash("Selecciona un mes válido.", "error")
            return redirect(
                url_for(
                    "report.ipv_report",
                    client_slug=client_slug,
                    business_slug=business_slug,
                )
            )

        try:
            daily_sales, selected_month = sales_service.get_ipv_daily_sales(
                month_str,
                business,
                business_filters,
            )

        except ValueError:
            flash("Formato de mes inválido. Usa YYYY-MM.", "error")

    return render_template(
        "report/ipv_report.html",
        business=business,
        daily_sales=daily_sales,
        daily_sales_json=json.dumps(daily_sales),
        selected_month=selected_month,
    )


@bp.route("/export-ipv", methods=["POST"])
def export_ipv(client_slug, business_slug):
    business, _, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response
    business_name = business.name if business.is_general else business.parent_name()
    month = request.form.get("selected_month", "_")

    try:
        data = sales_service.parse_json_payload(request.form.get("ipv_data", "[]"))
    except ValueError as e:
        flash(str(e), "error")
        return _redirect_report("report.ipv_report", business)

    try:
        # Generar el reporte en MS Excel
        excel_file = generate_excel_ipv(business_name, data, month)
    except Exception as e:
        flash("Ocurrio un error al tratar de generar el reporte en MS Excel.", "error")
        return _redirect_report("report.ipv_report", business)

    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"IPV_{business_name}_{month}.xlsx",
    )


@bp.route("/export-to-excel/inventory-consumption", methods=["POST"])
def export_to_excel_inventory_consumption(client_slug, business_slug):
    business, _, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response
    month = request.form.get("selected_month", "_")

    try:
        data = sales_service.parse_json_payload(
            request.form.get("consumption_export", "[]"),
            require_non_empty=True,
        )
    except ValueError as e:
        flash(str(e), "error")
        return _redirect_report("report.inventory_consumption_view", business)

    try:
        excel_file = generate_excel_inventory_consumption(business, data, month)
    except Exception as e:
        flash("Ocurrió un error al generar el archivo Excel.", "error")
        return _redirect_report("report.inventory_consumption_view", business)

    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"ConsumoInventario_{business.name}_{month}.xlsx",
    )


@bp.route("/monthly-sales-cocteleria", methods=["GET", "POST"])
def monthly_sales_coctelera(client_slug, business_slug):
    business, business_filters, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    daily_sales = []
    selected_month = None

    if request.method == "POST":
        # Obtener el mes seleccionado desde el formulario
        selected_month = request.form.get("month")

        if not selected_month:
            flash("Por favor, selecciona un mes.", "error")
            return render_template(
                "report/monthly_sales_by_product.html",
                business=business,
                daily_sales=daily_sales,
                selected_month=selected_month,
            )

        try:
            daily_sales = sales_service.get_monthly_sales_by_product_data(
                selected_month,
                business_filters["business_id"],
                business_filters.get("specific_business_id"),
                category_filter="cocteleria",
            )

        except ValueError:
            # Manejar errores si el formato del mes es incorrecto
            flash("Por favor, selecciona un mes válido.", "error")

    # logging.basicConfig(level=logging.DEBUG)
    # logging.debug("Datos generados para el reporte: %s", daily_sales)

    return render_template(
        "report/monthly_sales_cocteleria.html",
        business=business,
        daily_sales=daily_sales,
        daily_sales_json=json.dumps(daily_sales),
        selected_month=selected_month,
    )


@bp.route("/inventory-consumption", methods=["POST"])
def inventory_consumption(client_slug, business_slug):
    """Devuelve el consumo de materias primas (InventoryItem) derivado de las ventas de un mes.

    Espera un formulario o JSON con 'month' en formato YYYY-MM.
    """
    business, business_filters, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return jsonify({"error": "Negocio no encontrado."}), 404

    month = (
        request.form.get("month") or request.json.get("month")
        if request.is_json
        else None
    )
    if not month:
        return jsonify({"error": "El parámetro 'month' (YYYY-MM) es requerido."}), 400

    try:
        specific_business_id = business_filters.get("specific_business_id")
        data = sales_service.get_inventory_consumption(
            month, business_filters["business_id"], specific_business_id
        )
        return jsonify({"month": month, "consumption": data})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return (
            jsonify(
                {"error": "Error interno al calcular el consumo.", "detail": str(e)}
            ),
            500,
        )


@bp.route("/inventory-consumption/view", methods=["GET", "POST"])
def inventory_consumption_view(client_slug, business_slug):
    """Renderiza una plantilla con el consumo de inventario para el mes seleccionado."""
    is_htmx_request = request.headers.get("HX-Request") == "true"
    business, business_filters, redirect_response = _resolve_business_scope_or_redirect(
        client_slug,
        business_slug,
    )
    if redirect_response:
        return redirect_response

    selected_month = None
    consumption_by_day = []
    inline_message = None
    inline_message_type = None

    if request.method == "POST":
        selected_month = request.form.get("month")
        if not selected_month:
            inline_message = "Por favor, selecciona un mes."
            inline_message_type = "error"
            flash("Por favor, selecciona un mes.", "error")
            consumption_by_day = []

        if selected_month:
            try:
                consumption_by_day = sales_service.get_inventory_consumption_by_day(
                    selected_month,
                    business_filters["business_id"],
                    business_filters.get("specific_business_id"),
                )
            except ValueError:
                inline_message = "Formato de mes invalido. Usa YYYY-MM."
                inline_message_type = "error"
                flash("Formato de mes inválido. Usa YYYY-MM.", "error")

    template_context = {
        "business": business,
        "consumption_by_day": consumption_by_day,
        "selected_month": selected_month,
        "inline_message": inline_message,
        "inline_message_type": inline_message_type,
    }

    if is_htmx_request:
        return render_template(
            "report/partials/_inventory_consumption_content.html",
            **template_context,
        )

    return render_template("report/inventory_consumption.html", **template_context)
