"""Tests for unified security and governance audit access."""

from coati_payroll.audit_helpers import registrar_evento_seguridad
from coati_payroll.model import SecurityAuditLog, db
from tests.helpers.auth import login_user


def test_audit_viewer_and_csv_export_are_available_to_admin(app, client, admin_user, db_session):
    with app.app_context():
        registrar_evento_seguridad("user_updated", admin_user.usuario, objetivo="employee-user")
        db_session.commit()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/")
        export = client.get("/audit/export.csv")

        assert page.status_code == 200
        assert b"user_updated" in page.data
        assert b"employee-user" in page.data
        assert export.status_code == 200
        assert b"security" in export.data
        assert b"employee-user" in export.data


def test_login_failure_is_recorded(app, client, db_session):
    with app.app_context():
        response = client.post("/auth/login", data={"email": "unknown", "password": "bad-password"})
        assert response.status_code == 200
        entry = db_session.execute(
            db.select(SecurityAuditLog).filter_by(event="login_failed", actor="unknown")
        ).scalar_one()
        assert entry.success is False


def test_audit_source_filter_limits_to_requested_source(app, client, admin_user, db_session):
    """The ``source`` query param filters the unified viewer to one source."""
    with app.app_context():
        db_session.add(
            SecurityAuditLog(event="login_success", actor="op-a", target_username="op-a", success=True, details={})
        )
        db_session.add(
            SecurityAuditLog(event="user_updated", actor="op-b", target_username="target-b", success=True, details={})
        )
        db_session.commit()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/?source=security")

        assert page.status_code == 200
        assert b"login_success" in page.data
        assert b"user_updated" in page.data


def test_audit_actor_filter_narrows_results(app, client, admin_user, db_session):
    """The ``actor`` query param keeps only matching actors."""
    with app.app_context():
        for evento, actor in [("login_success", "alice"), ("login_failed", "bob")]:
            db_session.add(
                SecurityAuditLog(
                    event=evento,
                    actor=actor,
                    target_username=actor,
                    success=(evento == "login_success"),
                    details={},
                )
            )
        db_session.commit()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/?actor=alice")

        assert page.status_code == 200
        assert b"login_success" in page.data
        assert b"login_failed" not in page.data


def test_audit_target_filter_narrows_results(app, client, admin_user, db_session):
    """The ``target`` query param keeps only matching targets."""
    with app.app_context():
        db_session.add(
            SecurityAuditLog(event="user_updated", actor="op", target_username="employee-x", success=True, details={})
        )
        db_session.add(
            SecurityAuditLog(event="login_success", actor="op", target_username="employee-y", success=True, details={})
        )
        db_session.commit()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/?target=employee-x")

        assert page.status_code == 200
        assert b"user_updated" in page.data
        assert b"login_success" not in page.data


def test_audit_action_filter_narrows_results(app, client, admin_user, db_session):
    """The ``action`` query param keeps only matching events."""
    with app.app_context():
        db_session.add(
            SecurityAuditLog(event="login_success", actor="op", target_username="x", success=True, details={})
        )
        db_session.add(SecurityAuditLog(event="logout", actor="op", target_username="x", success=True, details={}))
        db_session.commit()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/?action=logout")

        assert page.status_code == 200
        assert b"logout" in page.data
        assert b"login_success" not in page.data


def test_audit_unknown_source_yields_empty_results(app, client, admin_user, db_session):
    """An unrecognized source returns no queries and thus no entries."""
    with app.app_context():
        db_session.add(
            SecurityAuditLog(event="login_success", actor="op", target_username="x", success=True, details={})
        )
        db_session.commit()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/?source=does-not-exist")

        assert page.status_code == 200
        assert b"login_success" not in page.data


def test_audit_pagination_offset_is_honored(app, client, admin_user, db_session):
    """Audit entries are paginated and offset moves to later pages."""
    with app.app_context():
        for i in range(51):
            db_session.add(
                SecurityAuditLog(event=f"event-{i:03d}", actor="op", target_username="x", success=True, details={})
            )
        db_session.commit()

        first_actor = db_session.query(SecurityAuditLog).order_by(SecurityAuditLog.timestamp.desc()).first()
        old_actor = db_session.query(SecurityAuditLog).order_by(SecurityAuditLog.timestamp.asc()).first()
        login_user(client, admin_user.usuario, "admin-password")

        page = client.get("/audit/?page=2")

        assert page.status_code == 200
        assert first_actor.event not in page.data.decode()
        assert old_actor.event in page.data.decode()
