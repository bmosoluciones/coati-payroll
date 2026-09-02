# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

"""Configuración de parámetros de cálculo."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for

from coati_payroll.forms import ConfiguracionCalculosForm
from coati_payroll.i18n import _
from coati_payroll.model import ConfiguracionCalculos, db
from coati_payroll.rbac import require_write_access

config_calculos_bp = Blueprint("config_calculos", __name__, url_prefix="/config-calculos")


def _get_or_create_global_config() -> ConfiguracionCalculos:
    """Get or create the global (empresa=None, pais=None) calculation config."""
    config = db.session.execute(
        db.select(ConfiguracionCalculos).filter(
            ConfiguracionCalculos.empresa_id.is_(None),
            ConfiguracionCalculos.pais_id.is_(None),
            ConfiguracionCalculos.activo.is_(True),
        )
    ).scalar_one_or_none()

    if config:
        return config

    config = ConfiguracionCalculos(
        empresa_id=None,
        pais_id=None,
        activo=True,
    )
    db.session.add(config)
    db.session.commit()
    return config


@config_calculos_bp.route("/", methods=["GET", "POST"])
@require_write_access()
def index():
    """Edit global calculation parameters."""
    config = _get_or_create_global_config()
    form = ConfiguracionCalculosForm(obj=config)

    if form.validate_on_submit():
        config.liquidacion_modo_dias = form.liquidacion_modo_dias.data
        config.liquidacion_factor_calendario = form.liquidacion_factor_calendario.data
        config.liquidacion_factor_laboral = form.liquidacion_factor_laboral.data
        config.dias_anio_antiguedad = form.dias_anio_antiguedad.data
        config.liquidacion_prioridad_prestamos = form.liquidacion_prioridad_prestamos.data
        config.liquidacion_prioridad_adelantos = form.liquidacion_prioridad_adelantos.data
        db.session.commit()
        flash(_("Configuración de cálculos actualizada."), "success")
        return redirect(url_for("config_calculos.index"))

    return render_template(
        "modules/config_calculos/index.html",
        form=form,
        config=config,
    )
