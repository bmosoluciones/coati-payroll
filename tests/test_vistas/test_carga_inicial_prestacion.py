# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for carga inicial prestacion (coati_payroll/vistas/carga_inicial_prestacion.py)."""

import io
from datetime import date
from decimal import Decimal

from openpyxl import load_workbook
from sqlalchemy import func, select

from coati_payroll.model import CargaInicialPrestacion, Empleado, Empresa, Moneda, Prestacion, PrestacionAcumulada
from tests.helpers.auth import login_user


def test_carga_inicial_prestacion_index_requires_authentication(app, client, db_session):
    """Test that carga inicial index requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_index_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access carga inicial list."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/")
        assert response.status_code == 200


def test_carga_inicial_prestacion_nueva_requires_authentication(app, client, db_session):
    """Test that creating initial loads requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/nueva", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_nueva_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access nueva carga form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/nueva")
        assert response.status_code == 200


def test_carga_inicial_prestacion_reporte_requires_authentication(app, client, db_session):
    """Test that report access requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/reporte", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_reporte_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can access reports."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/reporte")
        assert response.status_code == 200


def test_carga_inicial_prestacion_workflow_complete_process(app, client, admin_user, db_session):
    """End-to-end test: Complete initial load workflow."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: View all loads
        response = client.get("/carga-inicial-prestaciones/")
        assert response.status_code == 200

        # Step 2: Access creation form
        response = client.get("/carga-inicial-prestaciones/nueva")
        assert response.status_code == 200

        # Step 3: View report
        response = client.get("/carga-inicial-prestaciones/reporte")
        assert response.status_code == 200


def _create_test_data(db_session):
    """Create test data for carga inicial prestacion tests."""
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
        nombre="Dólar Estadounidense",
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
        salario_base=Decimal("1000.00"),
        moneda_id=moneda.id,
        activo=True,
        creado_por="test",
    )
    db_session.add(empleado)
    db_session.commit()
    db_session.refresh(empleado)

    return empresa, moneda, prestacion, empleado


def test_carga_inicial_prestacion_post_creates_new_record(app, client, admin_user, db_session):
    """Test POST to /nueva creates a new carga inicial prestacion record."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # POST to create new carga inicial
        response = client.post(
            "/carga-inicial-prestaciones/nueva",
            data={
                "empleado_id": empleado.id,
                "prestacion_id": prestacion.id,
                "anio_corte": 2024,
                "mes_corte": 6,
                "moneda_id": moneda.id,
                "saldo_acumulado": "1500.50",
                "tipo_cambio": "1.0",
                "saldo_convertido": "1500.50",
                "observaciones": "Test carga inicial",
            },
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/" in response.location

        # Verify record was created in database
        carga = db_session.execute(
            select(CargaInicialPrestacion).filter_by(
                empleado_id=empleado.id,
                prestacion_id=prestacion.id,
                anio_corte=2024,
                mes_corte=6,
            )
        ).scalar_one_or_none()

        assert carga is not None
        assert carga.estado == "draft"
        assert carga.saldo_acumulado == Decimal("1500.50")
        assert carga.saldo_convertido == Decimal("1500.50")
        assert carga.observaciones == "Test carga inicial"
        assert carga.creado_por == admin_user.usuario


def test_carga_inicial_prestacion_post_duplicate_detection(app, client, admin_user, db_session):
    """Test POST to /nueva detects duplicates and shows warning."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create existing carga inicial
        existing_carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            estado="draft",
            creado_por="test",
        )
        db_session.add(existing_carga)
        db_session.commit()

        # Try to POST duplicate
        response = client.post(
            "/carga-inicial-prestaciones/nueva",
            data={
                "empleado_id": empleado.id,
                "prestacion_id": prestacion.id,
                "anio_corte": 2024,
                "mes_corte": 6,
                "moneda_id": moneda.id,
                "saldo_acumulado": "2000.00",
                "tipo_cambio": "1.0",
                "saldo_convertido": "2000.00",
                "observaciones": "Duplicate test",
            },
            follow_redirects=False,
        )

        # Should return 200 with form (not redirect)
        assert response.status_code == 200

        # Verify only one record exists
        count = (
            db_session.execute(
                select(func.count(CargaInicialPrestacion.id)).filter_by(
                    empleado_id=empleado.id,
                    prestacion_id=prestacion.id,
                    anio_corte=2024,
                    mes_corte=6,
                )
            ).scalar()
            or 0
        )
        assert count == 1


