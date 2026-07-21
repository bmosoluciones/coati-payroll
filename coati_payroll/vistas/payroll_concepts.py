# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Payroll concepts CRUD routes: Percepciones, Deducciones, Prestaciones.

This module provides a unified, reusable backend for managing payroll concepts
(perceptions, deductions, benefits) with integrated calculation rule support.
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from coati_payroll.audit_helpers import (
    aprobar_concepto,
    crear_log_auditoria,
    detectar_cambios,
    marcar_como_borrador_si_editado,
    puede_aprobar_concepto,
    rechazar_concepto,
)
from coati_payroll.enums import EstadoAprobacion, FormulaType
from coati_payroll.forms import (
    DeduccionForm,
    PercepcionForm,
    PrestacionForm,
)
from coati_payroll.i18n import _
from coati_payroll.model import Deduccion, Percepcion, Prestacion, db
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.vistas.constants import PER_PAGE

# Create blueprints for each concept type
percepcion_bp = Blueprint("percepcion", __name__, url_prefix="/percepciones")
deduccion_bp = Blueprint("deduccion", __name__, url_prefix="/deducciones")
prestacion_bp = Blueprint("prestacion", __name__, url_prefix="/prestaciones")

# Constants
ERROR_CONCEPT_NOT_FOUND = "%(type)s no encontrada."


# ============================================================================
# SHARED UTILITIES
# ============================================================================


def get_concept_config(concept_type: str) -> dict:
    """Get configuration for a specific concept type.

    Args:
        concept_type: One of 'percepcion', 'deduccion', 'prestacion'

    Returns:
        Dictionary with model, form, labels, and template paths
    """
    match concept_type:
        case "percepcion":
            return {
                "model": Percepcion,
                "form": PercepcionForm,
                "singular": _("Percepción"),
                "plural": _("Percepciones"),
                "icon": "bi-plus-circle",
                "template_dir": "modules/percepcion",
                "blueprint": "percepcion",
                "route_prefix": "percepcion_",
            }
        case "deduccion":
            return {
                "model": Deduccion,
                "form": DeduccionForm,
                "singular": _("Deducción"),
                "plural": _("Deducciones"),
                "icon": "bi-dash-circle",
                "template_dir": "modules/deduccion",
                "blueprint": "deduccion",
                "route_prefix": "deduccion_",
            }
        case "prestacion":
            return {
                "model": Prestacion,
                "form": PrestacionForm,
                "singular": _("Prestación"),
                "plural": _("Prestaciones"),
                "icon": "bi-gift",
                "template_dir": "modules/prestacion",
                "blueprint": "prestacion",
                "route_prefix": "prestacion_",
            }
        case _:
            raise ValueError(f"Unknown concept type: {concept_type}")


def list_concepts(concept_type: str):
    """Generic list view for payroll concepts."""
    config = get_concept_config(concept_type)
    model_class = config["model"]

    page = request.args.get("page", 1, type=int)
    pagination = db.paginate(
        db.select(model_class).order_by(model_class.codigo),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        f"{config['template_dir']}/index.html",
        items=pagination.items,
        pagination=pagination,
        config=config,
    )


def create_concept(concept_type: str):
    """Generic create view for payroll concepts."""
    config = get_concept_config(concept_type)
    model_class = config["model"]
    form_class = config["form"]

    form = form_class()

    if form.validate_on_submit():
        concept = model_class()
        populate_concept_from_form(concept, form)
        concept.creado_por = current_user.usuario

        # Set initial status as draft
        concept.estado_aprobacion = EstadoAprobacion.BORRADOR

        db.session.add(concept)
        db.session.flush()  # Get the ID before creating audit log

        # Create audit log for creation
        crear_log_auditoria(
            concepto=concept,
            accion="created",
            usuario=current_user.usuario,
            descripcion=f"Creó {concept_type} '{concept.nombre}' (código: {concept.codigo})",
            estado_nuevo=EstadoAprobacion.BORRADOR,
        )

        db.session.commit()
        flash(_("%(type)s creada exitosamente en estado borrador.", type=config["singular"]), "success")
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    return render_template(
        f"{config['template_dir']}/form.html",
        form=form,
        title=_("Nueva %(type)s", type=config["singular"]),
        config=config,
    )


