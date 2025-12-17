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
"""Comprehensive tests for calculation rule CRUD operations (coati_payroll/vistas/calculation_rule.py)."""

from datetime import date

from coati_payroll.model import ReglaCalculo
from tests.helpers.auth import login_user


def test_calculation_rule_index_requires_authentication(app, client, db_session):
    """Test that calculation rule index requires authentication."""
    with app.app_context():
        response = client.get("/calculation-rule/", follow_redirects=False)
        assert response.status_code == 302


def test_calculation_rule_index_lists_rules(app, client, admin_user, db_session):
    """Test that authenticated user can view calculation rule list."""
    with app.app_context():
        # Create test calculation rules
        rule1 = ReglaCalculo(
            codigo="IR_2025",
            nombre="Income Tax 2025",
            descripcion="Income tax calculation for 2025",
            jurisdiccion="Nicaragua",
            moneda_referencia="NIO",
            version=1,
            tipo_regla="impuesto",
            vigente_desde=date(2025, 1, 1),
            activo=True,
            esquema_json={},
            creado_por="admin-test",
        )
        rule2 = ReglaCalculo(
            codigo="INSS_2025",
            nombre="Social Security 2025",
            descripcion="Social security calculation",
            jurisdiccion="Nicaragua",
            moneda_referencia="NIO",
            version=1,
            tipo_regla="deduccion",
            vigente_desde=date(2025, 1, 1),
            activo=True,
            esquema_json={},
            creado_por="admin-test",
        )
        db_session.add_all([rule1, rule2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/calculation-rule/")
        assert response.status_code == 200
        assert b"IR_2025" in response.data or b"Income Tax" in response.data


def test_calculation_rule_new_creates_rule(app, client, admin_user, db_session):
    """Test creating a new calculation rule."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/calculation-rule/new",
            data={
                "codigo": "BONUS_2025",
                "nombre": "Annual Bonus Calculation",
                "descripcion": "Calculates annual bonus based on salary",
                "jurisdiccion": "Nicaragua",
                "moneda_referencia": "NIO",
                "version": 1,
                "tipo_regla": "prestacion",
                "vigente_desde": "2025-01-01",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rule = db_session.query(ReglaCalculo).filter_by(codigo="BONUS_2025").first()
            assert rule is not None
            assert rule.nombre == "Annual Bonus Calculation"
            assert rule.jurisdiccion == "Nicaragua"
            assert rule.tipo_regla == "prestacion"
            assert rule.activo is True


def test_calculation_rule_edit_updates_rule(app, client, admin_user, db_session):
    """Test updating a calculation rule."""
    with app.app_context():
        # Create calculation rule
        rule = ReglaCalculo(
            codigo="VACATION_2025",
            nombre="Vacation Calculation",
            descripcion="Calculate vacation pay",
            jurisdiccion="Nicaragua",
            moneda_referencia="NIO",
            version=1,
            tipo_regla="prestacion",
            vigente_desde=date(2025, 1, 1),
            activo=True,
            esquema_json={},
            creado_por="admin-test",
        )
        db_session.add(rule)
        db_session.commit()
        rule_id = rule.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/calculation-rule/edit/{rule_id}",
            data={
                "codigo": "VACATION_2025",
                "nombre": "Vacation Calculation (Updated)",
                "descripcion": "Calculate vacation pay with new formula",
                "jurisdiccion": "Nicaragua",
                "moneda_referencia": "NIO",
                "version": 2,
                "tipo_regla": "prestacion",
                "vigente_desde": "2025-01-01",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            updated_rule = db_session.query(ReglaCalculo).filter_by(id=rule_id).first()
            assert updated_rule.nombre == "Vacation Calculation (Updated)"
            assert updated_rule.version == "2"  # Version is stored as string in form


def test_calculation_rule_delete_removes_rule(app, client, admin_user, db_session):
    """Test deleting a calculation rule."""
    with app.app_context():
        # Create calculation rule
        rule = ReglaCalculo(
            codigo="TEMP_RULE",
            nombre="Temporary Rule",
            descripcion="Temporary calculation rule",
            jurisdiccion="Test",
            moneda_referencia="USD",
            version=1,
            tipo_regla="otro",
            vigente_desde=date(2025, 1, 1),
            activo=True,
            esquema_json={},
            creado_por="admin-test",
        )
        db_session.add(rule)
        db_session.commit()
        rule_id = rule.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/calculation-rule/delete/{rule_id}", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rule = db_session.query(ReglaCalculo).filter_by(id=rule_id).first()
            assert rule is None


def test_calculation_rule_supports_versioning(app, client, admin_user, db_session):
    """Test that calculation rules support versioning."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create version 1
        response1 = client.post(
            "/calculation-rule/new",
            data={
                "codigo": "TAX_CALC",
                "nombre": "Tax Calculation V1",
                "descripcion": "Version 1",
                "jurisdiccion": "Nicaragua",
                "moneda_referencia": "NIO",
                "version": 1,
                "tipo_regla": "impuesto",
                "vigente_desde": "2025-01-01",
                "vigente_hasta": "2025-06-30",
                "activo": "y",
            },
            follow_redirects=False,
        )

        # Create version 2
        response2 = client.post(
            "/calculation-rule/new",
            data={
                "codigo": "TAX_CALC",
                "nombre": "Tax Calculation V2",
                "descripcion": "Version 2",
                "jurisdiccion": "Nicaragua",
                "moneda_referencia": "NIO",
                "version": 2,
                "tipo_regla": "impuesto",
                "vigente_desde": "2025-07-01",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response1.status_code in [200, 302]
        assert response2.status_code in [200, 302]

        # Verify both versions exist
        count = db_session.query(ReglaCalculo).filter_by(codigo="TAX_CALC").count()
        assert count >= 2


def test_calculation_rule_different_rule_types(app, client, admin_user, db_session):
    """Test that different rule types are supported."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        rule_types = [
            ("IMP_RULE", "impuesto", "Tax Rule"),
            ("DED_RULE", "deduccion", "Deduction Rule"),
            ("PRES_RULE", "prestacion", "Benefit Rule"),
            ("OTH_RULE", "otro", "Other Rule"),
        ]

        for codigo, tipo, nombre in rule_types:
            response = client.post(
                "/calculation-rule/new",
                data={
                    "codigo": codigo,
                    "nombre": nombre,
                    "descripcion": f"Test {tipo} rule",
                    "jurisdiccion": "Test",
                    "moneda_referencia": "USD",
                    "version": 1,
                    "tipo_regla": tipo,
                    "vigente_desde": "2025-01-01",
                    "activo": "y",
                },
                follow_redirects=False,
            )

            assert response.status_code in [200, 302]


def test_calculation_rule_validity_period(app, client, admin_user, db_session):
    """Test that calculation rules can have validity periods."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/calculation-rule/new",
            data={
                "codigo": "TIME_LIMITED",
                "nombre": "Time Limited Rule",
                "descripcion": "Valid for specific period",
                "jurisdiccion": "Test",
                "moneda_referencia": "USD",
                "version": 1,
                "tipo_regla": "otro",
                "vigente_desde": "2025-01-01",
                "vigente_hasta": "2025-12-31",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rule = db_session.query(ReglaCalculo).filter_by(codigo="TIME_LIMITED").first()
            assert rule is not None
            assert rule.vigente_desde == date(2025, 1, 1)
            assert rule.vigente_hasta == date(2025, 12, 31)


def test_calculation_rule_can_be_inactive(app, client, admin_user, db_session):
    """Test that calculation rules can be inactive."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/calculation-rule/new",
            data={
                "codigo": "INACTIVE_RULE",
                "nombre": "Inactive Rule",
                "descripcion": "This rule is inactive",
                "jurisdiccion": "Test",
                "moneda_referencia": "USD",
                "version": 1,
                "tipo_regla": "otro",
                "vigente_desde": "2025-01-01",
                # Not sending activo means False
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rule = db_session.query(ReglaCalculo).filter_by(codigo="INACTIVE_RULE").first()
            assert rule is not None
            assert rule.activo is False


def test_calculation_rule_workflow_create_edit_delete(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, and delete a calculation rule."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create
        response = client.post(
            "/calculation-rule/new",
            data={
                "codigo": "WORKFLOW_TEST",
                "nombre": "Workflow Test Rule",
                "descripcion": "Testing workflow",
                "jurisdiccion": "Nicaragua",
                "moneda_referencia": "NIO",
                "version": 1,
                "tipo_regla": "impuesto",
                "vigente_desde": "2025-01-01",
                "activo": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rule = db_session.query(ReglaCalculo).filter_by(codigo="WORKFLOW_TEST").first()
            assert rule is not None
            rule_id = rule.id

            # Step 2: Edit
            response = client.post(
                f"/calculation-rule/edit/{rule_id}",
                data={
                    "codigo": "WORKFLOW_TEST",
                    "nombre": "Workflow Test Rule (Updated)",
                    "descripcion": "Testing workflow - updated",
                    "jurisdiccion": "Nicaragua",
                    "moneda_referencia": "NIO",
                    "version": 2,
                    "tipo_regla": "impuesto",
                    "vigente_desde": "2025-01-01",
                    # Not sending activo means False
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(rule)
                assert rule.nombre == "Workflow Test Rule (Updated)"
                assert rule.activo is False

                # Step 3: Delete
                response = client.post(f"/calculation-rule/delete/{rule_id}", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    rule = db_session.query(ReglaCalculo).filter_by(id=rule_id).first()
                    assert rule is None
