# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for planilla (payroll) routes."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from tests.helpers.auth import login_user

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def tipo_planilla(app, db_session):
    """Create a TipoPlanilla for testing."""
    with app.app_context():
        from coati_payroll.model import TipoPlanilla

        tipo = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Planilla Mensual",
            periodicidad="monthly",
            activo=True,
        )
        db_session.add(tipo)
        db_session.commit()
        db_session.refresh(tipo)
        return tipo


@pytest.fixture
def moneda(app, db_session):
    """Create a Moneda for testing."""
    with app.app_context():
        from coati_payroll.model import Moneda

        moneda = Moneda(codigo="USD", nombre="Dolar", simbolo="$", activo=True)
        db_session.add(moneda)
        db_session.commit()
        db_session.refresh(moneda)
        return moneda


@pytest.fixture
def empresa(app, db_session):
    """Create an Empresa for testing."""
    with app.app_context():
        from coati_payroll.model import Empresa

        empresa = Empresa(
            codigo="TEST",
            razon_social="Test Company S.A.",
            ruc="123456789",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()
        db_session.refresh(empresa)
        return empresa


@pytest.fixture
def empleado(app, db_session, empresa, moneda):
    """Create an Empleado for testing."""
    with app.app_context():
        from coati_payroll.model import Empleado

        empleado = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP001",
            primer_nombre="Juan",
            primer_apellido="Perez",
            identificacion_personal="001-010101-0001A",
            salario_base=Decimal("1000.00"),
            moneda_id=moneda.id,
            fecha_alta=date.today(),
            activo=True,
        )
        db_session.add(empleado)
        db_session.commit()
        db_session.refresh(empleado)
        return empleado


