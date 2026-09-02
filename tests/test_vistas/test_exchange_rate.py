# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for exchange rate CRUD operations (coati_payroll/vistas/exchange_rate.py)."""

from sqlalchemy import func, select
from datetime import date, datetime
from decimal import Decimal
import io

from openpyxl import Workbook
from coati_payroll.model import Moneda, TipoCambio
from tests.helpers.auth import login_user


def test_exchange_rate_index_requires_authentication(app, client, db_session):
    """Test that exchange rate index requires authentication."""
    with app.app_context():
        response = client.get("/exchange_rate/", follow_redirects=False)
        assert response.status_code == 302


def test_exchange_rate_index_lists_rates(app, client, admin_user, db_session):
    """Test that authenticated user can view exchange rate list."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        # Create exchange rate
        rate = TipoCambio(
            fecha=date(2025, 1, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=eur.id,
            tasa=Decimal("0.92"),
            creado_por="admin-test",
        )
        db_session.add(rate)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/exchange_rate/")
        assert response.status_code == 200


def test_exchange_rate_index_supports_date_filters(app, client, admin_user, db_session):
    """Test that exchange rate list can be filtered by date range."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()
        db_session.refresh(usd)
        db_session.refresh(eur)

        # Create exchange rates for different dates
        rate1 = TipoCambio(
            fecha=date(2025, 1, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=eur.id,
            tasa=Decimal("0.92"),
            creado_por="admin-test",
        )
        rate2 = TipoCambio(
            fecha=date(2025, 6, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=eur.id,
            tasa=Decimal("0.94"),
            creado_por="admin-test",
        )
        db_session.add_all([rate1, rate2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Test date filter
        response = client.get("/exchange_rate/?fecha_desde=2025-01-01&fecha_hasta=2025-03-31")
        assert response.status_code == 200


def test_exchange_rate_new_creates_rate(app, client, admin_user, db_session):
    """Test creating a new exchange rate."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        nio = Moneda(codigo="NIO", nombre="Nicaraguan Córdoba", simbolo="C$", activo=True, creado_por="admin-test")
        db_session.add_all([usd, nio])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/exchange_rate/new",
            data={
                "fecha": "2025-01-15",
                "moneda_origen_id": usd.id,
                "moneda_destino_id": nio.id,
                "tasa": "36.75",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rate = db_session.execute(
                select(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=nio.id)
            ).scalar_one_or_none()
            assert rate is not None
            assert rate.tasa == Decimal("36.75")
            assert rate.fecha == date(2025, 1, 15)


def test_exchange_rate_edit_updates_rate(app, client, admin_user, db_session):
    """Test updating an exchange rate."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()
        db_session.refresh(usd)
        db_session.refresh(eur)

        # Create exchange rate
        rate = TipoCambio(
            fecha=date(2025, 1, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=eur.id,
            tasa=Decimal("0.92"),
            creado_por="admin-test",
        )
        db_session.add(rate)
        db_session.commit()
        db_session.refresh(rate)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/exchange_rate/edit/{rate.id}",
            data={
                "fecha": "2025-01-01",
                "moneda_origen_id": usd.id,
                "moneda_destino_id": eur.id,
                "tasa": "0.95",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            db_session.refresh(rate)
            assert rate.tasa == Decimal("0.95")


def test_exchange_rate_delete_removes_rate(app, client, admin_user, db_session):
    """Test deleting an exchange rate."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        gbp = Moneda(codigo="GBP", nombre="British Pound", simbolo="£", activo=True, creado_por="admin-test")
        db_session.add_all([usd, gbp])
        db_session.commit()

        # Create exchange rate
        rate = TipoCambio(
            fecha=date(2025, 1, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=gbp.id,
            tasa=Decimal("0.79"),
            creado_por="admin-test",
        )
        db_session.add(rate)
        db_session.commit()
        rate_id = rate.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/exchange_rate/delete/{rate_id}", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rate = db_session.execute(select(TipoCambio).filter_by(id=rate_id)).scalar_one_or_none()
            assert rate is None


def test_exchange_rate_supports_multiple_rates_same_currencies(app, client, admin_user, db_session):
    """Test that multiple exchange rates can exist for same currency pair on different dates."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create first rate
        response1 = client.post(
            "/exchange_rate/new",
            data={
                "fecha": "2025-01-01",
                "moneda_origen_id": usd.id,
                "moneda_destino_id": eur.id,
                "tasa": "0.92",
            },
            follow_redirects=False,
        )

        # Create second rate for different date
        response2 = client.post(
            "/exchange_rate/new",
            data={
                "fecha": "2025-02-01",
                "moneda_origen_id": usd.id,
                "moneda_destino_id": eur.id,
                "tasa": "0.93",
            },
            follow_redirects=False,
        )

        assert response1.status_code in [200, 302]
        assert response2.status_code in [200, 302]

        # Verify both exist
        count = (
            db_session.execute(
                select(func.count(TipoCambio.id)).filter_by(moneda_origen_id=usd.id, moneda_destino_id=eur.id)
            ).scalar()
            or 0
        )
        assert count >= 2


def test_exchange_rate_validates_decimal_precision(app, client, admin_user, db_session):
    """Test that exchange rates support decimal precision."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        jpy = Moneda(codigo="JPY", nombre="Japanese Yen", simbolo="¥", activo=True, creado_por="admin-test")
        db_session.add_all([usd, jpy])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/exchange_rate/new",
            data={
                "fecha": "2025-01-01",
                "moneda_origen_id": usd.id,
                "moneda_destino_id": jpy.id,
                "tasa": "149.25",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rate = db_session.execute(
                select(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=jpy.id)
            ).scalar_one_or_none()
            assert rate is not None
            assert rate.tasa == Decimal("149.25")


def test_exchange_rate_workflow_create_edit_delete(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, and delete an exchange rate."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        cad = Moneda(codigo="CAD", nombre="Canadian Dollar", simbolo="C$", activo=True, creado_por="admin-test")
        db_session.add_all([usd, cad])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create
        response = client.post(
            "/exchange_rate/new",
            data={
                "fecha": "2025-01-01",
                "moneda_origen_id": usd.id,
                "moneda_destino_id": cad.id,
                "tasa": "1.35",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            rate = db_session.execute(
                select(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=cad.id)
            ).scalar_one_or_none()
            assert rate is not None
            rate_id = rate.id

            # Step 2: Edit
            response = client.post(
                f"/exchange_rate/edit/{rate_id}",
                data={
                    "fecha": "2025-01-01",
                    "moneda_origen_id": usd.id,
                    "moneda_destino_id": cad.id,
                    "tasa": "1.37",
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(rate)
                assert rate.tasa == Decimal("1.37")

                # Step 3: Delete
                response = client.post(f"/exchange_rate/delete/{rate_id}", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    rate = db_session.execute(select(TipoCambio).filter_by(id=rate_id)).scalar_one_or_none()
                    assert rate is None


def test_exchange_rate_import_get_shows_form(app, client, admin_user, db_session):
    """Test that import form is displayed."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/exchange_rate/import")
        assert response.status_code == 200


def test_exchange_rate_filter_by_currency(app, client, admin_user, db_session):
    """Test filtering exchange rates by currency."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        gbp = Moneda(codigo="GBP", nombre="British Pound", simbolo="£", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur, gbp])
        db_session.commit()

        # Create different exchange rates
        rate1 = TipoCambio(
            fecha=date(2025, 1, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=eur.id,
            tasa=Decimal("0.92"),
            creado_por="admin-test",
        )
        rate2 = TipoCambio(
            fecha=date(2025, 1, 1),
            moneda_origen_id=usd.id,
            moneda_destino_id=gbp.id,
            tasa=Decimal("0.79"),
            creado_por="admin-test",
        )
        db_session.add_all([rate1, rate2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Filter by destination currency
        response = client.get(f"/exchange_rate/?moneda_destino_id={eur.id}")
        assert response.status_code == 200


# Helper function to create Excel file for testing
def create_excel_file(rows):
    """Create an Excel file in memory with the given rows.

    Args:
        rows: List of lists representing rows in the Excel file.
              First row should be headers.

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


def test_exchange_rate_import_post_no_file(app, client, admin_user, db_session):
    """Test import_excel POST without file in request."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post("/exchange_rate/import", data={}, follow_redirects=False)

        assert response.status_code == 302
        assert "/exchange_rate/import" in response.location


def test_exchange_rate_import_post_empty_filename(app, client, admin_user, db_session):
    """Test import_excel POST with empty filename."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/exchange_rate/import",
            data={"file": (io.BytesIO(b""), "")},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/exchange_rate/import" in response.location


def test_exchange_rate_import_post_non_excel_file(app, client, admin_user, db_session):
    """Test import_excel POST with non-Excel file extension."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/exchange_rate/import",
            data={"file": (io.BytesIO(b"test content"), "test.txt")},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/exchange_rate/import" in response.location


def test_exchange_rate_import_valid_excel_creates_records(app, client, admin_user, db_session):
    """Test import_excel with valid Excel file creates new records."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with valid data
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],
                ["2025-01-16", "EUR", "USD", 0.83],
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/exchange_rate/" in response.location

        # Verify records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 2


def test_exchange_rate_import_valid_excel_updates_existing(app, client, admin_user, db_session):
    """Test import_excel with valid Excel file updates existing records."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()
        db_session.refresh(usd)
        db_session.refresh(eur)

        # Create existing exchange rate
        existing_rate = TipoCambio(
            fecha=date(2025, 1, 15),
            moneda_origen_id=usd.id,
            moneda_destino_id=eur.id,
            tasa=Decimal("1.0"),
            creado_por="admin-test",
        )
        db_session.add(existing_rate)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with updated rate
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify record was updated
        db_session.refresh(existing_rate)
        assert existing_rate.tasa == Decimal("1.2")


def test_exchange_rate_import_insufficient_columns(app, client, admin_user, db_session):
    """Test import_excel with row having insufficient columns."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        db_session.add(usd)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with insufficient columns
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD"],  # Only 2 columns
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_invalid_date_formats(app, client, admin_user, db_session):
    """Test import_excel with various invalid date formats."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with invalid dates
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["invalid-date", "USD", "EUR", 1.2],
                ["32/13/2025", "USD", "EUR", 1.2],
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created due to errors
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_various_valid_date_formats(app, client, admin_user, db_session):
    """Test import_excel with various valid date formats."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with different valid date formats
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],  # ISO format
                ["15/01/2025", "EUR", "USD", 0.83],  # DD/MM/YYYY format
                [datetime(2025, 1, 17), "USD", "EUR", 1.25],  # datetime object
                [date(2025, 1, 18), "EUR", "USD", 0.8],  # date object
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify all records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 4


def test_exchange_rate_import_empty_currency_codes(app, client, admin_user, db_session):
    """Test import_excel with empty currency codes."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with empty currency codes
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "", "EUR", 1.2],  # Empty origin
                ["2025-01-16", "USD", "", 1.2],  # Empty destination
                ["2025-01-17", None, "EUR", 1.2],  # None origin
                ["2025-01-18", "USD", None, 1.2],  # None destination
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_nonexistent_currencies(app, client, admin_user, db_session):
    """Test import_excel with non-existent currency codes."""
    with app.app_context():
        # Create only USD currency
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        db_session.add(usd)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with non-existent currencies
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "XXX", 1.2],  # XXX doesn't exist
                ["2025-01-16", "YYY", "USD", 1.2],  # YYY doesn't exist
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_invalid_rate_values(app, client, admin_user, db_session):
    """Test import_excel with invalid exchange rate values."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with invalid rates
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 0],  # Zero
                ["2025-01-16", "USD", "EUR", -1.2],  # Negative
                ["2025-01-17", "USD", "EUR", "invalid"],  # Non-numeric string
                ["2025-01-18", "USD", "EUR", None],  # None
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_numeric_rate_types(app, client, admin_user, db_session):
    """Test import_excel with various numeric rate types."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with various numeric types
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],  # Float
                ["2025-01-16", "EUR", "USD", 1],  # Integer
                ["2025-01-17", "USD", "EUR", "1.25"],  # String number
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify all records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 3


def test_exchange_rate_import_mixed_success_and_errors(app, client, admin_user, db_session):
    """Test import_excel with mix of valid and invalid rows."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with mix of valid and invalid data
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],  # Valid
                ["invalid-date", "USD", "EUR", 1.2],  # Invalid date
                ["2025-01-16", "USD", "XXX", 1.2],  # Invalid currency
                ["2025-01-17", "EUR", "USD", 0.83],  # Valid
                ["2025-01-18", "USD", "EUR", -1],  # Invalid rate
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify only valid records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 2


def test_exchange_rate_import_skip_empty_rows(app, client, admin_user, db_session):
    """Test import_excel skips empty rows."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with empty rows
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],  # Valid
                [],  # Empty row
                [None, None, None, None],  # Row with all None
                ["2025-01-16", "EUR", "USD", 0.83],  # Valid
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify only valid records were created (empty rows skipped)
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 2


def test_exchange_rate_import_case_insensitive_currency_codes(app, client, admin_user, db_session):
    """Test import_excel handles currency codes case-insensitively."""
    with app.app_context():
        # Create currencies with uppercase codes
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with lowercase and mixed case currency codes
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "usd", "eur", 1.2],  # lowercase
                ["2025-01-16", "Usd", "Eur", 0.83],  # mixed case
                ["2025-01-17", "  USD  ", "  EUR  ", 1.25],  # with spaces
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify all records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 3


def test_exchange_rate_import_general_exception_handling(app, client, admin_user, db_session):
    """Test import_excel handles general exceptions gracefully."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create an invalid Excel file (corrupted content)
        invalid_file = io.BytesIO(b"This is not a valid Excel file")

        response = client.post(
            "/exchange_rate/import",
            data={"file": (invalid_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/exchange_rate/import" in response.location


def test_exchange_rate_import_many_errors_limited_display(app, client, admin_user, db_session):
    """Test import_excel limits error display when many errors occur."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with many invalid rows (more than the display limit)
        rows = [["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"]]
        for i in range(15):
            rows.append(["invalid-date", "USD", "EUR", 1.2])

        excel_file = create_excel_file(rows)

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_xls_extension(app, client, admin_user, db_session):
    """Test import_excel accepts .xls extension."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with .xls extension
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xls")},  # .xls extension
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/exchange_rate/" in response.location


def test_exchange_rate_import_inactive_currency_not_found(app, client, admin_user, db_session):
    """Test import_excel only uses active currencies."""
    with app.app_context():
        # Create currencies - one active, one inactive
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=False, creado_por="admin-test")  # Inactive
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Try to import with inactive currency
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                ["2025-01-15", "USD", "EUR", 1.2],  # EUR is inactive
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created (EUR is inactive)
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_non_string_date_invalid_type(app, client, admin_user, db_session):
    """Test import_excel with non-string/datetime/date fecha_val type (e.g., number)."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with numeric date (not datetime/date/string)
        excel_file = create_excel_file(
            [
                ["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"],
                [12345, "USD", "EUR", 1.2],  # Numeric date (not datetime object)
            ]
        )

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify no records were created
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 0


def test_exchange_rate_import_row_exception_continues(app, client, admin_user, db_session):
    """Test that exceptions in row processing are caught and other rows continue."""
    with app.app_context():
        # Create currencies
        usd = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        eur = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([usd, eur])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        # Create Excel file with a row that will cause issues and a valid row
        # Using very short row to trigger the len check
        wb = Workbook()
        ws = wb.active
        ws.append(["Fecha", "Moneda Base", "Moneda Destino", "Tipo de Cambio"])
        ws.append(["2025-01-15", "USD"])  # Short row - will trigger error
        ws.append(["2025-01-16", "USD", "EUR", 1.2])  # Valid row

        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        response = client.post(
            "/exchange_rate/import",
            data={"file": (excel_file, "rates.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify the valid row was created despite the error in previous row
        rates = db_session.execute(select(TipoCambio)).scalars().all()
        assert len(rates) == 1
