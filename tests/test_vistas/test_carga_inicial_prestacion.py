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


def test_carga_inicial_prestacion_nueva_requires_authentication(app, client, db_session):
    """Test that creating initial loads requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/nueva", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_nueva_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access nueva carga form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/nueva")
        assert response.status_code == 200


def test_carga_inicial_prestacion_reporte_requires_authentication(app, client, db_session):
    """Test that report access requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/reporte", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_reporte_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access reports."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/reporte")
        assert response.status_code == 200


def test_carga_inicial_prestacion_workflow_complete_process(app, client, admin_user, db_session):
    """End-to-end test: Complete initial load workflow."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all loads
        response = client.get("/carga-inicial-prestaciones/")
        assert response.status_code == 200

        # Step 2: Access creation form
        response = client.get("/carga-inicial-prestaciones/nueva")
        assert response.status_code == 200

        # Step 3: View report
        response = client.get("/carga-inicial-prestaciones/reporte")
        assert response.status_code == 200