@pytest.fixture
def planilla(app, db_session, tipo_planilla, moneda, empresa, admin_user):
    """Create a Planilla for testing."""
    with app.app_context():
        from coati_payroll.model import Planilla

        planilla = Planilla(
            nombre="Test Planilla",
            descripcion="Planilla de prueba",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            periodo_fiscal_inicio=date(2024, 1, 1),
            periodo_fiscal_fin=date(2024, 12, 31),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(planilla)
        db_session.commit()
        db_session.refresh(planilla)
        return planilla


@pytest.fixture
def percepcion(app, db_session):
    """Create a Percepcion for testing."""
    with app.app_context():
        from coati_payroll.model import Percepcion

        percepcion = Percepcion(
            codigo="BONO",
            nombre="Bono Mensual",
            descripcion="Bono mensual por desempeño",
            formula_tipo="fixed",
            activo=True,
        )
        db_session.add(percepcion)
        db_session.commit()
        db_session.refresh(percepcion)
        return percepcion


@pytest.fixture
def deduccion(app, db_session):
    """Create a Deduccion for testing."""
    with app.app_context():
        from coati_payroll.model import Deduccion

        deduccion = Deduccion(
            codigo="INSS",
            nombre="INSS Laboral",
            descripcion="Seguro Social Laboral",
            formula_tipo="percentage",
            tipo="general",
            activo=True,
        )
        db_session.add(deduccion)
        db_session.commit()
        db_session.refresh(deduccion)
        return deduccion


@pytest.fixture
def prestacion(app, db_session):
    """Create a Prestacion for testing."""
    with app.app_context():
        from coati_payroll.model import Prestacion

        prestacion = Prestacion(
            codigo="VAC",
            nombre="Vacaciones",
            descripcion="Acumulación de vacaciones",
            formula_tipo="porcentaje_salario",
            activo=True,
        )
        db_session.add(prestacion)
        db_session.commit()
        db_session.refresh(prestacion)
        return prestacion


@pytest.fixture
def regla_calculo(app, db_session):
    """Create a ReglaCalculo for testing."""
    with app.app_context():
        from coati_payroll.model import ReglaCalculo

        regla = ReglaCalculo(
            codigo="IR",
            nombre="Impuesto sobre la Renta",
            descripcion="Cálculo de IR",
            vigente_desde=date(2024, 1, 1),
            activo=True,
        )
        db_session.add(regla)
        db_session.commit()
        db_session.refresh(regla)
        return regla


# ============================================================================
# AUTHENTICATION & AUTHORIZATION TESTS
# ============================================================================


def test_planilla_index_requires_authentication(app, client, db_session):
    """Test that planilla index requires authentication."""
    with app.app_context():
        response = client.get("/planilla/", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_planilla_index_for_admin(app, client, admin_user, db_session):
    """Test that admin can access planilla index."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/planilla/")
        assert response.status_code == 200


def test_planilla_new_requires_authentication(app, client, db_session):
    """Test that creating a new planilla requires authentication."""
    with app.app_context():
        response = client.get("/planilla/new", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_planilla_new_requires_write_access(app, client, db_session):
    """Test that creating a new planilla requires write access."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        # Create AUDIT user (read-only)
        audit_user = create_user(db_session, "auditor", "password", tipo=TipoUsuario.AUDIT)
        login_user(client, audit_user.usuario, "password")

        response = client.get("/planilla/new", follow_redirects=False)
        # Should not allow access (403 or redirect)
        assert response.status_code in [302, 403]


def test_planilla_edit_requires_authentication(app, client, db_session):
    """Test that editing a planilla requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/edit", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_planilla_config_requires_authentication(app, client, db_session):
    """Test that accessing planilla config requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/config", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_nomina_list_requires_authentication(app, client, db_session):
    """Test that nomina list requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/nominas", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_nomina_view_requires_authentication(app, client, db_session):
    """Test that viewing nomina requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/nomina/888", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_planilla_ejecutar_requires_authentication(app, client, db_session):
    """Test that executing planilla requires authentication."""
    with app.app_context():
        response = client.post("/planilla/999/ejecutar", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_planilla_clone_requires_authentication(app, client, db_session, planilla):
    """Test that cloning a planilla requires authentication."""
    with app.app_context():
        response = client.post(f"/planilla/{planilla.id}/clone", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


# ============================================================================
# PLANILLA CRUD TESTS
# ============================================================================


def test_planilla_new_get_displays_form(app, client, admin_user, db_session, tipo_planilla, moneda):
    """Test that GET /planilla/new displays the form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/planilla/new")
        assert response.status_code == 200
        assert b"nombre" in response.data or b"Nombre" in response.data


def test_planilla_new_post_creates_planilla(app, client, admin_user, db_session, tipo_planilla, moneda, empresa):
    """Test that POST /planilla/new creates a new planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {
            "nombre": "Nueva Planilla",
            "descripcion": "Descripción de prueba",
            "tipo_planilla_id": tipo_planilla.id,
            "moneda_id": moneda.id,
            "empresa_id": empresa.id,
            "periodo_fiscal_inicio": "2024-01-01",
            "periodo_fiscal_fin": "2024-12-31",
            "prioridad_prestamos": 250,
            "prioridad_adelantos": 251,
            "aplicar_prestamos_automatico": True,
            "aplicar_adelantos_automatico": True,
            "activo": True,
        }

        response = client.post("/planilla/new", data=data, follow_redirects=False)
        assert response.status_code == 302  # Redirect after successful creation

        # Verify planilla was created
        from coati_payroll.model import Planilla, db

        planilla = db_session.execute(db.select(Planilla).filter_by(nombre="Nueva Planilla")).scalar_one_or_none()
        assert planilla is not None
        assert planilla.descripcion == "Descripción de prueba"


def test_planilla_edit_get_displays_form(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/edit displays the edit form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/edit")
        assert response.status_code == 200
        assert planilla.nombre.encode() in response.data


def test_planilla_edit_post_updates_planilla(app, client, admin_user, db_session, planilla):
    """Test that POST /planilla/<id>/edit updates the planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        planilla_id = planilla.id
        data = {
            "nombre": "Planilla Actualizada",
            "descripcion": planilla.descripcion,
            "tipo_planilla_id": planilla.tipo_planilla_id,
            "moneda_id": planilla.moneda_id,
            "empresa_id": planilla.empresa_id,
            "periodo_fiscal_inicio": "2024-01-01",
            "periodo_fiscal_fin": "2024-12-31",
            "prioridad_prestamos": 250,
            "prioridad_adelantos": 251,
            "aplicar_prestamos_automatico": True,
            "aplicar_adelantos_automatico": True,
            "activo": True,
        }

        response = client.post(f"/planilla/{planilla_id}/edit", data=data, follow_redirects=False)
        assert response.status_code == 302

        # Fetch and verify update
        from coati_payroll.model import Planilla

        updated_planilla = db_session.get(Planilla, planilla_id)
        assert updated_planilla.nombre == "Planilla Actualizada"


def test_planilla_config_displays_summary(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/config displays configuration summary."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/config")
        assert response.status_code == 200
        assert planilla.nombre.encode() in response.data


def test_planilla_delete_removes_planilla(app, client, admin_user, db_session, planilla):
    """Test that POST /planilla/<id>/delete removes the planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        planilla_id = planilla.id

        response = client.post(f"/planilla/{planilla_id}/delete", follow_redirects=False)
        assert response.status_code == 302

        # Verify planilla was deleted
        from coati_payroll.model import Planilla

        deleted = db_session.get(Planilla, planilla_id)
        assert deleted is None


def test_planilla_delete_is_blocked_if_has_nominas(app, client, admin_user, db_session, planilla):
    """Test that POST /planilla/<id>/delete is blocked when nominas exist."""
    with app.app_context():
        from coati_payroll.model import Nomina, Planilla

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

        response = client.post(f"/planilla/{planilla.id}/delete", follow_redirects=False)
        assert response.status_code == 302

        existing = db_session.get(Planilla, planilla.id)
        assert existing is not None


def test_planilla_index_shows_clone_action(app, client, admin_user, db_session, planilla):
    """Test that planilla index displays clone action for each planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/planilla/")
        assert response.status_code == 200
        assert f"/planilla/{planilla.id}/clone".encode() in response.data


def test_planilla_clone_creates_copy_with_associations(
    app, client, admin_user, db_session, planilla, percepcion, deduccion, prestacion
):
    """Test that POST /planilla/<id>/clone duplicates core planilla associations."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        from coati_payroll.model import (
            PlanillaIngreso,
            PlanillaDeduccion,
            PlanillaPrestacion,
            Planilla,
            VacationPolicy,
            db,
        )

        policy = VacationPolicy(
            codigo="VAC-CLONE-SOURCE",
            nombre="Vacaciones de la planilla origen",
            planilla_id=planilla.id,
            empresa_id=planilla.empresa_id,
            activo=True,
        )
        db_session.add(policy)
        db_session.flush()
        planilla.vacation_policy_id = policy.id

        ingreso = PlanillaIngreso(
            planilla_id=planilla.id,
            percepcion_id=percepcion.id,
            orden=3,
            editable=False,
            monto_predeterminado=Decimal("150.00"),
            porcentaje=Decimal("10.00"),
            activo=True,
            creado_por=admin_user.usuario,
        )
        ded = PlanillaDeduccion(
            planilla_id=planilla.id,
            deduccion_id=deduccion.id,
            prioridad=50,
            orden=2,
            editable=False,
            monto_predeterminado=Decimal("25.00"),
            porcentaje=Decimal("2.00"),
            activo=True,
            es_obligatoria=True,
            detener_si_insuficiente=True,
            creado_por=admin_user.usuario,
        )
        pres = PlanillaPrestacion(
            planilla_id=planilla.id,
            prestacion_id=prestacion.id,
            orden=4,
            editable=False,
            monto_predeterminado=Decimal("30.00"),
            porcentaje=Decimal("3.00"),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add_all([ingreso, ded, pres])
        db_session.commit()

        response = client.post(f"/planilla/{planilla.id}/clone", follow_redirects=False)
        assert response.status_code == 302

        clon = db_session.execute(
            db.select(Planilla)
            .where(
                Planilla.id != planilla.id,
                Planilla.nombre.like("Test Planilla (Copia%"),
            )
            .order_by(Planilla.timestamp.desc())
        ).scalar_one_or_none()

        assert clon is not None
        assert f"/planilla/{clon.id}/edit" in response.location
        assert clon.creado_por == admin_user.usuario
        assert clon.tipo_planilla_id == planilla.tipo_planilla_id
        assert clon.moneda_id == planilla.moneda_id
        assert clon.empresa_id == planilla.empresa_id
        # A policy bound to the source planilla cannot legally be reused by
        # the clone; it must be configured (or cloned) explicitly later.
        assert clon.vacation_policy_id is None

        db_session.refresh(clon)
        assert len(clon.planilla_percepciones) == 1
        assert len(clon.planilla_deducciones) == 1
        assert len(clon.planilla_prestaciones) == 1

        clon_ingreso = clon.planilla_percepciones[0]
        assert clon_ingreso.percepcion_id == percepcion.id
        assert clon_ingreso.orden == 3
        assert clon_ingreso.monto_predeterminado == Decimal("150.00")
        assert clon_ingreso.porcentaje == Decimal("10.00")

        clon_deduccion = clon.planilla_deducciones[0]
        assert clon_deduccion.deduccion_id == deduccion.id
        assert clon_deduccion.prioridad == 50
        assert clon_deduccion.orden == 2
        assert clon_deduccion.es_obligatoria is True
        assert clon_deduccion.detener_si_insuficiente is True

        clon_prestacion = clon.planilla_prestaciones[0]
        assert clon_prestacion.prestacion_id == prestacion.id
        assert clon_prestacion.orden == 4
        assert clon_prestacion.monto_predeterminado == Decimal("30.00")
        assert clon_prestacion.porcentaje == Decimal("3.00")


def test_planilla_edit_shows_clone_button(app, client, admin_user, db_session, planilla):
    """Test that planilla edit page displays clone button."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/edit")
        assert response.status_code == 200
        assert f"/planilla/{planilla.id}/clone".encode() in response.data
        assert b"Clonar" in response.data


# ============================================================================
# CONFIGURATION PAGE TESTS
# ============================================================================


def test_config_empleados_displays(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/config/empleados displays employee config."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/config/empleados")
        assert response.status_code == 200


def test_config_percepciones_displays(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/config/percepciones displays perception config."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/config/percepciones")
        assert response.status_code == 200


def test_config_deducciones_displays(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/config/deducciones displays deduction config."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/config/deducciones")
        assert response.status_code == 200


def test_config_prestaciones_displays(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/config/prestaciones displays benefits config."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/config/prestaciones")
        assert response.status_code == 200


def test_config_reglas_displays(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/config/reglas displays calculation rules config."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/config/reglas")
        assert response.status_code == 200


# ============================================================================
# ASSOCIATION MANAGEMENT TESTS
# ============================================================================


def test_add_empleado_to_planilla(app, client, admin_user, db_session, planilla, empleado):
    """Test that POST /planilla/<id>/empleado/add adds an employee."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {"empleado_id": empleado.id}
        response = client.post(f"/planilla/{planilla.id}/empleado/add", data=data, follow_redirects=False)
        assert response.status_code == 302

        # Verify association was created
        from coati_payroll.model import PlanillaEmpleado, db

        association = db_session.execute(
            db.select(PlanillaEmpleado).filter_by(planilla_id=planilla.id, empleado_id=empleado.id)
        ).scalar_one_or_none()
        assert association is not None


def test_remove_empleado_from_planilla(app, client, admin_user, db_session, planilla, empleado):
    """Test that POST /planilla/<id>/empleado/<assoc_id>/remove removes an employee."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # First add the employee
        from coati_payroll.model import PlanillaEmpleado

        association = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=date.today(),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()
        db_session.refresh(association)

        # Now remove it
        response = client.post(f"/planilla/{planilla.id}/empleado/{association.id}/remove", follow_redirects=False)
        assert response.status_code == 302

        # Verify it was removed
        removed = db_session.get(PlanillaEmpleado, association.id)
        assert removed is None


def test_add_percepcion_to_planilla(app, client, admin_user, db_session, planilla, percepcion):
    """Test that POST /planilla/<id>/percepcion/add adds a perception."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {"percepcion_id": percepcion.id, "orden": 1}
        response = client.post(f"/planilla/{planilla.id}/percepcion/add", data=data, follow_redirects=False)
        assert response.status_code == 302

        # Verify association was created
        from coati_payroll.model import PlanillaIngreso, db

        association = db_session.execute(
            db.select(PlanillaIngreso).filter_by(planilla_id=planilla.id, percepcion_id=percepcion.id)
        ).scalar_one_or_none()
        assert association is not None


def test_remove_percepcion_from_planilla(app, client, admin_user, db_session, planilla, percepcion):
    """Test that POST /planilla/<id>/percepcion/<assoc_id>/remove removes a perception."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # First add the perception
        from coati_payroll.model import PlanillaIngreso

        association = PlanillaIngreso(
            planilla_id=planilla.id,
            percepcion_id=percepcion.id,
            orden=1,
            editable=True,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()
        db_session.refresh(association)

        # Now remove it
        response = client.post(f"/planilla/{planilla.id}/percepcion/{association.id}/remove", follow_redirects=False)
        assert response.status_code == 302

        # Verify it was removed
        removed = db_session.get(PlanillaIngreso, association.id)
        assert removed is None


def test_add_deduccion_to_planilla(app, client, admin_user, db_session, planilla, deduccion):
    """Test that POST /planilla/<id>/deduccion/add adds a deduction."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {"deduccion_id": deduccion.id, "prioridad": 100, "es_obligatoria": "on"}
        response = client.post(f"/planilla/{planilla.id}/deduccion/add", data=data, follow_redirects=False)
        assert response.status_code == 302

        # Verify association was created
        from coati_payroll.model import PlanillaDeduccion, db

        association = db_session.execute(
            db.select(PlanillaDeduccion).filter_by(planilla_id=planilla.id, deduccion_id=deduccion.id)
        ).scalar_one_or_none()
        assert association is not None
        assert association.prioridad == 100


def test_remove_deduccion_from_planilla(app, client, admin_user, db_session, planilla, deduccion):
    """Test that POST /planilla/<id>/deduccion/<assoc_id>/remove removes a deduction."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # First add the deduction
        from coati_payroll.model import PlanillaDeduccion

        association = PlanillaDeduccion(
            planilla_id=planilla.id,
            deduccion_id=deduccion.id,
            prioridad=100,
            es_obligatoria=True,
            editable=True,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()
        db_session.refresh(association)

        # Now remove it
        response = client.post(f"/planilla/{planilla.id}/deduccion/{association.id}/remove", follow_redirects=False)
        assert response.status_code == 302

        # Verify it was removed
        removed = db_session.get(PlanillaDeduccion, association.id)
        assert removed is None


def test_update_deduccion_priority(app, client, admin_user, db_session, planilla, deduccion):
    """Test that POST /planilla/<id>/deduccion/<assoc_id>/update-priority updates priority."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # First add the deduction
        from coati_payroll.model import PlanillaDeduccion

        association = PlanillaDeduccion(
            planilla_id=planilla.id,
            deduccion_id=deduccion.id,
            prioridad=100,
            es_obligatoria=True,
            editable=True,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()
        db_session.refresh(association)

        # Update priority
        data = {"prioridad": 200}
        response = client.post(
            f"/planilla/{planilla.id}/deduccion/{association.id}/update-priority",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify priority was updated
        db_session.refresh(association)
        assert association.prioridad == 200


def test_add_prestacion_to_planilla(app, client, admin_user, db_session, planilla, prestacion):
    """Test that POST /planilla/<id>/prestacion/add adds a benefit."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {"prestacion_id": prestacion.id, "orden": 1}
        response = client.post(f"/planilla/{planilla.id}/prestacion/add", data=data, follow_redirects=False)
        assert response.status_code == 302

        # Verify association was created
        from coati_payroll.model import PlanillaPrestacion, db

        association = db_session.execute(
            db.select(PlanillaPrestacion).filter_by(planilla_id=planilla.id, prestacion_id=prestacion.id)
        ).scalar_one_or_none()
        assert association is not None


def test_remove_prestacion_from_planilla(app, client, admin_user, db_session, planilla, prestacion):
    """Test that POST /planilla/<id>/prestacion/<assoc_id>/remove removes a benefit."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # First add the benefit
        from coati_payroll.model import PlanillaPrestacion

        association = PlanillaPrestacion(
            planilla_id=planilla.id,
            prestacion_id=prestacion.id,
            orden=1,
            editable=True,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()
        db_session.refresh(association)

        # Now remove it
        response = client.post(f"/planilla/{planilla.id}/prestacion/{association.id}/remove", follow_redirects=False)
        assert response.status_code == 302

        # Verify it was removed
        removed = db_session.get(PlanillaPrestacion, association.id)
        assert removed is None


def test_add_regla_to_planilla(app, client, admin_user, db_session, planilla, regla_calculo):
    """Test that POST /planilla/<id>/regla/add adds a calculation rule."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {"regla_calculo_id": regla_calculo.id, "orden": 1}
        response = client.post(f"/planilla/{planilla.id}/regla/add", data=data, follow_redirects=False)
        assert response.status_code == 302

        # Verify association was created
        from coati_payroll.model import PlanillaReglaCalculo, db

        association = db_session.execute(
            db.select(PlanillaReglaCalculo).filter_by(planilla_id=planilla.id, regla_calculo_id=regla_calculo.id)
        ).scalar_one_or_none()
        assert association is not None


def test_remove_regla_from_planilla(app, client, admin_user, db_session, planilla, regla_calculo):
    """Test that POST /planilla/<id>/regla/<assoc_id>/remove removes a calculation rule."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # First add the rule
        from coati_payroll.model import PlanillaReglaCalculo

        association = PlanillaReglaCalculo(
            planilla_id=planilla.id,
            regla_calculo_id=regla_calculo.id,
            orden=1,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()
        db_session.refresh(association)

        # Now remove it
        response = client.post(f"/planilla/{planilla.id}/regla/{association.id}/remove", follow_redirects=False)
        assert response.status_code == 302

        # Verify it was removed
        removed = db_session.get(PlanillaReglaCalculo, association.id)
        assert removed is None


# ============================================================================
# NOMINA EXECUTION TESTS
# ============================================================================


def test_ejecutar_nomina_get_displays_form(app, client, admin_user, db_session, planilla, empleado):
    """Test that GET /planilla/<id>/ejecutar displays the execution form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Add employee to planilla
        from coati_payroll.model import PlanillaEmpleado

        association = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=date.today(),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/ejecutar")
        assert response.status_code == 200


def test_listar_nominas_displays_list(app, client, admin_user, db_session, planilla):
    """Test that GET /planilla/<id>/nominas displays nomina list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/nominas")
        assert response.status_code == 200


# ============================================================================
# NOVEDADES (NOVELTIES) CRUD TESTS
# ============================================================================


@pytest.fixture
def nomina(app, db_session, planilla, admin_user):
    """Create a Nomina for testing novedades."""
    with app.app_context():
        from coati_payroll.model import Nomina

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date.today(),
            periodo_fin=date.today() + timedelta(days=14),
            generado_por=admin_user.usuario,
            estado="generated",
        )
        db_session.add(nomina)
        db_session.commit()
        db_session.refresh(nomina)
        return nomina


@pytest.fixture
def nomina_empleado(app, db_session, nomina, empleado):
    """Create a NominaEmpleado for testing novedades."""
    with app.app_context():
        from coati_payroll.model import NominaEmpleado

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            salario_bruto=Decimal("1000.00"),
            total_ingresos=Decimal("1000.00"),
            total_deducciones=Decimal("100.00"),
            salario_neto=Decimal("900.00"),
            sueldo_base_historico=Decimal("1000.00"),
        )
        db_session.add(nomina_empleado)
        db_session.commit()
        db_session.refresh(nomina_empleado)
        return nomina_empleado


@pytest.fixture
def planilla_novedad_conceptos(app, db_session, planilla, percepcion, deduccion, admin_user):
    """Assign active income/deduction concepts to planilla for novedades tests."""
    with app.app_context():
        from coati_payroll.model import PlanillaIngreso, PlanillaDeduccion

        ingreso = PlanillaIngreso(
            planilla_id=planilla.id,
            percepcion_id=percepcion.id,
            orden=1,
            activo=True,
            creado_por=admin_user.usuario,
        )
        egreso = PlanillaDeduccion(
            planilla_id=planilla.id,
            deduccion_id=deduccion.id,
            prioridad=1,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add_all([ingreso, egreso])
        db_session.commit()
        return ingreso, egreso


def test_listar_novedades_displays(app, client, admin_user, db_session, planilla, nomina, empleado):
    """Test that GET /planilla/<id>/nomina/<nomina_id>/novedades displays novedades list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Add employee to planilla
        from coati_payroll.model import PlanillaEmpleado

        association = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=date.today(),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades")
        assert response.status_code == 200


def test_nueva_novedad_get_displays_form(app, client, admin_user, db_session, planilla, nomina, nomina_empleado):
    """Test that GET /planilla/<id>/nomina/<nomina_id>/novedades/new displays form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new")
        assert response.status_code == 200


def test_nueva_novedad_is_blocked_for_paid_nomina(app, client, admin_user, db_session, planilla, nomina):
    """Paid payrolls are immutable even though their state is not ``applied``."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        nomina.estado = "paid"
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new", follow_redirects=False)

        assert response.status_code == 302


def test_nueva_novedad_get_filters_concepts_by_planilla_state_and_type(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    deduccion,
    planilla_novedad_conceptos,
):
    """GET novedades/new should show only active planilla concepts and hide tax/social_security deductions."""
    with app.app_context():
        from coati_payroll.model import Planilla, Percepcion, Deduccion, PlanillaIngreso, PlanillaDeduccion

        login_user(client, admin_user.usuario, "admin-password")

        # Unassigned/hidden income concepts
        percepcion_no_asignada = Percepcion(
            codigo="BONO_OUT",
            nombre="Bono Fuera de Planilla",
            formula_tipo="fixed",
            activo=True,
        )
        percepcion_inactiva = Percepcion(
            codigo="BONO_OFF",
            nombre="Bono Inactivo",
            formula_tipo="fixed",
            activo=False,
        )

        # Deductions for filtering scenarios
        deduccion_tax = Deduccion(
            codigo="DED_TAX",
            nombre="Impuesto Test",
            tipo="tax",
            formula_tipo="fixed",
            activo=True,
        )
        deduccion_social = Deduccion(
            codigo="DED_SS",
            nombre="Seguro Social Test",
            tipo="social_security",
            formula_tipo="fixed",
            activo=True,
        )
        deduccion_otra_planilla = Deduccion(
            codigo="DED_OTHER",
            nombre="Deducción Otra Planilla",
            tipo="general",
            formula_tipo="fixed",
            activo=True,
        )
        deduccion_asoc_inactiva = Deduccion(
            codigo="DED_ASSOC_OFF",
            nombre="Deducción Asociación Inactiva",
            tipo="general",
            formula_tipo="fixed",
            activo=True,
        )
        deduccion_catalogo_inactivo = Deduccion(
            codigo="DED_CAT_OFF",
            nombre="Deducción Catálogo Inactivo",
            tipo="general",
            formula_tipo="fixed",
            activo=False,
        )
        db_session.add_all(
            [
                percepcion_no_asignada,
                percepcion_inactiva,
                deduccion_tax,
                deduccion_social,
                deduccion_otra_planilla,
                deduccion_asoc_inactiva,
                deduccion_catalogo_inactivo,
            ]
        )
        db_session.commit()

        # Second planilla to verify scope filtering
        otra_planilla = Planilla(
            nombre="Otra Planilla Test",
            descripcion="Planilla secundaria",
            tipo_planilla_id=planilla.tipo_planilla_id,
            moneda_id=planilla.moneda_id,
            empresa_id=planilla.empresa_id,
            periodo_fiscal_inicio=planilla.periodo_fiscal_inicio,
            periodo_fiscal_fin=planilla.periodo_fiscal_fin,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(otra_planilla)
        db_session.commit()
        db_session.refresh(otra_planilla)

        # Associations for visibility/hiding checks
        db_session.add(
            PlanillaIngreso(
                planilla_id=planilla.id,
                percepcion_id=percepcion_inactiva.id,
                orden=2,
                activo=True,
                creado_por=admin_user.usuario,
            )
        )
        db_session.add_all(
            [
                PlanillaDeduccion(
                    planilla_id=planilla.id,
                    deduccion_id=deduccion_tax.id,
                    prioridad=2,
                    activo=True,
                    creado_por=admin_user.usuario,
                ),
                PlanillaDeduccion(
                    planilla_id=planilla.id,
                    deduccion_id=deduccion_social.id,
                    prioridad=3,
                    activo=True,
                    creado_por=admin_user.usuario,
                ),
                PlanillaDeduccion(
                    planilla_id=planilla.id,
                    deduccion_id=deduccion_asoc_inactiva.id,
                    prioridad=4,
                    activo=False,
                    creado_por=admin_user.usuario,
                ),
                PlanillaDeduccion(
                    planilla_id=planilla.id,
                    deduccion_id=deduccion_catalogo_inactivo.id,
                    prioridad=5,
                    activo=True,
                    creado_por=admin_user.usuario,
                ),
                PlanillaDeduccion(
                    planilla_id=otra_planilla.id,
                    deduccion_id=deduccion_otra_planilla.id,
                    prioridad=1,
                    activo=True,
                    creado_por=admin_user.usuario,
                ),
            ]
        )
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new")
        assert response.status_code == 200

        # Visible: assigned and active
        assert b"BONO - Bono Mensual" in response.data
        assert b"INSS - INSS Laboral" in response.data

        # Hidden: not assigned, wrong type, inactive association, inactive concept, other planilla
        assert b"BONO_OUT - Bono Fuera de Planilla" not in response.data
        assert b"BONO_OFF - Bono Inactivo" not in response.data
        assert b"DED_TAX - Impuesto Test" not in response.data
        assert b"DED_SS - Seguro Social Test" not in response.data
        assert b"DED_OTHER - Deducci\xc3\xb3n Otra Planilla" not in response.data
        assert b"DED_ASSOC_OFF - Deducci\xc3\xb3n Asociaci\xc3\xb3n Inactiva" not in response.data
        assert b"DED_CAT_OFF - Deducci\xc3\xb3n Cat\xc3\xa1logo Inactivo" not in response.data


def test_nueva_novedad_post_creates_novedad(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado, percepcion, planilla_novedad_conceptos
):
    """Test that POST /planilla/<id>/nomina/<nomina_id>/novedades/new creates a novedad."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "BONO",
            "tipo_concepto": "income",
            "percepcion_id": percepcion.id,
            "tipo_valor": "monto",
            "valor_cantidad": 500,
            "fecha_novedad": date.today().isoformat(),
        }

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify novedad was created
        from coati_payroll.model import NominaNovedad, db

        novedad = db_session.execute(
            db.select(NominaNovedad).filter_by(nomina_id=nomina.id, codigo_concepto="BONO")
        ).scalar_one_or_none()
        assert novedad is not None
        assert novedad.empleado_id == nomina_empleado.empleado_id


def test_nueva_novedad_rejects_negative_value(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado, percepcion, planilla_novedad_conceptos
):
    """Negative values cannot be persisted and silently ignored by payroll."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new",
            data={
                "empleado_id": nomina_empleado.empleado_id,
                "codigo_concepto": "BONO",
                "tipo_concepto": "income",
                "percepcion_id": percepcion.id,
                "tipo_valor": "monto",
                "valor_cantidad": -500,
                "fecha_novedad": date.today().isoformat(),
            },
        )

        assert response.status_code == 200
        from coati_payroll.model import NominaNovedad, db

        assert (
            db_session.execute(
                db.select(NominaNovedad).filter_by(nomina_id=nomina.id, codigo_concepto="BONO")
            ).scalar_one_or_none()
            is None
        )


def test_nueva_novedad_post_uses_concept_absence_defaults_when_flags_omitted(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """When absence flags are omitted, use Percepcion defaults."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        percepcion.es_inasistencia = True
        percepcion.descontar_pago_inasistencia = True
        db_session.commit()

        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "BONO_DEF",
            "tipo_concepto": "income",
            "percepcion_id": percepcion.id,
            "tipo_valor": "monto",
            "valor_cantidad": 500,
            "fecha_novedad": date.today().isoformat(),
        }

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        from coati_payroll.model import NominaNovedad, db

        novedad = db_session.execute(
            db.select(NominaNovedad).filter_by(nomina_id=nomina.id, codigo_concepto="BONO_DEF")
        ).scalar_one_or_none()
        assert novedad is not None
        assert novedad.es_inasistencia is True
        assert novedad.descontar_pago_inasistencia is True


def test_nueva_novedad_post_respects_explicit_flags_over_concept_defaults(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """If flags are explicitly present in payload, they override concept defaults."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        percepcion.es_inasistencia = True
        percepcion.descontar_pago_inasistencia = True
        db_session.commit()

        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "BONO_EXP",
            "tipo_concepto": "income",
            "percepcion_id": percepcion.id,
            "tipo_valor": "monto",
            "valor_cantidad": 500,
            "fecha_novedad": date.today().isoformat(),
            "es_inasistencia": "",
            "descontar_pago_inasistencia": "",
        }

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        from coati_payroll.model import NominaNovedad, db

        novedad = db_session.execute(
            db.select(NominaNovedad).filter_by(nomina_id=nomina.id, codigo_concepto="BONO_EXP")
        ).scalar_one_or_none()
        assert novedad is not None
        assert novedad.es_inasistencia is False
        assert novedad.descontar_pago_inasistencia is False


def test_nueva_novedad_post_uses_deduccion_absence_defaults_when_flags_omitted(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    deduccion,
    planilla_novedad_conceptos,
):
    """When absence flags are omitted, use Deduccion defaults."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        deduccion.es_inasistencia = True
        deduccion.descontar_pago_inasistencia = True
        db_session.commit()

        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "INSS_DEF",
            "tipo_concepto": "deduction",
            "deduccion_id": deduccion.id,
            "tipo_valor": "dias",
            "valor_cantidad": 1,
            "fecha_novedad": date.today().isoformat(),
        }

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/new",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        from coati_payroll.model import NominaNovedad, db

        novedad = db_session.execute(
            db.select(NominaNovedad).filter_by(nomina_id=nomina.id, codigo_concepto="INSS_DEF")
        ).scalar_one_or_none()
        assert novedad is not None
        assert novedad.es_inasistencia is True
        assert novedad.descontar_pago_inasistencia is True


def test_editar_novedad_get_displays_form(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """Test that GET /planilla/<id>/nomina/<nomina_id>/novedades/<novedad_id>/edit displays form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create a novedad first
        from coati_payroll.model import NominaNovedad
        from decimal import Decimal

        novedad = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="BONO",
            tipo_valor="monto",
            valor_cantidad=Decimal("500.00"),
            fecha_novedad=date.today(),
            percepcion_id=percepcion.id,
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()
        db_session.refresh(novedad)

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad.id}/edit")
        assert response.status_code == 200


def test_editar_novedad_post_updates_novedad(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """Test that POST /planilla/<id>/nomina/<nomina_id>/novedades/<novedad_id>/edit updates novedad."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create a novedad first
        from coati_payroll.model import NominaNovedad
        from decimal import Decimal

        novedad = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="BONO",
            tipo_valor="monto",
            valor_cantidad=Decimal("500.00"),
            fecha_novedad=date.today(),
            percepcion_id=percepcion.id,
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()
        db_session.refresh(novedad)

        novedad_id = novedad.id

        # Update the novedad
        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "BONO_ACT",
            "tipo_concepto": "income",
            "percepcion_id": percepcion.id,
            "tipo_valor": "monto",
            "valor_cantidad": 750,
            "fecha_novedad": date.today().isoformat(),
        }

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/edit",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify novedad was updated
        updated_novedad = db_session.get(NominaNovedad, novedad_id)
        assert updated_novedad.codigo_concepto == "BONO_ACT"
        assert updated_novedad.valor_cantidad == Decimal("750.00")


def test_eliminar_novedad_removes_novedad(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado, percepcion
):
    """Test that POST /planilla/<id>/nomina/<nomina_id>/novedades/<novedad_id>/delete removes novedad."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create a novedad
        from coati_payroll.model import NominaNovedad
        from decimal import Decimal

        novedad = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="BONO",
            tipo_valor="monto",
            valor_cantidad=Decimal("500.00"),
            fecha_novedad=date.today(),
            percepcion_id=percepcion.id,
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()
        db_session.refresh(novedad)

        novedad_id = novedad.id

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify novedad was deleted
        deleted = db_session.get(NominaNovedad, novedad_id)
        assert deleted is None


def test_reintentar_nomina_success(app, client, admin_user, db_session, planilla):
    """Test that POST /planilla/<id>/nomina/<nomina_id>/reintentar retries a failed nomina."""
    with app.app_context():
        from coati_payroll.model import Nomina
        from coati_payroll.enums import NominaEstado
        from unittest.mock import patch

        login_user(client, admin_user.usuario, "admin-password")

        # Create a failed nomina
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date.today(),
            periodo_fin=date.today() + timedelta(days=14),
            generado_por=admin_user.usuario,
            estado=NominaEstado.ERROR,
            errores_calculo={"critical_error": "Test error"},
        )
        db_session.add(nomina)
        db_session.commit()
        db_session.refresh(nomina)

        # Mock the retry function where it's used (in the routes module)
        with patch("coati_payroll.vistas.planilla.nomina_routes.retry_failed_nomina") as mock_retry:
            mock_retry.return_value = {
                "success": True,
                "message": "Nomina re-enviada para procesamiento.",
            }

            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/reintentar",
                follow_redirects=True,
            )

            assert response.status_code == 200
            mock_retry.assert_called_once_with(nomina.id, admin_user.usuario)


def test_reintentar_nomina_wrong_state(app, client, admin_user, db_session, planilla):
    """Test that retry fails if nomina is not in ERROR state."""
    with app.app_context():
        from coati_payroll.model import Nomina
        from coati_payroll.enums import NominaEstado

        login_user(client, admin_user.usuario, "admin-password")

        # Create a nomina in GENERADO state (not ERROR)
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date.today(),
            periodo_fin=date.today() + timedelta(days=14),
            generado_por=admin_user.usuario,
            estado=NominaEstado.GENERADO,
        )
        db_session.add(nomina)
        db_session.commit()
        db_session.refresh(nomina)

        original_estado = nomina.estado

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/reintentar",
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Verify nomina state did not change (should still be GENERADO)
        db_session.refresh(nomina)
        assert nomina.estado == original_estado
        assert nomina.estado == NominaEstado.GENERADO

        # Verify we were redirected to the nomina view page
        # The response should contain the nomina view (check for common elements)
        assert (
            response.request.path.endswith(f"/nomina/{nomina.id}")
            or f"/planilla/{planilla.id}/nomina/{nomina.id}" in response.request.url
        )


def test_reintentar_nomina_requires_authentication(app, client, db_session):
    """Test that retry nomina route requires authentication."""
    with app.app_context():
        response = client.post("/planilla/999/nomina/888/reintentar", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_edit_delete_floating_novelty_inside_range(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """Test editing and deleting a floating novelty (nomina_id is None) whose date is within the Nomina's range."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        from coati_payroll.model import NominaNovedad

        # Create a floating novelty within range (nomina_id=None)
        novedad = NominaNovedad(
            nomina_id=None,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="BONO",
            tipo_valor="monto",
            valor_cantidad=Decimal("150.00"),
            fecha_novedad=nomina.periodo_inicio,  # exactly inside
            percepcion_id=percepcion.id,
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()
        db_session.refresh(novedad)

        novedad_id = novedad.id

        # 1. Test GET edit displays form
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/edit")
        assert response.status_code == 200

        # 2. Test POST edit successfully updates
        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "BONO",
            "tipo_concepto": "income",
            "percepcion_id": percepcion.id,
            "tipo_valor": "monto",
            "valor_cantidad": 200,
            "fecha_novedad": (nomina.periodo_inicio).isoformat(),
        }
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/edit",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302

        db_session.refresh(novedad)
        assert novedad.valor_cantidad == Decimal("200.00")

        # 3. Test POST delete successfully removes
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302

        deleted = db_session.get(NominaNovedad, novedad_id)
        assert deleted is None


def test_edit_delete_floating_novelty_outside_range_is_rejected(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """Test blocking edits to a floating novelty outside the payroll date range."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        from coati_payroll.model import NominaNovedad

        # Create a floating novelty outside range (nomina_id=None)
        novedad = NominaNovedad(
            nomina_id=None,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="BONO",
            tipo_valor="monto",
            valor_cantidad=Decimal("150.00"),
            fecha_novedad=nomina.periodo_inicio - timedelta(days=5),  # outside
            percepcion_id=percepcion.id,
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()
        db_session.refresh(novedad)

        novedad_id = novedad.id

        # 1. Test GET edit blocks with redirect
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/edit")
        assert response.status_code == 302

        # 2. Test POST edit blocks with redirect
        data = {
            "empleado_id": nomina_empleado.empleado_id,
            "codigo_concepto": "BONO",
            "tipo_concepto": "income",
            "percepcion_id": percepcion.id,
            "tipo_valor": "monto",
            "valor_cantidad": 200,
            "fecha_novedad": (nomina.periodo_inicio - timedelta(days=5)).isoformat(),
        }
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/edit",
            data=data,
            follow_redirects=False,
        )
        assert response.status_code == 302
        db_session.refresh(novedad)
        assert novedad.valor_cantidad == Decimal("150.00")  # unchanged

        # 3. Test POST delete blocks with redirect
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/novedades/{novedad_id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify not deleted
        still_exists = db_session.get(NominaNovedad, novedad_id)
        assert still_exists is not None


def test_concurrent_overlapping_nomina_novelties_isolation(
    app,
    client,
    admin_user,
    db_session,
    planilla,
    nomina,
    nomina_empleado,
    percepcion,
    planilla_novedad_conceptos,
):
    """Test isolation of novelties between concurrent/overlapping nominas of the same period.
    - A novelty explicitly assigned to Nomina A must NOT show in Nomina B's novelty list.
    - A novelty explicitly assigned to Nomina A must NOT get marked as EJECUTADA when Nomina B is applied.
    - A novelty explicitly assigned to Nomina A must NOT be loaded/processed during Nomina B's calculation.
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        from coati_payroll.model import Nomina, NominaNovedad, Empleado, PlanillaEmpleado
        from coati_payroll.enums import NominaEstado, NovedadEstado
        from coati_payroll.vistas.planilla.services import NovedadService
        from coati_payroll.nomina_engine.processors.novelty_processor import NoveltyProcessor
        from coati_payroll.nomina_engine.repositories.novelty_repository import NoveltyRepository

        # Associate the employee with the planilla
        association = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=nomina_empleado.empleado_id,
            fecha_inicio=nomina.periodo_inicio,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(association)
        db_session.commit()

        # Create a second, overlapping/concurrent Nomina B for the same planilla
        nomina_b = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=nomina.periodo_inicio,
            periodo_fin=nomina.periodo_fin,
            generado_por=admin_user.usuario,
            estado=NominaEstado.APROBADO,  # Set as approved so we can call apply
        )
        db_session.add(nomina_b)
        db_session.commit()
        db_session.refresh(nomina_b)

        # Create a novelty explicitly assigned to Nomina A
        novedad_a = NominaNovedad(
            nomina_id=nomina.id,  # Assigned to Nomina A
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="BONO",
            tipo_valor="monto",
            valor_cantidad=Decimal("123.45"),
            fecha_novedad=nomina.periodo_inicio,  # Within the date range of BOTH nominas
            percepcion_id=percepcion.id,
            estado=NovedadEstado.PENDIENTE,
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad_a)
        db_session.commit()
        db_session.refresh(novedad_a)

        # 1. Verify NovedadService.listar_novedades for Nomina B does NOT include novedad_a
        novedades_b = NovedadService.listar_novedades(planilla, nomina_b)
        assert novedad_a not in novedades_b

        # 2. Verify NovedadService.listar_novedades for Nomina A DOES include novedad_a
        novedades_a = NovedadService.listar_novedades(planilla, nomina)
        assert novedad_a in novedades_a

        # 3. Verify NoveltyProcessor does NOT load novelty_a when calculating Nomina B
        repo = NoveltyRepository(db_session)
        processor = NoveltyProcessor(repo)

        empleado_obj = db_session.get(Empleado, nomina_empleado.empleado_id)

        # Load novelties for Nomina B (should be empty/excluding novedad_a)
        novedades_load_b = processor.load_novelties(
            empleado_obj, nomina_b.periodo_inicio, nomina_b.periodo_fin, nomina_id=nomina_b.id
        )
        assert "BONO" not in novedades_load_b

        # Load novelties for Nomina A (should include novedad_a)
        novedades_load_a = processor.load_novelties(
            empleado_obj, nomina.periodo_inicio, nomina.periodo_fin, nomina_id=nomina.id
        )
        assert novedades_load_a.get("BONO") == Decimal("123.45")

        # 4. Verify applying Nomina B (making it executed/applied) does NOT mark novedad_a as EJECUTADA
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina_b.id}/aplicar",
            follow_redirects=False,
        )
        assert response.status_code == 302

        db_session.refresh(nomina_b)
        assert nomina_b.estado == NominaEstado.APLICADO

        db_session.refresh(novedad_a)
        assert novedad_a.estado == NovedadEstado.PENDIENTE  # Stays pending!


def test_planilla_approval_routes_change_state_and_create_audit_log(client, db_session, admin_user, planilla):
    """Planilla approval is exposed through the UI and remains auditable."""
    from coati_payroll.model import PlanillaAuditLog, db

    login_user(client, "admin-test", "admin-password")

    response = client.post(f"/planilla/{planilla.id}/approve", follow_redirects=False)
    assert response.status_code == 302
    db_session.refresh(planilla)
    assert planilla.estado_aprobacion == "approved"
    assert planilla.aprobado_por == admin_user.usuario
    assert (
        db_session.execute(
            db.select(PlanillaAuditLog).filter_by(planilla_id=planilla.id, accion="approved")
        ).scalar_one_or_none()
        is not None
    )

    response = client.post(
        f"/planilla/{planilla.id}/reject", data={"razon": "Ajuste pendiente"}, follow_redirects=False
    )
    assert response.status_code == 302
    db_session.refresh(planilla)
    assert planilla.estado_aprobacion == "draft"
    assert planilla.aprobado_por is None
    assert (
        db_session.execute(
            db.select(PlanillaAuditLog).filter_by(planilla_id=planilla.id, accion="rejected")
        ).scalar_one_or_none()
        is not None
    )
