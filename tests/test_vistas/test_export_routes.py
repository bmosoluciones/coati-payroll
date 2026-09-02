# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for export routes in planilla module."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

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
            prioridad_prestamos=250,
            prioridad_adelantos=251,
            aplicar_prestamos_automatico=True,
            aplicar_adelantos_automatico=True,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(planilla)
        db_session.commit()
        db_session.refresh(planilla)
        return planilla


@pytest.fixture
def empleado(app, db_session, empresa):
    """Create an Empleado for testing."""
    with app.app_context():
        from tests.factories.employee_factory import create_employee

        empleado = create_employee(
            db_session,
            empresa.id,
            codigo="EMP001",
            primer_nombre="Juan",
            primer_apellido="Perez",
            identificacion_personal="001-010101-0001A",
            salario_base=Decimal("1000.00"),
        )
        return empleado


@pytest.fixture
def nomina(app, db_session, planilla, admin_user):
    """Create a Nomina for testing."""
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
    """Create a NominaEmpleado for testing."""
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
def comprobante_contable(app, db_session, nomina):
    """Create a ComprobanteContable for testing."""
    with app.app_context():
        from coati_payroll.model import ComprobanteContable

        comprobante = ComprobanteContable(
            nomina_id=nomina.id,
            fecha_calculo=date.today(),
            advertencias=None,
        )
        db_session.add(comprobante)
        db_session.commit()
        db_session.refresh(comprobante)
        return comprobante


@pytest.fixture
def other_planilla(app, db_session, tipo_planilla, moneda, empresa, admin_user):
    """Create another Planilla for testing mismatched nomina scenarios."""
    with app.app_context():
        from coati_payroll.model import Planilla

        other_planilla = Planilla(
            nombre="Other Planilla",
            descripcion="Another planilla",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            periodo_fiscal_inicio=date(2024, 1, 1),
            periodo_fiscal_fin=date(2024, 12, 31),
            prioridad_prestamos=250,
            prioridad_adelantos=251,
            aplicar_prestamos_automatico=True,
            aplicar_adelantos_automatico=True,
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(other_planilla)
        db_session.commit()
        db_session.refresh(other_planilla)
        return other_planilla


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def assert_redirects_to_ver_nomina(response, planilla_id, nomina_id):
    """Helper to assert redirect to ver_nomina or planilla detail page."""
    assert response.status_code == 302
    # Check for either the route name or the URL path
    assert (
        "planilla.ver_nomina" in response.location or f"/planilla/{planilla_id}/nomina/{nomina_id}" in response.location
    )


# ============================================================================
# AUTHENTICATION & AUTHORIZATION TESTS
# ============================================================================


def test_exportar_nomina_excel_requires_authentication(app, client, db_session):
    """Test that exportar_nomina_excel requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/nomina/888/exportar-excel", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_exportar_prestaciones_excel_requires_authentication(app, client, db_session):
    """Test that exportar_prestaciones_excel requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/nomina/888/exportar-prestaciones-excel", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_exportar_comprobante_excel_requires_authentication(app, client, db_session):
    """Test that exportar_comprobante_excel requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/nomina/888/exportar-comprobante-excel", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_exportar_comprobante_detallado_excel_requires_authentication(app, client, db_session):
    """Test that exportar_comprobante_detallado_excel requires authentication."""
    with app.app_context():
        response = client.get("/planilla/999/nomina/888/exportar-comprobante-detallado-excel", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_export_routes_require_read_access(app, client, db_session):
    """Test that export routes require read access."""
    with app.app_context():
        from coati_payroll.enums import TipoUsuario
        from tests.factories.user_factory import create_user

        # Create a user without read access would need specific RBAC setup
        # For now, we just verify that admin users can access
        admin_user = create_user(db_session, "admin", "password", tipo=TipoUsuario.ADMIN)
        login_user(client, admin_user.usuario, "password")

        # These will fail with 404 due to non-existent IDs, but not with 403 (forbidden)
        response = client.get("/planilla/999/nomina/888/exportar-excel", follow_redirects=False)
        assert response.status_code != 403  # Should not be forbidden


# ============================================================================
# EXPORTAR NOMINA EXCEL TESTS
# ============================================================================


def test_exportar_nomina_excel_without_openpyxl(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_nomina_excel when openpyxl is not available."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=False):
            response = client.get(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-excel",
                follow_redirects=False,
            )
            # Should redirect when openpyxl not available
            assert response.status_code == 302
            assert f"/planilla/{planilla.id}/nomina/{nomina.id}" in response.location


def test_exportar_nomina_excel_with_invalid_planilla_id(app, client, admin_user, db_session):
    """Test exportar_nomina_excel with non-existent planilla ID."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get("/planilla/99999/nomina/88888/exportar-excel", follow_redirects=False)
            assert response.status_code == 404


def test_exportar_nomina_excel_with_invalid_nomina_id(app, client, admin_user, db_session, planilla):
    """Test exportar_nomina_excel with non-existent nomina ID."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(f"/planilla/{planilla.id}/nomina/99999/exportar-excel", follow_redirects=False)
            assert response.status_code == 404


def test_exportar_nomina_excel_with_mismatched_nomina(app, client, admin_user, db_session, other_planilla, nomina):
    """Test exportar_nomina_excel when nomina doesn't belong to planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                f"/planilla/{other_planilla.id}/nomina/{nomina.id}/exportar-excel",
                follow_redirects=False,
            )
            # Should redirect to listar_nominas
            assert response.status_code == 302
            assert f"/planilla/{other_planilla.id}/nominas" in response.location


