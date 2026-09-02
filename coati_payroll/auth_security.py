# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""One-time email tokens and trusted-browser credentials."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app, request

from coati_payroll.model import NavegadorConfiable, TokenCorreo, Usuario, db

PASSWORD_RESET_PURPOSE = "password_reset"
LOGIN_VERIFICATION_PURPOSE = "login_verification"
TRUSTED_BROWSER_COOKIE = "coati_trusted_browser"
MAX_LOGIN_TOKEN_ATTEMPTS = 5


def utc_now() -> datetime:
    """Return a naive UTC datetime compatible with SQLAlchemy DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def hash_secret(value: str) -> str:
    """Hash a bearer secret before storing it in the database."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_metadata() -> tuple[str | None, str | None]:
    return request.remote_addr, request.user_agent.string[:512] if request.user_agent else None


def issue_email_token(
    usuario: Usuario,
    purpose: str,
    *,
    ttl_minutes: int,
    code: bool = False,
) -> tuple[TokenCorreo, str]:
    """Issue a fresh one-time token and invalidate older tokens of its purpose."""
    now = utc_now()
    db.session.query(TokenCorreo).filter(
        TokenCorreo.usuario_id == usuario.id,
        TokenCorreo.proposito == purpose,
        TokenCorreo.usado_en.is_(None),
    ).update({TokenCorreo.usado_en: now}, synchronize_session=False)

    raw_token = f"{secrets.randbelow(1_000_000):06d}" if code else secrets.token_urlsafe(32)
    ip_address, user_agent = _request_metadata()
    token = TokenCorreo(
        usuario_id=usuario.id,
        token_hash=hash_secret(raw_token),
        proposito=purpose,
        expira_en=now + timedelta(minutes=max(1, ttl_minutes)),
        ip_solicitud=ip_address,
        user_agent=user_agent,
    )
    db.session.add(token)
    db.session.flush()
    return token, raw_token


def find_email_token(raw_token: str, purpose: str) -> TokenCorreo | None:
    """Return an active token without revealing whether another token exists."""
    now = utc_now()
    token = db.session.execute(
        db.select(TokenCorreo).filter(
            TokenCorreo.token_hash == hash_secret(raw_token),
            TokenCorreo.proposito == purpose,
            TokenCorreo.usado_en.is_(None),
            TokenCorreo.expira_en > now,
            TokenCorreo.intentos_fallidos < MAX_LOGIN_TOKEN_ATTEMPTS,
        )
    ).scalar_one_or_none()
    return token


def consume_email_token(token: TokenCorreo) -> None:
    token.usado_en = utc_now()


def issue_trusted_browser(response, usuario: Usuario) -> None:
    """Issue a random, revocable browser cookie after verified login."""
    from coati_payroll.email_service import get_email_configuration

    configuration = get_email_configuration()
    trusted_days = max(1, int(configuration.navegador_confiable_dias)) if configuration else 30
    raw_token = secrets.token_urlsafe(32)
    now = utc_now()
    browser = NavegadorConfiable(
        usuario_id=usuario.id,
        token_hash=hash_secret(raw_token),
        expira_en=now + timedelta(days=trusted_days),
        ultimo_uso_en=now,
        user_agent_hash=hashlib.sha256((request.user_agent.string if request.user_agent else "").encode()).hexdigest(),
    )
    db.session.add(browser)
    db.session.commit()

    response.set_cookie(
        TRUSTED_BROWSER_COOKIE,
        raw_token,
        max_age=trusted_days * 24 * 60 * 60,
        secure=bool(current_app.config.get("SESSION_COOKIE_SECURE", True)),
        httponly=True,
        samesite="Lax",
        path="/",
    )


def is_trusted_browser(usuario: Usuario) -> bool:
    """Validate the browser credential for this user and refresh last usage."""
    raw_token = request.cookies.get(TRUSTED_BROWSER_COOKIE)
    if not raw_token:
        return False
    now = utc_now()
    browser = db.session.execute(
        db.select(NavegadorConfiable).filter(
            NavegadorConfiable.usuario_id == usuario.id,
            NavegadorConfiable.token_hash == hash_secret(raw_token),
            NavegadorConfiable.revocado_en.is_(None),
            NavegadorConfiable.expira_en > now,
        )
    ).scalar_one_or_none()
    if browser is None:
        return False

    current_user_agent_hash = hashlib.sha256(
        (request.user_agent.string if request.user_agent else "").encode()
    ).hexdigest()
    if browser.user_agent_hash and browser.user_agent_hash != current_user_agent_hash:
        return False
    browser.ultimo_uso_en = now
    db.session.commit()
    return True


def revoke_trusted_browsers(usuario: Usuario) -> None:
    """Revoke all browser credentials after a password/security change."""
    now = utc_now()
    db.session.query(NavegadorConfiable).filter(
        NavegadorConfiable.usuario_id == usuario.id,
        NavegadorConfiable.revocado_en.is_(None),
    ).update({NavegadorConfiable.revocado_en: now}, synchronize_session=False)
