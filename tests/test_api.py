"""Security and tenant-scope tests for the versioned integration API."""

from datetime import UTC, datetime, timedelta

from coati_payroll.api import issue_api_token
from coati_payroll.auth import proteger_passwd
from coati_payroll.enums import TipoUsuario
from coati_payroll.model import Usuario


def test_health_is_public_but_resources_require_bearer_token(app, client, db_session):
    with app.app_context():
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/employees").status_code == 401


def test_api_token_is_hashed_and_scope_is_enforced(app, client, db_session):
    with app.app_context():
        user = Usuario(
            usuario="integration-user",
            acceso=proteger_passwd("password"),
            nombre="Integration",
            apellido="User",
            correo_electronico="integration@test.com",
            tipo=TipoUsuario.HHRR.value,
            activo=True,
        )
        db_session.add(user)
        db_session.flush()
        record, raw_token = issue_api_token(user, "integration", {"read"})
        db_session.commit()

        assert record.token_hash != raw_token
        assert client.get("/api/v1/employees", headers={"Authorization": f"Bearer {raw_token}"}).status_code == 200
        response = client.post(
            "/api/v1/novelties",
            json={"empleado_id": "missing", "codigo_concepto": "BONUS"},
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == 403


def test_expired_token_is_rejected_without_timezone_error(app, client, admin_user, db_session):
    with app.app_context():
        _record, raw_token = issue_api_token(admin_user, "expired", {"read"}, datetime.now(UTC) - timedelta(minutes=1))
        db_session.commit()

        response = client.get("/api/v1/employees", headers={"Authorization": f"Bearer {raw_token}"})
        assert response.status_code == 401


def test_admin_token_still_requires_write_scope(app, client, admin_user, db_session):
    with app.app_context():
        _record, raw_token = issue_api_token(admin_user, "read-only", {"read"})
        db_session.commit()

        response = client.post(
            "/api/v1/novelties",
            json={"empleado_id": "missing", "codigo_concepto": "BONUS"},
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == 403