def test_exportar_nomina_excel_success(app, client, admin_user, db_session, planilla, nomina, nomina_empleado):
    """Test successful exportar_nomina_excel."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock the export service
        mock_output = BytesIO(b"fake excel content")
        mock_filename = "nomina_test.xlsx"

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_nomina_excel",
                return_value=(mock_output, mock_filename),
            ):
                response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-excel")
                assert response.status_code == 200
                assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exportar_nomina_excel_handles_exception(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_nomina_excel handles exceptions from export service."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_nomina_excel",
                side_effect=Exception("Export failed"),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-excel",
                    follow_redirects=False,
                )
                # Should redirect on error
                assert response.status_code == 302
                assert f"/planilla/{planilla.id}/nomina/{nomina.id}" in response.location


# ============================================================================
# EXPORTAR PRESTACIONES EXCEL TESTS
# ============================================================================


def test_exportar_prestaciones_excel_without_openpyxl(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_prestaciones_excel when openpyxl is not available."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=False):
            response = client.get(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-prestaciones-excel",
                follow_redirects=False,
            )
            # Should redirect when openpyxl not available
            assert response.status_code == 302
            assert f"/planilla/{planilla.id}/nomina/{nomina.id}" in response.location


def test_exportar_prestaciones_excel_with_invalid_planilla_id(app, client, admin_user, db_session):
    """Test exportar_prestaciones_excel with non-existent planilla ID."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get("/planilla/99999/nomina/88888/exportar-prestaciones-excel", follow_redirects=False)
            assert response.status_code == 404


def test_exportar_prestaciones_excel_with_mismatched_nomina(
    app, client, admin_user, db_session, other_planilla, nomina
):
    """Test exportar_prestaciones_excel when nomina doesn't belong to planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                f"/planilla/{other_planilla.id}/nomina/{nomina.id}/exportar-prestaciones-excel",
                follow_redirects=False,
            )
            # Should redirect to listar_nominas
            assert response.status_code == 302
            assert f"/planilla/{other_planilla.id}/nominas" in response.location


def test_exportar_prestaciones_excel_success(app, client, admin_user, db_session, planilla, nomina, nomina_empleado):
    """Test successful exportar_prestaciones_excel."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock the export service
        mock_output = BytesIO(b"fake excel content")
        mock_filename = "prestaciones_test.xlsx"

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_prestaciones_excel",
                return_value=(mock_output, mock_filename),
            ):
                response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-prestaciones-excel")
                assert response.status_code == 200
                assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exportar_prestaciones_excel_handles_exception(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_prestaciones_excel handles exceptions from export service."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_prestaciones_excel",
                side_effect=Exception("Export failed"),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-prestaciones-excel",
                    follow_redirects=False,
                )
                # Should redirect on error
                assert response.status_code == 302
                assert f"/planilla/{planilla.id}/nomina/{nomina.id}" in response.location


# ============================================================================
# EXPORTAR COMPROBANTE EXCEL TESTS
# ============================================================================


def test_exportar_comprobante_excel_without_openpyxl(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_comprobante_excel when openpyxl is not available."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=False):
            response = client.get(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-excel",
                follow_redirects=False,
            )
            # Should redirect when openpyxl not available
            assert_redirects_to_ver_nomina(response, planilla.id, nomina.id)


def test_exportar_comprobante_excel_with_invalid_planilla_id(app, client, admin_user, db_session):
    """Test exportar_comprobante_excel with non-existent planilla ID."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get("/planilla/99999/nomina/88888/exportar-comprobante-excel", follow_redirects=False)
            assert response.status_code == 404


def test_exportar_comprobante_excel_with_mismatched_nomina(app, client, admin_user, db_session, other_planilla, nomina):
    """Test exportar_comprobante_excel when nomina doesn't belong to planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                f"/planilla/{other_planilla.id}/nomina/{nomina.id}/exportar-comprobante-excel",
                follow_redirects=False,
            )
            # Should redirect to listar_nominas
            assert response.status_code == 302
            assert f"/planilla/{other_planilla.id}/nominas" in response.location


def test_exportar_comprobante_excel_without_comprobante(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_comprobante_excel when comprobante doesn't exist."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-excel",
                follow_redirects=False,
            )
            # Should redirect when comprobante doesn't exist
            assert_redirects_to_ver_nomina(response, planilla.id, nomina.id)


