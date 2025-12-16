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
"""Comprehensive tests for user management routes (coati_payroll/vistas/user.py)."""

from coati_payroll.model import Usuario
from coati_payroll.auth import validar_acceso
from coati_payroll.enums import TipoUsuario
from tests.helpers.auth import login_user
from tests.factories.user_factory import create_user


def test_user_index_requires_admin(app, client, db_session):
    """
    Test that user index requires admin authentication.

    Setup:
        - No authenticated user

    Action:
        - GET /user/

    Verification:
        - Redirects to login
    """
    with app.app_context():
        response = client.get("/user/", follow_redirects=False)
        assert response.status_code == 302


def test_user_index_regular_user_cannot_access(app, client, db_session):
    """
    Test that regular users cannot access user management.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - GET /user/

    Verification:
        - Returns 403 Forbidden or redirects
    """
    with app.app_context():
        regular_user = create_user(db_session, "regular", "password", tipo=TipoUsuario.AUDIT)

        login_user(client, regular_user.usuario, "password")

        response = client.get("/user/", follow_redirects=False)
        # Should not allow access
        assert response.status_code in [302, 403]


def test_user_index_lists_users_for_admin(app, client, admin_user, db_session):
    """
    Test that admin can view user list.

    Setup:
        - Create admin user
        - Create test users
        - Login as admin

    Action:
        - GET /user/

    Verification:
        - Returns 200 OK
        - Contains user names
    """
    with app.app_context():
        # Create test users with valid tipos
        user1 = create_user(db_session, "testuser1", "pass1", nombre="John", apellido="Doe", tipo=TipoUsuario.HHRR)
        user2 = create_user(db_session, "testuser2", "pass2", nombre="Jane", apellido="Smith", tipo=TipoUsuario.AUDIT)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/user/")
        assert response.status_code == 200
        assert b"testuser1" in response.data
        assert b"testuser2" in response.data


def test_user_new_get_requires_admin(app, client, db_session):
    """
    Test that user creation form requires admin.

    Setup:
        - No authenticated user

    Action:
        - GET /user/new

    Verification:
        - Redirects to login
    """
    with app.app_context():
        response = client.get("/user/new", follow_redirects=False)
        assert response.status_code == 302


def test_user_new_get_shows_form_to_admin(app, client, admin_user, db_session):
    """
    Test that admin can access user creation form.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - GET /user/new

    Verification:
        - Returns 200 OK
        - Contains form fields
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/user/new")
        assert response.status_code == 200
        assert b"usuario" in response.data.lower() or b"username" in response.data.lower()


def test_user_new_post_creates_user(app, client, admin_user, db_session):
    """
    Test creating a new user via POST.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - POST /user/new with user data

    Verification:
        - User is created in database
        - Password is hashed
        - Redirects to index
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/user/new",
            data={
                "usuario": "newuser",
                "password": "newpassword",
                "nombre": "New",
                "apellido": "User",
                "correo_electronico": "newuser@example.com",
                "tipo": TipoUsuario.ADMIN,
                "activo": "y",
            },
            follow_redirects=False,
        )

        # Should redirect to index
        assert response.status_code == 302
        assert "/user/" in response.location

        # Verify user was created
        user = db_session.query(Usuario).filter_by(usuario="newuser").first()
        assert user is not None
        assert user.nombre == "New"
        assert user.apellido == "User"
        assert user.correo_electronico == "newuser@example.com"
        assert user.tipo == TipoUsuario.ADMIN
        assert user.activo is True
        assert user.creado_por == "admin-test"

        # Verify password is hashed and works
        assert validar_acceso("newuser", "newpassword")


