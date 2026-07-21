# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""App module."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.functions import count

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.model import db, Empleado, Empresa, Planilla, Nomina

app = Blueprint("app", __name__)


@app.route("/", methods=["GET"])
@login_required
def index():
    # Get statistics for dashboard
    total_empleados = db.session.execute(db.select(count(Empleado.id)).filter(Empleado.activo.is_(True))).scalar() or 0
    total_empresas = db.session.execute(db.select(count(Empresa.id)).filter(Empresa.activo.is_(True))).scalar() or 0
    total_planillas = db.session.execute(db.select(count(Planilla.id)).filter(Planilla.activo.is_(True))).scalar() or 0
    total_nominas = db.session.execute(db.select(count(Nomina.id))).scalar() or 0

    # Get recent payrolls (last 5)
    recent_nominas = (
        db.session.execute(db.select(Nomina).order_by(Nomina.fecha_generacion.desc()).limit(5)).scalars().all()
    )

    return render_template(
        "index.html",
        total_empleados=total_empleados,
        total_empresas=total_empresas,
        total_planillas=total_planillas,
        total_nominas=total_nominas,
        recent_nominas=recent_nominas,
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for container orchestration.

    Returns a simple OK response to indicate the application is running.
    This endpoint does not require authentication and does not check database connectivity.
    """
    return {"status": "ok"}, 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check endpoint for container orchestration.

    Returns OK if the application is ready to serve traffic (database is accessible).
    This endpoint does not require authentication.
    """
    try:
        # Test database connectivity using a fresh connection
        # This avoids issues with session state from other parts of the application
        with db.engine.connect() as connection:
            connection.execute(db.text("SELECT 1")).scalar()
        return {"status": "ok"}, 200
    except SQLAlchemyError:
        return {"status": "unavailable"}, 503
    except Exception:
        # Catch any other exception that might occur
        return {"status": "unavailable"}, 503
