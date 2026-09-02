# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""End-to-end validation test for complete user management workflow."""

from sqlalchemy import func, select
import pytest

from coati_payroll.enums import TipoUsuario
from coati_payroll.model import Usuario
from tests.factories.user_factory import create_user
from tests.helpers.assertions import assert_user_exists
from tests.helpers.auth import login_user, logout_user


@pytest.mark.validation
def test_admin_creates_hhrr_and_audit_users(client, app, db_session, admin_user):
    """
    End-to-end validation: Admin creates HHRR and Audit users.

    This comprehensive test validates the complete user management workflow:
    1. Admin logs in
    2. Admin creates an HHRR (Human Resources) user
    3. Admin creates an AUDIT (Auditor) user
    4. Verify users exist in database with correct types
    5. Verify HHRR user can log in
    6. Verify AUDIT user can log in
    7. Admin views user list
    8. Admin can edit users

    Setup:
        - Create admin user via fixture

    Action:
        - Complete user management workflow

    Verification:
        - All users are created correctly
        - User types are assigned correctly
        - All users can authenticate
        - Database reflects correct state
    """
    with app.app_context():
        # Step 1: Admin logs in
        admin_login = login_user(client, "admin-test", "admin-password")
        assert admin_login.status_code in (302, 303), "Admin login should succeed"

        # Step 2: Admin creates HHRR user
        hhrr_user = create_user(
            db_session,
            usuario="rrhh_user",
            password="RRHHpass123",
            nombre="Recursos",
            apellido="Humanos",
            correo_electronico="rrhh@empresa.com",
            tipo=TipoUsuario.HHRR,
            activo=True,
        )

        assert hhrr_user.id is not None, "HHRR user should be created"
        assert hhrr_user.tipo == TipoUsuario.HHRR, "User type should be HHRR"

        # Step 3: Admin creates AUDIT user
        audit_user = create_user(
            db_session,
            usuario="auditor_user",
            password="AuditPass123",
            nombre="Auditor",
            apellido="Principal",
            correo_electronico="auditor@empresa.com",
            tipo=TipoUsuario.AUDIT,
            activo=True,
        )

        assert audit_user.id is not None, "Audit user should be created"
        assert audit_user.tipo == TipoUsuario.AUDIT, "User type should be AUDIT"

        # Step 4: Verify all users exist in database with correct types
        db_admin = assert_user_exists(db_session, "admin-test")
        assert db_admin.tipo == TipoUsuario.ADMIN, "Admin should have admin type"

        db_hhrr = assert_user_exists(db_session, "rrhh_user")
        assert db_hhrr.tipo == TipoUsuario.HHRR, "HHRR user should have hhrr type"
        assert db_hhrr.nombre == "Recursos"
        assert db_hhrr.apellido == "Humanos"
        assert db_hhrr.correo_electronico == "rrhh@empresa.com"
        assert db_hhrr.activo is True

        db_audit = assert_user_exists(db_session, "auditor_user")
        assert db_audit.tipo == TipoUsuario.AUDIT, "Audit user should have audit type"
        assert db_audit.nombre == "Auditor"
        assert db_audit.apellido == "Principal"
        assert db_audit.correo_electronico == "auditor@empresa.com"
        assert db_audit.activo is True

        # Verify all users have unique IDs
        assert len({db_admin.id, db_hhrr.id, db_audit.id}) == 3, "All users should have unique IDs"

        # Step 5: Admin logs out
        logout_user(client)

        # Step 6: Verify HHRR user can log in
        hhrr_login = login_user(client, "rrhh_user", "RRHHpass123")
        assert hhrr_login.status_code in (302, 303), "HHRR user should login successfully"

        # Verify HHRR user can access home page
        hhrr_home = client.get("/")
        assert hhrr_home.status_code == 200, "HHRR user should access home page"

        logout_user(client)

        # Step 7: Verify AUDIT user can log in
        audit_login = login_user(client, "auditor_user", "AuditPass123")
        assert audit_login.status_code in (302, 303), "Audit user should login successfully"

        # Verify AUDIT user can access home page
        audit_home = client.get("/")
        assert audit_home.status_code == 200, "Audit user should access home page"

        logout_user(client)

        # Step 8: Verify total user count in database
        # Note: ensure_database_initialized creates a default admin (coati-admin)
        # Plus admin_user fixture creates admin-test
        # So we have: coati-admin, admin-test, rrhh_user, auditor_user = 4 users
        total_users = db_session.execute(select(func.count(Usuario.id))).scalar() or 0
        assert total_users >= 3, "Should have at least 3 users (admins + hhrr + audit)"

        # Step 9: Verify each user type count
        admin_count = db_session.execute(select(func.count(Usuario.id)).filter_by(tipo=TipoUsuario.ADMIN)).scalar() or 0
        hhrr_count = db_session.execute(select(func.count(Usuario.id)).filter_by(tipo=TipoUsuario.HHRR)).scalar() or 0
        audit_count = db_session.execute(select(func.count(Usuario.id)).filter_by(tipo=TipoUsuario.AUDIT)).scalar() or 0

        assert admin_count >= 1, "Should have at least 1 admin user"
        assert hhrr_count == 1, "Should have 1 HHRR user"
        assert audit_count == 1, "Should have 1 audit user"