def edit_concept(concept_type: str, concept_id: str):
    """Generic edit view for payroll concepts."""
    config = get_concept_config(concept_type)
    model_class = config["model"]
    form_class = config["form"]

    concept = db.session.get(model_class, concept_id)
    if not concept:
        flash(_(ERROR_CONCEPT_NOT_FOUND, type=config["singular"]), "error")
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    # Store original values for change detection
    original_data = {
        "nombre": concept.nombre,
        "descripcion": concept.descripcion,
        "codigo": concept.codigo,
        "formula_tipo": concept.formula_tipo,
        "monto_default": concept.monto_default,
        "porcentaje": concept.porcentaje,
        "base_calculo": concept.base_calculo,
        "invertir_asiento_contable": getattr(concept, "invertir_asiento_contable", None),
        "mostrar_como_ingreso_reportes": getattr(concept, "mostrar_como_ingreso_reportes", None),
        "es_inasistencia": getattr(concept, "es_inasistencia", None),
        "descontar_pago_inasistencia": getattr(concept, "descontar_pago_inasistencia", None),
        "activo": concept.activo,
    }

    form = form_class(obj=concept)
    if request.method == "GET" and hasattr(form, "formula_tipo"):
        normalized_formula_type = FormulaType.normalize(getattr(concept, "formula_tipo", None))
        if normalized_formula_type:
            form.formula_tipo.data = normalized_formula_type.value

    if form.validate_on_submit():
        populate_concept_from_form(concept, form)
        concept.modificado_por = current_user.usuario

        # Detect changes
        new_data = {
            "nombre": concept.nombre,
            "descripcion": concept.descripcion,
            "codigo": concept.codigo,
            "formula_tipo": concept.formula_tipo,
            "monto_default": concept.monto_default,
            "porcentaje": concept.porcentaje,
            "base_calculo": concept.base_calculo,
            "invertir_asiento_contable": getattr(concept, "invertir_asiento_contable", None),
            "mostrar_como_ingreso_reportes": getattr(concept, "mostrar_como_ingreso_reportes", None),
            "es_inasistencia": getattr(concept, "es_inasistencia", None),
            "descontar_pago_inasistencia": getattr(concept, "descontar_pago_inasistencia", None),
            "activo": concept.activo,
        }
        cambios = detectar_cambios(original_data, new_data)

        # Mark as draft if edited (unless created by plugin)
        if cambios:
            marcar_como_borrador_si_editado(concept, current_user.usuario, cambios)

        db.session.commit()

        if concept.estado_aprobacion == EstadoAprobacion.BORRADOR and not concept.creado_por_plugin:
            flash(
                _("%(type)s actualizada. Estado cambiado a borrador - requiere aprobación.", type=config["singular"]),
                "warning",
            )
        else:
            flash(_("%(type)s actualizada exitosamente.", type=config["singular"]), "success")

        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    return render_template(
        f"{config['template_dir']}/form.html",
        form=form,
        title=_("Editar %(type)s", type=config["singular"]),
        concept=concept,
        config=config,
    )


def delete_concept(concept_type: str, concept_id: str):
    """Generic delete view for payroll concepts."""
    config = get_concept_config(concept_type)
    model_class = config["model"]

    concept = db.session.get(model_class, concept_id)
    if not concept:
        flash(_(ERROR_CONCEPT_NOT_FOUND, type=config["singular"]), "error")
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    # Check if concept is in use
    if hasattr(concept, "planillas") and concept.planillas:
        flash(
            _(
                "No se puede eliminar: %(type)s está asociada a una o más planillas.",
                type=config["singular"],
            ),
            "error",
        )
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    db.session.delete(concept)
    db.session.commit()
    flash(_("%(type)s eliminada exitosamente.", type=config["singular"]), "success")
    return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))


