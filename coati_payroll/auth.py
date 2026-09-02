# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Auth module."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from datetime import datetime, UTC, timedelta
import hmac
from typing import cast

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_user, logout_user, login_required

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.model import TokenCorreo, Usuario, database
from coati_payroll.audit_helpers import registrar_evento_seguridad
from coati_payroll.forms import (
    LoginForm,
    LoginVerificationForm,
    PasswordRecoveryRequestForm,
    PasswordResetForm,
)
from coati_payroll.i18n import _
from coati_payroll.rate_limiting import limiter
from coati_payroll.auth_security import (
    LOGIN_VERIFICATION_PURPOSE,
    MAX_LOGIN_TOKEN_ATTEMPTS,
    PASSWORD_RESET_PURPOSE,
    consume_email_token,
    find_email_token,
    hash_secret,
    is_trusted_browser,
    issue_email_token,
    issue_trusted_browser,
    revoke_trusted_browsers,
    utc_now,
)
from coati_payroll.email_service import email_delivery_configured, get_email_configuration, send_email

auth = Blueprint("auth", __name__)
PENDING_LOGIN_USER_KEY = "pending_login_user_id"
PENDING_LOGIN_TOKEN_KEY = "pending_login_token_id"
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    """Mostrar y procesar el formulario de inicio de sesión.

    Rate limited to 5 attempts per minute per IP address to prevent
    brute force attacks on user credentials. Rate limiting is configured
    in coati_payroll/__init__.py using Flask-Limiter.
    """
    form = LoginForm()

    if form.validate_on_submit():
        usuario_id = form.email.data or ""
        clave = form.password.data or ""

        registro = autenticar_usuario(usuario_id, clave)
        if registro is not None:
            registrar_evento_seguridad("login_success", registro.usuario, objetivo=registro.usuario)
            database.session.commit()
            configuration = get_email_configuration()
            requires_verification = bool(
                registro.correo_electronico
                and configuration is not None
                and configuration.proteger_inicio_sesion_origen_desconocido
            )
            if requires_verification and not is_trusted_browser(registro):
                if _start_login_verification(registro, configuration):
                    flash(_("Hemos enviado un código de verificación a tu correo."), "info")
                    return redirect(url_for("auth.verify_login"))
                flash(_("No fue posible enviar el código de verificación. Contacta al administrador."), "error")
            else:
                login_user(registro)
                response = redirect(url_for("app.index"))
                issue_trusted_browser(response, registro)
                return response

        # Si llegamos aquí, el login falló
        registrar_evento_seguridad("login_failed", usuario_id, objetivo=usuario_id, exito=False)
        database.session.commit()
        flash(_("Usuario o contraseña incorrectos."), "error")

    return render_template("auth/login.html", form=form)


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    """Cerrar sesión del usuario."""
    registrar_evento_seguridad("logout", current_user.usuario, objetivo=current_user.usuario)
    database.session.commit()
    logout_user()
    flash(_("Sesión cerrada correctamente."), "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------------------
# Proteger contraseñas de usuarios.
# ---------------------------------------------------------------------------------------
ph = PasswordHasher()


def proteger_passwd(clave: str, /) -> bytes:
    """Devuelve una contraseña salteada con argon2."""
    _hash = ph.hash(clave.encode()).encode("utf-8")

    return _hash


def validar_acceso(usuario_id: str, acceso: str, /) -> bool:
    """Verify credentials and apply persistent failed-login protection."""
    return autenticar_usuario(usuario_id, acceso) is not None


def _find_user(identifier: str) -> Usuario | None:
    """Find a user by username or email without exposing which one matched."""
    registro = database.session.execute(database.select(Usuario).filter_by(usuario=identifier)).scalar_one_or_none()
    if registro is None:
        registro = database.session.execute(
            database.select(Usuario).filter_by(correo_electronico=identifier)
        ).scalar_one_or_none()
    return registro


def autenticar_usuario(usuario_id: str, acceso: str) -> Usuario | None:
    """Authenticate a user and return it only after a valid password."""
    registro = _find_user(usuario_id)
    if registro is None or not registro.activo:
        return None

    now = utc_now()
    if registro.bloqueado_hasta is not None:
        if registro.bloqueado_hasta > now:
            return None
        registro.bloqueado_hasta = None
        registro.intentos_login_fallidos = 0

    try:
        hash_pwd = (
            registro.acceso.decode("utf-8") if isinstance(registro.acceso, (bytes, bytearray)) else registro.acceso
        )
        ph.verify(hash_pwd, acceso)
    except (VerifyMismatchError, VerificationError, TypeError, AttributeError):
        registro.intentos_login_fallidos = (registro.intentos_login_fallidos or 0) + 1
        if registro.intentos_login_fallidos >= MAX_FAILED_LOGIN_ATTEMPTS:
            registro.bloqueado_hasta = now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
        database.session.commit()
        return None

    registro.intentos_login_fallidos = 0
    registro.bloqueado_hasta = None
    registro.ultimo_acceso = datetime.now(UTC)
    database.session.commit()
    return registro


def _start_login_verification(usuario: Usuario, configuration) -> bool:
    """Create and email a one-time login code."""
    if not email_delivery_configured(configuration):
        return False
    token, code = issue_email_token(
        usuario,
        LOGIN_VERIFICATION_PURPOSE,
        ttl_minutes=configuration.codigo_login_expira_minutos,
        code=True,
    )
    if not send_email(
        usuario.correo_electronico,
        _("Código de verificación de inicio de sesión"),
        _(
            "Tu código de verificación es: %(code)s\n\n"
            "El código expira en %(minutes)s minutos y solo puede utilizarse una vez. "
            "Si no solicitaste este inicio de sesión, cambia tu contraseña."
        )
        % {"code": code, "minutes": configuration.codigo_login_expira_minutos},
    ):
        database.session.rollback()
        return False
    database.session.commit()
    session[PENDING_LOGIN_USER_KEY] = usuario.id
    session[PENDING_LOGIN_TOKEN_KEY] = token.id
    return True


@auth.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def forgot_password():
    """Request a reset email while keeping account existence private."""
    form = PasswordRecoveryRequestForm()
    if form.validate_on_submit():
        usuario = _find_user(form.identificador.data.strip())
        configuration = get_email_configuration()
        if (
            usuario is not None
            and usuario.activo
            and usuario.correo_electronico
            and email_delivery_configured(configuration)
        ):
            token, raw_token = issue_email_token(
                usuario,
                PASSWORD_RESET_PURPOSE,
                ttl_minutes=30,
            )
            reset_url = url_for("auth.reset_password", token=raw_token, _external=True)
            sent = send_email(
                usuario.correo_electronico,
                _("Restablecer contraseña de Coati Payroll"),
                _(
                    "Recibimos una solicitud para restablecer tu contraseña.\n\n"
                    "Abre este enlace para continuar (expira en 30 minutos):\n%(url)s\n\n"
                    "Si no solicitaste el cambio, ignora este mensaje."
                )
                % {"url": reset_url},
            )
            if sent:
                database.session.commit()
            else:
                database.session.rollback()
        # Deliberately identical for unknown users, missing email, and delivery failure.
        flash(_("Si la cuenta existe y tiene un correo configurado, recibirás instrucciones."), "info")
        return redirect(url_for("auth.forgot_password"))
    return render_template("auth/forgot_password.html", form=form)


@auth.route("/reset-password/<string:token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Reset a password using a hashed, expiring, one-time token."""
    token_record = find_email_token(token, PASSWORD_RESET_PURPOSE)
    if token_record is None or token_record.usuario is None or not token_record.usuario.activo:
        flash(_("El enlace de recuperación no es válido o ya expiró."), "error")
        return redirect(url_for("auth.forgot_password"))

    form = PasswordResetForm()
    if form.validate_on_submit():
        token_record = find_email_token(token, PASSWORD_RESET_PURPOSE)
        if token_record is None or token_record.usuario is None:
            flash(_("El enlace de recuperación no es válido o ya expiró."), "error")
            return redirect(url_for("auth.forgot_password"))
        usuario = cast(Usuario, token_record.usuario)
        usuario.acceso = proteger_passwd(form.nueva_contrasena.data)
        usuario.intentos_login_fallidos = 0
        usuario.bloqueado_hasta = None
        consume_email_token(token_record)
        revoke_trusted_browsers(usuario)
        database.session.commit()
        flash(_("Contraseña actualizada. Ya puedes iniciar sesión."), "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)


@auth.route("/verify-login", methods=["GET", "POST"])
def verify_login():
    """Verify an email code before completing an unknown-browser login."""
    user_id = session.get(PENDING_LOGIN_USER_KEY)
    token_id = session.get(PENDING_LOGIN_TOKEN_KEY)
    if not user_id or not token_id:
        return redirect(url_for("auth.login"))

    usuario = database.session.get(Usuario, user_id)
    token_record = database.session.get(TokenCorreo, token_id)
    now = utc_now()
    if (
        usuario is None
        or token_record is None
        or token_record.usuario_id != usuario.id
        or token_record.proposito != LOGIN_VERIFICATION_PURPOSE
        or token_record.usado_en is not None
        or token_record.expira_en <= now
        or token_record.intentos_fallidos >= MAX_LOGIN_TOKEN_ATTEMPTS
    ):
        session.pop(PENDING_LOGIN_USER_KEY, None)
        session.pop(PENDING_LOGIN_TOKEN_KEY, None)
        flash(_("El código de verificación no es válido o ya expiró."), "error")
        return redirect(url_for("auth.login"))

    form = LoginVerificationForm()
    if form.validate_on_submit():
        expected = hash_secret(form.codigo.data)
        if not hmac.compare_digest(token_record.token_hash, expected):
            token_record.intentos_fallidos += 1
            if token_record.intentos_fallidos >= MAX_LOGIN_TOKEN_ATTEMPTS:
                consume_email_token(token_record)
            database.session.commit()
            flash(_("El código de verificación no es válido."), "error")
            return render_template("auth/verify_login.html", form=form)

        consume_email_token(token_record)
        session.pop(PENDING_LOGIN_USER_KEY, None)
        session.pop(PENDING_LOGIN_TOKEN_KEY, None)
        database.session.commit()
        login_user(usuario)
        response = redirect(url_for("app.index"))
        issue_trusted_browser(response, usuario)
        return response
    return render_template("auth/verify_login.html", form=form)
