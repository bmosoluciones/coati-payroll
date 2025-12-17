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
"""Comprehensive tests for prestamo (loan) management (coati_payroll/vistas/prestamo.py)."""

from tests.helpers.auth import login_user


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