def populate_concept_from_form(concept, form):
    """Populate a concept model from a form.

    This is a shared function that handles the common fields
    across Percepcion, Deduccion, and Prestacion.
    """
    concept.codigo = form.codigo.data
    concept.nombre = form.nombre.data
    concept.descripcion = form.descripcion.data
    normalized_formula_type = FormulaType.normalize(form.formula_tipo.data)
    concept.formula_tipo = normalized_formula_type.value if normalized_formula_type else form.formula_tipo.data
    concept.activo = form.activo.data

    # Handle monto_default
    if form.monto_default.data:
        concept.monto_default = Decimal(str(form.monto_default.data))
    else:
        concept.monto_default = None

    # Handle porcentaje
    if form.porcentaje.data:
        concept.porcentaje = Decimal(str(form.porcentaje.data))
    else:
        concept.porcentaje = None

    # Common optional fields
    if hasattr(form, "base_calculo") and form.base_calculo.data:
        concept.base_calculo = form.base_calculo.data

    if hasattr(form, "unidad_calculo") and form.unidad_calculo.data:
        concept.unidad_calculo = form.unidad_calculo.data

    if hasattr(form, "recurrente"):
        concept.recurrente = form.recurrente.data

    if hasattr(form, "contabilizable"):
        concept.contabilizable = form.contabilizable.data

    if hasattr(form, "invertir_asiento_contable"):
        concept.invertir_asiento_contable = form.invertir_asiento_contable.data

    if hasattr(form, "codigo_cuenta_debe") and form.codigo_cuenta_debe.data:
        concept.codigo_cuenta_debe = form.codigo_cuenta_debe.data

    if hasattr(form, "descripcion_cuenta_debe") and form.descripcion_cuenta_debe.data:
        concept.descripcion_cuenta_debe = form.descripcion_cuenta_debe.data

    if hasattr(form, "codigo_cuenta_haber") and form.codigo_cuenta_haber.data:
        concept.codigo_cuenta_haber = form.codigo_cuenta_haber.data

    if hasattr(form, "descripcion_cuenta_haber") and form.descripcion_cuenta_haber.data:
        concept.descripcion_cuenta_haber = form.descripcion_cuenta_haber.data

    if hasattr(form, "mostrar_como_ingreso_reportes"):
        concept.mostrar_como_ingreso_reportes = form.mostrar_como_ingreso_reportes.data

    if hasattr(form, "editable_en_nomina"):
        concept.editable_en_nomina = form.editable_en_nomina.data

    if hasattr(form, "es_inasistencia"):
        concept.es_inasistencia = form.es_inasistencia.data

    if hasattr(form, "descontar_pago_inasistencia"):
        concept.descontar_pago_inasistencia = form.descontar_pago_inasistencia.data

    # Vigencia fields
    if hasattr(form, "vigente_desde"):
        concept.vigente_desde = form.vigente_desde.data

    if hasattr(form, "valido_hasta"):
        concept.valido_hasta = form.valido_hasta.data

    # Type-specific fields
    if hasattr(form, "gravable"):  # Percepcion
        concept.gravable = form.gravable.data

    if hasattr(form, "tipo") and form.tipo.data:  # Deduccion, Prestacion
        concept.tipo = form.tipo.data

    if hasattr(form, "es_impuesto"):  # Deduccion
        concept.es_impuesto = form.es_impuesto.data

    if hasattr(form, "antes_impuesto"):  # Deduccion
        concept.antes_impuesto = form.antes_impuesto.data

    # Prestacion-specific fields
    if hasattr(form, "tope_aplicacion"):
        if form.tope_aplicacion.data:
            concept.tope_aplicacion = Decimal(str(form.tope_aplicacion.data))
        else:
            concept.tope_aplicacion = None


