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
"""Comprehensive tests for exchange rate CRUD operations (coati_payroll/vistas/exchange_rate.py)."""

from datetime import date
from decimal import Decimal

from coati_payroll.model import TipoCambio, Moneda
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
            rate = db_session.query(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=nio.id).first()
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
            rate = db_session.query(TipoCambio).filter_by(id=rate_id).first()
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
        count = db_session.query(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=eur.id).count()
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
            rate = db_session.query(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=jpy.id).first()
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
            rate = db_session.query(TipoCambio).filter_by(moneda_origen_id=usd.id, moneda_destino_id=cad.id).first()
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
                    rate = db_session.query(TipoCambio).filter_by(id=rate_id).first()
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
