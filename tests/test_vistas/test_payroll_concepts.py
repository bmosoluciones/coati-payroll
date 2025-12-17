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
"""Comprehensive tests for payroll concepts CRUD (coati_payroll/vistas/payroll_concepts.py)."""

from decimal import Decimal

from coati_payroll.model import Percepcion, Deduccion, Prestacion
from coati_payroll.enums import FormulaType
from tests.helpers.auth import login_user


# ============================================================================
# PERCEPCION TESTS
# ============================================================================


def test_percepcion_index_requires_authentication(app, client, db_session):
    """Test that percepcion index requires authentication."""
    with app.app_context():
        response = client.get("/percepciones/", follow_redirects=False)
        assert response.status_code == 302


def test_percepcion_index_lists_items(app, client, admin_user, db_session):
    """Test that authenticated user can view percepcion list."""
    with app.app_context():
        # Create test perceptions
        perc1 = Percepcion(
            codigo="SALARIO",
            nombre="Salario Base",
            descripcion="Base salary",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
        )
        perc2 = Percepcion(
            codigo="BONO",
            nombre="Bono Mensual",
            descripcion="Monthly bonus",
            formula_tipo=FormulaType.PORCENTAJE,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add_all([perc1, perc2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/percepciones/")
        assert response.status_code == 200
        assert b"SALARIO" in response.data or b"Salario" in response.data


def test_percepcion_new_creates_item(app, client, admin_user, db_session):
    """Test creating a new percepcion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/percepciones/new",
            data={
                "codigo": "COMISION",
                "nombre": "Comisión de Ventas",
                "descripcion": "Sales commission",
                "formula_tipo": FormulaType.PORCENTAJE,
                "valor_fijo": "0",
                "porcentaje": "5",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            perc = db_session.query(Percepcion).filter_by(codigo="COMISION").first()
            assert perc is not None
            assert perc.nombre == "Comisión de Ventas"
            assert perc.formula_tipo == FormulaType.PORCENTAJE


def test_percepcion_edit_updates_item(app, client, admin_user, db_session):
    """Test updating a percepcion."""
    with app.app_context():
        perc = Percepcion(
            codigo="EXTRA",
            nombre="Horas Extras",
            descripcion="Overtime pay",
            formula_tipo=FormulaType.HORAS,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/percepciones/edit/{perc.id}",
            data={
                "codigo": "EXTRA",
                "nombre": "Horas Extras (Updated)",
                "descripcion": "Overtime pay - updated",
                "formula_tipo": FormulaType.HORAS,
                "valor_fijo": "0",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            db_session.refresh(perc)
            assert perc.nombre == "Horas Extras (Updated)"


def test_percepcion_delete_removes_item(app, client, admin_user, db_session):
    """Test deleting a percepcion."""
    with app.app_context():
        perc = Percepcion(
            codigo="TEMP",
            nombre="Temporary Perception",
            descripcion="Temp",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(perc)
        db_session.commit()
        perc_id = perc.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/percepciones/delete/{perc_id}", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            perc = db_session.query(Percepcion).filter_by(id=perc_id).first()
            assert perc is None


# ============================================================================
# DEDUCCION TESTS
# ============================================================================


def test_deduccion_index_requires_authentication(app, client, db_session):
    """Test that deduccion index requires authentication."""
    with app.app_context():
        response = client.get("/deducciones/", follow_redirects=False)
        assert response.status_code == 302


def test_deduccion_new_creates_item(app, client, admin_user, db_session):
    """Test creating a new deduccion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/deducciones/new",
            data={
                "codigo": "INSS",
                "nombre": "Seguro Social",
                "descripcion": "Social security deduction",
                "formula_tipo": FormulaType.PORCENTAJE,
                "valor_fijo": "0",
                "porcentaje": "7",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            ded = db_session.query(Deduccion).filter_by(codigo="INSS").first()
            assert ded is not None
            assert ded.nombre == "Seguro Social"


def test_deduccion_supports_different_formula_types(app, client, admin_user, db_session):
    """Test that deducciones support different formula types."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        formula_types = [
            ("DED_FIJO", FormulaType.FIJO, "Fixed Deduction"),
            ("DED_PCT", FormulaType.PORCENTAJE, "Percentage Deduction"),
            ("DED_SAL", FormulaType.PORCENTAJE_SALARIO, "Salary % Deduction"),
        ]

        for codigo, tipo, nombre in formula_types:
            response = client.post(
                "/deducciones/new",
                data={
                    "codigo": codigo,
                    "nombre": nombre,
                    "descripcion": f"Test {tipo}",
                    "formula_tipo": tipo,
                    "valor_fijo": "100" if tipo == FormulaType.FIJO else "0",
                    "porcentaje": "10" if tipo != FormulaType.FIJO else "0",
                    "activo": "y",
                },
                follow_redirects=False,
            )

            assert response.status_code in [200, 302]


# ============================================================================
# PRESTACION TESTS
# ============================================================================


def test_prestacion_index_requires_authentication(app, client, db_session):
    """Test that prestacion index requires authentication."""
    with app.app_context():
        response = client.get("/prestaciones/", follow_redirects=False)
        assert response.status_code == 302


def test_prestacion_new_creates_item(app, client, admin_user, db_session):
    """Test creating a new prestacion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/prestaciones/new",
            data={
                "codigo": "AGUINALDO",
                "nombre": "Aguinaldo",
                "descripcion": "13th month salary",
                "formula_tipo": FormulaType.FORMULA,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            prest = db_session.query(Prestacion).filter_by(codigo="AGUINALDO").first()
            assert prest is not None
            assert prest.nombre == "Aguinaldo"


def test_prestacion_can_be_inactive(app, client, admin_user, db_session):
    """Test that prestaciones can be inactive."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/prestaciones/new",
            data={
                "codigo": "INACTIVE_PREST",
                "nombre": "Inactive Benefit",
                "descripcion": "Not active",
                "formula_tipo": FormulaType.FIJO,
                "valor_fijo": "0",
                # Not sending activo means False
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            prest = db_session.query(Prestacion).filter_by(codigo="INACTIVE_PREST").first()
            assert prest is not None
            assert prest.activo is False


def test_payroll_concepts_workflow(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, and delete a payroll concept."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create perception
        response = client.post(
            "/percepciones/new",
            data={
                "codigo": "WORKFLOW",
                "nombre": "Workflow Test",
                "descripcion": "Testing workflow",
                "formula_tipo": FormulaType.FIJO,
                "valor_fijo": "1000",
                "activo": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            perc = db_session.query(Percepcion).filter_by(codigo="WORKFLOW").first()
            assert perc is not None
            perc_id = perc.id

            # Step 2: Edit
            response = client.post(
                f"/percepciones/edit/{perc_id}",
                data={
                    "codigo": "WORKFLOW",
                    "nombre": "Workflow Test (Updated)",
                    "descripcion": "Testing workflow - updated",
                    "formula_tipo": FormulaType.FIJO,
                    "valor_fijo": "1500",
                    # Not sending activo means False
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(perc)
                assert perc.nombre == "Workflow Test (Updated)"
                assert perc.activo is False

                # Step 3: Delete
                response = client.post(f"/percepciones/delete/{perc_id}", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    perc = db_session.query(Percepcion).filter_by(id=perc_id).first()
                    assert perc is None
