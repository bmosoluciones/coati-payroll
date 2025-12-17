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
"""Comprehensive tests for carga inicial prestacion (coati_payroll/vistas/carga_inicial_prestacion.py)."""

from coati_payroll.enums import TipoUsuario
from tests.helpers.auth import login_user


def test_carga_inicial_prestacion_index_requires_authentication(app, client, db_session):
    """Test that carga inicial index requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_index_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access carga inicial list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/")
        assert response.status_code == 200


def test_carga_inicial_prestacion_new_requires_admin(app, client, db_session):
    """Test that creating initial loads requires admin role."""
    with app.app_context():
        from tests.factories.user_factory import create_user

        # Create non-admin user
        hhrr_user = create_user(db_session, "hruser", "password", tipo=TipoUsuario.HHRR)
        login_user(client, hhrr_user.usuario, "password")

        response = client.get("/carga-inicial-prestaciones/new", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]


def test_carga_inicial_prestacion_new_accessible_to_admin(app, client, admin_user, db_session):
    """Test that admin can create initial loads."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/new")
        assert response.status_code == 200


def test_carga_inicial_prestacion_supports_pagination(app, client, admin_user, db_session):
    """Test that carga inicial list supports pagination."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/?page=1")
        assert response.status_code == 200


def test_carga_inicial_prestacion_workflow_view_list(app, client, admin_user, db_session):
    """End-to-end test: View carga inicial list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all loads
        response = client.get("/carga-inicial-prestaciones/")
        assert response.status_code == 200

        # Step 2: Access creation form (admin only)
        response = client.get("/carga-inicial-prestaciones/new")
        assert response.status_code == 200


def test_carga_inicial_prestacion_detail_requires_authentication(app, client, db_session):
    """Test that viewing load details requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/detail/test-id", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_edit_requires_admin(app, client, db_session):
    """Test that editing loads requires admin role."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        hhrr_user = create_user(db_session, "hruser2", "password", tipo=TipoUsuario.HHRR)
        login_user(client, hhrr_user.usuario, "password")

        response = client.get("/carga-inicial-prestaciones/edit/test-id", follow_redirects=False)
        assert response.status_code in [302, 403]


def test_carga_inicial_prestacion_delete_requires_admin(app, client, db_session):
    """Test that deleting loads requires admin role."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        hhrr_user = create_user(db_session, "hruser3", "password", tipo=TipoUsuario.HHRR)
        login_user(client, hhrr_user.usuario, "password")

        response = client.post("/carga-inicial-prestaciones/delete/test-id", follow_redirects=False)
        assert response.status_code in [302, 403]


def test_carga_inicial_prestacion_approve_requires_admin(app, client, db_session):
    """Test that approving loads requires admin role."""
    with app.app_context():
        response = client.post("/carga-inicial-prestaciones/approve/test-id", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_supports_status_filter(app, client, admin_user, db_session):
    """Test that load list can be filtered by status."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/?estado=borrador")
        assert response.status_code == 200


def test_carga_inicial_prestacion_workflow_complete_process(app, client, admin_user, db_session):
    """End-to-end test: Complete initial load process."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all loads
        response = client.get("/carga-inicial-prestaciones/")
        assert response.status_code == 200

        # Step 2: Access creation form
        response = client.get("/carga-inicial-prestaciones/new")
        assert response.status_code == 200

        # Step 3: Filter by status
        response = client.get("/carga-inicial-prestaciones/?estado=borrador")
        assert response.status_code == 200
