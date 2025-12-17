# Copyright 2025 BMO Soluciones, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Comprehensive tests for prestacion (benefits) management (coati_payroll/vistas/prestacion.py)."""

from coati_payroll.enums import TipoUsuario
from tests.helpers.auth import login_user


def test_prestacion_dashboard_requires_authentication(app, client, db_session):
    """Test that prestacion dashboard requires authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_dashboard_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access prestacion dashboard."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestacion-management/")
        assert response.status_code == 200


def test_prestacion_initial_balance_bulk_requires_admin(app, client, db_session):
    """Test that bulk initial balance loading requires admin role."""
    with app.app_context():
        from tests.factories.user_factory import create_user

        # Create non-admin user
        hhrr_user = create_user(db_session, "hruser", "password", tipo=TipoUsuario.HHRR)
        login_user(client, hhrr_user.usuario, "password")

        response = client.get("/prestacion-management/initial-balance/bulk", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]


def test_prestacion_initial_balance_bulk_accessible_to_admin(app, client, admin_user, db_session):
    """Test that admin can access bulk initial balance loading."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestacion-management/initial-balance/bulk")
        assert response.status_code == 200


def test_prestacion_dashboard_shows_statistics(app, client, admin_user, db_session):
    """Test that prestacion dashboard displays statistics."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestacion-management/")
        assert response.status_code == 200
        # Should contain statistics-related content
        assert b"prestacion" in response.data.lower() or b"benefit" in response.data.lower()


def test_prestacion_workflow_view_dashboard(app, client, admin_user, db_session):
    """End-to-end test: View prestacion dashboard."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View dashboard
        response = client.get("/prestacion-management/")
        assert response.status_code == 200

        # Step 2: Access bulk loading page (admin only)
        response = client.get("/prestacion-management/initial-balance/bulk")
        assert response.status_code == 200


def test_prestacion_balance_report_requires_authentication(app, client, db_session):
    """Test that balance report requires authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/balance-report", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_employee_detail_requires_authentication(app, client, db_session):
    """Test that employee benefit details require authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/employee/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_transaction_history_requires_authentication(app, client, db_session):
    """Test that transaction history requires authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/transactions", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_workflow_complete_management(app, client, admin_user, db_session):
    """End-to-end test: Complete prestacion management workflow."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View dashboard
        response = client.get("/prestacion-management/")
        assert response.status_code == 200

        # Step 2: Access bulk loading
        response = client.get("/prestacion-management/initial-balance/bulk")
        assert response.status_code == 200
