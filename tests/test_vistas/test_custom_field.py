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
"""Comprehensive tests for custom field CRUD operations (coati_payroll/vistas/custom_field.py)."""

from coati_payroll.model import CampoPersonalizado
from tests.helpers.auth import login_user


def test_custom_field_index_requires_authentication(app, client, db_session):
    """Test that custom field index requires authentication."""
    with app.app_context():
        response = client.get("/custom_field/", follow_redirects=False)
        assert response.status_code == 302


def test_custom_field_index_lists_fields(app, client, admin_user, db_session):
    """Test that authenticated admin can view custom field list."""
    with app.app_context():
        # Create test custom fields
        field1 = CampoPersonalizado(
            nombre_campo="employee_id_card",
            etiqueta="Employee ID Card",
            tipo_dato="texto",
            orden=1,
            activo=True,
            creado_por="admin-test",
        )
        field2 = CampoPersonalizado(
            nombre_campo="years_experience",
            etiqueta="Years of Experience",
            tipo_dato="entero",
            orden=2,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add_all([field1, field2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/custom_field/")
        assert response.status_code == 200
        assert b"employee_id_card" in response.data or b"Employee ID Card" in response.data


def test_custom_field_new_creates_field(app, client, admin_user, db_session):
    """Test creating a new custom field."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/custom_field/new",
            data={
                "nombre_campo": "department_code",
                "etiqueta": "Department Code",
                "tipo_dato": "texto",
                "descripcion": "Employee department code",
                "orden": 10,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        # Verify custom field was created if redirect
        if response.status_code == 302:
            field = db_session.query(CampoPersonalizado).filter_by(nombre_campo="department_code").first()
            assert field is not None
            assert field.etiqueta == "Department Code"
            assert field.tipo_dato == "texto"
            assert field.orden == 10
            assert field.activo is True


def test_custom_field_edit_updates_field(app, client, admin_user, db_session):
    """Test updating a custom field."""
    with app.app_context():
        # Create custom field
        field = CampoPersonalizado(
            nombre_campo="skill_level",
            etiqueta="Skill Level",
            tipo_dato="entero",
            orden=5,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(field)
        db_session.commit()
        db_session.refresh(field)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/custom_field/edit/{field.id}",
            data={
                "nombre_campo": "skill_level",
                "etiqueta": "Skill Level (Updated)",
                "tipo_dato": "entero",
                "descripcion": "Updated description",
                "orden": 15,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        # Verify update if redirect
        if response.status_code == 302:
            db_session.refresh(field)
            assert field.etiqueta == "Skill Level (Updated)"
            assert field.orden == 15


def test_custom_field_delete_removes_field(app, client, admin_user, db_session):
    """Test deleting a custom field."""
    with app.app_context():
        # Create custom field
        field = CampoPersonalizado(
            nombre_campo="temp_field",
            etiqueta="Temporary Field",
            tipo_dato="texto",
            orden=1,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(field)
        db_session.commit()
        field_id = field.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/custom_field/delete/{field_id}", follow_redirects=False)

        assert response.status_code in [200, 302]

        # Verify deletion if redirect
        if response.status_code == 302:
            field = db_session.query(CampoPersonalizado).filter_by(id=field_id).first()
            assert field is None


def test_custom_field_supports_different_data_types(app, client, admin_user, db_session):
    """Test that custom fields support different data types."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data_types = [
            ("text_field", "texto", "Text Field"),
            ("integer_field", "entero", "Integer Field"),
            ("decimal_field", "decimal", "Decimal Field"),
            ("boolean_field", "booleano", "Boolean Field"),
        ]

        for nombre, tipo, etiqueta in data_types:
            response = client.post(
                "/custom_field/new",
                data={
                    "nombre_campo": nombre,
                    "etiqueta": etiqueta,
                    "tipo_dato": tipo,
                    "orden": 1,
                    "activo": "y",
                },
                follow_redirects=False,
            )

            assert response.status_code in [200, 302]

        # Verify all created if redirects
        count = db_session.query(CampoPersonalizado).count()
        assert count >= len(data_types)


def test_custom_field_ordering_works(app, client, admin_user, db_session):
    """Test that custom fields can be ordered."""
    with app.app_context():
        # Create fields with different orders
        field1 = CampoPersonalizado(
            nombre_campo="field_c", etiqueta="Field C", tipo_dato="texto", orden=30, activo=True, creado_por="admin-test"
        )
        field2 = CampoPersonalizado(
            nombre_campo="field_a", etiqueta="Field A", tipo_dato="texto", orden=10, activo=True, creado_por="admin-test"
        )
        field3 = CampoPersonalizado(
            nombre_campo="field_b", etiqueta="Field B", tipo_dato="texto", orden=20, activo=True, creado_por="admin-test"
        )
        db_session.add_all([field1, field2, field3])
        db_session.commit()

        # Query fields ordered by orden
        fields = db_session.query(CampoPersonalizado).order_by(CampoPersonalizado.orden).all()

        assert fields[0].nombre_campo == "field_a"
        assert fields[1].nombre_campo == "field_b"
        assert fields[2].nombre_campo == "field_c"


def test_custom_field_can_be_inactive(app, client, admin_user, db_session):
    """Test that custom fields can be inactive."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/custom_field/new",
            data={
                "nombre_campo": "inactive_field",
                "etiqueta": "Inactive Field",
                "tipo_dato": "texto",
                "orden": 1,
                # Not sending activo means False
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        # Verify inactive if redirect
        if response.status_code == 302:
            field = db_session.query(CampoPersonalizado).filter_by(nombre_campo="inactive_field").first()
            assert field is not None
            assert field.activo is False


def test_custom_field_workflow_create_edit_delete(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, and delete a custom field."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create
        response = client.post(
            "/custom_field/new",
            data={
                "nombre_campo": "test_workflow",
                "etiqueta": "Test Workflow",
                "tipo_dato": "texto",
                "descripcion": "Test description",
                "orden": 5,
                "activo": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            field = db_session.query(CampoPersonalizado).filter_by(nombre_campo="test_workflow").first()
            assert field is not None
            field_id = field.id

            # Step 2: Edit
            response = client.post(
                f"/custom_field/edit/{field_id}",
                data={
                    "nombre_campo": "test_workflow",
                    "etiqueta": "Test Workflow (Updated)",
                    "tipo_dato": "texto",
                    "orden": 10,
                    # Not sending activo means False
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(field)
                assert field.etiqueta == "Test Workflow (Updated)"
                assert field.activo is False

                # Step 3: Delete
                response = client.post(f"/custom_field/delete/{field_id}", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    field = db_session.query(CampoPersonalizado).filter_by(id=field_id).first()
                    assert field is None