# ============================================================================
# PERCEPCION ROUTES
# ============================================================================


@percepcion_bp.route("/", methods=["GET"])
@require_read_access()
def percepcion_index():
    """List all perceptions."""
    return list_concepts("percepcion")


@percepcion_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def percepcion_new():
    """Create a new perception. Admin and HR can create perceptions."""
    return create_concept("percepcion")


@percepcion_bp.route("/edit/<string:concept_id>", methods=["GET", "POST"])
@require_write_access()
def percepcion_edit(concept_id: str):
    """Edit an existing perception. Admin and HR can edit perceptions."""
    return edit_concept("percepcion", concept_id)


@percepcion_bp.route("/delete/<string:concept_id>", methods=["POST"])
@require_write_access()
def percepcion_delete(concept_id: str):
    """Delete a perception. Admin and HR can delete perceptions."""
    return delete_concept("percepcion", concept_id)


# ============================================================================
# DEDUCCION ROUTES
# ============================================================================


@deduccion_bp.route("/", methods=["GET"])
@require_read_access()
def deduccion_index():
    """List all deductions."""
    return list_concepts("deduccion")


@deduccion_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def deduccion_new():
    """Create a new deduction. Admin and HR can create deductions."""
    return create_concept("deduccion")


@deduccion_bp.route("/edit/<string:concept_id>", methods=["GET", "POST"])
@require_write_access()
def deduccion_edit(concept_id: str):
    """Edit an existing deduction. Admin and HR can edit deductions."""
    return edit_concept("deduccion", concept_id)


@deduccion_bp.route("/delete/<string:concept_id>", methods=["POST"])
@require_write_access()
def deduccion_delete(concept_id: str):
    """Delete a deduction. Admin and HR can delete deductions."""
    return delete_concept("deduccion", concept_id)


# ============================================================================
# PRESTACION ROUTES
# ============================================================================


@prestacion_bp.route("/", methods=["GET"])
@require_read_access()
def prestacion_index():
    """List all benefits."""
    return list_concepts("prestacion")


@prestacion_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def prestacion_new():
    """Create a new benefit. Admin and HR can create benefits."""
    return create_concept("prestacion")


@prestacion_bp.route("/edit/<string:concept_id>", methods=["GET", "POST"])
@require_write_access()
def prestacion_edit(concept_id: str):
    """Edit an existing benefit. Admin and HR can edit benefits."""
    return edit_concept("prestacion", concept_id)


@prestacion_bp.route("/delete/<string:concept_id>", methods=["POST"])
@require_write_access()
def prestacion_delete(concept_id: str):
    """Delete a benefit. Admin and HR can delete benefits."""
    return delete_concept("prestacion", concept_id)


# ============================================================================
# APPROVAL ROUTES (for all concept types)
# ============================================================================


def approve_concept_route(concept_type: str, concept_id: str):
    """Generic approval route for payroll concepts."""
    # Check if user can approve
    if not puede_aprobar_concepto(current_user.tipo):
        flash(_("No tiene permisos para aprobar conceptos de nómina."), "error")
        return redirect(url_for(f"{concept_type}.{concept_type}_index"))

    config = get_concept_config(concept_type)
    model_class = config["model"]

    concept = db.session.get(model_class, concept_id)
    if not concept:
        flash(_(ERROR_CONCEPT_NOT_FOUND, type=config["singular"]), "error")
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    # Approve the concept
    if aprobar_concepto(concept, current_user.usuario):
        db.session.commit()
        flash(_("%(type)s aprobada exitosamente.", type=config["singular"]), "success")
    else:
        flash(_("%(type)s ya está aprobada.", type=config["singular"]), "info")

    return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))


