# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""
Coati Payroll
=============

Simple payroll management system.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from os import environ
from datetime import datetime

# <-------------------------------------------------------------------------> #
# Third party packages
# <-------------------------------------------------------------------------> #
from flask import Flask, flash, redirect, url_for
from flask_alembic import Alembic
from flask_babel import Babel
from flask_login import LoginManager
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
import flask_session.sqlalchemy.sqlalchemy as fs_sqlalchemy
from sqlalchemy import Column, DateTime, Integer, LargeBinary, Sequence, String

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.app import app as app_blueprint
from coati_payroll.auth import auth
from coati_payroll.config import DIRECTORIO_ARCHIVOS_BASE, DIRECTORIO_PLANTILLAS_BASE
from coati_payroll.i18n import _
from coati_payroll.model import Usuario, db
from coati_payroll.log import log
from coati_payroll.plugin_manager import get_active_plugins_menu_entries, register_active_plugins, sync_plugin_registry


# Patch Flask-Session to use extend_existing=True for the sessions table
# This prevents the "Table 'sessions' is already defined" error when the app
# is initialized multiple times (e.g., by the CLI).
#
# NOTE: This monkey-patch is necessary because Flask-Session v0.8.0 does not
# provide a configuration option to set extend_existing=True on the sessions
# table. Without this, the CLI fails when it initializes the app multiple times.
# This is a minimal, surgical fix that only modifies the table_args to add
# extend_existing=True. If Flask-Session adds native support for this in a
# future version, this patch can be removed.
def _patched_create_session_model(db, table_name, schema=None, bind_key=None, sequence=None):
    """Patched version of Flask-Session's create_session_model that includes extend_existing=True."""

    class Session(db.Model):
        __tablename__ = table_name
        # Include extend_existing=True to allow table redefinition
        __table_args__ = {"schema": schema, "extend_existing": True} if schema else {"extend_existing": True}
        __bind_key__ = bind_key

        id = Column(Integer, Sequence(sequence), primary_key=True) if sequence else Column(Integer, primary_key=True)
        session_id = Column(String(255), unique=True)
        data = Column(LargeBinary)
        expiry = Column(DateTime)

        def __init__(self, session_id: str, data, expiry: datetime):
            self.session_id = session_id
            self.data = data
            self.expiry = expiry

        def __repr__(self):
            return f"<Session data {self.data}>"

    return Session


fs_sqlalchemy.create_session_model = _patched_create_session_model

# Third party libraries
alembic = Alembic()
session_manager = Session()
login_manager = LoginManager()
babel = Babel()
csrf = CSRFProtect()
limiter = None  # Will be initialized in create_app()


# ---------------------------------------------------------------------------------------
# Control de acceso a la aplicación con la extensión flask_login.
# ---------------------------------------------------------------------------------------
@login_manager.user_loader
def cargar_sesion(identidad):
    """Devuelve la entrada correspondiente al usuario que inicio sesión desde la base de datos."""
    if identidad is not None:
        return db.session.get(Usuario, identidad)
    return None


@login_manager.unauthorized_handler
def no_autorizado():
    """Redirecciona al inicio de sesión usuarios no autorizados."""
    flash(_("Favor iniciar sesión para acceder al sistema."), "warning")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------------------
# Locale selector for Flask-Babel
# ---------------------------------------------------------------------------------------
def get_locale():
    """Determine the locale for the current request.

    Returns the language configured in the database (with caching).
    Falls back to English if database is not available.
    """
    try:
        from coati_payroll.locale_config import get_language_from_db

        return get_language_from_db()
    except Exception:
        # Fallback to default if database not available (e.g., during initialization)
        return "en"