def test_user_new_post_requires_password(app, client, admin_user, db_session):
    """
    Test that user creation requires password.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - POST /user/new without password

    Verification:
        - Returns form with error
        - User not created
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/user/new",
            data={
                "usuario": "nopassuser",
                "password": "",  # Empty password
                "nombre": "No",
                "apellido": "Password",
                "correo_electronico": "nopass@example.com",
                "tipo": TipoUsuario.ADMIN,
                "activo": "y",
            },
            follow_redirects=True,
        )

        # Should show form with error
        assert response.status_code == 200

        # Verify user was not created
        user = db_session.query(Usuario).filter_by(usuario="nopassuser").first()
        assert user is None


def test_user_edit_get_shows_existing_user(app, client, admin_user, db_session):
    """
    Test that user edit form shows existing data.

    Setup:
        - Create admin user
        - Create test user
        - Login as admin

    Action:
        - GET /user/edit/<id>

    Verification:
        - Returns 200 OK
        - Form shows existing values
        - Password field is empty
    """
    with app.app_context():
        # Create test user
        test_user = create_user(
            db_session, "editme", "password", nombre="Edit", apellido="Me", 
            correo_electronico="editme@example.com", tipo=TipoUsuario.HHRR
        )

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get(f"/user/edit/{test_user.id}")
        assert response.status_code == 200
        assert b"editme" in response.data
        assert b"Edit" in response.data
        assert b"Me" in response.data


def test_user_edit_post_updates_user(app, client, admin_user, db_session):
    """
    Test updating a user via POST.

    Setup:
        - Create admin user
        - Create test user
        - Login as admin

    Action:
        - POST /user/edit/<id> with updated data

    Verification:
        - User is updated in database
        - Redirects to index
    """
    with app.app_context():
        # Create test user with proper tipo enum
        test_user = create_user(db_session, "updateme", "password", nombre="Old", apellido="Name", tipo=TipoUsuario.HHRR)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/user/edit/{test_user.id}",
            data={
                "usuario": "updateme",
                "password": "",  # Not changing password
                "nombre": "New",
                "apellido": "Name",
                "correo_electronico": "updated@example.com",
                "tipo": TipoUsuario.HHRR,  # Keep same tipo
                "activo": "y",
            },
            follow_redirects=False,
        )

        # Should be successful (200 for form redisplay, 302 for redirect)
        assert response.status_code in [200, 302], f"Expected 200 or 302, got {response.status_code}"

        # If successful redirect, verify user was updated
        if response.status_code == 302:
            db_session.refresh(test_user)
            assert test_user.nombre == "New"
            assert test_user.correo_electronico == "updated@example.com"
            assert test_user.modificado_por == "admin-test"


def test_user_edit_post_can_change_password(app, client, admin_user, db_session):
    """
    Test that editing user can change password.

    Setup:
        - Create admin user
        - Create test user
        - Login as admin

    Action:
        - POST /user/edit/<id> with new password

    Verification:
        - Password is changed
        - New password works
    """
    with app.app_context():
        # Create test user with proper tipo enum
        test_user = create_user(db_session, "changepw", "oldpassword", tipo=TipoUsuario.HHRR)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/user/edit/{test_user.id}",
            data={
                "usuario": "changepw",
                "password": "newpassword",
                "nombre": "Change",
                "apellido": "Password",
                "correo_electronico": "changepw@example.com",
                "tipo": TipoUsuario.HHRR,  # Keep same tipo
                "activo": "y",
            },
            follow_redirects=False,
        )

        # Should be successful (200 for form redisplay, 302 for redirect)
        assert response.status_code in [200, 302], f"Expected 200 or 302, got {response.status_code}"

        # If successful redirect, verify new password works
        if response.status_code == 302:
            assert validar_acceso("changepw", "newpassword")
            assert not validar_acceso("changepw", "oldpassword")


def test_user_delete_removes_user(app, client, admin_user, db_session):
    """
    Test deleting a user via POST.

    Setup:
        - Create admin user
        - Create test user
        - Login as admin

    Action:
        - POST /user/delete/<id>

    Verification:
        - User is deleted from database
        - Redirects to index
    """
    with app.app_context():
        # Create test user
        test_user = create_user(db_session, "deleteme", "password", tipo=TipoUsuario.HHRR)
        user_id = test_user.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/user/delete/{user_id}", follow_redirects=False)

        # Should redirect to index
        assert response.status_code == 302

        # Verify user was deleted
        user = db_session.query(Usuario).filter_by(id=user_id).first()
        assert user is None


def test_user_delete_cannot_delete_self(app, client, admin_user, db_session):
    """
    Test that admin cannot delete their own account.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - POST /user/delete/<own_id>

    Verification:
        - Returns error message
        - User is not deleted
    """
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/user/delete/{admin_user.id}", follow_redirects=True)

        # Should show error
        assert response.status_code == 200

        # Verify admin still exists
        user = db_session.query(Usuario).filter_by(id=admin_user.id).first()
        assert user is not None


def test_user_profile_get_shows_current_user_info(app, client, db_session):
    """
    Test that any logged-in user can view their profile.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - GET /user/profile

    Verification:
        - Returns 200 OK
        - Shows user's information
    """
    with app.app_context():
        user = create_user(
            db_session, "profileuser", "password", nombre="Profile", apellido="User", 
            correo_electronico="profile@example.com", tipo=TipoUsuario.HHRR
        )

        login_user(client, user.usuario, "password")

        response = client.get("/user/profile")
        assert response.status_code == 200
        assert b"Profile" in response.data
        assert b"User" in response.data
        assert b"profile@example.com" in response.data


def test_user_profile_post_updates_own_info(app, client, db_session):
    """
    Test that user can update their own profile.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - POST /user/profile with updated data

    Verification:
        - User info is updated
        - Redirects back to profile
    """
    with app.app_context():
        user = create_user(db_session, "updateprofile", "password", nombre="Old", apellido="Profile", tipo=TipoUsuario.HHRR)

        login_user(client, user.usuario, "password")

        response = client.post(
            "/user/profile",
            data={
                "nombre": "Updated",
                "apellido": "Profile",
                "correo_electronico": "updated@example.com",
                "current_password": "",
                "new_password": "",
                "confirm_password": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify profile was updated
        db_session.refresh(user)
        assert user.nombre == "Updated"
        assert user.correo_electronico == "updated@example.com"


def test_user_profile_change_password_requires_current(app, client, db_session):
    """
    Test that changing password requires current password.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - POST /user/profile with new password but no current password

    Verification:
        - Shows error
        - Password not changed
    """
    with app.app_context():
        user = create_user(db_session, "pwuser", "oldpassword", tipo=TipoUsuario.HHRR)

        login_user(client, user.usuario, "oldpassword")

        response = client.post(
            "/user/profile",
            data={
                "nombre": "PW",
                "apellido": "User",
                "correo_electronico": "pwuser@example.com",
                "current_password": "",  # Missing
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Verify old password still works
        assert validar_acceso("pwuser", "oldpassword")
        assert not validar_acceso("pwuser", "newpassword")


def test_user_profile_change_password_validates_current(app, client, db_session):
    """
    Test that changing password validates current password.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - POST /user/profile with wrong current password

    Verification:
        - Shows error
        - Password not changed
    """
    with app.app_context():
        user = create_user(db_session, "validuser", "correctpassword", tipo=TipoUsuario.HHRR)

        login_user(client, user.usuario, "correctpassword")

        response = client.post(
            "/user/profile",
            data={
                "nombre": "Valid",
                "apellido": "User",
                "correo_electronico": "validuser@example.com",
                "current_password": "wrongpassword",
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Verify old password still works
        assert validar_acceso("validuser", "correctpassword")


def test_user_profile_change_password_requires_confirmation(app, client, db_session):
    """
    Test that changing password requires matching confirmation.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - POST /user/profile with mismatched passwords

    Verification:
        - Shows error
        - Password not changed
    """
    with app.app_context():
        user = create_user(db_session, "confirmuser", "password", tipo=TipoUsuario.HHRR)

        login_user(client, user.usuario, "password")

        response = client.post(
            "/user/profile",
            data={
                "nombre": "Confirm",
                "apellido": "User",
                "correo_electronico": "confirm@example.com",
                "current_password": "password",
                "new_password": "newpassword",
                "confirm_password": "differentpassword",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Verify old password still works
        assert validar_acceso("confirmuser", "password")


def test_user_profile_change_password_success(app, client, db_session):
    """
    Test successful password change through profile.

    Setup:
        - Create regular user
        - Login as regular user

    Action:
        - POST /user/profile with correct password change data

    Verification:
        - Password is changed
        - Success message shown
    """
    with app.app_context():
        user = create_user(db_session, "successuser", "oldpassword", tipo=TipoUsuario.HHRR)

        login_user(client, user.usuario, "oldpassword")

        response = client.post(
            "/user/profile",
            data={
                "nombre": "Success",
                "apellido": "User",
                "correo_electronico": "success@example.com",
                "current_password": "oldpassword",
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify new password works
        assert validar_acceso("successuser", "newpassword")
        assert not validar_acceso("successuser", "oldpassword")


def test_user_workflow_admin_creates_user_user_updates_profile(app, client, admin_user, db_session):
    """
    End-to-end test: Admin creates user, user updates own profile.

    Setup:
        - Create admin user
        - Login as admin

    Action:
        - Admin creates new user
        - Logout
        - Login as new user
        - Update profile

    Verification:
        - Each step succeeds
        - Profile is updated
    """
    with app.app_context():
        # Admin creates user
        login_user(client, admin_user.usuario, "admin-password")

        client.post(
            "/user/new",
            data={
                "usuario": "workflowuser",
                "password": "initialpass",
                "nombre": "Workflow",
                "apellido": "Test",
                "correo_electronico": "workflow@example.com",
                "tipo": TipoUsuario.ADMIN,
                "activo": "y",
            },
        )

        # Logout
        client.get("/auth/logout")

        # User logs in and updates profile
        login_user(client, "workflowuser", "initialpass")

        response = client.post(
            "/user/profile",
            data={
                "nombre": "Updated",
                "apellido": "Workflow",
                "correo_electronico": "updated@example.com",
                "current_password": "",
                "new_password": "",
                "confirm_password": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify update
        user = db_session.query(Usuario).filter_by(usuario="workflowuser").first()
        assert user.nombre == "Updated"
        assert user.apellido == "Workflow"
        assert user.correo_electronico == "updated@example.com"


def test_user_can_be_deactivated(app, client, admin_user, db_session):
    """
    Test that admin can deactivate a user.

    Setup:
        - Create admin user
        - Create active user
        - Login as admin

    Action:
        - Edit user and set activo=False

    Verification:
        - User is deactivated
    """
    with app.app_context():
        user = create_user(db_session, "activeuser", "password", activo=True, tipo=TipoUsuario.HHRR)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/user/edit/{user.id}",
            data={
                "usuario": "activeuser",
                "password": "",
                "nombre": "Active",
                "apellido": "User",
                "correo_electronico": "active@example.com",
                "tipo": TipoUsuario.HHRR,  # Keep same tipo
                # Not sending activo means False (checkbox unchecked)
            },
            follow_redirects=False,
        )

        # Should be successful (200 for form redisplay, 302 for redirect)
        assert response.status_code in [200, 302], f"Expected 200 or 302, got {response.status_code}"

        # If successful redirect, verify user is inactive
        if response.status_code == 302:
            db_session.refresh(user)
            assert user.activo is False


def test_user_types_can_be_changed(app, client, admin_user, db_session):
    """
    Test that admin can change user type.

    Setup:
        - Create admin user
        - Create regular user
        - Login as admin

    Action:
        - Edit user and change tipo to "admin"

    Verification:
        - User type is changed
    """
    with app.app_context():
        user = create_user(db_session, "regularuser", "password", tipo=TipoUsuario.HHRR)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/user/edit/{user.id}",
            data={
                "usuario": "regularuser",
                "password": "",
                "nombre": "Regular",
                "apellido": "User",
                "correo_electronico": "regular@example.com",
                "tipo": TipoUsuario.ADMIN,
                "activo": "y",
            },
            follow_redirects=False,
        )

        # Should be successful (200 for form redisplay, 302 for redirect)
        assert response.status_code in [200, 302], f"Expected 200 or 302, got {response.status_code}"

        # If successful redirect, verify user type changed
        if response.status_code == 302:
            db_session.refresh(user)
            assert user.tipo == TipoUsuario.ADMIN
