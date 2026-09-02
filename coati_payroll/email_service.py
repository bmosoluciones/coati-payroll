# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Database-backed email delivery for authentication messages."""

from __future__ import annotations

import base64
import hashlib
import smtplib
import ssl
from email.message import EmailMessage

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from coati_payroll.log import log
from coati_payroll.model import ConfiguracionCorreo, db


def get_email_configuration(*, create: bool = False) -> ConfiguracionCorreo | None:
    """Return the singleton email configuration stored in the database."""
    configuration = db.session.execute(
        db.select(ConfiguracionCorreo).order_by(ConfiguracionCorreo.id)
    ).scalars().first()
    if configuration is None and create:
        configuration = ConfiguracionCorreo()
        db.session.add(configuration)
        db.session.flush()
    return configuration


def _fernet() -> Fernet:
    """Build an encryption key from the application's secret key."""
    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY is required to protect SMTP credentials")
    secret_bytes = secret_key if isinstance(secret_key, bytes) else str(secret_key).encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret_bytes).digest())
    return Fernet(key)


def encrypt_smtp_password(password: str) -> bytes:
    """Encrypt an SMTP password before it is persisted."""
    return _fernet().encrypt(password.encode("utf-8"))


def decrypt_smtp_password(configuration: ConfiguracionCorreo) -> str | None:
    """Decrypt an SMTP password only at the point of SMTP authentication."""
    if not configuration.smtp_password_encrypted:
        return None
    try:
        return _fernet().decrypt(bytes(configuration.smtp_password_encrypted)).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        log.warning("Unable to decrypt SMTP credentials from database: %s", type(exc).__name__)
        return None


def email_delivery_configured(configuration: ConfiguracionCorreo | None = None) -> bool:
    """Return whether the DB configuration is sufficient for delivery."""
    configuration = configuration or get_email_configuration()
    if configuration is None or not configuration.activo:
        return False
    if not configuration.smtp_host or not configuration.sender_email:
        return False
    try:
        port = int(configuration.smtp_port or 0)
    except (TypeError, ValueError):
        return False
    if not 1 <= port <= 65535:
        return False
    if configuration.smtp_username and not decrypt_smtp_password(configuration):
        return False
    return True


def send_email(to: str, subject: str, body: str, *, html_body: str | None = None) -> bool:
    """Send one email using only the active configuration from the database.

    Delivery errors are logged without credentials and reported as ``False``
    so callers can keep authentication and recovery responses generic.
    """
    configuration = get_email_configuration()
    if not email_delivery_configured(configuration):
        log.warning("Email delivery requested but SMTP is not configured in the database")
        return False

    if any(
        "\r" in value or "\n" in value
        for value in (to, subject, configuration.sender_email or "", configuration.sender_name or "")
    ):
        log.warning("Rejected email containing a header injection character")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{configuration.sender_name} <{configuration.sender_email}>"
        if configuration.sender_name
        else configuration.sender_email
    )
    message["To"] = to
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    password = decrypt_smtp_password(configuration)
    try:
        if configuration.smtp_use_ssl:
            server = smtplib.SMTP_SSL(
                configuration.smtp_host,
                int(configuration.smtp_port),
                timeout=current_app.config.get("MAIL_TIMEOUT", 10),
                context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(
                configuration.smtp_host,
                int(configuration.smtp_port),
                timeout=current_app.config.get("MAIL_TIMEOUT", 10),
            )

        with server:
            if configuration.smtp_use_tls and not configuration.smtp_use_ssl:
                server.starttls(context=ssl.create_default_context())
            if configuration.smtp_username:
                server.login(configuration.smtp_username, password or "")
            server.send_message(message)
        return True
    except (OSError, ValueError, smtplib.SMTPException) as exc:
        log.warning("SMTP delivery failed: %s", type(exc).__name__)
        return False
