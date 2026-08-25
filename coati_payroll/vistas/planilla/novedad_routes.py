# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Routes for managing novedades (novelties)."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from coati_payroll.model import db, Planilla, Nomina, NominaNovedad
from coati_payroll.forms import NominaNovedadForm
from coati_payroll.i18n import _
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.vistas.planilla import planilla_bp
from coati_payroll.vistas.planilla.helpers import populate_novedad_form_choices
from coati_payroll.vistas.planilla.services import NovedadService

# Constants
ROUTE_LISTAR_NOVEDADES = "planilla.listar_novedades"
ROUTE_LISTAR_NOMINAS = "planilla.listar_nominas"
ERROR_NOMINA_NO_PERTENECE = "La nómina no pertenece a esta planilla."
TEMPLATE_NOVEDAD_FORM = "modules/planilla/novedades/form.html"
NOVEDAD_LOCKED_NOMINA_STATES = {
    "applied",
    "paid",
    "cancelled",
}


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/novedades", methods=["GET"])
@require_read_access()
def listar_novedades(planilla_id: str, nomina_id: str):
    """List all novedades (novelties) for a specific nomina."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    novedades = NovedadService.listar_novedades(planilla, nomina)

    return render_template(
        "modules/planilla/novedades/index.html",
        planilla=planilla,
        nomina=nomina,
        novedades=novedades,
    )


@planilla_bp.route("/<planilla_id>/nomina/<nomina_id>/novedades/new", methods=["GET", "POST"])
@require_write_access()
def nueva_novedad(planilla_id: str, nomina_id: str):
    """Add a new novedad to a nomina."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if nomina.estado in NOVEDAD_LOCKED_NOMINA_STATES:
        flash(_("No se pueden agregar novedades a una nómina aplicada, pagada o anulada."), "error")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    form = NominaNovedadForm()
    populate_novedad_form_choices(form, nomina_id)

    if form.validate_on_submit():
        # Validate that fecha_novedad falls within the nomina period
        is_valid, error_message = NovedadService.validar_fecha_novedad(form.fecha_novedad.data, nomina)
        if not is_valid:
            flash(error_message or _("Fecha de novedad inválida."), "error")
            return render_template(
                TEMPLATE_NOVEDAD_FORM,
                form=form,
                planilla=planilla,
                nomina=nomina,
            )

        NovedadService.crear_novedad(nomina, form, current_user.usuario)
        flash(_("Novedad agregada exitosamente."), "success")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    return render_template(
        TEMPLATE_NOVEDAD_FORM,
        planilla=planilla,
        nomina=nomina,
        form=form,
        is_edit=False,
    )


def _validar_pertenencia_novedad(novedad: NominaNovedad, nomina_id: str, nomina: Nomina) -> bool:
    """Verifica si la novedad pertenece a la nómina (por ID o por rango de fechas si es flotante)."""
    if novedad.nomina_id == nomina_id:
        return True
    if novedad.nomina_id is None:
        if novedad.fecha_novedad and nomina.periodo_inicio <= novedad.fecha_novedad <= nomina.periodo_fin:
            return True
    return False


@planilla_bp.route(
    "/<planilla_id>/nomina/<nomina_id>/novedades/<novedad_id>/edit",
    methods=["GET", "POST"],
)
@require_write_access()
def editar_novedad(planilla_id: str, nomina_id: str, novedad_id: str):
    """Edit an existing novedad."""
    planilla = db.get_or_404(Planilla, planilla_id)
    nomina = db.get_or_404(Nomina, nomina_id)
    novedad = db.get_or_404(NominaNovedad, novedad_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if not _validar_pertenencia_novedad(novedad, nomina_id, nomina):
        flash(_("La novedad no pertenece a esta nómina."), "error")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    if nomina.estado in NOVEDAD_LOCKED_NOMINA_STATES:
        flash(_("No se pueden editar novedades de una nómina aplicada, pagada o anulada."), "error")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    form = NominaNovedadForm(obj=novedad)
    populate_novedad_form_choices(form, nomina_id)

    # Set tipo_concepto based on existing data
    if request.method == "GET":
        if novedad.percepcion_id:
            form.tipo_concepto.data = "income"
            form.percepcion_id.data = novedad.percepcion_id
        elif novedad.deduccion_id:
            form.tipo_concepto.data = "deduction"
            form.deduccion_id.data = novedad.deduccion_id

    if form.validate_on_submit():
        # Validate that fecha_novedad falls within the nomina period
        is_valid, error_message = NovedadService.validar_fecha_novedad(form.fecha_novedad.data, nomina)
        if not is_valid:
            flash(error_message or _("Fecha de novedad inválida."), "error")
            return render_template(
                TEMPLATE_NOVEDAD_FORM,
                form=form,
                planilla=planilla,
                nomina=nomina,
                novedad=novedad,
            )

        NovedadService.actualizar_novedad(novedad, form, current_user.usuario)
        flash(_("Novedad actualizada exitosamente."), "success")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    return render_template(
        TEMPLATE_NOVEDAD_FORM,
        planilla=planilla,
        nomina=nomina,
        form=form,
        novedad=novedad,
        is_edit=True,
    )


@planilla_bp.route(
    "/<planilla_id>/nomina/<nomina_id>/novedades/<novedad_id>/delete",
    methods=["POST"],
)
@require_write_access()
def eliminar_novedad(planilla_id: str, nomina_id: str, novedad_id: str):
    """Delete a novedad from a nomina."""
    nomina = db.get_or_404(Nomina, nomina_id)
    novedad = db.get_or_404(NominaNovedad, novedad_id)

    if nomina.planilla_id != planilla_id:
        flash(_(ERROR_NOMINA_NO_PERTENECE), "error")
        return redirect(url_for(ROUTE_LISTAR_NOMINAS, planilla_id=planilla_id))

    if not _validar_pertenencia_novedad(novedad, nomina_id, nomina):
        flash(_("La novedad no pertenece a esta nómina."), "error")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    if nomina.estado in NOVEDAD_LOCKED_NOMINA_STATES:
        flash(_("No se pueden eliminar novedades de una nómina aplicada, pagada o anulada."), "error")
        return redirect(
            url_for(
                ROUTE_LISTAR_NOVEDADES,
                planilla_id=planilla_id,
                nomina_id=nomina_id,
            )
        )

    db.session.delete(novedad)
    db.session.commit()
    flash(_("Novedad eliminada exitosamente."), "success")
    return redirect(url_for(ROUTE_LISTAR_NOVEDADES, planilla_id=planilla_id, nomina_id=nomina_id))
