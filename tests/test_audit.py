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
