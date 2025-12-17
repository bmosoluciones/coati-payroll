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
"""Comprehensive tests for report management routes (coati_payroll/vistas/report.py)."""

from coati_payroll.enums import TipoUsuario
from tests.helpers.auth import login_user


def test_report_index_requires_authentication(app, client, db_session):
    """Test that report index requires authentication."""
    with app.app_context():
        response = client.get("/report/", follow_redirects=False)
        assert response.status_code == 302


def test_report_admin_index_requires_authentication(app, client, db_session):
    """Test that admin report index requires authentication."""
    with app.app_context():
        response = client.get("/report/admin", follow_redirects=False)
        assert response.status_code == 302


def test_report_admin_index_requires_admin_role(app, client, db_session):
    """Test that admin report page requires admin role."""
    with app.app_context():
        from tests.factories.user_factory import create_user

        # Create non-admin user
        hhrr_user = create_user(db_session, "hruser", "password", tipo=TipoUsuario.HHRR)
        login_user(client, hhrr_user.usuario, "password")

        response = client.get("/report/admin", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]
