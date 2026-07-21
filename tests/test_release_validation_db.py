# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Release validation tests for external database engines."""

import os

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL is not defined, skipping external database validation tests.",
)


def test_database_create_all_works_with_external_engine():
    """Validate schema creation succeeds with database.create_all()."""
    from coati_payroll import create_app, ensure_database_initialized
    from coati_payroll.model import db

    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "release-validation-secret",
            "SQLALCHEMY_DATABASE_URI": os.environ["DATABASE_URL"],
        }
    )

    with app.app_context():
        db.drop_all()
        ensure_database_initialized(app)

        table_names = inspect(db.engine).get_table_names()
        assert table_names, "database.create_all() should create the application schema."


@pytest.mark.xfail
def test_alembic_can_downgrade_and_upgrade_on_external_engine():
    """Validate alembic migrations run from head to base and back to head."""
    from coati_payroll import alembic, create_app, ensure_database_initialized
    from coati_payroll.model import db

    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "release-validation-secret",
            "COATI_AUTO_MIGRATE": "0",
            "SQLALCHEMY_DATABASE_URI": os.environ["DATABASE_URL"],
        }
    )

    with app.app_context():
        db.drop_all()
        ensure_database_initialized(app)

        alembic.stamp("head")
        head_version = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        assert head_version is not None

        alembic.downgrade("base")

        try:
            downgraded_version = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
            assert downgraded_version is None
        except (OperationalError, ProgrammingError):
            pass

        alembic.upgrade()
        upgraded_version = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        assert upgraded_version is not None
