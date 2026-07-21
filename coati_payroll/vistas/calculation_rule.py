# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Calculation rules CRUD routes."""

from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user

from coati_payroll.forms import ReglaCalculoForm
from coati_payroll.i18n import _
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.model import ReglaCalculo, db
from coati_payroll.vistas.constants import PER_PAGE
from coati_payroll.formula_engine import (
    FormulaEngine,
    FormulaEngineError,
    EXAMPLE_IR_NICARAGUA_SCHEMA,
    get_available_sources_for_ui,
)

calculation_rule_bp = Blueprint("calculation_rule", __name__, url_prefix="/calculation-rule")

# Constants
ERROR_RULE_NOT_FOUND = "Regla no encontrada"


@calculation_rule_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all calculation rules with pagination."""
    page = request.args.get("page", 1, type=int)
    pagination = db.paginate(
        db.select(ReglaCalculo).order_by(ReglaCalculo.codigo, ReglaCalculo.version.desc()),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "modules/calculation_rule/index.html",
        rules=pagination.items,
        pagination=pagination,
    )


# Default schema structure for new rules
DEFAULT_SCHEMA = {
    "meta": {
        "name": "",
        "currency": "",
        "description": "",
    },
    "inputs": [],
    "steps": [],
    "tax_tables": {},
    "output": "",
}


@calculation_rule_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def new():
    """Create a new calculation rule."""
    form = ReglaCalculoForm()

    if form.validate_on_submit():
        rule = ReglaCalculo()
        rule.codigo = form.codigo.data
        rule.nombre = form.nombre.data
        rule.descripcion = form.descripcion.data
        rule.jurisdiccion = form.jurisdiccion.data
        rule.moneda_referencia = form.moneda_referencia.data
        rule.version = form.version.data
        rule.tipo_regla = form.tipo_regla.data
        rule.vigente_desde = form.vigente_desde.data
        rule.vigente_hasta = form.vigente_hasta.data
        rule.activo = form.activo.data
        # Initialize with default schema structure
        # Note: The rule's reference currency is for calculation purposes.
        # The actual payroll currency is defined in TipoPlanilla.
        rule.esquema_json = DEFAULT_SCHEMA
        rule.creado_por = current_user.usuario

        db.session.add(rule)
        db.session.commit()
        flash(_("Regla de cálculo creada exitosamente."), "success")
        return redirect(url_for("calculation_rule.edit_schema", id_=rule.id))

    return render_template(
        "modules/calculation_rule/form.html",
        form=form,
        title=_("Nueva Regla de Cálculo"),
    )


@calculation_rule_bp.route("/edit/<string:id_>", methods=["GET", "POST"])
@require_write_access()
def edit(id_: str):
    """Edit an existing calculation rule metadata."""
    rule = db.session.get(ReglaCalculo, id_)
    if not rule:
        flash(_(ERROR_RULE_NOT_FOUND), "error")
        return redirect(url_for("calculation_rule.index"))

    form = ReglaCalculoForm(obj=rule)

    if form.validate_on_submit():
        rule.codigo = form.codigo.data
        rule.nombre = form.nombre.data
        rule.descripcion = form.descripcion.data
        rule.jurisdiccion = form.jurisdiccion.data
        rule.moneda_referencia = form.moneda_referencia.data
        rule.version = form.version.data
        rule.tipo_regla = form.tipo_regla.data
        rule.vigente_desde = form.vigente_desde.data
        rule.vigente_hasta = form.vigente_hasta.data
        rule.activo = form.activo.data
        rule.modificado_por = current_user.usuario

        db.session.commit()
        flash(_("Regla de cálculo actualizada exitosamente."), "success")
        return redirect(url_for("calculation_rule.index"))

    return render_template(
        "modules/calculation_rule/form.html",
        form=form,
        title=_("Editar Regla de Cálculo"),
        rule=rule,
    )


@calculation_rule_bp.route("/edit-schema/<string:id_>", methods=["GET"])
@require_write_access()
def edit_schema(id_: str):
    """Edit the JSON schema of a calculation rule."""

    rule = db.session.get(ReglaCalculo, id_)

    if not rule:
        flash(_(ERROR_RULE_NOT_FOUND), "error")
        return redirect(url_for("calculation_rule.index"))

    # Get available data sources for the UI
    available_sources = get_available_sources_for_ui()

    raw_schema = rule.esquema_json
    if raw_schema:
        current_schema = json.loads(json.dumps(dict(raw_schema)))
    else:
        current_schema = DEFAULT_SCHEMA

    return render_template(
        "modules/calculation_rule/schema_editor.html",
        rule=rule,
        schema_data=current_schema,
        example_schema_data=EXAMPLE_IR_NICARAGUA_SCHEMA,
        available_sources_data=available_sources,
    )


@calculation_rule_bp.route("/api/save-schema/<string:id_>", methods=["POST"])
@require_write_access()
def save_schema(id_: str):
    """API endpoint to save the JSON schema."""
    rule = db.session.get(ReglaCalculo, id_)
    if not rule:
        return jsonify({"success": False, "error": ERROR_RULE_NOT_FOUND}), 404

    try:
        data = request.get_json()
        schema = data.get("schema", {})

        # Validate schema by trying to create a FormulaEngine instance
        try:
            FormulaEngine(schema)
        except FormulaEngineError as e:
            return jsonify({"success": False, "error": f"Esquema inválido: {e}"}), 400

        rule.esquema_json = schema
        rule.modificado_por = current_user.usuario
        db.session.commit()

        return jsonify({"success": True, "message": "Esquema guardado exitosamente"})
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"JSON inválido: {e}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@calculation_rule_bp.route("/api/validate-schema/<string:id_>", methods=["POST"])
@require_write_access()
def validate_schema_api(id_: str):
    """API endpoint to validate a JSON schema without saving it."""
    rule = db.session.get(ReglaCalculo, id_)
    if not rule:
        return jsonify({"success": False, "error": ERROR_RULE_NOT_FOUND}), 404

    try:
        data = request.get_json()
        schema = data.get("schema", {})

        # Validate schema structure and formula safety
        from coati_payroll.schema_validator import validate_schema_deep

        try:
            validate_schema_deep(schema)
        except Exception as e:
            return jsonify({"success": False, "error": f"Esquema inválido: {e}"}), 400

        # Also validate by trying to create a FormulaEngine instance
        try:
            FormulaEngine(schema)
        except FormulaEngineError as e:
            return jsonify({"success": False, "error": f"Esquema inválido: {e}"}), 400

        return jsonify({"success": True, "message": "Esquema válido"})
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"JSON inválido: {e}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@calculation_rule_bp.route("/api/test-schema/<string:id_>", methods=["POST"])
@require_write_access()
def test_schema(id_: str):
    """API endpoint to test the calculation schema with sample data."""
    rule = db.session.get(ReglaCalculo, id_)
    if not rule:
        return jsonify({"success": False, "error": ERROR_RULE_NOT_FOUND}), 404

    try:
        data = request.get_json()
        schema = data.get("schema", rule.esquema_json or {})
        test_inputs = data.get("inputs", {})

        engine = FormulaEngine(schema)
        result = engine.execute(test_inputs)

        return jsonify({"success": True, "result": result})
    except FormulaEngineError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@calculation_rule_bp.route("/delete/<string:id_>", methods=["POST"])
@require_write_access()
def delete(id_: str):
    """Delete a calculation rule."""
    rule = db.session.get(ReglaCalculo, id_)
    if not rule:
        flash(_(ERROR_RULE_NOT_FOUND), "error")
        return redirect(url_for("calculation_rule.index"))

    db.session.delete(rule)
    db.session.commit()
    flash(_("Regla de cálculo eliminada exitosamente."), "success")
    return redirect(url_for("calculation_rule.index"))


@calculation_rule_bp.route("/duplicate/<string:id_>", methods=["POST"])
@require_write_access()
def duplicate(id_: str):
    """Duplicate a calculation rule with a new version."""
    rule = db.session.get(ReglaCalculo, id_)
    if not rule:
        flash(_(ERROR_RULE_NOT_FOUND), "error")
        return redirect(url_for("calculation_rule.index"))

    # Create a new rule with incremented version
    new_rule = ReglaCalculo()
    new_rule.codigo = rule.codigo
    new_rule.nombre = rule.nombre
    new_rule.descripcion = rule.descripcion
    new_rule.jurisdiccion = rule.jurisdiccion
    new_rule.moneda_referencia = rule.moneda_referencia
    new_rule.tipo_regla = rule.tipo_regla
    new_rule.vigente_desde = rule.vigente_desde
    new_rule.vigente_hasta = rule.vigente_hasta
    new_rule.activo = False  # New version starts inactive
    new_rule.esquema_json = rule.esquema_json.copy() if rule.esquema_json else {}
    new_rule.creado_por = current_user.usuario

    # Increment version
    try:
        parts = rule.version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        new_rule.version = ".".join(parts)
    except (ValueError, IndexError):
        new_rule.version = rule.version + ".1"

    db.session.add(new_rule)
    db.session.commit()
    flash(_("Regla de cálculo duplicada exitosamente."), "success")
    return redirect(url_for("calculation_rule.edit_schema", id_=new_rule.id))
