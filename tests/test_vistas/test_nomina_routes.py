# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for nomina routes (coati_payroll/vistas/planilla/nomina_routes.py)."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from coati_payroll.enums import NominaEstado
from coati_payroll.model import (
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    NominaNovedad,
    Prestacion,
    PrestacionAcumulada,
    ComprobanteContable,
)
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
            dias=30,
            periodos_por_anio=12,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
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
def nomina(app, db_session, planilla, admin_user):
    """Create a Nomina for testing."""
    with app.app_context():
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 1, 1),
            periodo_fin=date(2025, 1, 31),
            generado_por=admin_user.usuario,
            estado="generated",
        )
        db_session.add(nomina)
        db_session.commit()
        db_session.refresh(nomina)
        return nomina


@pytest.fixture
def nomina_empleado(app, db_session, nomina, empleado):
    """Create a NominaEmpleado for testing."""
    with app.app_context():
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
def nomina_detalle(app, db_session, nomina_empleado):
    """Create a NominaDetalle for testing."""
    with app.app_context():
        detalle = NominaDetalle(
            nomina_empleado_id=nomina_empleado.id,
            tipo="income",
            codigo="SALARIO",
            descripcion="Salario Base",
            monto=Decimal("1000.00"),
            orden=1,
        )
        db_session.add(detalle)
        db_session.commit()
        db_session.refresh(detalle)
        return detalle


# ============================================================================
# TESTS FOR ejecutar_nomina
# ============================================================================


def test_ejecutar_nomina_get_requires_write_access(app, client, db_session, planilla):
    """Test that ejecutar_nomina GET requires write access."""
    with app.app_context():
        response = client.get(f"/planilla/{planilla.id}/ejecutar", follow_redirects=False)
        assert response.status_code == 302


def test_ejecutar_nomina_get_accessible_to_authenticated_users(app, client, admin_user, db_session, planilla):
    """Test that authenticated users can access ejecutar_nomina form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/ejecutar")
        assert response.status_code == 200


def test_ejecutar_nomina_get_handles_multiple_nominas_with_cancelled(app, client, admin_user, db_session, planilla):
    """GET /ejecutar should not fail when planilla has multiple payroll runs, including cancelled ones."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        nomina_enero = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 1, 1),
            periodo_fin=date(2025, 1, 31),
            generado_por=admin_user.usuario,
            estado=NominaEstado.GENERADO,
        )
        nomina_febrero_anulada = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 28),
            generado_por=admin_user.usuario,
            estado=NominaEstado.ANULADO,
        )
        db_session.add_all([nomina_enero, nomina_febrero_anulada])
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/ejecutar")
        assert response.status_code == 200


