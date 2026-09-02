# SPDX-License-Identifier: Apache-2.0
"""Regression tests for email recovery and unknown-browser protection."""

import re
from importlib import import_module

from coati_payroll.auth_security import PASSWORD_RESET_PURPOSE
from coati_payroll.enums import TipoUsuario
from coati_payroll.model import ConfiguracionCorreo, TokenCorreo, db
from tests.factories.user_factory import create_user
from tests.helpers.auth import login_user


def _email_config(db_session, *, protect=False):
    configuration = ConfiguracionCorreo(
        smtp_host="smtp.example.test",
        smtp_port=587,
        sender_email="noreply@example.test",
        sender_name="Coati Payroll",
        activo=True,
        proteger_inicio_sesion_origen_desconocido=protect,
        codigo_login_expira_minutos=10,
        navegador_confiable_dias=30,
    )
    db_session.add(configuration)
    db_session.commit()
    return configuration


def test_forgot_password_keeps_unknown_and_known_accounts_generic(client, db_session, monkeypatch):
    user = create_user(db_session, "recoverable", "old-password", correo_electronico="user@example.test")
    _email_config(db_session)
    auth_module = import_module("coati_payroll.auth")
    monkeypatch.setattr(auth_module, "send_email", lambda *args, **kwargs: True)

    known = client.post("/auth/forgot-password", data={"identificador": user.usuario})
    unknown = client.post("/auth/forgot-password", data={"identificador": "does-not-exist"})

    assert known.status_code == unknown.status_code == 302
    assert known.headers["Location"] == unknown.headers["Location"]
    assert db.session.query(TokenCorreo).filter_by(proposito=PASSWORD_RESET_PURPOSE).count() == 1


def test_password_reset_is_one_time_and_revokes_trusted_browsers(client, db_session, monkeypatch):
    user = create_user(db_session, "reset-user", "old-password", correo_electronico="reset@example.test")
    _email_config(db_session)
    sent = {}

    def capture_email(to, subject, body, **kwargs):
        sent["body"] = body
        return True

    monkeypatch.setattr(import_module("coati_payroll.auth"), "send_email", capture_email)
    client.post("/auth/forgot-password", data={"identificador": user.usuario})
    token = re.search(r"reset-password/([^\s]+)", sent["body"]).group(1)

    assert client.get(f"/auth/reset-password/{token}").status_code == 200
    response = client.post(
        f"/auth/reset-password/{token}",
        data={"nueva_contrasena": "new-password", "confirmar_contrasena": "new-password"},
    )
    assert response.status_code == 302
    assert client.get(f"/auth/reset-password/{token}").status_code == 302

    from coati_payroll.auth import validar_acceso

    assert validar_acceso(user.usuario, "old-password") is False
    assert validar_acceso(user.usuario, "new-password") is True


def test_unknown_browser_requires_email_code_and_sets_trusted_cookie(client, db_session, monkeypatch):
    user = create_user(db_session, "secure-user", "secure-password", correo_electronico="secure@example.test")
    _email_config(db_session, protect=True)
    sent = {}

    def capture_email(to, subject, body, **kwargs):
        sent["body"] = body
        return True

    monkeypatch.setattr(import_module("coati_payroll.auth"), "send_email", capture_email)
    challenge = login_user(client, user.usuario, "secure-password")
    assert challenge.status_code == 302
    assert challenge.headers["Location"].endswith("/auth/verify-login")
    assert b"_user_id" not in challenge.data

    code = re.search(r"\b(\d{6})\b", sent["body"]).group(1)
    verified = client.post("/auth/verify-login", data={"codigo": code})
    assert verified.status_code == 302
    assert verified.headers["Location"].endswith("/")
    assert client.get_cookie("coati_trusted_browser") is not None

    client.post("/auth/logout")
    sent.clear()
    trusted_login = login_user(client, user.usuario, "secure-password")
    assert trusted_login.status_code == 302
    assert trusted_login.headers["Location"].endswith("/")
    assert sent == {}


def test_unknown_browser_protection_does_not_apply_without_user_email(client, db_session):
    user = create_user(db_session, "no-email-user", "secure-password")
    _email_config(db_session, protect=True)

    response = login_user(client, user.usuario, "secure-password")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_failed_login_persists_lockout(client, db_session):
    user = create_user(db_session, "locked-user", "secure-password")

    for _ in range(5):
        assert login_user(client, user.usuario, "wrong-password").status_code == 200

    db_session.refresh(user)
    assert user.intentos_login_fallidos == 5
    assert user.bloqueado_hasta is not None
    assert login_user(client, user.usuario, "secure-password").status_code == 200


def test_admin_can_configure_encrypted_smtp_and_security(client, db_session, admin_user):
    login_user(client, admin_user.usuario, "admin-password")
    response = client.post(
        "/settings/email",
        data={
            "smtp_host": "smtp.example.test",
            "smtp_port": "465",
            "smtp_username": "mailer",
            "smtp_password": "smtp-secret",
            "sender_email": "noreply@example.com",
            "sender_name": "Coati Payroll",
            "smtp_use_ssl": "y",
            "activo": "y",
            "proteger_inicio_sesion_origen_desconocido": "y",
            "codigo_login_expira_minutos": "15",
            "navegador_confiable_dias": "45",
        },
    )

    assert response.status_code == 302
    configuration = db_session.query(ConfiguracionCorreo).one()
    assert configuration.smtp_password_encrypted not in (None, b"smtp-secret")
    assert configuration.proteger_inicio_sesion_origen_desconocido is True
    assert configuration.navegador_confiable_dias == 45


def test_non_admin_cannot_configure_email(client, db_session):
    user = create_user(db_session, "hr-config", "password", tipo=TipoUsuario.HHRR)
    login_user(client, user.usuario, "password")

    assert client.get("/settings/email").status_code == 403
