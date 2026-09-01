# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for access validation functionality."""

from tests.factories.user_factory import create_user


def test_validar_acceso_valid_credentials(app, db_session):
    """
    Test validar_acceso with valid credentials.

    Setup:
        - Create a test user

    Action:
        - Validate access with correct credentials

    Verification:
        - Validation succeeds
    """
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        create_user(db_session, "testuser_val1", "testpass")

        result = validar_acceso("testuser_val1", "testpass")
        assert result is True


def test_validar_acceso_invalid_password(app, db_session):
    """
    Test validar_acceso with invalid password.

    Setup:
        - Create a test user

    Action:
        - Validate access with wrong password

    Verification:
        - Validation fails
    """
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        create_user(db_session, "testuser_val2", "testpass")

        result = validar_acceso("testuser_val2", "wrongpass")
        assert result is False


def test_validar_acceso_rejects_inactive_user(app, db_session):
    """Disabled accounts must not authenticate even with valid credentials."""
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        user = create_user(db_session, "inactive_user", "testpass")
        user.activo = False
        db_session.commit()

        assert validar_acceso("inactive_user", "testpass") is False
        db_session.refresh(user)
        assert user.ultimo_acceso is None


def test_validar_acceso_nonexistent_user(app, db_session):
    """
    Test validar_acceso with non-existent user.

    Setup:
        - Clean database

    Action:
        - Validate access for non-existent user

    Verification:
        - Validation fails
    """
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        result = validar_acceso("nonexistent_user", "anypass")
        assert result is False


def test_validar_acceso_by_email(app, db_session):
    """
    Test validar_acceso with email instead of username.

    Setup:
        - Create a test user with email

    Action:
        - Validate access using email

    Verification:
        - Validation succeeds
    """
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        create_user(db_session, "testuser_val3", "testpass", correo_electronico="test@example.com")

        result = validar_acceso("test@example.com", "testpass")
        assert result is True


def test_validar_acceso_updates_ultimo_acceso(app, db_session):
    """
    Test that validar_acceso updates ultimo_acceso timestamp.

    Setup:
        - Create a test user

    Action:
        - Validate access successfully

    Verification:
        - ultimo_acceso field is updated
    """
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        user = create_user(db_session, "testuser_val4", "testpass")
        initial_ultimo_acceso = user.ultimo_acceso

        result = validar_acceso("testuser_val4", "testpass")
        assert result is True

        # Refresh user from database
        db_session.refresh(user)
        assert user.ultimo_acceso is not None

        # If there was no initial ultimo_acceso, it should now be set
        if initial_ultimo_acceso is None:
            assert user.ultimo_acceso is not None


def test_validar_acceso_failed_does_not_update_ultimo_acceso(app, db_session):
    """
    Test that failed validation doesn't update ultimo_acceso.

    Setup:
        - Create a test user

    Action:
        - Attempt validation with wrong password

    Verification:
        - ultimo_acceso field is not updated
    """
    from coati_payroll.auth import validar_acceso

    with app.app_context():
        user = create_user(db_session, "testuser_val5", "testpass")
        initial_ultimo_acceso = user.ultimo_acceso

        result = validar_acceso("testuser_val5", "wrongpass")
        assert result is False

        # Refresh user from database
        db_session.refresh(user)
        assert user.ultimo_acceso == initial_ultimo_acceso
