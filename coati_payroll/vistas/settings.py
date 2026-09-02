# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Settings page to consolidate administrative options."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for

from coati_payroll.email_service import encrypt_smtp_password, get_email_configuration
from coati_payroll.enums import TipoUsuario
from coati_payroll.forms import ConfiguracionCorreoForm
from coati_payroll.i18n import _
from coati_payroll.model import db
from coati_payroll.rbac import require_role, require_write_access

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET"])
@require_write_access()
def index():
    """Display settings page with links to all configuration options."""
    return render_template("modules/settings/index.html")


@settings_bp.route("/email", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def email():
    """Configure DB-backed SMTP delivery and unknown-browser protection."""
    configuration = get_email_configuration()
    form = ConfiguracionCorreoForm(obj=configuration)
    if configuration is None and not form.is_submitted():
        form.smtp_port.data = 587
        form.smtp_use_tls.data = True
        form.smtp_use_ssl.data = False
        form.sender_name.data = "Coati Payroll"
        form.codigo_login_expira_minutos.data = 10
        form.navegador_confiable_dias.data = 30

    if form.validate_on_submit():
        if form.smtp_use_tls.data and form.smtp_use_ssl.data:
            form.smtp_use_ssl.errors.append(_("Seleccione TLS o SSL, no ambos."))
        if form.activo.data and (not form.smtp_host.data or not form.sender_email.data):
            form.smtp_host.errors.append(_("El servidor SMTP y el correo remitente son requeridos al habilitar el envío."))
        if form.smtp_username.data and not form.smtp_password.data and not (
            configuration and configuration.smtp_password_encrypted
        ):
            form.smtp_password.errors.append(_("La contraseña SMTP es requerida cuando se especifica un usuario."))

        if form.errors:
            return render_template("modules/settings/email.html", form=form, email_config=configuration)

        if configuration is None:
            from coati_payroll.model import ConfiguracionCorreo

            configuration = ConfiguracionCorreo()
            db.session.add(configuration)

        configuration.smtp_host = form.smtp_host.data.strip() if form.smtp_host.data else None
        configuration.smtp_port = form.smtp_port.data
        configuration.smtp_username = form.smtp_username.data.strip() if form.smtp_username.data else None
        if form.smtp_password.data:
            configuration.smtp_password_encrypted = encrypt_smtp_password(form.smtp_password.data)
        configuration.smtp_use_tls = bool(form.smtp_use_tls.data)
        configuration.smtp_use_ssl = bool(form.smtp_use_ssl.data)
        configuration.sender_email = form.sender_email.data.strip() if form.sender_email.data else None
        configuration.sender_name = form.sender_name.data.strip()
        configuration.activo = bool(form.activo.data)
        configuration.proteger_inicio_sesion_origen_desconocido = bool(
            form.proteger_inicio_sesion_origen_desconocido.data
        )
        configuration.codigo_login_expira_minutos = form.codigo_login_expira_minutos.data
        configuration.navegador_confiable_dias = form.navegador_confiable_dias.data
        configuration.modificado_por = _current_admin_name()
        db.session.commit()
        flash(_("Configuración de correo actualizada correctamente."), "success")
        return redirect(url_for("settings.email"))

    return render_template("modules/settings/email.html", form=form, email_config=configuration)


def _current_admin_name() -> str | None:
    """Return the current administrator name for the audit columns."""
    from flask_login import current_user

    return current_user.usuario if current_user.is_authenticated else None