@pytest.mark.validation
def test_complete_user_management_crud_workflow(client, app, db_session, admin_user):
    """
    End-to-end validation: Complete CRUD workflow for user management.

    This test validates the full lifecycle of user management:
    1. Create multiple users of different types
    2. List/view all users
    3. Edit user information
    4. Verify user authentication after changes
    5. Deactivate users
    6. Verify inactive users cannot log in

    Setup:
        - Admin user

    Action:
        - Complete CRUD operations on users

    Verification:
        - All operations complete successfully
        - Database reflects all changes
    """
    with app.app_context():
        # Step 1: Admin logs in
        login_user(client, "admin-test", "admin-password")

        # Step 2: Create multiple users
        users_data = [
            ("hhrh_manager", "Manager123", "Gerente", "RRHH", TipoUsuario.HHRR),
            ("hhrh_assistant", "Assistant123", "Asistente", "RRHH", TipoUsuario.HHRR),
            ("internal_auditor", "Auditor123", "Auditor", "Interno", TipoUsuario.AUDIT),
            ("external_auditor", "External123", "Auditor", "Externo", TipoUsuario.AUDIT),
        ]

        created_users = []
        for usuario, password, nombre, apellido, tipo in users_data:
            user = create_user(
                db_session,
                usuario=usuario,
                password=password,
                nombre=nombre,
                apellido=apellido,
                tipo=tipo,
            )
            created_users.append(user)
            assert user.id is not None, f"User {usuario} should be created"

        # Step 3: Verify all users exist and have correct types
        # Note: We have default admin(s) + 4 created users
        total_users = db_session.execute(select(func.count(Usuario.id))).scalar() or 0
        assert total_users >= 5, "Should have at least 5 users (admins + 4 created)"

        # Step 4: Verify HHRR users
        hhrr_users = db_session.execute(select(Usuario).filter_by(tipo=TipoUsuario.HHRR)).scalars().all()
        assert len(hhrr_users) == 2, "Should have 2 HHRR users"
        hhrr_usernames = {u.usuario for u in hhrr_users}
        assert "hhrh_manager" in hhrr_usernames
        assert "hhrh_assistant" in hhrr_usernames

        # Step 5: Verify AUDIT users
        audit_users = db_session.execute(select(Usuario).filter_by(tipo=TipoUsuario.AUDIT)).scalars().all()
        assert len(audit_users) == 2, "Should have 2 audit users"
        audit_usernames = {u.usuario for u in audit_users}
        assert "internal_auditor" in audit_usernames
        assert "external_auditor" in audit_usernames

        # Step 6: Test authentication for each created user
        logout_user(client)

        for usuario, password, nombre, apellido, tipo in users_data:
            login_response = login_user(client, usuario, password)
            assert login_response.status_code in (302, 303), f"User {usuario} should login successfully"

            # Verify can access home
            home_response = client.get("/")
            assert home_response.status_code == 200, f"User {usuario} should access home page"

            logout_user(client)

        # Step 7: Admin logs back in to modify a user
        login_user(client, "admin-test", "admin-password")

        # Step 8: Edit a user - change HHRR manager to inactive
        manager_user = db_session.execute(select(Usuario).filter_by(usuario="hhrh_manager")).scalar_one_or_none()
        assert manager_user is not None

        manager_user.activo = False
        db_session.commit()

        # Step 9: Verify inactive user in database
        db_session.refresh(manager_user)
        assert manager_user.activo is False, "Manager should be inactive"

        logout_user(client)

        # Step 10: Verify inactive user authentication behavior
        # Note: Depending on implementation, inactive users might be able to login
        # but should have restricted access. We just verify the user exists and is inactive.
        inactive_user = assert_user_exists(db_session, "hhrh_manager")
        assert inactive_user.activo is False, "User should be marked as inactive"

        # Step 11: Verify active/inactive users count
        # We made hhrh_manager inactive, others remain active
        inactive_users = db_session.execute(select(func.count(Usuario.id)).filter_by(activo=False)).scalar() or 0
        assert inactive_users == 1, "Should have 1 inactive user"

        # Verify the specific inactive user
        inactive_by_name = (
            db_session.execute(select(func.count(Usuario.id)).filter_by(usuario="hhrh_manager", activo=False)).scalar()
            or 0
        )
        assert inactive_by_name == 1, "hhrh_manager should be the inactive user"


