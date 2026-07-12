# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from os import environ
from pathlib import Path

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll import create_app
from coati_payroll.log import log
from coati_payroll.config import configuration
from coati_payroll.wsgi_server import serve

# Base de datos SQLite para fines de desarrollo.
# No recomendado para producción.
repo_root = Path(__file__).resolve().parent
default_db_path = repo_root.joinpath("coati_payroll.db")
default_db_uri = f"sqlite:///{default_db_path}"

db_url = environ.get("DATABASE_URL", None)
flask_env = environ.get("FLASK_ENV", "").lower()

if flask_env == "production":
    secret_key = environ.get("SECRET_KEY", None)
    admin_user = environ.get("ADMIN_USER", None)
    admin_password = environ.get("ADMIN_PASSWORD", None)
    if not db_url:
        log.error("DATABASE_URL not set in production environment")
        raise RuntimeError("DATABASE_URL must be set when FLASK_ENV=production")
    if not secret_key:
        log.error("SECRET_KEY not set in production environment")
        raise RuntimeError("SECRET_KEY must be set when FLASK_ENV=production")
    if not admin_user or not admin_password:
        log.error("ADMIN_USER/ADMIN_PASSWORD not set in production environment")
        raise RuntimeError("ADMIN_USER and ADMIN_PASSWORD must be set when FLASK_ENV=production")
else:
    if not db_url:
        log.warning("DATABASE_URL not set, using default SQLite database")

# Crear aplicación.
cfg = dict(configuration)
app = create_app(cfg)
log.trace("App initialized")

# Antes de ejecutar el servidor:
#   export FLASK_APP=app:app
#   payrollctl database init
#   payrollctl database migrate

# Puerto predefinido.
port = int(environ.get("PORT", 5000))

if __name__ == "__main__":
    serve(app=app, host="0.0.0.0", port=port)
