# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Auth module."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from datetime import datetime, UTC

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.model import Usuario, database
from coati_payroll.forms import LoginForm
from coati_payroll.i18n import _
from coati_payroll.rate_limiting import limiter

auth = Blueprint("auth", __name__)


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

        if validar_acceso(usuario_id, clave):
            # Cargar el registro del usuario (puede buscar por usuario o correo)
            registro = database.session.execute(
                database.select(Usuario).filter_by(usuario=usuario_id)
            ).scalar_one_or_none()

            if not registro:
                registro = database.session.execute(
                    database.select(Usuario).filter_by(correo_electronico=usuario_id)
                ).scalar_one_or_none()

            if registro is not None:
                login_user(registro)
                return redirect(url_for("app.index"))

        # Si llegamos aquí, el login falló
        flash(_("Usuario o contraseña incorrectos."), "error")

    return render_template("auth/login.html", form=form)


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    """Cerrar sesión del usuario."""
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
    """Verifica el inicio de sesión del usuario."""
    if not (
        registro := database.session.execute(
            database.select(Usuario).filter_by(usuario=usuario_id)
        ).scalar_one_or_none()
    ):
        registro = database.session.execute(
            database.select(Usuario).filter_by(correo_electronico=usuario_id)
        ).scalar_one_or_none()

    if registro is not None and registro.activo:
        try:
            hash_pwd = (
                registro.acceso.decode("utf-8") if isinstance(registro.acceso, (bytes, bytearray)) else registro.acceso
            )
            ph.verify(hash_pwd, acceso)
            clave_validada = True
        except VerifyMismatchError:
            clave_validada = False
    else:
        clave_validada = False

    if clave_validada and registro is not None:
        registro.ultimo_acceso = datetime.now(UTC)
        database.session.commit()

    return clave_validada
