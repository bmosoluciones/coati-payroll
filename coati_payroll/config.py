# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Base configuration for the payroll module."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
import sys
from os import environ, getcwd, path
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.log import log


# ---------------------------------------------------------------------------------------
# Configuration file loading functionality
# ---------------------------------------------------------------------------------------
def load_config_from_file() -> dict:
    """
    Busca y carga configuración desde archivo con ConfigObj.

    Busca en las siguientes ubicaciones en orden:
    1. /etc/coati-payroll/coati-payroll.conf
    2. /etc/coati-payroll.conf
    3. ~/.config/coati-payroll/coati-payroll.conf
    3. ./coati-payroll.conf

    Returns:
        dict: Diccionario de configuración, vacío si no se encuentra archivo
    """
    try:
        from configobj import ConfigObj
    except ImportError:
        log.debug("ConfigObj not available, skipping file-based configuration.")
        return {}

    search_paths = [
        "/etc/coati-payroll/coati-payroll.conf",
        "/etc/coati-payroll.conf",
        path.expanduser("~/.config/coati-payroll/coati-payroll.conf"),
        path.join(getcwd(), "coati-payroll.conf"),
    ]

    for config_path in search_paths:
        if config_path and path.isfile(config_path):
            try:
                log.info("Loading configuration from file: %s", config_path)
                config_obj = ConfigObj(config_path, encoding="utf-8")

                config_dict = dict(config_obj)

                if "DATABASE_URL" in config_dict:
                    config_dict["SQLALCHEMY_DATABASE_URI"] = config_dict["DATABASE_URL"]

                if "REDIS_URL" in config_dict:
                    config_dict["CACHE_REDIS_URL"] = config_dict["REDIS_URL"]

                return config_dict

            except Exception as e:
                log.warning("Error loading configuration from %s: %s", config_path, e)
                continue

    log.trace("No configuration file found in search paths.")
    return {}


# < --------------------------------------------------------------------------------------------- >
# Configuración central de la aplicación.
BOOLEAN_TRUE = {"1", "true", "yes", "on", "ok"}
VALORES_TRUE = BOOLEAN_TRUE | {"development", "dev"}
DEBUG_VARS = ["DEBUG", "CI", "DEV", "DEVELOPMENT"]
FRAMEWORK_VARS = ["FLASK_ENV", "DJANGO_DEBUG", "NODE_ENV"]
GENERIC_VARS = ["ENV", "APP_ENV"]

# < --------------------------------------------------------------------------------------------- >
# Gestión de variables de entorno.
DESARROLLO = any(
    str(environ.get(var, "")).strip().lower() in VALORES_TRUE for var in [*DEBUG_VARS, *FRAMEWORK_VARS, *GENERIC_VARS]
)

# Auto-migrate configuration - enables automatic database migrations on startup
AUTO_MIGRATE = environ.get("COATI_AUTO_MIGRATE", "0").strip().lower() in BOOLEAN_TRUE

# < --------------------------------------------------------------------------------------------- >
# Directorios base de la aplicacion
DIRECTORIO_ACTUAL: Path = Path(path.abspath(path.dirname(__file__)))
DIRECTORIO_APP: Path = DIRECTORIO_ACTUAL.parent.absolute()
DIRECTORIO_DESARROLLO: Path = DIRECTORIO_APP
DIRECTORIO_PLANTILLAS_BASE: str = path.join(DIRECTORIO_ACTUAL, "templates")
DIRECTORIO_ARCHIVOS_BASE: str = path.join(DIRECTORIO_ACTUAL, "static")

# < --------------------------------------------------------------------------------------------- >
# Directorios personalizados para la aplicación.
DIRECTORIO_ARCHIVOS = DIRECTORIO_ARCHIVOS_BASE
DIRECTORIO_PLANTILLAS = DIRECTORIO_PLANTILLAS_BASE

# < --------------------------------------------------------------------------------------------- >
TESTING = (
    "PYTEST_CURRENT_TEST" in environ
    or "PYTEST_VERSION" in environ
    or "TESTING" in environ
    or hasattr(sys, "_called_from_test")
    or environ.get("CI")
    or "pytest" in sys.modules
    or path.basename(sys.argv[0]) in ["pytest", "py.test"]
)

if TESTING:
    # Use DB in memory for tests to avoid filesystem side-effects
    SQLITE: str = "sqlite:///:memory:"
else:
    # File-based sqlite in project root
    sqlite_file = DIRECTORIO_DESARROLLO.joinpath("coati_payroll.db")
    SQLITE = f"sqlite:///{sqlite_file.as_posix()}"

