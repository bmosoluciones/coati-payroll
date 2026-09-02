# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for vacation routes."""

from tests.helpers.auth import login_user


def test_vacation_policy_index_requires_authentication(app, client, db_session):
    """Test that vacation policy index requires authentication."""
    with app.app_context():
        response = client.get("/vacation/policies", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_policy_index_for_admin(app, client, admin_user, db_session):
    """Test that admin can access vacation policy index."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/vacation/policies")
        assert response.status_code == 200


def test_vacation_account_index_requires_authentication(app, client, db_session):
    """Test that vacation account index requires authentication."""
    with app.app_context():
        response = client.get("/vacation/accounts", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_account_index_for_admin(app, client, admin_user, db_session):
    """Test that admin can access vacation account index."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/vacation/accounts")
        assert response.status_code == 200


def test_vacation_policy_new_requires_authentication(app, client, db_session):
    """Test that creating a new vacation policy requires authentication."""
    with app.app_context():
        response = client.get("/vacation/policies/new", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_policy_new_requires_write_access(app, client, db_session):
    """Test that creating a new vacation policy requires write access."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        # Create AUDIT user (read-only)
        audit_user = create_user(db_session, "auditor", "password", tipo=TipoUsuario.AUDIT)
        login_user(client, audit_user.usuario, "password")

        response = client.get("/vacation/policies/new", follow_redirects=False)
        # Should not allow access (403 or redirect)
        assert response.status_code in [302, 403]


def test_vacation_policy_view_requires_authentication(app, client, db_session):
    """Test that viewing a vacation policy requires authentication."""
    with app.app_context():
        response = client.get("/vacation/policies/999", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_policy_edit_requires_authentication(app, client, db_session):
    """Test that editing a vacation policy requires authentication."""
    with app.app_context():
        response = client.get("/vacation/policies/999/edit", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_leave_requests_requires_authentication(app, client, db_session):
    """Test that viewing leave requests requires authentication."""
    with app.app_context():
        response = client.get("/vacation/leave-requests", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_account_view_requires_authentication(app, client, db_session):
    """Test that viewing vacation account requires authentication."""
    with app.app_context():
        response = client.get("/vacation/accounts/999", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_vacation_policy_detail_not_found(app, client, admin_user, db_session):
    """Test that viewing a non-existent vacation policy redirects to index."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/vacation/policies/non-existent-policy-id", follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to policy index after not finding the policy




def test_vacation_policy_new_shows_paid_vacation_percentage_field(app, client, admin_user, db_session):
    """Test new vacation policy form includes liability accrual percentage field."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/vacation/policies/new")
        assert response.status_code == 200
        assert b"Porcentaje de pago de vacaciones" in response.data

def test_vacation_policy_detail_success(app, client, admin_user, db_session):
    """Test that viewing an existing vacation policy shows details."""
    from decimal import Decimal
    from coati_payroll.model import VacationPolicy, Empresa

    with app.app_context():
        # Create required entities
        empresa = Empresa(codigo="TEST001", razon_social="Test Company", ruc="J-123", activo=True)
        db_session.add(empresa)
        db_session.commit()

        # Create vacation policy without planilla (global policy)
        # Note: planilla_id is None to create a global policy, avoiding dependency
        # on planilla.view route which may not be implemented
        policy = VacationPolicy(
            codigo="POL001",
            nombre="Test Policy",
            empresa_id=empresa.id,
            planilla_id=None,
            accrual_rate=Decimal("15.0000"),
            activo=True,
        )
        db_session.add(policy)
        db_session.commit()

        policy_id = policy.id

        # Test viewing the policy detail
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/vacation/policies/{policy_id}")
        assert response.status_code == 200
        assert b"Porcentaje de pago de vacaciones" in response.data
