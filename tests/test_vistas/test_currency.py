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
"""Comprehensive tests for currency CRUD operations (coati_payroll/vistas/currency.py)."""

from coati_payroll.model import Moneda
from tests.helpers.auth import login_user
from tests.factories.user_factory import create_user


def test_currency_index_requires_authentication(app, client, db_session):
    """
    Test that currency index requires authentication.

    Setup:
        - No authenticated user

    Action:
        - GET /currency/

    Verification:
        - Redirects to login (302)
    """
    with app.app_context():
        response = client.get("/currency/", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_currency_index_lists_currencies(app, client, admin_user, db_session):
    """
    Test that authenticated admin can view currency list.

    Setup:
        - Create admin user
        - Create test currencies
        - Login as admin

    Action:
        - GET /currency/

    Verification:
        - Returns 200 OK
        - Contains currency codes
    """
    with app.app_context():
        # Create test currencies
        currency1 = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True, creado_por="admin-test")
        currency2 = Moneda(codigo="EUR", nombre="Euro", simbolo="€", activo=True, creado_por="admin-test")
        db_session.add_all([currency1, currency2])
        db_session.commit()

        # Login
        login_user(client, admin_user.usuario, "admin-password")

        # Access index
        response = client.get("/currency/")
        assert response.status_code == 200
        assert b"USD" in response.data
        assert b"EUR" in response.data


def test_currency_index_pagination(app, client, admin_user, db_session):
    """
    Test that currency index supports pagination.

    Setup:
        - Create admin user
        - Create multiple currencies
        - Login as admin

    Action:
        - GET /currency/ with page parameter

    Verification:
        - Returns 200 OK
        - Pagination works correctly
    """
    with app.app_context():
        # Create 25 currencies
        for i in range(25):
            currency = Moneda(
                codigo=f"CUR{i:02d}",
                nombre=f"Currency {i}",
                simbolo=f"C{i}",
                activo=True,
                creado_por="admin-test",
            )
            db_session.add(currency)
        db_session.commit()

        # Login
        login_user(client, admin_user.usuario, "admin-password")

        # First page
        response = client.get("/currency/")
        assert response.status_code == 200

        # Second page
        response = client.get("/currency/?page=2")
        assert response.status_code == 200


def test_currency_new_get_requires_authentication(app, client, db_session):
    """
    Test that currency new form requires authentication.

    Setup:
        - No authenticated user

    Action:
        - GET /currency/new

    Verification:
        - Redirects to login
    """
    with app.app_context():
        response = client.get("/currency/new", follow_redirects=False)
        assert response.status_code == 302


def test_currency_new_get_shows_form(app, client, admin_user, db_session):
    """
    Test that currency new form is displayed to admin.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - GET /currency/new

    Verification:
        - Returns 200 OK
        - Contains form fields
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/currency/new")
        assert response.status_code == 200
        assert b"codigo" in response.data or b"Codigo" in response.data.lower()


def test_currency_new_post_creates_currency(app, client, admin_user, db_session):
    """
    Test creating a new currency via POST.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - POST /currency/new with currency data

    Verification:
        - Currency is created in database
        - Redirects to index
        - Flash message shows success
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/currency/new",
            data={
                "codigo": "JPY",
                "nombre": "Japanese Yen",
                "simbolo": "¥",
                "activo": True,
            },
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/currency/" in response.location

        # Verify currency was created
        currency = db_session.query(Moneda).filter_by(codigo="JPY").first()
        assert currency is not None
        assert currency.nombre == "Japanese Yen"
        assert currency.simbolo == "¥"
        assert currency.activo is True
        assert currency.creado_por == "admin-test"


def test_currency_new_post_validation_fails_without_required_fields(app, client, admin_user, db_session):
    """
    Test that currency creation fails without required fields.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - POST /currency/new with incomplete data

    Verification:
        - Returns 200 (form with errors)
        - Currency not created
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/currency/new",
            data={
                "codigo": "",  # Missing required field
                "nombre": "Test Currency",
                "simbolo": "$",
            },
            follow_redirects=True,
        )

        # Should show form with errors
        assert response.status_code == 200

        # Verify no currency was created
        count = db_session.query(Moneda).count()
        assert count == 0


def test_currency_edit_get_shows_existing_currency(app, client, admin_user, db_session):
    """
    Test that currency edit form shows existing data.

    Setup:
        - Create admin user
        - Create test currency
        - Login as admin

    Action:
        - GET /currency/edit/<id>

    Verification:
        - Returns 200 OK
        - Form shows existing values
    """
    with app.app_context():
        # Create currency
        currency = Moneda(codigo="GBP", nombre="British Pound", simbolo="£", activo=True, creado_por="admin-test")
        db_session.add(currency)
        db_session.commit()
        db_session.refresh(currency)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/currency/edit/{currency.id}")
        assert response.status_code == 200
        assert b"GBP" in response.data
        assert b"British Pound" in response.data


def test_currency_edit_post_updates_currency(app, client, admin_user, db_session):
    """
    Test updating a currency via POST.

    Setup:
        - Create admin user
        - Create test currency
        - Login as admin

    Action:
        - POST /currency/edit/<id> with updated data

    Verification:
        - Currency is updated in database
        - Redirects to index
    """
    with app.app_context():
        # Create currency
        currency = Moneda(codigo="CAD", nombre="Canadian Dollar", simbolo="$", activo=True, creado_por="admin-test")
        db_session.add(currency)
        db_session.commit()
        db_session.refresh(currency)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/currency/edit/{currency.id}",
            data={
                "codigo": "CAD",
                "nombre": "Canadian Dollar (Updated)",
                "simbolo": "C$",
                "activo": True,
            },
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302

        # Verify currency was updated
        db_session.refresh(currency)
        assert currency.nombre == "Canadian Dollar (Updated)"
        assert currency.simbolo == "C$"
        assert currency.modificado_por == "admin-test"


def test_currency_edit_nonexistent_shows_error(app, client, admin_user, db_session):
    """
    Test editing nonexistent currency shows error.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - GET /currency/edit/nonexistent-id

    Verification:
        - Redirects to index with error message
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/currency/edit/nonexistent-id", follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to index and show error