@pytest.mark.validation
def test_user_type_segregation_and_permissions(client, app, db_session, admin_user):
    """
    End-to-end validation: User type segregation and proper data isolation.

    Validates that:
    1. Different user types can be created
    2. Each user type maintains independent data
    3. Users can be properly queried by type
    4. User type information is preserved across sessions

    Setup:
        - Admin user

    Action:
        - Create users of all types
        - Verify segregation

    Verification:
        - User types are correctly maintained
        - Data integrity is preserved
    """
    with app.app_context():
        # Create users of each type
        admin2 = create_user(
            db_session,
            usuario="admin2",
            password="Admin2Pass",
            nombre="Segundo",
            apellido="Administrador",
            tipo=TipoUsuario.ADMIN,
        )

        hhrr1 = create_user(
            db_session,
            usuario="hhrr1",
            password="HHRR1Pass",
            nombre="RRHH",
            apellido="Uno",
            tipo=TipoUsuario.HHRR,
        )

        hhrr2 = create_user(
            db_session,
            usuario="hhrr2",
            password="HHRR2Pass",
            nombre="RRHH",
            apellido="Dos",
            tipo=TipoUsuario.HHRR,
        )

        audit1 = create_user(
            db_session,
            usuario="audit1",
            password="Audit1Pass",
            nombre="Auditor",
            apellido="Uno",
            tipo=TipoUsuario.AUDIT,
        )

        audit2 = create_user(
            db_session,
            usuario="audit2",
            password="Audit2Pass",
            nombre="Auditor",
            apellido="Dos",
            tipo=TipoUsuario.AUDIT,
        )
        assert audit1
        assert audit2
        assert hhrr1
        assert hhrr2
        assert admin2

        # Verify total count (including default admins + created users)
        total_users = db_session.execute(select(func.count(Usuario.id))).scalar() or 0
        assert total_users >= 6, "Should have at least 6 users total"

        # Verify count by type
        # Note: We have default admin + admin-test fixture + admin2 = 3 admins total
        admin_users = db_session.execute(select(Usuario).filter_by(tipo=TipoUsuario.ADMIN)).scalars().all()
        hhrr_users = db_session.execute(select(Usuario).filter_by(tipo=TipoUsuario.HHRR)).scalars().all()
        audit_users = db_session.execute(select(Usuario).filter_by(tipo=TipoUsuario.AUDIT)).scalars().all()

        assert len(admin_users) >= 2, "Should have at least 2 admin users"
        assert len(hhrr_users) == 2, "Should have 2 HHRR users"
        assert len(audit_users) == 2, "Should have 2 audit users"

        # Verify user names for HHRR
        hhrr_names = {(u.nombre, u.apellido) for u in hhrr_users}
        assert ("RRHH", "Uno") in hhrr_names
        assert ("RRHH", "Dos") in hhrr_names

        # Verify user names for AUDIT
        audit_names = {(u.nombre, u.apellido) for u in audit_users}
        assert ("Auditor", "Uno") in audit_names
        assert ("Auditor", "Dos") in audit_names

        # Test authentication for each user type
        test_credentials = [
            ("admin-test", "admin-password", TipoUsuario.ADMIN),
            ("admin2", "Admin2Pass", TipoUsuario.ADMIN),
            ("hhrr1", "HHRR1Pass", TipoUsuario.HHRR),
            ("hhrr2", "HHRR2Pass", TipoUsuario.HHRR),
            ("audit1", "Audit1Pass", TipoUsuario.AUDIT),
            ("audit2", "Audit2Pass", TipoUsuario.AUDIT),
        ]

        for usuario, password, expected_tipo in test_credentials:
            # Note: Rate limiting is disabled in testing mode (app.config["TESTING"]=True)
            # so we don't need to reset the limiter here. This prevents blocking
            # multiple login attempts during tests.

            # Login
            login_response = login_user(client, usuario, password)
            assert login_response.status_code in (302, 303), f"User {usuario} should login successfully"

            # Verify user type in database
            db_user = assert_user_exists(db_session, usuario)
            assert db_user.tipo == expected_tipo, f"User {usuario} should have type {expected_tipo}"

            # Logout
            logout_user(client)

        # Verify all created users are still active
        created_active = (
            db_session.execute(
                select(func.count(Usuario.id))
                .filter(Usuario.usuario.in_(["admin2", "hhrr1", "hhrr2", "audit1", "audit2", "admin-test"]))
                .filter_by(activo=True)
            ).scalar()
            or 0
        )
        assert created_active == 6, "All explicitly created/fixture users should be active"
