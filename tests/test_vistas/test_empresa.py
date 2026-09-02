# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for empresa (company) CRUD operations (coati_payroll/vistas/empresa.py)."""

from datetime import date, timedelta

from sqlalchemy import select
from coati_payroll.enums import NominaEstado
from coati_payroll.model import Empresa, Moneda, Nomina, Planilla, TipoPlanilla
from tests.helpers.auth import login_user


def test_empresa_index_requires_authentication(app, client, db_session):
    """Test that empresa index requires authentication."""
    with app.app_context():
        response = client.get("/empresa/", follow_redirects=False)
        assert response.status_code == 302


def test_empresa_index_lists_companies(app, client, admin_user, db_session):
    """Test that authenticated user can view company list."""
    with app.app_context():
        # Create test companies
        empresa1 = Empresa(
            codigo="EMP001",
            razon_social="Company One S.A.",
            ruc="J-12345678-9",
            activo=True,
            creado_por="admin-test",
        )
        empresa2 = Empresa(
            codigo="EMP002",
            razon_social="Company Two S.A.",
            ruc="J-98765432-1",
            activo=True,
            creado_por="admin-test",
        )
        db_session.add_all([empresa1, empresa2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/empresa/")
        assert response.status_code == 200
        assert b"Company One" in response.data or b"EMP001" in response.data


def test_empresa_new_requires_admin(app, client, db_session):
    """Test that only admin can create companies."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        # Create non-admin user
        hr_user = create_user(db_session, "hruser", "password", tipo=TipoUsuario.HHRR)

        login_user(client, hr_user.usuario, "password")

        response = client.get("/empresa/new", follow_redirects=False)
        # Should not allow access (403 or redirect)
        assert response.status_code in [302, 403]


def test_empresa_new_creates_company(app, client, admin_user, db_session):
    """Test creating a new company as admin."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/empresa/new",
            data={
                "codigo": "NEWCO",
                "razon_social": "New Company S.A.",
                "ruc": "J-11111111-1",
                "direccion": "123 Main St",
                "telefono": "555-1234",
                "correo": "info@newcompany.com",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            empresa = db_session.execute(select(Empresa).filter_by(codigo="NEWCO")).scalar_one_or_none()
            assert empresa is not None
            assert empresa.razon_social == "New Company S.A."
            assert empresa.ruc == "J-11111111-1"
            assert empresa.activo is True
            assert empresa.primer_mes_nomina is not None
            assert empresa.primer_anio_nomina is not None
            assert 1 <= int(empresa.primer_mes_nomina) <= 12


def test_empresa_edit_requires_admin(app, client, db_session):
    """Test that only admin can edit companies."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        # Create company
        empresa = Empresa(
            codigo="EDITCO",
            razon_social="Edit Company S.A.",
            ruc="J-22222222-2",
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(empresa)
        db_session.commit()

        # Create non-admin user
        hr_user = create_user(db_session, "hruser2", "password", tipo=TipoUsuario.HHRR)

        login_user(client, hr_user.usuario, "password")

        response = client.get(f"/empresa/{empresa.id}/edit", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]


def test_empresa_edit_updates_company(app, client, admin_user, db_session):
    """Test updating a company as admin."""
    with app.app_context():
        # Create company
        empresa = Empresa(
            codigo="UPDCO",
            razon_social="Update Company S.A.",
            ruc="J-33333333-3",
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(empresa)
        db_session.commit()
        db_session.refresh(empresa)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/empresa/{empresa.id}/edit",
            data={
                "codigo": "UPDCO",
                "razon_social": "Updated Company S.A.",
                "ruc": "J-33333333-3",
                "direccion": "456 New St",
                "telefono": "555-5678",
                "correo": "info@updated.com",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            db_session.refresh(empresa)
            assert empresa.razon_social == "Updated Company S.A."
            assert empresa.direccion == "456 New St"


def test_empresa_delete_requires_admin(app, client, db_session):
    """Test that only admin can delete companies."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        # Create company
        empresa = Empresa(
            codigo="DELCO",
            razon_social="Delete Company S.A.",
            ruc="J-44444444-4",
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(empresa)
        db_session.commit()

        # Create non-admin user
        hr_user = create_user(db_session, "hruser3", "password", tipo=TipoUsuario.HHRR)

        login_user(client, hr_user.usuario, "password")

        response = client.post(f"/empresa/{empresa.id}/delete", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]


def test_empresa_delete_removes_company(app, client, admin_user, db_session):
    """Test deleting a company as admin."""
    with app.app_context():
        # Create company
        empresa = Empresa(
            codigo="REMCO",
            razon_social="Remove Company S.A.",
            ruc="J-55555555-5",
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(empresa)
        db_session.commit()
        empresa_id = empresa.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/empresa/{empresa_id}/delete", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            empresa = db_session.execute(select(Empresa).filter_by(id=empresa_id)).scalar_one_or_none()
            assert empresa is None


def test_empresa_delete_prevents_deletion_if_has_employees(app, client, admin_user, db_session):
    """Test that company cannot be deleted if it has employees."""
    with app.app_context():
        from tests.factories.company_factory import create_company
        from tests.factories.employee_factory import create_employee

        # Create company
        empresa = create_company(db_session, "EMPCO", "Employee Company", "J-66666666-6")

        # Create employee with all required fields
        empleado = create_employee(
            db_session,
            empresa_id=empresa.id,
            primer_nombre="John",
            primer_apellido="Doe",
        )
        assert empleado

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/empresa/{empresa.id}/delete", follow_redirects=True)

        assert response.status_code == 200

        # Verify company still exists
        db_session.refresh(empresa)
        assert empresa is not None


def test_empresa_delete_prevents_deletion_if_has_nominas(app, client, admin_user, db_session):
    """Test that company cannot be deleted if it has associated nominas."""
    with app.app_context():
        from tests.factories.company_factory import create_company

        empresa = create_company(db_session, "EMPNOM", "Nomina Company", "J-66666666-7")

        tipo_planilla = TipoPlanilla(codigo="QN", descripcion="Quincenal", periodicidad="biweekly", activo=True)
        moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
        db_session.add_all([tipo_planilla, moneda])
        db_session.flush()

        planilla = Planilla(
            nombre="Planilla empresa con nómina",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(planilla)
        db_session.flush()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date.today(),
            periodo_fin=date.today() + timedelta(days=14),
            generado_por=admin_user.usuario,
            estado="generated",
        )
        db_session.add(nomina)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/empresa/{empresa.id}/delete", follow_redirects=True)

        assert response.status_code == 200
        db_session.refresh(empresa)
        assert empresa is not None


def test_empresa_edit_locks_initial_period_when_has_applied_or_paid_nominas(app, client, admin_user, db_session):
    """It should keep bootstrap fields unchanged when payroll already applied/paid."""
    with app.app_context():
        empresa = Empresa(
            codigo="LOCKED01",
            razon_social="Locked Company S.A.",
            ruc="J-99999999-9",
            activo=True,
            primer_mes_nomina=3,
            primer_anio_nomina=2025,
            creado_por="admin-test",
        )
        db_session.add(empresa)
        db_session.flush()

        tipo_planilla = TipoPlanilla(codigo="MN1", descripcion="Mensual", periodicidad="monthly", activo=True)
        moneda = Moneda(codigo="EUR", nombre="Euro", simbolo="EUR", activo=True)
        db_session.add_all([tipo_planilla, moneda])
        db_session.flush()

        planilla = Planilla(
            nombre="Planilla Lock",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(planilla)
        db_session.flush()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date.today(),
            periodo_fin=date.today() + timedelta(days=14),
            generado_por=admin_user.usuario,
            estado=NominaEstado.APLICADO.value,
        )
        db_session.add(nomina)
        db_session.commit()
        db_session.refresh(empresa)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/empresa/{empresa.id}/edit",
            data={
                "codigo": empresa.codigo,
                "razon_social": "Locked Company Updated",
                "ruc": empresa.ruc,
                "primer_mes_nomina": "9",
                "primer_anio_nomina": "2026",
                "activo": "y",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        db_session.refresh(empresa)
        assert empresa.razon_social == "Locked Company Updated"
        assert empresa.primer_mes_nomina == 3
        assert empresa.primer_anio_nomina == 2025

def test_empresa_toggle_active_changes_status(app, client, admin_user, db_session):
    """Test toggling company active status."""
    with app.app_context():
        # Create active company
        empresa = Empresa(
            codigo="TOGCO",
            razon_social="Toggle Company S.A.",
            ruc="J-77777777-7",
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(empresa)
        db_session.commit()
        db_session.refresh(empresa)

        login_user(client, admin_user.usuario, "admin-password")

        # Toggle to inactive
        response = client.post(f"/empresa/{empresa.id}/toggle", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            db_session.refresh(empresa)
            assert empresa.activo is False

            # Toggle back to active
            response = client.post(f"/empresa/{empresa.id}/toggle", follow_redirects=False)

            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(empresa)
                assert empresa.activo is True


def test_empresa_workflow_create_edit_toggle_delete(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, toggle, and delete a company."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create
        response = client.post(
            "/empresa/new",
            data={
                "codigo": "WORKFLOW",
                "razon_social": "Workflow Company S.A.",
                "ruc": "J-88888888-8",
                "direccion": "789 Test St",
                "activo": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            empresa = db_session.execute(select(Empresa).filter_by(codigo="WORKFLOW")).scalar_one_or_none()
            assert empresa is not None
            empresa_id = empresa.id

            # Step 2: Edit
            response = client.post(
                f"/empresa/{empresa_id}/edit",
                data={
                    "codigo": "WORKFLOW",
                    "razon_social": "Workflow Company S.A. (Updated)",
                    "ruc": "J-88888888-8",
                    "direccion": "999 Updated St",
                    "activo": "y",
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(empresa)
                assert empresa.razon_social == "Workflow Company S.A. (Updated)"

                # Step 3: Toggle active
                response = client.post(f"/empresa/{empresa_id}/toggle", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    db_session.refresh(empresa)
                    assert empresa.activo is False

                    # Step 4: Delete
                    response = client.post(f"/empresa/{empresa_id}/delete", follow_redirects=False)
                    assert response.status_code in [200, 302]

                    if response.status_code == 302:
                        empresa = db_session.execute(select(Empresa).filter_by(id=empresa_id)).scalar_one_or_none()
                        assert empresa is None


def test_empresa_can_have_multiple_with_same_name(app, client, admin_user, db_session):
    """Test that multiple companies can have similar names but unique codes."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create first company
        response1 = client.post(
            "/empresa/new",
            data={
                "codigo": "ACME1",
                "razon_social": "ACME Corp",
                "ruc": "J-11111111-A",
                "activo": "y",
            },
            follow_redirects=False,
        )

        # Create second company with same name
        response2 = client.post(
            "/empresa/new",
            data={
                "codigo": "ACME2",
                "razon_social": "ACME Corp",
                "ruc": "J-11111111-B",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response1.status_code in [200, 302]
        assert response2.status_code in [200, 302]

        from sqlalchemy import func, select

        # Verify both exist
        count = (
            db_session.execute(select(func.count(Empresa.id)).filter(Empresa.razon_social == "ACME Corp")).scalar() or 0
        )
        assert count >= 2
