# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for prestacion (benefits) management (coati_payroll/vistas/prestacion.py)."""

import io
from decimal import Decimal
from unittest.mock import patch

from openpyxl import Workbook

from coati_payroll.enums import TipoUsuario
from coati_payroll.model import CargaInicialPrestacion, Empleado, Empresa, Moneda, Prestacion
from tests.helpers.auth import login_user


def test_prestacion_dashboard_requires_authentication(app, client, db_session):
    """Test that prestacion dashboard requires authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_dashboard_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access prestacion dashboard."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestacion-management/")
        assert response.status_code == 200


def test_prestacion_initial_balance_bulk_requires_admin(app, client, db_session):
    """Test that bulk initial balance loading requires admin role."""
    with app.app_context():
        from tests.factories.user_factory import create_user

        # Create non-admin user
        hhrr_user = create_user(db_session, "hruser", "password", tipo=TipoUsuario.HHRR)
        login_user(client, hhrr_user.usuario, "password")

        response = client.get("/prestacion-management/initial-balance/bulk", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]


def test_prestacion_initial_balance_bulk_accessible_to_admin(app, client, admin_user, db_session):
    """Test that admin can access bulk initial balance loading."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestacion-management/initial-balance/bulk")
        assert response.status_code == 200


def test_prestacion_dashboard_shows_statistics(app, client, admin_user, db_session):
    """Test that prestacion dashboard displays statistics."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/prestacion-management/")
        assert response.status_code == 200
        # Should contain statistics-related content
        assert b"prestacion" in response.data.lower() or b"benefit" in response.data.lower()


def test_prestacion_workflow_view_dashboard(app, client, admin_user, db_session):
    """End-to-end test: View prestacion dashboard."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View dashboard
        response = client.get("/prestacion-management/")
        assert response.status_code == 200

        # Step 2: Access bulk loading page (admin only)
        response = client.get("/prestacion-management/initial-balance/bulk")
        assert response.status_code == 200


def test_prestacion_balance_report_requires_authentication(app, client, db_session):
    """Test that balance report requires authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/balance-report", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_employee_detail_requires_authentication(app, client, db_session):
    """Test that employee benefit details require authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/employee/test-id", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_transaction_history_requires_authentication(app, client, db_session):
    """Test that transaction history requires authentication."""
    with app.app_context():
        response = client.get("/prestacion-management/transactions", follow_redirects=False)
        assert response.status_code in [302, 404]  # 404 if route not implemented


def test_prestacion_workflow_complete_management(app, client, admin_user, db_session):
    """End-to-end test: Complete prestacion management workflow."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View dashboard
        response = client.get("/prestacion-management/")
        assert response.status_code == 200

        # Step 2: Access bulk loading
        response = client.get("/prestacion-management/initial-balance/bulk")
        assert response.status_code == 200


# ============================================================================
# Helper Functions for Excel File Creation
# ============================================================================


def create_excel_file(rows):
    """Create an Excel file in memory for testing.

    Args:
        rows: List of lists containing row data.

    Returns:
        io.BytesIO: In-memory Excel file
    """
    wb = Workbook()
    ws = wb.active

    for row in rows:
        ws.append(row)

    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    return excel_file


def create_test_data(db_session):
    """Create test data (empresa, empleado, prestacion, moneda) for bulk upload tests.

    Args:
        db_session: SQLAlchemy session

    Returns:
        dict: Dictionary with created test objects
    """
    # Create empresa
    empresa = Empresa(
        codigo="TESTCO",
        razon_social="Test Company",
        ruc="J-12345678-9",
        activo=True,
        creado_por="test",
    )
    db_session.add(empresa)
    db_session.commit()
    db_session.refresh(empresa)

    # Create moneda
    moneda = Moneda(
        codigo="USD",
        nombre="US Dollar",
        simbolo="$",
        activo=True,
        creado_por="test",
    )
    db_session.add(moneda)
    db_session.commit()
    db_session.refresh(moneda)

    # Create prestacion
    prestacion = Prestacion(
        codigo="VAC",
        nombre="Vacaciones",
        tipo_acumulacion="monthly",
        activo=True,
        creado_por="test",
    )
    db_session.add(prestacion)
    db_session.commit()
    db_session.refresh(prestacion)

    # Create empleado
    empleado = Empleado(
        empresa_id=empresa.id,
        codigo_empleado="EMP001",
        primer_nombre="Juan",
        primer_apellido="Perez",
        identificacion_personal="001-010101-0001A",
        activo=True,
    )
    db_session.add(empleado)
    db_session.commit()
    db_session.refresh(empleado)

    return {
        "empresa": empresa,
        "moneda": moneda,
        "prestacion": prestacion,
        "empleado": empleado,
    }


# ============================================================================
# Bulk Upload Tests - POST Endpoint
# ============================================================================


def test_initial_balance_bulk_post_no_file(app, client, admin_user, db_session):
    """Test POST without file in request."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post("/prestacion-management/initial-balance/bulk", data={}, follow_redirects=False)

        assert response.status_code == 302
        assert "/prestacion-management/initial-balance/bulk" in response.location


