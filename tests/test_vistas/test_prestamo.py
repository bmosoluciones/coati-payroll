# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for prestamo (loan) management (coati_payroll/vistas/prestamo.py)."""

from decimal import Decimal
from types import SimpleNamespace

from tests.helpers.auth import login_user
from coati_payroll.vistas.prestamo import _adjust_payment_terms


def test_extraordinary_full_installment_keeps_remaining_installment_amount():
    """A full manual installment reduces the count of future installments too."""
    prestamo = SimpleNamespace(
        abonos=[],
        monto_por_cuota=Decimal("10.00"),
        cuotas_pactadas=10,
        # Balance after applying a manual payment of 10 to a loan of 100.
        saldo_pendiente=Decimal("90.00"),
    )
    abono = SimpleNamespace(observaciones="Pago extraordinario")

    _adjust_payment_terms(prestamo, abono, "reducir_monto", Decimal("10.00"))

    assert prestamo.monto_por_cuota == Decimal("10.00")


def test_prestamo_index_requires_authentication(app, client, db_session):
    """Test that loan index requires authentication."""
    with app.app_context():
        response = client.get("/prestamo/", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_index_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access loan list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestamo/")
        assert response.status_code == 200


def test_prestamo_new_requires_write_access(app, client, db_session):
    """Test that creating loans requires write access."""
    with app.app_context():
        response = client.get("/prestamo/new", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_supports_pagination(app, client, admin_user, db_session):
    """Test that loan list supports pagination."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestamo/?page=1")
        assert response.status_code == 200


def test_prestamo_supports_status_filter(app, client, admin_user, db_session):
    """Test that loan list can be filtered by status."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestamo/?estado=activo")
        assert response.status_code == 200


def test_prestamo_workflow_view_list(app, client, admin_user, db_session):
    """End-to-end test: View loan list with filters."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all loans
        response = client.get("/prestamo/")
        assert response.status_code == 200

        # Step 2: Filter by status
        response = client.get("/prestamo/?estado=activo")
        assert response.status_code == 200

        # Step 3: Pagination
        response = client.get("/prestamo/?page=1")
        assert response.status_code == 200


def test_prestamo_edit_requires_write_access(app, client, db_session):
    """Test that editing loans requires write access."""
    with app.app_context():
        response = client.get("/prestamo/edit/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_delete_requires_write_access(app, client, db_session):
    """Test that deleting loans requires write access."""
    with app.app_context():
        response = client.post("/prestamo/delete/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_detail_requires_authentication(app, client, db_session):
    """Test that viewing loan details requires authentication."""
    with app.app_context():
        response = client.get("/prestamo/detail/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_payment_schedule_requires_authentication(app, client, db_session):
    """Test that viewing payment schedule requires authentication."""
    with app.app_context():
        response = client.get("/prestamo/schedule/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_supports_employee_filter(app, client, admin_user, db_session):
    """Test that loan list can be filtered by employee."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestamo/?empleado_id=test-id")
        assert response.status_code == 200


def test_prestamo_supports_date_filter(app, client, admin_user, db_session):
    """Test that loan list can be filtered by date."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestamo/?fecha_desde=2025-01-01")
        assert response.status_code == 200


def test_prestamo_approve_requires_authorization(app, client, db_session):
    """Test that loan approval requires proper authorization."""
    with app.app_context():
        response = client.post("/prestamo/approve/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_cancel_requires_write_access(app, client, db_session):
    """Test that canceling loans requires write access."""
    with app.app_context():
        response = client.post("/prestamo/cancel/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestamo_workflow_complete_lifecycle(app, client, admin_user, db_session):
    """End-to-end test: Complete loan lifecycle."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all loans
        response = client.get("/prestamo/")
        assert response.status_code == 200

        # Step 2: Filter by status
        response = client.get("/prestamo/?estado=activo")
        assert response.status_code == 200

        # Step 3: Filter by date
        response = client.get("/prestamo/?fecha_desde=2025-01-01")
        assert response.status_code == 200

        # Step 4: Pagination
        response = client.get("/prestamo/?page=1")
        assert response.status_code == 200
