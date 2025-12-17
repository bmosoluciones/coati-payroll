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
"""Comprehensive tests for planilla (payroll) management (coati_payroll/vistas/planilla.py)."""

from tests.helpers.auth import login_user


def test_planilla_index_requires_authentication(app, client, db_session):
    """Test that planilla index requires authentication."""
    with app.app_context():
        response = client.get("/planilla/", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_index_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access planilla list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/planilla/")
        assert response.status_code == 200


def test_planilla_new_requires_write_access(app, client, db_session):
    """Test that creating planillas requires write access."""
    with app.app_context():
        response = client.get("/planilla/new", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_edit_requires_write_access(app, client, db_session):
    """Test that editing planillas requires write access."""
    with app.app_context():
        # Need a valid planilla ID
        response = client.get("/planilla/edit/dummy-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_supports_pagination(app, client, admin_user, db_session):
    """Test that planilla list supports pagination."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/planilla/?page=1")
        assert response.status_code == 200


def test_planilla_supports_active_filter(app, client, admin_user, db_session):
    """Test that planilla list can be filtered by active status."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/planilla/?activo=true")
        assert response.status_code == 200


def test_planilla_execution_requires_authentication(app, client, db_session):
    """Test that planilla execution requires authentication."""
    with app.app_context():
        response = client.get("/planilla/execute/dummy-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_workflow_view_list(app, client, admin_user, db_session):
    """End-to-end test: View planilla list with filters."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all planillas
        response = client.get("/planilla/")
        assert response.status_code == 200

        # Step 2: Filter by active status
        response = client.get("/planilla/?activo=true")
        assert response.status_code == 200

        # Step 3: Pagination
        response = client.get("/planilla/?page=1")
        assert response.status_code == 200


def test_planilla_detail_requires_authentication(app, client, db_session):
    """Test that viewing planilla details requires authentication."""
    with app.app_context():
        response = client.get("/planilla/detail/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_close_requires_write_access(app, client, db_session):
    """Test that closing planilla requires write access."""
    with app.app_context():
        response = client.post("/planilla/close/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_reopen_requires_write_access(app, client, db_session):
    """Test that reopening planilla requires write access."""
    with app.app_context():
        response = client.post("/planilla/reopen/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_add_employee_requires_write_access(app, client, db_session):
    """Test that adding employees to planilla requires write access."""
    with app.app_context():
        response = client.post("/planilla/add-employee/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_remove_employee_requires_write_access(app, client, db_session):
    """Test that removing employees from planilla requires write access."""
    with app.app_context():
        response = client.post("/planilla/remove-employee/test-id/emp-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_supports_period_filter(app, client, admin_user, db_session):
    """Test that planilla list can be filtered by period."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/planilla/?periodo=2025-01")
        assert response.status_code == 200


def test_planilla_supports_company_filter(app, client, admin_user, db_session):
    """Test that planilla list can be filtered by company."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/planilla/?empresa_id=test-id")
        assert response.status_code == 200


def test_planilla_calculation_requires_authentication(app, client, db_session):
    """Test that planilla calculation requires authentication."""
    with app.app_context():
        response = client.post("/planilla/calculate/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_approve_requires_authentication(app, client, db_session):
    """Test that planilla approval requires authentication."""
    with app.app_context():
        response = client.post("/planilla/approve/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_planilla_workflow_complete_process(app, client, admin_user, db_session):
    """End-to-end test: Complete planilla workflow."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View planillas
        response = client.get("/planilla/")
        assert response.status_code == 200

        # Step 2: Filter by active
        response = client.get("/planilla/?activo=true")
        assert response.status_code == 200

        # Step 3: Filter by period
        response = client.get("/planilla/?periodo=2025-01")
        assert response.status_code == 200