# ---------------------------------------------------------------------------------------
# app factory.
# ---------------------------------------------------------------------------------------
def create_app(config) -> Flask:
    """App factory."""

    app = Flask(
        __name__,
        static_folder=DIRECTORIO_ARCHIVOS_BASE,
        template_folder=DIRECTORIO_PLANTILLAS_BASE,
    )

    if config:
        app.config.from_mapping(config)
    else:
        from coati_payroll.config import configuration

        app.config.from_object(configuration)

    # Warn if using default SECRET_KEY in production
    from coati_payroll.config import DESARROLLO

    if not DESARROLLO and app.config.get("SECRET_KEY") == "dev":
        log.critical("Using default SECRET_KEY in production — aborting startup.")
        raise RuntimeError("SECRET_KEY must be set in production")

    log.trace("create_app: initializing app")

    # Configure Alembic migrations directory
    from os.path import abspath, dirname, join

    migrations_dir = abspath(join(dirname(__file__), "migrations"))
    app.config.setdefault("ALEMBIC", {})
    app.config["ALEMBIC"]["script_location"] = migrations_dir

    # Initialize database and alembic
    db.init_app(app)
    alembic.init_app(app)

    try:
        with app.app_context():
            sync_plugin_registry()
    except Exception as exc:
        log.trace("create_app: sync_plugin_registry raised: %s", exc)

    # Configure session storage
    # In testing mode, respect the SESSION_TYPE from config (e.g., filesystem)
    # to avoid conflicts with parallel test execution
    if not app.config.get("SESSION_TYPE"):
        if session_redis_url := environ.get("SESSION_REDIS_URL", None):
            from redis import Redis

            app.config["SESSION_TYPE"] = "redis"
            app.config["SESSION_REDIS"] = Redis.from_url(session_redis_url)

        else:
            app.config["SESSION_TYPE"] = "sqlalchemy"
            app.config["SESSION_SQLALCHEMY"] = db
            app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"
            app.config["SESSION_PERMANENT"] = False
            app.config["SESSION_USE_SIGNER"] = True

    # Configure secure session cookies
    # These settings protect against session hijacking and cookie theft
    from datetime import timedelta

    app.config["SESSION_COOKIE_HTTPONLY"] = True  # Prevent JavaScript access to cookies
    app.config["SESSION_COOKIE_SECURE"] = not DESARROLLO  # Only send over HTTPS in production
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)  # Session timeout

    # Configure Flask-Babel
    app.config["BABEL_DEFAULT_LOCALE"] = "es"
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = join(dirname(__file__), "translations")
    app.config["BABEL_SUPPORTED_LOCALES"] = ["es", "en"]
    babel.init_app(app, locale_selector=get_locale)

    session_manager.init_app(app)
    login_manager.init_app(app)

    # Initialize CSRF protection globally
    # This protects all forms from Cross-Site Request Forgery attacks
    # CSRF is automatically disabled in testing mode (WTF_CSRF_ENABLED = False in test config)
    csrf.init_app(app)

    # Initialize rate limiting
    # Protects against brute force attacks and abuse
    global limiter
    from coati_payroll.rate_limiting import configure_rate_limiting

    limiter = configure_rate_limiting(app)

    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(app_blueprint, url_prefix="/")

    try:
        with app.app_context():
            register_active_plugins(app)
    except Exception as exc:
        log.trace("create_app: register_active_plugins raised: %s", exc)

    # Register CRUD blueprints
    from coati_payroll.vistas import (
        user_bp,
        currency_bp,
        exchange_rate_bp,
        employee_bp,
        custom_field_bp,
        calculation_rule_bp,
        percepcion_bp,
        deduccion_bp,
        prestacion_bp,
        planilla_bp,
        nomina_bp,
        tipo_planilla_bp,
        prestamo_bp,
        empresa_bp,
        configuracion_bp,
        carga_inicial_prestacion_bp,
        vacation_bp,
        prestacion_management_bp,
        report_bp,
        settings_bp,
        implementation_bp,
        plugins_bp,
        config_calculos_bp,
        liquidacion_bp,
    )

    app.register_blueprint(user_bp)
    app.register_blueprint(currency_bp)
    app.register_blueprint(exchange_rate_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(custom_field_bp)
    app.register_blueprint(calculation_rule_bp)
    app.register_blueprint(percepcion_bp)
    app.register_blueprint(deduccion_bp)
    app.register_blueprint(prestacion_bp)
    app.register_blueprint(planilla_bp)
    app.register_blueprint(nomina_bp)
    app.register_blueprint(tipo_planilla_bp)
    app.register_blueprint(prestamo_bp)
    app.register_blueprint(empresa_bp)
    app.register_blueprint(configuracion_bp)
    app.register_blueprint(carga_inicial_prestacion_bp)
    app.register_blueprint(vacation_bp)
    app.register_blueprint(prestacion_management_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(implementation_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(config_calculos_bp)
    app.register_blueprint(liquidacion_bp)

    @app.context_processor
    def inject_plugins_menu():
        try:
            plugin_actives = get_active_plugins_menu_entries()
        except Exception:
            plugin_actives = []
        return {"plugin_actives": plugin_actives}

    # Register CLI commands
    from coati_payroll.cli import register_cli_commands

    register_cli_commands(app)

    # Configure security headers
    # This adds HTTP security headers to all responses to protect against
    # common web vulnerabilities (XSS, clickjacking, MIME sniffing, etc.)
    from coati_payroll.security import configure_security_headers

    configure_security_headers(app)

    return app


def ensure_database_initialized(app: Flask | None = None) -> None:
    """Verifica que la base de datos haya sido inicializada.

    - Si la tabla de `Usuario` no existe, ejecuta `create_all()`.
    - Si no existe al menos un usuario con `tipo='admin'`, crea un usuario
      administrador usando las variables de entorno `ADMIN_USER` y
      `ADMIN_PASSWORD` (con valores por defecto si no están presentes).

    Esta función puede llamarse con la `app` o desde un `app.app_context()` ya activo.
    """

    from coati_payroll.auth import proteger_passwd as _proteger_passwd

    # Determinar si debemos usar el contexto de la app pasada o el actual.
    ctx = app
    if ctx is None:
        from flask import current_app

        ctx = current_app

    with ctx.app_context():
        # Crear todas las tablas definidas (idempotente). Esto garantiza que
        # el archivo sqlite se cree cuando se use una URI sqlite.
        try:
            # Logear información útil para diagnóstico
            try:
                log.trace("ensure_database_initialized: engine.url = %s", db.engine.url)
            except Exception:
                log.trace("ensure_database_initialized: could not read _db.engine.url")

            try:
                db_uri = ctx.config.get("SQLALCHEMY_DATABASE_URI")
                log.trace("ensure_database_initialized: Flask SQLALCHEMY_DATABASE_URI = %s", db_uri)
            except Exception:
                log.trace("ensure_database_initialized: could not read SQLALCHEMY_DATABASE_URI from ctx.config")

            log.trace("ensure_database_initialized: calling create_all()")
            db.create_all()
            log.trace("ensure_database_initialized: create_all() completed")
        except Exception as exc:
            from sqlalchemy.exc import OperationalError, ProgrammingError

            msg = str(exc).lower()
            if isinstance(exc, (OperationalError, ProgrammingError)) and "already exists" in msg:
                log.trace("ensure_database_initialized: create_all skipped existing objects")
            else:
                log.trace("ensure_database_initialized: create_all() raised: %s", exc)
                try:
                    log.exception("ensure_database_initialized: create_all() exception")
                except Exception:
                    pass

        # Comprobar existencia de al menos un admin.
        registro_admin = db.session.execute(db.select(Usuario).filter_by(tipo="admin")).scalar_one_or_none()

        if registro_admin is None:
            # Leer credenciales de entorno o usar valores por defecto.
            admin_user = environ.get("ADMIN_USER", "coati-admin")
            admin_pass = environ.get("ADMIN_PASSWORD", "coati-admin")

            nuevo = Usuario()
            nuevo.usuario = admin_user
            nuevo.acceso = _proteger_passwd(admin_pass)
            nuevo.nombre = "Administrador"
            nuevo.apellido = ""
            nuevo.correo_electronico = None
            nuevo.tipo = "admin"
            nuevo.activo = True

            db.session.add(nuevo)
            db.session.commit()

        # Handle database migrations with Alembic
        # Check if AUTO_MIGRATE is enabled and run migrations if database is already initialized
        from coati_payroll.config import AUTO_MIGRATE

        if AUTO_MIGRATE:
            try:
                log.trace("ensure_database_initialized: AUTO_MIGRATE enabled, running alembic.upgrade()")
                alembic.upgrade()
                log.info("Database migrated successfully with alembic.upgrade()")
            except Exception as exc:
                log.warning("Error during automatic database migration: %s", exc)
                # Don't fail initialization if migration fails.

        # Initialize language from environment variable if provided
        try:
            from coati_payroll.locale_config import initialize_language_from_env

            initialize_language_from_env()
        except Exception as exc:
            log.trace("Could not initialize language from environment: %s", exc)
