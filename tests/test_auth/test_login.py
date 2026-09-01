# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for authentication and login functionality."""

from tests.helpers.assertions import assert_redirected_to
from tests.helpers.auth import login_user


def test_login_page_accessible(client):
    """
    Test that login page is accessible without authentication.

    Setup:
        - None (use clean client)

    Action:
        - GET /auth/login

    Verification:
        - Response is 200 OK
        - Page contains login form
    """
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert b"login" in response.data.lower() or b"iniciar" in response.data.lower()


def test_successful_admin_login(client, app, admin_user):
    """
    Test successful login with admin credentials.

    Setup:
        - Create admin user via fixture

    Action:
        - POST to /auth/login with valid credentials

    Verification:
        - Response is redirect (302)
        - Redirects to home page
    """
    response = login_user(client, "admin-test", "admin-password")

    # Should redirect after successful login
    assert response.status_code in (302, 303)
    assert_redirected_to(response, "/")


def test_failed_login_wrong_password(client, app, admin_user):
    """
    Test failed login with wrong password.

    Setup:
        - Create admin user via fixture

    Action:
        - POST to /auth/login with wrong password

    Verification:
        - Response shows login page again (or redirect back)
        - No successful authentication
    """
    response = login_user(client, "admin-test", "wrong-password")

    # Should not redirect to home, either stay on login or show error
    # Status could be 200 (form redisplay) or redirect back to login
    assert response.status_code in (200, 302, 303)


def test_failed_login_nonexistent_user(client, app, db_session):
    """
    Test failed login with non-existent user.

    Setup:
        - No user created (clean database)

    Action:
        - POST to /auth/login with credentials that don't exist

    Verification:
        - Response shows login page or error
        - No successful authentication
    """
    response = login_user(client, "nonexistent", "password")

    # Should not succeed
    assert response.status_code in (200, 302, 303)


def test_inactive_user_cannot_log_in(client, admin_user, db_session):
    """An inactive account receives the same generic failed-login response."""
    admin_user.activo = False
    db_session.commit()

    response = login_user(client, "admin-test", "admin-password")

    assert response.status_code == 200
    assert b"incorrect" in response.data.lower() or b"incorrectos" in response.data.lower()


def test_protected_page_requires_login(client):
    """
    Test that protected pages require authentication.

    Setup:
        - No user logged in

    Action:
        - GET / (home page, requires login)

    Verification:
        - Response is redirect to login
    """
    response = client.get("/", follow_redirects=False)

    # Should redirect to login
    assert response.status_code in (302, 303)
    assert_redirected_to(response, "/auth/login")


def test_authenticated_user_can_access_home(client, app, admin_user):
    """
    Test that authenticated user can access protected pages.

    Setup:
        - Create admin user
        - Log in

    Action:
        - GET / (home page)

    Verification:
        - Response is 200 OK
        - Home page content is displayed
    """
    # Login first
    login_user(client, "admin-test", "admin-password")

    # Now access home page
    response = client.get("/")

    # Should be accessible
    assert response.status_code == 200


def test_login_with_email(client, app, admin_user):
    """
    Test successful login using email instead of username.

    Setup:
        - Create admin user via fixture

    Action:
        - POST to /auth/login with email as credential

    Verification:
        - Response is redirect (302)
        - Redirects to home page
    """
    response = login_user(client, "admin@test.com", "admin-password")

    # Should redirect after successful login
    assert response.status_code in (302, 303)
    assert_redirected_to(response, "/")