def test_carga_inicial_prestacion_editar_get_request(app, client, admin_user, db_session):
    """Test GET to /editar loads the edit form."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create carga inicial
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            estado="draft",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)

        # GET edit form
        response = client.get(f"/carga-inicial-prestaciones/{carga.id}/editar")
        assert response.status_code == 200


def test_carga_inicial_prestacion_editar_applied_status_redirects(app, client, admin_user, db_session):
    """Test that editing an applied carga inicial redirects with warning."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create applied carga inicial
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            estado="applied",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)

        # Try to edit applied carga
        response = client.get(f"/carga-inicial-prestaciones/{carga.id}/editar", follow_redirects=False)

        # Should redirect to index
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/" in response.location


def test_carga_inicial_prestacion_editar_post_updates_record(app, client, admin_user, db_session):
    """Test POST to /editar updates existing carga inicial prestacion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create carga inicial
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            observaciones="Original",
            estado="draft",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)

        # POST to update
        response = client.post(
            f"/carga-inicial-prestaciones/{carga.id}/editar",
            data={
                "empleado_id": empleado.id,
                "prestacion_id": prestacion.id,
                "anio_corte": 2024,
                "mes_corte": 7,  # Changed month
                "moneda_id": moneda.id,
                "saldo_acumulado": "2500.75",  # Changed amount
                "tipo_cambio": "1.0",
                "saldo_convertido": "2500.75",
                "observaciones": "Updated",  # Changed observations
            },
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/" in response.location

        # Verify record was updated
        db_session.refresh(carga)
        assert carga.mes_corte == 7
        assert carga.saldo_acumulado == Decimal("2500.75")
        assert carga.saldo_convertido == Decimal("2500.75")
        assert carga.observaciones == "Updated"
        assert carga.modificado_por == admin_user.usuario


def test_carga_inicial_prestacion_aplicar_creates_transaction(app, client, admin_user, db_session):
    """Test POST to /aplicar creates transaction in prestacion_acumulada."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create carga inicial
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            observaciones="Test application",
            estado="draft",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)

        # POST to apply
        response = client.post(
            f"/carga-inicial-prestaciones/{carga.id}/aplicar",
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/" in response.location

        # Verify carga status updated
        db_session.refresh(carga)
        assert carga.estado == "applied"
        assert carga.aplicado_por == admin_user.usuario
        assert carga.fecha_aplicacion is not None

        # Verify transaction created in prestacion_acumulada
        transaction = db_session.execute(
            select(PrestacionAcumulada).filter_by(carga_inicial_id=carga.id)
        ).scalar_one_or_none()

        assert transaction is not None
        assert transaction.empleado_id == empleado.id
        assert transaction.prestacion_id == prestacion.id
        assert transaction.tipo_transaccion == "saldo_inicial"
        assert transaction.monto_transaccion == Decimal("1000.00")
        assert transaction.saldo_nuevo == Decimal("1000.00")
        assert transaction.empresa_id == empresa.id


def test_carga_inicial_prestacion_eliminar_deletes_draft(app, client, admin_user, db_session):
    """Test POST to /eliminar deletes draft carga inicial."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create carga inicial
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            estado="draft",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)
        carga_id = carga.id

        # POST to delete
        response = client.post(
            f"/carga-inicial-prestaciones/{carga_id}/eliminar",
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/" in response.location

        # Verify record was deleted
        deleted_carga = db_session.execute(select(CargaInicialPrestacion).filter_by(id=carga_id)).scalar_one_or_none()
        assert deleted_carga is None


def test_carga_inicial_prestacion_eliminar_applied_redirects(app, client, admin_user, db_session):
    """Test that deleting an applied carga inicial redirects with warning."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create applied carga inicial
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            estado="applied",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)
        carga_id = carga.id

        # Try to delete applied carga
        response = client.post(
            f"/carga-inicial-prestaciones/{carga_id}/eliminar",
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/" in response.location

        # Verify record still exists
        still_exists = db_session.execute(select(CargaInicialPrestacion).filter_by(id=carga_id)).scalar_one_or_none()
        assert still_exists is not None
        assert still_exists.estado == "applied"


def test_carga_inicial_prestacion_reporte_excel_requires_authentication(app, client, db_session):
    """Test that Excel report requires authentication."""
    with app.app_context():
        response = client.get("/carga-inicial-prestaciones/reporte/excel", follow_redirects=False)
        assert response.status_code == 302


def test_carga_inicial_prestacion_reporte_excel_accessible_to_authenticated_users(app, client, admin_user, db_session):
    """Test that authenticated users can download Excel report."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/carga-inicial-prestaciones/reporte/excel")

        # Should return 200 and Excel file
        assert response.status_code == 200
        assert response.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response.headers.get("Content-Disposition", "")
        assert "prestaciones_acumuladas.xlsx" in response.headers.get("Content-Disposition", "")


def test_carga_inicial_prestacion_reporte_excel_with_data(app, client, admin_user, db_session):
    """Test Excel report generation with actual data."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create and apply a carga inicial to generate transactions
        carga = CargaInicialPrestacion(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            anio_corte=2024,
            mes_corte=6,
            moneda_id=moneda.id,
            saldo_acumulado=Decimal("1000.00"),
            tipo_cambio=Decimal("1.0"),
            saldo_convertido=Decimal("1000.00"),
            observaciones="Test for Excel export",
            estado="draft",
            creado_por="test",
        )
        db_session.add(carga)
        db_session.commit()
        db_session.refresh(carga)

        # Apply the carga to create a transaction
        transaccion = PrestacionAcumulada(
            empleado_id=carga.empleado_id,
            prestacion_id=carga.prestacion_id,
            fecha_transaccion=date(2024, 6, 15),
            tipo_transaccion="saldo_inicial",
            anio=carga.anio_corte,
            mes=carga.mes_corte,
            moneda_id=carga.moneda_id,
            monto_transaccion=carga.saldo_convertido,
            saldo_anterior=Decimal("0.00"),
            saldo_nuevo=carga.saldo_convertido,
            carga_inicial_id=carga.id,
            observaciones=f"Carga inicial - {carga.observaciones or ''}",
            procesado_por="test",
            creado_por="test",
        )
        db_session.add(transaccion)
        db_session.commit()

        # Request Excel report
        response = client.get("/carga-inicial-prestaciones/reporte/excel")

        # Should return 200 and Excel file
        assert response.status_code == 200
        assert response.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        # Verify the content is a valid Excel file
        excel_data = io.BytesIO(response.data)
        wb = load_workbook(excel_data)
        ws = wb.active

        # Verify worksheet name
        assert ws.title == "Prestaciones Acumuladas"

        # Verify headers are present
        assert ws.cell(row=1, column=1).value == "ID Transacción"
        assert ws.cell(row=1, column=2).value == "Fecha Transacción"
        assert ws.cell(row=1, column=3).value == "Código Empleado"

        # Verify data row exists
        assert ws.cell(row=2, column=1).value == transaccion.id
        assert ws.cell(row=2, column=3).value == empleado.codigo_empleado


def test_carga_inicial_prestacion_reporte_excel_with_filters(app, client, admin_user, db_session):
    """Test Excel report generation with query filters."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create transaction
        transaccion = PrestacionAcumulada(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            fecha_transaccion=date(2024, 6, 15),
            tipo_transaccion="saldo_inicial",
            anio=2024,
            mes=6,
            moneda_id=moneda.id,
            monto_transaccion=Decimal("1000.00"),
            saldo_anterior=Decimal("0.00"),
            saldo_nuevo=Decimal("1000.00"),
            observaciones="Test transaction",
            procesado_por="test",
            creado_por="test",
        )
        db_session.add(transaccion)
        db_session.commit()

        # Request Excel report with filters
        response = client.get(
            f"/carga-inicial-prestaciones/reporte/excel?empleado_id={empleado.id}&prestacion_id={prestacion.id}"
        )

        # Should return 200 and Excel file
        assert response.status_code == 200
        assert response.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_carga_inicial_prestacion_reporte_excel_with_date_filters(app, client, admin_user, db_session):
    """Test Excel report generation with date filters."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create test data
        empresa, moneda, prestacion, empleado = _create_test_data(db_session)

        # Create transaction
        transaccion = PrestacionAcumulada(
            empleado_id=empleado.id,
            prestacion_id=prestacion.id,
            fecha_transaccion=date(2024, 6, 15),
            tipo_transaccion="saldo_inicial",
            anio=2024,
            mes=6,
            moneda_id=moneda.id,
            monto_transaccion=Decimal("1000.00"),
            saldo_anterior=Decimal("0.00"),
            saldo_nuevo=Decimal("1000.00"),
            observaciones="Test transaction",
            procesado_por="test",
            creado_por="test",
        )
        db_session.add(transaccion)
        db_session.commit()

        # Request Excel report with date filters
        response = client.get("/carga-inicial-prestaciones/reporte/excel?fecha_desde=2024-06-01&fecha_hasta=2024-06-30")

        # Should return 200 and Excel file
        assert response.status_code == 200
        assert response.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_carga_inicial_prestacion_reporte_excel_without_openpyxl(app, client, admin_user, db_session, monkeypatch):
    """Test Excel report when openpyxl is not available."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Mock ImportError for openpyxl
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("openpyxl not available")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Request Excel report
        response = client.get("/carga-inicial-prestaciones/reporte/excel", follow_redirects=False)

        # Should redirect to reporte page with error message
        assert response.status_code == 302
        assert "/carga-inicial-prestaciones/reporte" in response.location
