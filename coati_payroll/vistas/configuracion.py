# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Global configuration views."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from flask import Blueprint, flash, redirect, render_template, url_for

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.i18n import _
from coati_payroll.rbac import require_write_access
from coati_payroll.locale_config import (
    SUPPORTED_LANGUAGES,
    get_language_from_db,
    set_language_in_db,
)

configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")


@configuracion_bp.route("/", methods=["GET"])
@require_write_access()
def index():
    """Display global configuration page."""
    current_language = get_language_from_db()
    language_names = {"en": "English", "es": "Español"}
    from coati_payroll.forms import ConfiguracionIdiomaForm

    form = ConfiguracionIdiomaForm()
    form.idioma.choices = [(lang, language_names[lang]) for lang in SUPPORTED_LANGUAGES]
    form.idioma.data = current_language
    return render_template(
        "modules/configuracion/index.html",
        current_language=current_language,
        supported_languages=SUPPORTED_LANGUAGES,
        language_names=language_names,
        form=form,
    )


@configuracion_bp.route("/idioma", methods=["POST"])
@require_write_access()
def cambiar_idioma():
    """Change the application language."""
    from coati_payroll.forms import ConfiguracionIdiomaForm

    language_names = {"en": "English", "es": "Español"}
    form = ConfiguracionIdiomaForm()
    form.idioma.choices = [(lang, language_names[lang]) for lang in SUPPORTED_LANGUAGES]
    if form.validate_on_submit():
        new_language = form.idioma.data
        try:
            set_language_in_db(new_language)
            flash(
                _(
                    "Idioma actualizado a %(language)s.",
                    language=language_names[new_language],
                ),
                "success",
            )
        except Exception as e:
            flash(_("Error al actualizar el idioma: %(error)s", error=str(e)), "danger")
        return redirect(url_for("configuracion.index"))
    for _field, errors in form.errors.items():
        for error in errors:
            flash(error, "danger")
    return redirect(url_for("configuracion.index"))
