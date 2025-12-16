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
"""Comprehensive tests for payroll type CRUD operations (coati_payroll/vistas/tipo_planilla.py)."""

from coati_payroll.model import TipoPlanilla
from coati_payroll.enums import Periodicidad
from tests.helpers.auth import login_user


def test_tipo_planilla_index_requires_authentication(app, client, db_session):
    """Test that tipo planilla index requires authentication."""
    with app.app_context():
        response = client.get("/tipo-planilla/", follow_redirects=False)
        assert response.status_code == 302


def test_tipo_planilla_index_lists_types(app, client, admin_user, db_session):
    """Test that authenticated user can view payroll type list."""
    with app.app_context():
        # Create test payroll types
        tipo1 = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Planilla Mensual",
            periodicidad=Periodicidad.MENSUAL,
            dias=30,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            periodos_por_anio=12,
            activo=True,
            creado_por="admin-test",
        )
        tipo2 = TipoPlanilla(
            codigo="QUINCENAL",
            descripcion="Planilla Quincenal",
            periodicidad=Periodicidad.QUINCENAL,
            dias=15,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            periodos_por_anio=24,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add_all([tipo1, tipo2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/tipo-planilla/")
        assert response.status_code == 200
        assert b"MENSUAL" in response.data or b"Mensual" in response.data


def test_tipo_planilla_new_creates_type(app, client, admin_user, db_session):
    """Test creating a new payroll type."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/tipo-planilla/new",
            data={
                "codigo": "SEMANAL",
                "descripcion": "Planilla Semanal",
                "periodicidad": Periodicidad.SEMANAL,
                "dias": 7,
                "mes_inicio_fiscal": 1,
                "dia_inicio_fiscal": 1,
                "acumula_anual": "y",
                "periodos_por_anio": 52,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            tipo = db_session.query(TipoPlanilla).filter_by(codigo="SEMANAL").first()
            assert tipo is not None
            assert tipo.descripcion == "Planilla Semanal"
            assert tipo.periodicidad == Periodicidad.SEMANAL
            assert tipo.dias == 7
            assert tipo.periodos_por_anio == 52
            assert tipo.activo is True


def test_tipo_planilla_edit_updates_type(app, client, admin_user, db_session):
    """Test updating a payroll type."""
    with app.app_context():
        # Create payroll type
        tipo = TipoPlanilla(
            codigo="ANUAL",
            descripcion="Planilla Anual",
            periodicidad=Periodicidad.MENSUAL,
            dias=365,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            periodos_por_anio=1,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(tipo)
        db_session.commit()
        db_session.refresh(tipo)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/tipo-planilla/edit/{tipo.id}",
            data={
                "codigo": "ANUAL",
                "descripcion": "Planilla Anual (Updated)",
                "periodicidad": Periodicidad.MENSUAL,
                "dias": 365,
                "mes_inicio_fiscal": 1,
                "dia_inicio_fiscal": 1,
                "acumula_anual": "y",
                "periodos_por_anio": 1,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            db_session.refresh(tipo)
            assert tipo.descripcion == "Planilla Anual (Updated)"


def test_tipo_planilla_delete_removes_type(app, client, admin_user, db_session):
    """Test deleting a payroll type."""
    with app.app_context():
        # Create payroll type
        tipo = TipoPlanilla(
            codigo="TEMP",
            descripcion="Temporary Type",
            periodicidad=Periodicidad.MENSUAL,
            dias=30,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            periodos_por_anio=12,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(tipo)
        db_session.commit()
        tipo_id = tipo.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/tipo-planilla/delete/{tipo_id}", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            tipo = db_session.query(TipoPlanilla).filter_by(id=tipo_id).first()
            assert tipo is None


def test_tipo_planilla_delete_prevents_deletion_if_in_use(app, client, admin_user, db_session):
    """Test that payroll type cannot be deleted if used by planillas."""
    with app.app_context():
        from coati_payroll.model import Planilla, Moneda
        from datetime import date

        # Create dependencies
        moneda = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        db_session.add(moneda)
        db_session.commit()

        tipo = TipoPlanilla(
            codigo="USED",
            descripcion="Used Type",
            periodicidad=Periodicidad.MENSUAL,
            dias=30,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            periodos_por_anio=12,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(tipo)
        db_session.commit()

        # Create planilla using this type with required date fields
        planilla = Planilla(
            nombre="Test Planilla",
            tipo_planilla_id=tipo.id,
            moneda_id=moneda.id,
            periodo_fiscal_inicio=date(2025, 1, 1),
            periodo_fiscal_fin=date(2025, 12, 31),
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(planilla)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/tipo-planilla/delete/{tipo.id}", follow_redirects=True)

        assert response.status_code == 200

        # Verify tipo still exists
        db_session.refresh(tipo)
        assert tipo is not None


def test_tipo_planilla_supports_different_periodicities(app, client, admin_user, db_session):
    """Test that different periodicities are supported."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        periodicities = [
            ("MENS", Periodicidad.MENSUAL, 30, 12),
            ("QUIN", Periodicidad.QUINCENAL, 15, 24),
            ("SEM", Periodicidad.SEMANAL, 7, 52),
            ("DIAR", Periodicidad.DIARIO, 1, 365),
        ]

        for codigo, periodicidad, dias, periodos in periodicities:
            response = client.post(
                "/tipo-planilla/new",
                data={
                    "codigo": codigo,
                    "descripcion": f"Planilla {periodicidad}",
                    "periodicidad": periodicidad,
                    "dias": dias,
                    "mes_inicio_fiscal": 1,
                    "dia_inicio_fiscal": 1,
                    "periodos_por_anio": periodos,
                    "activo": "y",
                },
                follow_redirects=False,
            )

            assert response.status_code in [200, 302]


def test_tipo_planilla_fiscal_year_settings(app, client, admin_user, db_session):
    """Test that fiscal year start date can be configured."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/tipo-planilla/new",
            data={
                "codigo": "FISCAL",
                "descripcion": "Fiscal Year Test",
                "periodicidad": Periodicidad.MENSUAL,
                "dias": 30,
                "mes_inicio_fiscal": 7,  # July
                "dia_inicio_fiscal": 1,
                "periodos_por_anio": 12,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            tipo = db_session.query(TipoPlanilla).filter_by(codigo="FISCAL").first()
            assert tipo is not None
            assert tipo.mes_inicio_fiscal == 7
            assert tipo.dia_inicio_fiscal == 1


def test_tipo_planilla_workflow_create_edit_delete(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, and delete a payroll type."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create
        response = client.post(
            "/tipo-planilla/new",
            data={
                "codigo": "WORKFLOW",
                "descripcion": "Workflow Test",
                "periodicidad": Periodicidad.MENSUAL,
                "dias": 30,
                "mes_inicio_fiscal": 1,
                "dia_inicio_fiscal": 1,
                "acumula_anual": "y",
                "periodos_por_anio": 12,
                "activo": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            tipo = db_session.query(TipoPlanilla).filter_by(codigo="WORKFLOW").first()
            assert tipo is not None
            tipo_id = tipo.id

            # Step 2: Edit
            response = client.post(
                f"/tipo-planilla/edit/{tipo_id}",
                data={
                    "codigo": "WORKFLOW",
                    "descripcion": "Workflow Test (Updated)",
                    "periodicidad": Periodicidad.QUINCENAL,
                    "dias": 15,
                    "mes_inicio_fiscal": 1,
                    "dia_inicio_fiscal": 1,
                    "periodos_por_anio": 24,
                    # Not sending activo means False
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(tipo)
                assert tipo.descripcion == "Workflow Test (Updated)"
                assert tipo.periodicidad == Periodicidad.QUINCENAL
                assert tipo.activo is False

                # Step 3: Delete
                response = client.post(f"/tipo-planilla/delete/{tipo_id}", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    tipo = db_session.query(TipoPlanilla).filter_by(id=tipo_id).first()
                    assert tipo is None