# < --------------------------------------------------------------------------------------------- >
# Configuración de la aplicación:
# Se siguen las recomendaciones de "Twelve Factors App" y las opciones se leen del entorno.
CONFIGURACION: dict[str, str | bool | Path | int | None] = {}
CONFIGURACION["SECRET_KEY"] = environ.get("SECRET_KEY") or "dev"  # nosec
CONFIGURACION["SQLALCHEMY_DATABASE_URI"] = environ.get("DATABASE_URL") or SQLITE  # nosec
# Upload size limit (bytes). Default ~2 MB, roughly ~1000 Excel rows for typical uploads.
CONFIGURACION["MAX_CONTENT_LENGTH"] = int(environ.get("MAX_CONTENT_LENGTH", str(2 * 1024 * 1024)))
# Opciones comunes de configuración.
CONFIGURACION["PRESERVE_CONTEXT_ON_EXCEPTION"] = False

if DESARROLLO:
    log.warning("Using default configuration.")
    log.info("Default configuration is not recommended for use in production environments.")
    CONFIGURACION["SQLALCHEMY_TRACK_MODIFICATIONS"] = "False"
    CONFIGURACION["TEMPLATES_AUTO_RELOAD"] = True

# < --------------------------------------------------------------------------------------------- >
# Corrige la URI de conexión a la base de datos si el usuario omite el driver apropiado.

database_url_base = CONFIGURACION.get("SQLALCHEMY_DATABASE_URI")
if isinstance(database_url_base, str):

    DATABASE_URL_BASE = database_url_base
    DATABASE_URL_CORREGIDA = DATABASE_URL_BASE

    prefix = DATABASE_URL_BASE.split(":", 1)[0]  # Extraer prefijo: "postgres", "mysql", etc.

    # Caso especial: Heroku + PostgreSQL
    if environ.get("DYNO") and prefix in (
        "postgres",
        "postgresql",
    ):  # type: ignore[operator]
        parsed = urlparse(DATABASE_URL_BASE)  # type: ignore[arg-type]
        query = parse_qs(parsed.query)
        query["sslmode"] = ["require"]
        DATABASE_URL_CORREGIDA = urlunparse(parsed._replace(scheme="postgresql", query=urlencode(query, doseq=True)))

    else:
        # Corrige el esquema según el prefijo detectado
        match prefix:
            case "postgresql":
                parsed = urlparse(DATABASE_URL_BASE)
                query = parse_qs(parsed.query)
                query.pop("sslmode", None)
                new_query = urlencode(query, doseq=True) if query else ""
                cleaned = urlunparse(parsed._replace(query=new_query))
                DATABASE_URL_CORREGIDA = "postgresql+pg8000" + cleaned[10:]
            case "postgres":
                parsed = urlparse(DATABASE_URL_BASE)
                query = parse_qs(parsed.query)
                query.pop("sslmode", None)
                new_query = urlencode(query, doseq=True) if query else ""
                cleaned = urlunparse(parsed._replace(query=new_query))
                DATABASE_URL_CORREGIDA = "postgresql+pg8000" + cleaned[8:]
            case "mysql":
                DATABASE_URL_CORREGIDA = "mysql+mysqlconnector" + DATABASE_URL_BASE[5:]
            case "mariadb":
                DATABASE_URL_CORREGIDA = "mariadb+mariadbconnector" + DATABASE_URL_BASE[7:]

    # Actualizar configuración si hubo cambio
    if DATABASE_URL_BASE != DATABASE_URL_CORREGIDA:
        log.info("Database URI corrected")
        CONFIGURACION["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL_CORREGIDA

# < --------------------------------------------------------------------------------------------- >
# Queue configuration for background job processing
# Background queues require Dramatiq + Redis.
# If unavailable, payroll execution remains synchronous.
CONFIGURACION["QUEUE_ENABLED"] = environ.get("QUEUE_ENABLED", "1") in [
    "1",
    "true",
    "True",
    "yes",
]

# Background payroll processing configuration
# Threshold for automatic background processing (number of employees)
# Payrolls with more employees than this threshold will be processed in background
# Default: 100 employees. Can be adjusted based on system performance:
# - For systems with complex formulas or slow performance: lower to 50 or 25
# - For high-performance systems: increase to 200 or 500
CONFIGURACION["BACKGROUND_PAYROLL_THRESHOLD"] = int(environ.get("BACKGROUND_PAYROLL_THRESHOLD", "100"))

# < --------------------------------------------------------------------------------------------- >
configuration = CONFIGURACION