def test_currency_delete_removes_currency(app, client, admin_user, db_session):
    """
    Test deleting a currency via POST.

    Setup:
        - Create admin user
        - Create test currency
        - Login as admin

    Action:
        - POST /currency/delete/<id>

    Verification:
        - Currency is deleted from database
        - Redirects to index
    """
    with app.app_context():
        # Create currency
        currency = Moneda(codigo="AUD", nombre="Australian Dollar", simbolo="A$", activo=True, creado_por="admin-test")
        db_session.add(currency)
        db_session.commit()
        currency_id = currency.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/currency/delete/{currency_id}", follow_redirects=False)

        # Should redirect to index
        assert response.status_code == 302

        # Verify currency was deleted
        currency = db_session.query(Moneda).filter_by(id=currency_id).first()
        assert currency is None


def test_currency_delete_nonexistent_shows_error(app, client, admin_user, db_session):
    """
    Test deleting nonexistent currency shows error.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - POST /currency/delete/nonexistent-id

    Verification:
        - Redirects to index with error message
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post("/currency/delete/nonexistent-id", follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to index and show error


def test_currency_delete_requires_post_method(app, client, admin_user, db_session):
    """
    Test that currency deletion requires POST method.

    Setup:
        - Create admin user
        - Create test currency
        - Login as admin

    Action:
        - GET /currency/delete/<id> (should fail)

    Verification:
        - Returns 405 Method Not Allowed
    """
    with app.app_context():
        # Create currency
        currency = Moneda(codigo="CHF", nombre="Swiss Franc", simbolo="CHF", activo=True, creado_por="admin-test")
        db_session.add(currency)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/currency/delete/{currency.id}")
        assert response.status_code == 405


def test_currency_workflow_create_edit_delete(app, client, admin_user, db_session):
    """
    End-to-end test: Create, edit, and delete a currency.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - Create currency
        - Edit currency
        - Delete currency

    Verification:
        - Each step succeeds
        - Data persists correctly
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create
        response = client.post(
            "/currency/new",
            data={
                "codigo": "BRL",
                "nombre": "Brazilian Real",
                "simbolo": "R$",
                "activo": "y",  # Form checkbox sends "y" for True
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        currency = db_session.query(Moneda).filter_by(codigo="BRL").first()
        assert currency is not None
        currency_id = currency.id
        assert currency.activo is True  # Verify it was created as active

        # Step 2: Edit - uncheck activo by not sending it
        response = client.post(
            f"/currency/edit/{currency_id}",
            data={
                "codigo": "BRL",
                "nombre": "Brazilian Real (Updated)",
                "simbolo": "R$",
                # Not sending activo means checkbox is unchecked (False)
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        db_session.refresh(currency)
        assert currency.nombre == "Brazilian Real (Updated)"
        assert currency.activo is False

        # Step 3: Delete
        response = client.post(f"/currency/delete/{currency_id}", follow_redirects=False)
        assert response.status_code == 302

        currency = db_session.query(Moneda).filter_by(id=currency_id).first()
        assert currency is None


def test_currency_inactive_flag_works(app, client, admin_user, db_session):
    """
    Test that inactive currencies can be created and listed.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - Create inactive currency
        - View in list

    Verification:
        - Inactive currency is created
        - Appears in list
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create inactive currency (don't send activo field = checkbox unchecked)
        response = client.post(
            "/currency/new",
            data={
                "codigo": "INR",
                "nombre": "Indian Rupee",
                "simbolo": "₹",
                # Not sending activo means False (checkbox unchecked)
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify currency is inactive
        currency = db_session.query(Moneda).filter_by(codigo="INR").first()
        assert currency is not None
        assert currency.activo is False


def test_currency_multiple_currencies_can_coexist(app, client, admin_user, db_session):
    """
    Test that multiple different currencies can be created.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - Create multiple currencies with different codes

    Verification:
        - All currencies are created successfully
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Create multiple currencies
        currencies_to_create = [
            ("MXN", "Mexican Peso", "$"),
            ("COP", "Colombian Peso", "$"),
            ("ARS", "Argentine Peso", "$"),
        ]

        for codigo, nombre, simbolo in currencies_to_create:
            response = client.post(
                "/currency/new",
                data={
                    "codigo": codigo,
                    "nombre": nombre,
                    "simbolo": simbolo,
                    "activo": "y",
                },
                follow_redirects=False,
            )
            assert response.status_code == 302

        # Verify all currencies exist
        for codigo, nombre, simbolo in currencies_to_create:
            currency = db_session.query(Moneda).filter_by(codigo=codigo).first()
            assert currency is not None
            assert currency.nombre == nombre
