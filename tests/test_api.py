"""Security and tenant-scope tests for the versioned integration API."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from coati_payroll.api import issue_api_token
from coati_payroll.auth import proteger_passwd
from coati_payroll.enums import ReportType, TipoUsuario
from coati_payroll.model import (
    Empleado,
    Empresa,
    Moneda,
    Nomina,
    NominaEmpleado,
    NominaNovedad,
    Planilla,
    Report,
    TipoPlanilla,
    Usuario,
)

_apidata_seq = {"n": 0}


def _base_data(db_session):
    _apidata_seq["n"] += 1
    n = _apidata_seq["n"]
    moneda = Moneda(codigo=f"NIO{n}", nombre="Córdoba", simbolo="C$", activo=True)
    db_session.add(moneda)
    db_session.flush()
    empresa = Empresa(codigo=f"API{n:04d}", razon_social=f"API Co {n}", ruc=f"J-API{n}")
    db_session.add(empresa)
    db_session.flush()
    empleado = Empleado(
        codigo_empleado=f"API-EMP{n}",
        primer_nombre="Ana",
        primer_apellido="López",
        identificacion_personal=f"001-010101-100{n}A",
        fecha_alta=date(2020, 1, 1),
        salario_base=Decimal("1000.00"),
        moneda_id=moneda.id,
        empresa_id=empresa.id,
        activo=True,
    )
    db_session.add(empleado)
    db_session.flush()
    return moneda, empresa, empleado


def _writable_user(db_session, scope="write", tipo=TipoUsuario.ADMIN.value):
    user = Usuario(
        usuario=f"api-user-{scope}-{tipo}",
        acceso=proteger_passwd("password"),
        nombre="Api",
        apellido="User",
        correo_electronico=f"api-{scope}-{tipo}@test.com",
        tipo=tipo,
        activo=True,
    )
    db_session.add(user)
    db_session.flush()
    record, raw = issue_api_token(user, f"token-{scope}", {scope}, expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.commit()
    return user, raw


def _auth(raw_token):
    return {"Authorization": f"Bearer {raw_token}"}


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


def _payroll(db_session, empresa, moneda, empleado):
    _apidata_seq["n"] += 1
    n = _apidata_seq["n"]
    tipo_planilla = TipoPlanilla(
        codigo=f"API-MENSUAL{n}",
        descripcion="Mensual",
        periodicidad="monthly",
        dias=30,
        periodos_por_anio=12,
        mes_inicio_fiscal=1,
        dia_inicio_fiscal=1,
    )
    db_session.add(tipo_planilla)
    db_session.flush()
    planilla = Planilla(
        nombre=f"API Planilla {n}",
        tipo_planilla_id=tipo_planilla.id,
        empresa_id=empresa.id,
        moneda_id=moneda.id,
        activo=True,
    )
    db_session.add(planilla)
    db_session.flush()
    nomina = Nomina(
        planilla_id=planilla.id,
        periodo_inicio=date(2026, 1, 1),
        periodo_fin=date(2026, 1, 31),
        estado="generated",
        total_neto=Decimal("700.00"),
    )
    db_session.add(nomina)
    db_session.flush()
    nomina_empleado = NominaEmpleado(
        nomina_id=nomina.id,
        empleado_id=empleado.id,
        salario_bruto=Decimal("1000.00"),
        total_ingresos=Decimal("1000.00"),
        total_deducciones=Decimal("300.00"),
        salario_neto=Decimal("700.00"),
        sueldo_base_historico=Decimal("1000.00"),
    )
    db_session.add(nomina_empleado)
    db_session.commit()
    return planilla, nomina, nomina_empleado


def test_payrolls_and_results_endpoints(app, client, db_session):
    with app.app_context():
        moneda, empresa, empleado = _base_data(db_session)
        _planilla, nomina, _nomina_empleado = _payroll(db_session, empresa, moneda, empleado)
        _user, raw_token = _writable_user(db_session, scope="read", tipo=TipoUsuario.ADMIN.value)
        headers = _auth(raw_token)

        payrolls = client.get("/api/v1/payrolls", headers=headers)
        assert payrolls.status_code == 200
        assert payrolls.get_json()["data"][0]["id"] == nomina.id
        assert payrolls.get_json()["data"][0]["total_neto"] == "700.00"

        results = client.get(f"/api/v1/payrolls/{nomina.id}/results", headers=headers)
        assert results.status_code == 200
        row = results.get_json()["data"][0]
        assert row["employee_id"] == empleado.id
        assert row["net"] == "700.00"


def test_reports_endpoint_lists_only_enabled(app, client, db_session):
    with app.app_context():
        enabled = Report(
            name="Enabled Report",
            description="test",
            type=ReportType.CUSTOM,
            status="enabled",
            base_entity="Employee",
            category="employee",
        )
        disabled = Report(
            name="Disabled Report",
            description="test",
            type=ReportType.CUSTOM,
            status="disabled",
            base_entity="Employee",
            category="employee",
        )
        db_session.add_all([enabled, disabled])
        db_session.commit()
        _user, raw_token = _writable_user(db_session, scope="read", tipo=TipoUsuario.ADMIN.value)

        response = client.get("/api/v1/reports", headers=_auth(raw_token))

        assert response.status_code == 200
        names = [row["name"] for row in response.get_json()["data"]]
        assert "Enabled Report" in names
        assert "Disabled Report" not in names


def test_novelties_list_filters_by_tenant(app, client, db_session):
    with app.app_context():
        moneda, empresa, empleado = _base_data(db_session)
        _other_moneda, other_empresa, other_empleado = _base_data(db_session)
        db_session.add_all(
            [
                NominaNovedad(empleado_id=empleado.id, codigo_concepto="BONUS", valor_cantidad=Decimal("50.00")),
                NominaNovedad(empleado_id=other_empleado.id, codigo_concepto="BONUS", valor_cantidad=Decimal("99.00")),
            ]
        )
        db_session.commit()
        user, raw_token = _writable_user(db_session, scope="read", tipo=TipoUsuario.HHRR.value)
        user.empresas.append(empresa)
        db_session.commit()

        response = client.get("/api/v1/novelties", headers=_auth(raw_token))

        assert response.status_code == 200
        rows = response.get_json()["data"]
        assert len(rows) == 1
        assert rows[0]["empleado_id"] == empleado.id
        assert rows[0]["valor"] == "50.00"


def test_novelties_create_success_and_tenant_guard(app, client, db_session):
    with app.app_context():
        moneda, empresa, empleado = _base_data(db_session)
        user, raw_token = _writable_user(db_session, scope="write", tipo=TipoUsuario.HHRR.value)
        user.empresas.append(empresa)
        db_session.commit()

        created = client.post(
            "/api/v1/novelties",
            json={"empleado_id": empleado.id, "codigo_concepto": "SALARIO", "valor_cantidad": 10},
            headers=_auth(raw_token),
        )
        assert created.status_code == 201
        assert created.get_json()["id"]

        denied = client.post(
            "/api/v1/novelties",
            json={"empleado_id": "missing-tenant", "codigo_concepto": "SALARIO"},
            headers=_auth(raw_token),
        )
        assert denied.status_code == 400


def test_payroll_results_rejects_cross_tenant(app, client, db_session):
    with app.app_context():
        moneda, empresa, empleado = _base_data(db_session)
        _planilla, nomina, _ne = _payroll(db_session, empresa, moneda, empleado)
        user, raw_token = _writable_user(db_session, scope="read", tipo=TipoUsuario.HHRR.value)
        db_session.commit()

        response = client.get(f"/api/v1/payrolls/{nomina.id}/results", headers=_auth(raw_token))

        assert response.status_code == 404


def test_payrolls_list_is_tenant_scoped_for_hr(app, client, db_session):
    with app.app_context():
        moneda, empresa, empleado = _base_data(db_session)
        _other_moneda, other_empresa, other_empleado = _base_data(db_session)
        _planilla1, nomina1, _ = _payroll(db_session, empresa, moneda, empleado)
        _planilla2, nomina2, _ = _payroll(db_session, other_empresa, _other_moneda, other_empleado)
        user, raw_token = _writable_user(db_session, scope="read", tipo=TipoUsuario.HHRR.value)
        user.empresas.append(empresa)
        db_session.commit()

        response = client.get("/api/v1/payrolls", headers=_auth(raw_token))

        assert response.status_code == 200
        ids = [row["id"] for row in response.get_json()["data"]]
        assert nomina1.id in ids
        assert nomina2.id not in ids


def test_inactive_user_token_is_rejected(app, client, db_session):
    with app.app_context():
        _moneda, _empresa, _empleado = _base_data(db_session)
        user, raw_token = _writable_user(db_session, scope="read", tipo=TipoUsuario.HHRR.value)
        user.activo = False
        db_session.commit()

        response = client.get("/api/v1/employees", headers=_auth(raw_token))

        assert response.status_code == 401