def test_exportar_comprobante_excel_with_warnings(
    app, client, admin_user, db_session, planilla, nomina, comprobante_contable
):
    """Test exportar_comprobante_excel when comprobante has warnings."""
    with app.app_context():
        # Update comprobante to have warnings
        comprobante_contable.advertencias = {"warning": "Configuration incomplete"}
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Mock the export service
        mock_output = BytesIO(b"fake excel content")
        mock_filename = "comprobante_test.xlsx"

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_comprobante_excel",
                return_value=(mock_output, mock_filename),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-excel",
                    follow_redirects=False,
                )
                # Should still export successfully even with warnings
                assert response.status_code == 200
                assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exportar_comprobante_excel_success(
    app, client, admin_user, db_session, planilla, nomina, comprobante_contable
):
    """Test successful exportar_comprobante_excel."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock the export service
        mock_output = BytesIO(b"fake excel content")
        mock_filename = "comprobante_test.xlsx"

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_comprobante_excel",
                return_value=(mock_output, mock_filename),
            ):
                response = client.get(f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-excel")
                assert response.status_code == 200
                assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exportar_comprobante_excel_handles_exception(
    app, client, admin_user, db_session, planilla, nomina, comprobante_contable
):
    """Test exportar_comprobante_excel handles exceptions from export service."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_comprobante_excel",
                side_effect=Exception("Export failed"),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-excel",
                    follow_redirects=False,
                )
                # Should redirect on error
                assert_redirects_to_ver_nomina(response, planilla.id, nomina.id)


# ============================================================================
# EXPORTAR COMPROBANTE DETALLADO EXCEL TESTS
# ============================================================================


def test_exportar_comprobante_detallado_excel_without_openpyxl(app, client, admin_user, db_session, planilla, nomina):
    """Test exportar_comprobante_detallado_excel when openpyxl is not available."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=False):
            response = client.get(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-detallado-excel",
                follow_redirects=False,
            )
            # Should redirect when openpyxl not available
            assert_redirects_to_ver_nomina(response, planilla.id, nomina.id)


def test_exportar_comprobante_detallado_excel_with_invalid_planilla_id(app, client, admin_user, db_session):
    """Test exportar_comprobante_detallado_excel with non-existent planilla ID."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                "/planilla/99999/nomina/88888/exportar-comprobante-detallado-excel", follow_redirects=False
            )
            assert response.status_code == 404


def test_exportar_comprobante_detallado_excel_with_mismatched_nomina(
    app, client, admin_user, db_session, other_planilla, nomina
):
    """Test exportar_comprobante_detallado_excel when nomina doesn't belong to planilla."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                f"/planilla/{other_planilla.id}/nomina/{nomina.id}/exportar-comprobante-detallado-excel",
                follow_redirects=False,
            )
            # Should redirect to listar_nominas
            assert response.status_code == 302
            assert f"/planilla/{other_planilla.id}/nominas" in response.location


def test_exportar_comprobante_detallado_excel_without_comprobante(
    app, client, admin_user, db_session, planilla, nomina
):
    """Test exportar_comprobante_detallado_excel when comprobante doesn't exist."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            response = client.get(
                f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-detallado-excel",
                follow_redirects=False,
            )
            # Should redirect when comprobante doesn't exist
            assert_redirects_to_ver_nomina(response, planilla.id, nomina.id)


def test_exportar_comprobante_detallado_excel_with_warnings(
    app, client, admin_user, db_session, planilla, nomina, comprobante_contable
):
    """Test exportar_comprobante_detallado_excel when comprobante has warnings."""
    with app.app_context():
        # Update comprobante to have warnings
        comprobante_contable.advertencias = {"warning": "Configuration incomplete"}
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Mock the export service
        mock_output = BytesIO(b"fake excel content")
        mock_filename = "comprobante_detallado_test.xlsx"

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_comprobante_detallado_excel",
                return_value=(mock_output, mock_filename),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-detallado-excel",
                    follow_redirects=False,
                )
                # Should still export successfully even with warnings
                assert response.status_code == 200
                assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exportar_comprobante_detallado_excel_success(
    app, client, admin_user, db_session, planilla, nomina, comprobante_contable
):
    """Test successful exportar_comprobante_detallado_excel."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock the export service
        mock_output = BytesIO(b"fake excel content")
        mock_filename = "comprobante_detallado_test.xlsx"

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_comprobante_detallado_excel",
                return_value=(mock_output, mock_filename),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-detallado-excel"
                )
                assert response.status_code == 200
                assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exportar_comprobante_detallado_excel_handles_exception(
    app, client, admin_user, db_session, planilla, nomina, comprobante_contable
):
    """Test exportar_comprobante_detallado_excel handles exceptions from export service."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.planilla.export_routes.check_openpyxl_available", return_value=True):
            with patch(
                "coati_payroll.vistas.planilla.export_routes.ExportService.exportar_comprobante_detallado_excel",
                side_effect=Exception("Export failed"),
            ):
                response = client.get(
                    f"/planilla/{planilla.id}/nomina/{nomina.id}/exportar-comprobante-detallado-excel",
                    follow_redirects=False,
                )
                # Should redirect on error
                assert_redirects_to_ver_nomina(response, planilla.id, nomina.id)