def reject_concept_route(concept_type: str, concept_id: str):
    """Generic rejection route for payroll concepts."""
    # Check if user can approve/reject
    if not puede_aprobar_concepto(current_user.tipo):
        flash(_("No tiene permisos para rechazar conceptos de nómina."), "error")
        return redirect(url_for(f"{concept_type}.{concept_type}_index"))

    config = get_concept_config(concept_type)
    model_class = config["model"]

    concept = db.session.get(model_class, concept_id)
    if not concept:
        flash(_(ERROR_CONCEPT_NOT_FOUND, type=config["singular"]), "error")
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    # Get rejection reason from form
    razon = request.form.get("razon", "")

    # Reject the concept
    rechazar_concepto(concept, current_user.usuario, razon)
    db.session.commit()
    flash(_("%(type)s marcada como borrador.", type=config["singular"]), "warning")

    return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))


def view_audit_log_route(concept_type: str, concept_id: str):
    """View audit log for a specific concept."""
    config = get_concept_config(concept_type)
    model_class = config["model"]

    concept = db.session.get(model_class, concept_id)
    if not concept:
        flash(_(ERROR_CONCEPT_NOT_FOUND, type=config["singular"]), "error")
        return redirect(url_for(f"{config['blueprint']}.{concept_type}_index"))

    # Get audit logs
    audit_logs = sorted(concept.audit_logs, key=lambda x: x.timestamp, reverse=True)

    return render_template(
        "modules/payroll_concepts/audit_log.html",
        concept=concept,
        audit_logs=audit_logs,
        config=config,
    )


# Percepcion approval routes
@percepcion_bp.route("/approve/<string:concept_id>", methods=["POST"])
@require_write_access()
def percepcion_approve(concept_id: str):
    """Approve a perception. Only ADMIN and HHRR can approve."""
    return approve_concept_route("percepcion", concept_id)


@percepcion_bp.route("/reject/<string:concept_id>", methods=["POST"])
@require_write_access()
def percepcion_reject(concept_id: str):
    """Reject a perception. Only ADMIN and HHRR can reject."""
    return reject_concept_route("percepcion", concept_id)


@percepcion_bp.route("/audit/<string:concept_id>", methods=["GET"])
@require_read_access()
def percepcion_audit(concept_id: str):
    """View audit log for a perception."""
    return view_audit_log_route("percepcion", concept_id)


# Deduccion approval routes
@deduccion_bp.route("/approve/<string:concept_id>", methods=["POST"])
@require_write_access()
def deduccion_approve(concept_id: str):
    """Approve a deduction. Only ADMIN and HHRR can approve."""
    return approve_concept_route("deduccion", concept_id)


@deduccion_bp.route("/reject/<string:concept_id>", methods=["POST"])
@require_write_access()
def deduccion_reject(concept_id: str):
    """Reject a deduction. Only ADMIN and HHRR can reject."""
    return reject_concept_route("deduccion", concept_id)


@deduccion_bp.route("/audit/<string:concept_id>", methods=["GET"])
@require_read_access()
def deduccion_audit(concept_id: str):
    """View audit log for a deduction."""
    return view_audit_log_route("deduccion", concept_id)


# Prestacion approval routes
@prestacion_bp.route("/approve/<string:concept_id>", methods=["POST"])
@require_write_access()
def prestacion_approve(concept_id: str):
    """Approve a benefit. Only ADMIN and HHRR can approve."""
    return approve_concept_route("prestacion", concept_id)


@prestacion_bp.route("/reject/<string:concept_id>", methods=["POST"])
@require_write_access()
def prestacion_reject(concept_id: str):
    """Reject a benefit. Only ADMIN and HHRR can reject."""
    return reject_concept_route("prestacion", concept_id)


@prestacion_bp.route("/audit/<string:concept_id>", methods=["GET"])
@require_read_access()
def prestacion_audit(concept_id: str):
    """View audit log for a benefit."""
    return view_audit_log_route("prestacion", concept_id)