def test_ejecutar_nomina_post_requires_write_access(app, client, db_session, planilla):
    """Test that ejecutar_nomina POST requires write access."""
    with app.app_context():
        response = client.post(
            f"/planilla/{planilla.id}/ejecutar",
            data={
                "periodo_inicio": "2025-01-01",
                "periodo_fin": "2025-01-31",
                "fecha_calculo": "2025-01-31",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


def test_ejecutar_nomina_post_missing_period(app, client, admin_user, db_session, planilla):
    """Test that ejecutar_nomina POST validates required period fields."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/planilla/{planilla.id}/ejecutar",
            data={},
            follow_redirects=False,
        )
        assert response.status_code == 302  # Redirects back with error


def test_ejecutar_nomina_post_invalid_date_format(app, client, admin_user, db_session, planilla):
    """Test that ejecutar_nomina POST validates date format."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/planilla/{planilla.id}/ejecutar",
            data={
                "periodo_inicio": "invalid-date",
                "periodo_fin": "2025-01-31",
                "fecha_calculo": "2025-01-31",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302  # Redirects back with error


@patch("coati_payroll.vistas.planilla.nomina_routes.NominaService.ejecutar_nomina")
def test_ejecutar_nomina_post_success(mock_ejecutar, app, client, admin_user, db_session, planilla):
    """Test successful nomina execution."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock successful execution
        mock_nomina = MagicMock()
        mock_nomina.id = "test-nomina-id"
        mock_nomina.procesamiento_en_background = False
        mock_ejecutar.return_value = (mock_nomina, [], [])

        response = client.post(
            f"/planilla/{planilla.id}/ejecutar",
            data={
                "periodo_inicio": "2025-01-01",
                "periodo_fin": "2025-01-31",
                "fecha_calculo": "2025-01-31",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/planilla/{planilla.id}/nomina/{mock_nomina.id}" in response.location


@patch("coati_payroll.vistas.planilla.nomina_routes.NominaService.ejecutar_nomina")
def test_ejecutar_nomina_post_background_processing(mock_ejecutar, app, client, admin_user, db_session, planilla):
    """Test nomina execution with background processing."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock background processing
        mock_nomina = MagicMock()
        mock_nomina.id = "test-nomina-id"
        mock_nomina.procesamiento_en_background = True
        mock_nomina.total_empleados = 10
        mock_ejecutar.return_value = (mock_nomina, [], [])

        response = client.post(
            f"/planilla/{planilla.id}/ejecutar",
            data={
                "periodo_inicio": "2025-01-01",
                "periodo_fin": "2025-01-31",
                "fecha_calculo": "2025-01-31",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


@patch("coati_payroll.vistas.planilla.nomina_routes.NominaService.ejecutar_nomina")
def test_ejecutar_nomina_post_displays_warning_messages(
    mock_ejecutar, app, client, admin_user, db_session, planilla, nomina
):
    """Warnings returned by service must be shown to the user in response UI."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        warning = (
            "WARNING: Este calculo de planilla tiene menos dias de lo esperado para una periodicidad mensual."
        )
        nomina.procesamiento_en_background = False
        mock_ejecutar.return_value = (nomina, [], [warning])

        response = client.post(
            f"/planilla/{planilla.id}/ejecutar",
            data={
                "periodo_inicio": "2025-01-01",
                "periodo_fin": "2025-01-01",
                "fecha_calculo": "2025-01-01",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert warning in response.get_data(as_text=True)


# ============================================================================
# TESTS FOR listar_nominas
# ============================================================================


def test_listar_nominas_requires_read_access(app, client, db_session, planilla):
    """Test that listar_nominas requires read access."""
    with app.app_context():
        response = client.get(f"/planilla/{planilla.id}/nominas", follow_redirects=False)
        assert response.status_code == 302


def test_listar_nominas_accessible_to_authenticated_users(app, client, admin_user, db_session, planilla, nomina):
    """Test that authenticated users can list nominas."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nominas")
        assert response.status_code == 200


def test_listar_nominas_shows_nominas(app, client, admin_user, db_session, planilla, nomina):
    """Test that listar_nominas displays nominas."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nominas")
        assert response.status_code == 200
        # Check that nomina is in the response
        assert nomina.id.encode() in response.data or str(nomina.id) in response.get_data(as_text=True)


# ============================================================================
# TESTS FOR ver_nomina
# ============================================================================


def test_ver_nomina_requires_read_access(app, client, db_session, planilla, nomina):
    """Test that ver_nomina requires read access."""
    with app.app_context():
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}", follow_redirects=False)
        assert response.status_code == 302


def test_ver_nomina_accessible_to_authenticated_users(app, client, admin_user, db_session, planilla, nomina):
    """Test that authenticated users can view nomina."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}")
        assert response.status_code == 200


def test_ver_nomina_wrong_planilla_redirects(app, client, admin_user, db_session, planilla, nomina):
    """Test that ver_nomina redirects if nomina doesn't belong to planilla."""
    with app.app_context():
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda

        from coati_payroll.model import db

        # Create another planilla
        tipo_planilla = db_session.execute(db.select(TipoPlanilla).filter_by(codigo="MENSUAL")).scalar_one()
        moneda = db_session.execute(db.select(Moneda).filter_by(codigo="USD")).scalar_one()

        other_planilla = Planilla(
            nombre="Other Planilla",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(other_planilla)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{other_planilla.id}/nomina/{nomina.id}", follow_redirects=False)
        assert response.status_code == 302


def test_ver_nomina_with_errors(app, client, admin_user, db_session, planilla, nomina):
    """Test that ver_nomina displays errors from log."""
    with app.app_context():
        # Add error log entry
        nomina.log_procesamiento = [{"status": "error", "message": "Test error"}]
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}")
        assert response.status_code == 200


def test_ver_nomina_with_warnings(app, client, admin_user, db_session, planilla, nomina):
    """Test that ver_nomina displays warnings from log."""
    with app.app_context():
        # Add warning log entry
        nomina.log_procesamiento = [{"status": "warning", "message": "Test warning"}]
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}")
        assert response.status_code == 200


def test_ver_nomina_muestra_salario_base_ajustado_por_inasistencia(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Detalle por empleado should display base salary net of absence discount."""
    with app.app_context():
        nomina_empleado.sueldo_base_historico = Decimal("1000.00")
        nomina_empleado.inasistencia_descuento = Decimal("333.33")
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}")
        assert response.status_code == 200
        assert b"Detalle por Empleado" in response.data
        assert b"666.67" in response.data


# ============================================================================
# TESTS FOR ver_nomina_empleado
# ============================================================================


def test_ver_nomina_empleado_requires_read_access(app, client, db_session, planilla, nomina, nomina_empleado):
    """Test that ver_nomina_empleado requires read access."""
    with app.app_context():
        response = client.get(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}",
            follow_redirects=False,
        )
        assert response.status_code == 302


def test_ver_nomina_empleado_accessible_to_authenticated_users(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Test that authenticated users can view nomina empleado."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")
        assert response.status_code == 200


def test_ver_nomina_empleado_wrong_nomina_redirects(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Test that ver_nomina_empleado redirects if empleado doesn't belong to nomina."""
    with app.app_context():
        from coati_payroll.model import Nomina

        # Create another nomina
        other_nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 28),
            estado="generated",
        )
        db_session.add(other_nomina)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(
            f"/planilla/{planilla.id}/nomina/{other_nomina.id}/empleado/{nomina_empleado.id}",
            follow_redirects=False,
        )
        assert response.status_code == 302


def test_ver_nomina_empleado_shows_detalles(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado, nomina_detalle
):
    """Test that ver_nomina_empleado displays detalles."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")
        assert response.status_code == 200


def test_ver_nomina_empleado_muestra_salario_base_ajustado_por_inasistencia(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Salario Base in summary should display base salary net of absence discount."""
    with app.app_context():
        nomina_empleado.salario_bruto = Decimal("1000.00")
        nomina_empleado.total_ingresos = Decimal("333.33")
        nomina_empleado.inasistencia_descuento = Decimal("333.33")
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")
        assert response.status_code == 200
        assert b"Salario Base:" in response.data
        assert b"666.67" in response.data


def test_ver_nomina_empleado_muestra_seccion_novedades_aplicadas(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Employee payroll detail should always show applied novelties section."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")
        assert response.status_code == 200
        assert b"Novedades Aplicadas al Calculo" in response.data
        assert b"Conciliacion de Salario Base" in response.data


def test_ver_nomina_empleado_muestra_detalle_dinamico_de_novedades(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Applied novelties detail must render novelty data dynamically."""
    with app.app_context():
        novedad = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="AJUSTE_VAR",
            tipo_valor="horas",
            valor_cantidad=Decimal("2.50"),
            fecha_novedad=date(2025, 1, 10),
            estado="pending",
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")
        assert response.status_code == 200
        assert b"AJUSTE_VAR" in response.data
        assert b"2.50" in response.data
        assert b"horas" in response.data
        assert b"Detalle Monto" in response.data
        assert b"Total novedades aplicadas" in response.data


def test_ver_nomina_empleado_calcula_monto_referencia_para_deduccion_por_horas(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """If there is no direct amount line, deduction-by-hours should show a dynamic estimated amount."""
    with app.app_context():
        nomina.configuracion_snapshot = {
            "dias_mes_nomina": 10,
            "horas_jornada_diaria": 5,
        }
        nomina_empleado.sueldo_base_historico = Decimal("1000.00")
        novedad = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="AJUSTE_HORAS",
            tipo_valor="horas",
            valor_cantidad=Decimal("2.00"),
            fecha_novedad=date(2025, 1, 12),
            es_inasistencia=True,
            descontar_pago_inasistencia=True,
            estado="pending",
            creado_por=admin_user.usuario,
        )
        db_session.add(novedad)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")
        assert response.status_code == 200
        assert b"AJUSTE_HORAS" in response.data
        assert b"40.00" in response.data
        assert b"Monto estimado por ajuste de salario base segun configuracion de la nomina" in response.data


def test_ver_nomina_empleado_concilia_residuo_con_descuento_total_persistido(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """When snapshot is empty, residual cents should be reconciled against persisted descuento total."""
    with app.app_context():
        nomina.configuracion_snapshot = {}
        nomina_empleado.sueldo_base_historico = Decimal("10000.00")
        nomina_empleado.inasistencia_descuento = Decimal("416.67")

        novedad_dia = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="VAC_DESC",
            tipo_valor="dias",
            valor_cantidad=Decimal("1.00"),
            es_inasistencia=True,
            descontar_pago_inasistencia=True,
            estado="pending",
            creado_por=admin_user.usuario,
        )
        novedad_hora = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=nomina_empleado.empleado_id,
            codigo_concepto="LLEGADA_TARDE",
            tipo_valor="horas",
            valor_cantidad=Decimal("2.00"),
            es_inasistencia=True,
            descontar_pago_inasistencia=True,
            estado="pending",
            creado_por=admin_user.usuario,
        )
        db_session.add_all([novedad_dia, novedad_hora])
        db_session.flush()

        detalle_dia = NominaDetalle(
            nomina_empleado_id=nomina_empleado.id,
            tipo="income",
            codigo="VAC_DESC",
            descripcion="Reclasificacion vacaciones",
            monto=Decimal("333.33"),
            orden=5,
        )
        db_session.add(detalle_dia)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/empleado/{nomina_empleado.id}")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "VAC_DESC" in html
        assert "LLEGADA_TARDE" in html
        assert "333.33" in html
        assert "83.34" in html
        assert "Monto estimado por ajuste de salario base segun configuracion de la nomina" in html


# ============================================================================
# TESTS FOR progreso_nomina
# ============================================================================


def test_progreso_nomina_requires_read_access(app, client, db_session, planilla, nomina):
    """Test that progreso_nomina requires read access."""
    with app.app_context():
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/progreso", follow_redirects=False)
        assert response.status_code == 302


def test_progreso_nomina_returns_json(app, client, admin_user, db_session, planilla, nomina):
    """Test that progreso_nomina returns JSON with progress data."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Set progress data
        from coati_payroll.model import db

        nomina = db.session.merge(nomina)
        nomina.total_empleados = 10
        nomina.empleados_procesados = 5
        nomina.empleados_con_error = 1
        nomina.procesamiento_en_background = True
        nomina.estado = "calculando"
        db.session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/progreso")
        assert response.status_code == 200
        assert response.is_json

        data = response.get_json()
        assert data["estado"] == "calculando"
        assert data["total_empleados"] == 10
        assert data["empleados_procesados"] == 5
        assert data["empleados_con_error"] == 1
        assert data["progreso_porcentaje"] == 50
        assert data["procesamiento_en_background"] is True


def test_progreso_nomina_wrong_planilla_returns_404(app, client, admin_user, db_session, planilla, nomina):
    """Test that progreso_nomina returns 404 if nomina doesn't belong to planilla."""
    with app.app_context():
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda

        from coati_payroll.model import db

        # Create another planilla
        tipo_planilla = db_session.execute(db.select(TipoPlanilla).filter_by(codigo="MENSUAL")).scalar_one()
        moneda = db_session.execute(db.select(Moneda).filter_by(codigo="USD")).scalar_one()

        other_planilla = Planilla(
            nombre="Other Planilla",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(other_planilla)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{other_planilla.id}/nomina/{nomina.id}/progreso")
        assert response.status_code == 404


# ============================================================================
# TESTS FOR aprobar_nomina
# ============================================================================


def test_aprobar_nomina_requires_write_access(app, client, db_session, planilla, nomina):
    """Test that aprobar_nomina requires write access."""
    with app.app_context():
        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aprobar", follow_redirects=False)
        assert response.status_code == 302


def test_aprobar_nomina_success(app, client, admin_user, db_session, planilla, nomina):
    """Test successful nomina approval."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        # Ensure nomina is in correct state
        nomina = db.session.merge(nomina)
        nomina.estado = "generated"
        db.session.commit()
        db.session.refresh(nomina)
        assert nomina.estado == "generated"

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aprobar", follow_redirects=False)
        assert response.status_code == 302

        # Verify nomina was approved
        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == "approved"


def test_aprobar_nomina_wrong_state(app, client, admin_user, db_session, planilla, nomina):
    """Test that aprobar_nomina only works for 'generated' state."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Change state to something other than 'generated'
        nomina.estado = "approved"
        db_session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aprobar", follow_redirects=False)
        assert response.status_code == 302  # Redirects with error


def test_aprobar_nomina_error_state_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that aprobar_nomina fails if nomina is in error state."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        nomina = db.session.merge(nomina)
        nomina.estado = NominaEstado.ERROR
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aprobar", follow_redirects=False)
        assert response.status_code == 302

        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == NominaEstado.ERROR


def test_aprobar_nomina_with_errors_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that aprobar_nomina fails if nomina has errors."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        # Add error log entry
        nomina = db.session.merge(nomina)
        nomina.estado = "generated"
        nomina.log_procesamiento = [{"status": "error", "message": "Test error"}]
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aprobar", follow_redirects=False)
        assert response.status_code == 302  # Redirects with error

        # Verify nomina was NOT approved
        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == "generated"


def test_aprobar_nomina_generated_with_errors_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that aprobar_nomina fails if nomina is generated with errors."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        nomina = db.session.merge(nomina)
        nomina.estado = NominaEstado.GENERADO_CON_ERRORES
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aprobar", follow_redirects=False)
        assert response.status_code == 302

        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == NominaEstado.GENERADO_CON_ERRORES


# ============================================================================
# TESTS FOR aplicar_nomina
# ============================================================================


def test_aplicar_nomina_requires_write_access(app, client, db_session, planilla, nomina):
    """Test that aplicar_nomina requires write access."""
    with app.app_context():
        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302


def test_aplicar_nomina_success(app, client, admin_user, db_session, planilla, nomina):
    """Test successful nomina application regenerates accounting voucher in DB."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        # First approve the nomina
        nomina = db.session.merge(nomina)
        nomina.estado = "approved"
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302

        # Verify nomina was applied
        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == "applied"

        comprobante = db.session.execute(
            db.select(ComprobanteContable).filter_by(nomina_id=nomina.id)
        ).scalar_one_or_none()
        assert comprobante is not None


def test_aplicar_nomina_rolls_back_when_voucher_regeneration_fails(
    app, client, admin_user, db_session, planilla, nomina
):
    """Applying payroll must rollback state changes if voucher regeneration fails."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        nomina = db.session.merge(nomina)
        nomina.estado = NominaEstado.APROBADO
        db.session.commit()
        nomina_id = nomina.id

        with (
            patch("coati_payroll.vistas.planilla.nomina_routes.db.session.rollback") as mock_rollback,
            patch("coati_payroll.vistas.planilla.nomina_routes.db.session.commit") as mock_commit,
            patch(
                "coati_payroll.vistas.planilla.nomina_routes._regenerar_comprobante_contable_nomina",
                side_effect=Exception("voucher regen failed"),
            ),
        ):
            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina_id}/aplicar",
                follow_redirects=False,
            )
            assert response.status_code == 302
            mock_rollback.assert_called_once()
            mock_commit.assert_not_called()


def test_aplicar_nomina_wrong_state(app, client, admin_user, db_session, planilla, nomina):
    """Test that aplicar_nomina only works for 'approved' state."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        # Ensure state is 'generated'
        nomina = db.session.merge(nomina)
        nomina.estado = "generated"
        db.session.commit()
        db.session.refresh(nomina)
        assert nomina.estado == "generated"

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302  # Redirects with error

        # Verify nomina was NOT applied
        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == "generated"


def test_aplicar_nomina_error_state_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that aplicar_nomina fails if nomina is in error state."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        nomina = db.session.merge(nomina)
        nomina.estado = NominaEstado.ERROR
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302

        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == NominaEstado.ERROR


def test_aplicar_nomina_generated_with_errors_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that aplicar_nomina fails if nomina is generated with errors."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        nomina = db.session.merge(nomina)
        nomina.estado = NominaEstado.GENERADO_CON_ERRORES
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302

        updated_nomina = db.session.get(Nomina, nomina.id)
        assert updated_nomina.estado == NominaEstado.GENERADO_CON_ERRORES


def test_aplicar_nomina_creates_prestacion_ledger_transactions(
    app, client, admin_user, db_session, planilla, nomina, nomina_empleado
):
    """Applying a payroll must persist prestaciones accumulation transactions."""
    with app.app_context():
        from coati_payroll.model import db, PlanillaEmpleado

        login_user(client, admin_user.usuario, "admin-password")

        nomina = db.session.merge(nomina)
        nomina_empleado = db.session.merge(nomina_empleado)
        nomina.estado = NominaEstado.APROBADO
        db.session.flush()

        prestacion = Prestacion(
            codigo="PREST_TEST_APPLY",
            nombre="Prestacion Test Apply",
            tipo="employer",
            formula_tipo="fixed",
            monto_default=Decimal("0.00"),
            tipo_acumulacion="annual",
            activo=True,
        )
        db.session.add(prestacion)
        db.session.flush()

        detalle_prestacion = NominaDetalle(
            nomina_empleado_id=nomina_empleado.id,
            tipo="benefit",
            codigo=prestacion.codigo,
            descripcion=prestacion.nombre,
            monto=Decimal("125.50"),
            orden=99,
            prestacion_id=prestacion.id,
        )
        db.session.add(detalle_prestacion)
        db.session.add(
            PlanillaEmpleado(
                planilla_id=planilla.id,
                empleado_id=nomina_empleado.empleado_id,
                activo=True,
            )
        )
        db.session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/aplicar", follow_redirects=False)
        assert response.status_code == 302

        transacciones = (
            db.session.query(PrestacionAcumulada)
            .filter(
                PrestacionAcumulada.nomina_id == nomina.id,
                PrestacionAcumulada.empleado_id == nomina_empleado.empleado_id,
                PrestacionAcumulada.prestacion_id == prestacion.id,
            )
            .all()
        )
        assert len(transacciones) == 1
        assert transacciones[0].tipo_transaccion == "adicion"
        assert transacciones[0].monto_transaccion == Decimal("125.50")


def test_aplicar_prestaciones_nomina_is_idempotent(app, db_session, planilla, nomina, nomina_empleado, admin_user):
    """Prestaciones ledger generation must be idempotent for the same payroll."""
    with app.app_context():
        from coati_payroll.model import db
        from coati_payroll.vistas.planilla.nomina_routes import _aplicar_prestaciones_nomina

        nomina = db.session.merge(nomina)
        planilla = db.session.merge(planilla)
        nomina_empleado = db.session.merge(nomina_empleado)
        nomina.estado = NominaEstado.APROBADO
        db.session.flush()

        prestacion = Prestacion(
            codigo="PREST_TEST_IDEMP",
            nombre="Prestacion Test Idempotent",
            tipo="employer",
            formula_tipo="fixed",
            monto_default=Decimal("0.00"),
            tipo_acumulacion="annual",
            activo=True,
        )
        db.session.add(prestacion)
        db.session.flush()

        detalle_prestacion = NominaDetalle(
            nomina_empleado_id=nomina_empleado.id,
            tipo="benefit",
            codigo=prestacion.codigo,
            descripcion=prestacion.nombre,
            monto=Decimal("200.00"),
            orden=100,
            prestacion_id=prestacion.id,
        )
        db.session.add(detalle_prestacion)
        db.session.commit()

        _aplicar_prestaciones_nomina(nomina, planilla, admin_user.usuario)
        db.session.flush()
        _aplicar_prestaciones_nomina(nomina, planilla, admin_user.usuario)
        db.session.commit()

        transacciones = (
            db.session.query(PrestacionAcumulada)
            .filter(
                PrestacionAcumulada.nomina_id == nomina.id,
                PrestacionAcumulada.empleado_id == nomina_empleado.empleado_id,
                PrestacionAcumulada.prestacion_id == prestacion.id,
            )
            .all()
        )
        assert len(transacciones) == 1


# ============================================================================
# TESTS FOR anular_nomina
# ============================================================================


def test_anular_nomina_requires_write_access(app, client, db_session, planilla, nomina):
    """Test that anular_nomina requires write access."""
    with app.app_context():
        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/anular", follow_redirects=False)
        assert response.status_code == 302


def test_anular_nomina_success_for_generated_state(app, client, admin_user, db_session, planilla, nomina):
    """Test successful nomina cancellation for generated state."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        nomina.estado = NominaEstado.GENERADO
        db_session.commit()

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/anular",
            data={"razon_anulacion": "Periodo inválido"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        db_session.refresh(nomina)
        assert nomina.estado == NominaEstado.ANULADO
        assert nomina.razon_anulacion == "Periodo inválido"
        assert nomina.anulado_por == admin_user.usuario


def test_anular_nomina_aplicado_state_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that anular_nomina does not allow applied/payroll-paid nominas."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        nomina.estado = NominaEstado.APLICADO
        db_session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/anular", follow_redirects=False)
        assert response.status_code == 302

        db_session.refresh(nomina)
        assert nomina.estado == NominaEstado.APLICADO


def test_ver_nomina_shows_anular_button_for_non_applied_states(app, client, admin_user, db_session, planilla, nomina):
    """Detail view should show Anular action when nomina is not applied/paid."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        nomina.estado = NominaEstado.GENERADO
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Anular" in html
        assert f"/planilla/{planilla.id}/nomina/{nomina.id}/anular" in html


def test_ver_nomina_hides_anular_button_for_applied_state(app, client, admin_user, db_session, planilla, nomina):
    """Detail view should not show Anular action for applied nominas."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        nomina.estado = NominaEstado.APLICADO
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert f"/planilla/{planilla.id}/nomina/{nomina.id}/anular" not in html


# ============================================================================
# TESTS FOR reintentar_nomina
# ============================================================================


def test_reintentar_nomina_requires_write_access(app, client, db_session, planilla, nomina):
    """Test that reintentar_nomina requires write access."""
    with app.app_context():
        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/reintentar", follow_redirects=False)
        assert response.status_code == 302


@patch("coati_payroll.vistas.planilla.nomina_routes.retry_failed_nomina")
def test_reintentar_nomina_success(mock_retry, app, client, admin_user, db_session, planilla, nomina):
    """Test successful nomina retry."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to error state
        nomina.estado = NominaEstado.ERROR
        db_session.commit()

        # Mock successful retry
        mock_retry.return_value = {"success": True}

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/reintentar", follow_redirects=False)
        assert response.status_code == 302


@patch("coati_payroll.vistas.planilla.nomina_routes.retry_failed_nomina")
def test_reintentar_nomina_failure(mock_retry, app, client, admin_user, db_session, planilla, nomina):
    """Test failed nomina retry."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to error state
        nomina.estado = NominaEstado.ERROR
        db_session.commit()

        # Mock failed retry
        mock_retry.return_value = {"success": False, "error": "Test error"}

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/reintentar", follow_redirects=False)
        assert response.status_code == 302


def test_reintentar_nomina_wrong_state(app, client, admin_user, db_session, planilla, nomina):
    """Test that reintentar_nomina only works for 'error' state."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Keep state as 'generated'
        assert nomina.estado == "generated"

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/reintentar", follow_redirects=False)
        assert response.status_code == 302  # Redirects with error


# ============================================================================
# TESTS FOR recalcular_nomina
# ============================================================================


def test_recalcular_nomina_requires_write_access(app, client, db_session, planilla, nomina):
    """Test that recalcular_nomina requires write access."""
    with app.app_context():
        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/recalcular", follow_redirects=False)
        assert response.status_code == 302


@patch("coati_payroll.vistas.planilla.nomina_routes.NominaService.recalcular_nomina")
def test_recalcular_nomina_success(mock_recalcular, app, client, admin_user, db_session, planilla, nomina):
    """Test successful nomina recalculation."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock successful recalculation
        mock_new_nomina = MagicMock()
        mock_new_nomina.id = "new-nomina-id"
        mock_recalcular.return_value = (mock_new_nomina, [], [])

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/recalcular", follow_redirects=False)
        assert response.status_code == 302
        assert f"/planilla/{planilla.id}/nomina/{mock_new_nomina.id}" in response.location


def test_recalcular_nomina_aplicado_state_fails(app, client, admin_user, db_session, planilla, nomina):
    """Test that recalcular_nomina fails for 'applied' state."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to applied state
        nomina.estado = "applied"
        db_session.commit()

        response = client.post(f"/planilla/{planilla.id}/nomina/{nomina.id}/recalcular", follow_redirects=False)
        assert response.status_code == 302  # Redirects with error


# ============================================================================
# TESTS FOR ver_log_nomina
# ============================================================================


def test_ver_log_nomina_requires_read_access(app, client, db_session, planilla, nomina):
    """Test that ver_log_nomina requires read access."""
    with app.app_context():
        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/log", follow_redirects=False)
        assert response.status_code == 302


def test_ver_log_nomina_accessible_to_authenticated_users(app, client, admin_user, db_session, planilla, nomina):
    """Test that authenticated users can view nomina log."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Add log entries
        nomina.log_procesamiento = [
            {"status": "info", "message": "Test info"},
            {"status": "error", "message": "Test error"},
        ]
        db_session.commit()

        response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/log")
        assert response.status_code == 200


def test_ver_log_nomina_wrong_planilla_redirects(app, client, admin_user, db_session, planilla, nomina):
    """Test that ver_log_nomina redirects if nomina doesn't belong to planilla."""
    with app.app_context():
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda

        from coati_payroll.model import db

        # Create another planilla
        tipo_planilla = db_session.execute(db.select(TipoPlanilla).filter_by(codigo="MENSUAL")).scalar_one()
        moneda = db_session.execute(db.select(Moneda).filter_by(codigo="USD")).scalar_one()

        other_planilla = Planilla(
            nombre="Other Planilla",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(other_planilla)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/planilla/{other_planilla.id}/nomina/{nomina.id}/log", follow_redirects=False)
        assert response.status_code == 302


# ============================================================================
# TESTS FOR regenerar_comprobante_contable
# ============================================================================


def test_regenerar_comprobante_contable_requires_write_access(app, client, db_session, planilla, nomina):
    """Test that regenerar_comprobante_contable requires write access."""
    with app.app_context():
        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
        )
        assert response.status_code == 302


def test_regenerar_comprobante_contable_wrong_planilla_redirects(app, client, admin_user, db_session, planilla, nomina):
    """Test that regenerar_comprobante_contable redirects if nomina doesn't belong to planilla."""
    with app.app_context():
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda
        from coati_payroll.model import db

        # Create another planilla
        tipo_planilla = db_session.execute(db.select(TipoPlanilla).filter_by(codigo="MENSUAL")).scalar_one()
        moneda = db_session.execute(db.select(Moneda).filter_by(codigo="USD")).scalar_one()

        other_planilla = Planilla(
            nombre="Other Planilla",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(other_planilla)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/planilla/{other_planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
        )
        assert response.status_code == 302


def test_regenerar_comprobante_contable_invalid_state(app, client, admin_user, db_session, planilla, nomina):
    """Test that regenerar_comprobante_contable only works for APLICADO or PAGADO state."""
    with app.app_context():
        from coati_payroll.model import db

        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to 'generated' state (invalid for regenerar_comprobante)
        nomina = db.session.merge(nomina)
        nomina.estado = "generated"
        db_session.commit()

        response = client.post(
            f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
        )
        assert response.status_code == 302
        # Should redirect to ver_nomina with error message


def test_regenerar_comprobante_contable_aplicado_state_success(app, client, admin_user, db_session, planilla, nomina):
    """Test successful comprobante regeneration for APLICADO state."""
    with app.app_context():
        from coati_payroll.model import db
        from unittest.mock import MagicMock, patch

        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to 'applied' state
        nomina = db.session.merge(nomina)
        nomina.estado = "applied"
        nomina.periodo_fin = date(2025, 1, 31)
        db_session.commit()

        # Mock the AccountingVoucherService
        mock_comprobante = MagicMock()
        mock_comprobante.advertencias = []

        with patch(
            "coati_payroll.nomina_engine.services.accounting_voucher_service.AccountingVoucherService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_accounting_voucher.return_value = mock_comprobante
            mock_service_class.return_value = mock_service

            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
            )
            assert response.status_code == 302
            assert f"/planilla/{planilla.id}/nomina/{nomina.id}/log" in response.location


def test_regenerar_comprobante_contable_pagado_state_success(app, client, admin_user, db_session, planilla, nomina):
    """Test successful comprobante regeneration for PAGADO state."""
    with app.app_context():
        from coati_payroll.model import db
        from unittest.mock import MagicMock, patch

        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to 'paid' state
        nomina = db.session.merge(nomina)
        nomina.estado = "paid"
        nomina.periodo_fin = date(2025, 1, 31)
        db_session.commit()

        # Mock the AccountingVoucherService
        mock_comprobante = MagicMock()
        mock_comprobante.advertencias = []

        with patch(
            "coati_payroll.nomina_engine.services.accounting_voucher_service.AccountingVoucherService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_accounting_voucher.return_value = mock_comprobante
            mock_service_class.return_value = mock_service

            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
            )
            assert response.status_code == 302
            assert f"/planilla/{planilla.id}/nomina/{nomina.id}/log" in response.location


def test_regenerar_comprobante_contable_with_warnings(app, client, admin_user, db_session, planilla, nomina):
    """Test comprobante regeneration displays warnings if configuration incomplete."""
    with app.app_context():
        from coati_payroll.model import db
        from unittest.mock import MagicMock, patch

        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to 'applied' state
        nomina = db.session.merge(nomina)
        nomina.estado = "applied"
        nomina.periodo_fin = date(2025, 1, 31)
        db_session.commit()

        # Mock the AccountingVoucherService with warnings
        mock_comprobante = MagicMock()
        mock_comprobante.advertencias = ["Warning 1: Configuration incomplete", "Warning 2: Missing account"]

        with patch(
            "coati_payroll.nomina_engine.services.accounting_voucher_service.AccountingVoucherService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_accounting_voucher.return_value = mock_comprobante
            mock_service_class.return_value = mock_service

            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
            )
            assert response.status_code == 302
            # Warnings should be flashed to the user


def test_regenerar_comprobante_contable_handles_exception(app, client, admin_user, db_session, planilla, nomina):
    """Test that regenerar_comprobante_contable handles exceptions gracefully."""
    with app.app_context():
        from coati_payroll.model import db
        from unittest.mock import MagicMock, patch

        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to 'applied' state
        nomina = db.session.merge(nomina)
        nomina.estado = "applied"
        nomina.periodo_fin = date(2025, 1, 31)
        db_session.commit()

        # Mock the AccountingVoucherService to raise an exception
        with patch(
            "coati_payroll.nomina_engine.services.accounting_voucher_service.AccountingVoucherService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_accounting_voucher.side_effect = Exception("Database error")
            mock_service_class.return_value = mock_service

            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
            )
            assert response.status_code == 302
            # Should redirect to ver_log_nomina with error message


def test_regenerar_comprobante_contable_uses_fecha_calculo_original(
    app, client, admin_user, db_session, planilla, nomina
):
    """Test that regenerar_comprobante_contable uses fecha_calculo_original if available."""
    with app.app_context():
        from coati_payroll.model import db
        from unittest.mock import MagicMock, patch

        login_user(client, admin_user.usuario, "admin-password")

        # Set nomina to 'applied' state with fecha_calculo_original
        nomina = db.session.merge(nomina)
        nomina.estado = "applied"
        nomina.fecha_calculo_original = date(2025, 1, 15)
        nomina.periodo_fin = date(2025, 1, 31)
        db_session.commit()

        # Mock the AccountingVoucherService
        mock_comprobante = MagicMock()
        mock_comprobante.advertencias = []

        with patch(
            "coati_payroll.nomina_engine.services.accounting_voucher_service.AccountingVoucherService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_accounting_voucher.return_value = mock_comprobante
            mock_service_class.return_value = mock_service

            response = client.post(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/regenerar-comprobante", follow_redirects=False
            )
            assert response.status_code == 302
            assert f"/planilla/{planilla.id}/nomina/{nomina.id}/log" in response.location