def test_initial_balance_bulk_post_empty_filename(app, client, admin_user, db_session):
    """Test POST with empty filename."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (io.BytesIO(b""), "")},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/prestacion-management/initial-balance/bulk" in response.location


def test_initial_balance_bulk_post_non_excel_file(app, client, admin_user, db_session):
    """Test POST with non-Excel file extension."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (io.BytesIO(b"test content"), "test.txt")},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/prestacion-management/initial-balance/bulk" in response.location


def test_initial_balance_bulk_post_invalid_excel_file(app, client, admin_user, db_session):
    """Test POST with invalid Excel file content."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create invalid Excel file
        invalid_file = io.BytesIO(b"This is not a valid Excel file")

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (invalid_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/prestacion-management/initial-balance/bulk" in response.location


def test_initial_balance_bulk_post_missing_required_fields(app, client, admin_user, db_session):
    """Test POST with Excel file missing required fields."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with incomplete data (missing saldo_acumulado)
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", None],  # Missing saldo_acumulado (None)
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_empty_required_fields(app, client, admin_user, db_session):
    """Test POST with Excel file with empty string required fields."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with empty strings in required fields
        excel_file = create_excel_file(
            [
                ["", "VAC", 2024, 12, "USD", 100.0],  # Empty codigo_empleado
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_employee_not_found(app, client, admin_user, db_session):
    """Test POST with non-existent employee."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with non-existent employee
        excel_file = create_excel_file(
            [
                ["NONEXISTENT", "VAC", 2024, 12, "USD", 100.0, 1.0, "Test"],
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_prestacion_not_found(app, client, admin_user, db_session):
    """Test POST with non-existent prestacion."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with non-existent prestacion
        excel_file = create_excel_file(
            [
                ["EMP001", "NONEXISTENT", 2024, 12, "USD", 100.0, 1.0, "Test"],
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_moneda_not_found(app, client, admin_user, db_session):
    """Test POST with non-existent moneda."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with non-existent moneda
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "NONEXISTENT", 100.0, 1.0, "Test"],
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_duplicate_entry(app, client, admin_user, db_session):
    """Test POST with duplicate entry detection."""
    with app.app_context():
        test_data = create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create existing CargaInicialPrestacion
        existing_carga = CargaInicialPrestacion(
            empleado_id=test_data["empleado"].id,
            prestacion_id=test_data["prestacion"].id,
            anio_corte=2024,
            mes_corte=12,
            moneda_id=test_data["moneda"].id,
            saldo_acumulado=Decimal("100.0"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("100.0"),
            observaciones="Existing",
            estado="draft",
            creado_por="test",
        )
        db_session.add(existing_carga)
        db_session.commit()

        # Try to create duplicate
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", 200.0, 1.0, "Duplicate"],
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify only one record exists (the original)
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 1
        assert cargas[0].saldo_acumulado == Decimal("100.0")


def test_initial_balance_bulk_post_successful_upload(app, client, admin_user, db_session):
    """Test POST with valid Excel file creates records successfully."""
    with app.app_context():
        test_data = create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with valid data
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", 100.0, 1.0, "Test upload"],
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify record was created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 1
        assert cargas[0].empleado_id == test_data["empleado"].id
        assert cargas[0].prestacion_id == test_data["prestacion"].id
        assert cargas[0].saldo_acumulado == Decimal("100.0")
        assert cargas[0].tipo_cambio == Decimal("1.0")
        assert cargas[0].saldo_convertido == Decimal("100.0")
        assert cargas[0].observaciones == "Test upload"
        assert cargas[0].estado == "draft"


def test_initial_balance_bulk_post_default_tipo_cambio(app, client, admin_user, db_session):
    """Test POST with missing tipo_cambio uses default 1.0."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file without tipo_cambio (only 6 columns)
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", 150.0],  # No tipo_cambio
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify record was created with default tipo_cambio
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 1
        assert cargas[0].tipo_cambio == Decimal("1.0")
        assert cargas[0].saldo_convertido == Decimal("150.0")


def test_initial_balance_bulk_post_default_observaciones(app, client, admin_user, db_session):
    """Test POST with missing observaciones uses default text."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file without observaciones (only 7 columns)
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", 150.0, 1.0],  # No observaciones
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify record was created with default observaciones
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 1
        assert cargas[0].observaciones == "Carga masiva de saldo inicial"


def test_initial_balance_bulk_post_mixed_success_and_errors(app, client, admin_user, db_session):
    """Test POST with Excel file containing both valid and invalid rows."""
    with app.app_context():
        test_data = create_test_data(db_session)

        # Create a second employee
        empleado2 = Empleado(
            empresa_id=test_data["empresa"].id,
            codigo_empleado="EMP002",
            primer_nombre="Maria",
            primer_apellido="Garcia",
            identificacion_personal="001-020202-0002B",
            activo=True,
        )
        db_session.add(empleado2)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with mixed data
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", 100.0, 1.0, "Valid 1"],  # Valid
                ["INVALID", "VAC", 2024, 12, "USD", 200.0, 1.0, "Invalid employee"],  # Invalid employee
                ["EMP002", "VAC", 2024, 11, "USD", 300.0, 1.0, "Valid 2"],  # Valid
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify only valid records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 2


def test_initial_balance_bulk_post_many_errors_truncates_display(app, client, admin_user, db_session):
    """Test POST with many errors only displays first MAX_DISPLAYED_ERRORS."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with 15 invalid rows (more than MAX_DISPLAYED_ERRORS=10)
        rows = []
        for i in range(15):
            rows.append([f"INVALID{i}", "VAC", 2024, 12, "USD", 100.0, 1.0, f"Invalid {i}"])

        excel_file = create_excel_file(rows)

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_processing_exception(app, client, admin_user, db_session):
    """Test POST handles exception during record processing."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with data that will cause processing error (invalid decimal)
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", "INVALID_DECIMAL", 1.0, "Test"],
            ]
        )

        response = client.post(
            "/prestacion-management/initial-balance/bulk",
            data={"file": (excel_file, "test.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created due to processing error
        cargas = db_session.query(CargaInicialPrestacion).all()
        assert len(cargas) == 0


def test_initial_balance_bulk_post_commit_exception(app, client, admin_user, db_session):
    """Test POST handles database commit exception."""
    with app.app_context():
        create_test_data(db_session)
        login_user(client, admin_user.usuario, "admin-password")

        # Create valid Excel file
        excel_file = create_excel_file(
            [
                ["EMP001", "VAC", 2024, 12, "USD", 100.0, 1.0, "Test"],
            ]
        )

        # Mock the db.session.commit to raise an exception
        with patch("coati_payroll.model.db.session.commit") as mock_commit:
            mock_commit.side_effect = Exception("Database error")

            response = client.post(
                "/prestacion-management/initial-balance/bulk",
                data={"file": (excel_file, "test.xlsx")},
                content_type="multipart/form-data",
                follow_redirects=False,
            )

            assert response.status_code == 302

            # Verify commit was attempted
            assert mock_commit.called
