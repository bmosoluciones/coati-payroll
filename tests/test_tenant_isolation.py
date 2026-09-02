# SPDX-License-Identifier: Apache-2.0
"""Regression tests for company/tenant isolation."""

from coati_payroll.auth import proteger_passwd
from coati_payroll.model import Deduccion, Empleado, Empresa, Percepcion, Prestacion, Usuario
from tests.helpers.auth import login_user


def _company(db_session, code: str) -> Empresa:
    company = Empresa(codigo=code, razon_social=f"Company {code}", ruc=f"RUC-{code}")
    db_session.add(company)
    db_session.flush()
    return company


def _employee(db_session, company: Empresa, identification: str) -> Empleado:
    employee = Empleado(
        empresa_id=company.id,
        primer_nombre=identification,
        primer_apellido="Employee",
        identificacion_personal=identification,
        salario_base=0,
    )
    db_session.add(employee)
    return employee


def _user(db_session, username: str, *companies: Empresa) -> Usuario:
    user = Usuario(
        usuario=username,
        acceso=proteger_passwd("password"),
        tipo="hr",
        activo=True,
    )
    user.empresas = list(companies)
    db_session.add(user)
    db_session.commit()
    return user


def test_employee_index_isolated_to_assigned_active_company(app, client, db_session):
    company_a = _company(db_session, "A")
    company_b = _company(db_session, "B")
    employee_a = _employee(db_session, company_a, "ID-A")
    employee_b = _employee(db_session, company_b, "ID-B")
    user = _user(db_session, "hr-a", company_a)
    db_session.commit()

    with app.app_context():
        login_user(client, user.usuario, "password")
        response = client.get("/employee/")

    assert response.status_code == 200
    assert employee_a.codigo_empleado.encode() in response.data
    assert employee_b.codigo_empleado.encode() not in response.data


def test_multi_company_user_must_switch_active_company(app, client, db_session):
    company_a = _company(db_session, "MA")
    company_b = _company(db_session, "MB")
    employee_a = _employee(db_session, company_a, "ID-MA")
    employee_b = _employee(db_session, company_b, "ID-MB")
    user = _user(db_session, "hr-multi", company_a, company_b)
    db_session.commit()

    with app.app_context():
        login_user(client, user.usuario, "password")
        assert employee_a.codigo_empleado.encode() not in client.get("/employee/").data
        switch = client.post("/empresa/seleccionar", data={"empresa_id": company_b.id})
        assert switch.status_code == 302
        response = client.get("/employee/")

    assert employee_b.codigo_empleado.encode() in response.data
    assert employee_a.codigo_empleado.encode() not in response.data


def test_cross_company_employee_edit_is_not_reachable(app, client, db_session):
    company_a = _company(db_session, "EA")
    company_b = _company(db_session, "EB")
    employee_b = _employee(db_session, company_b, "ID-EB")
    user = _user(db_session, "hr-edit", company_a)
    db_session.commit()

    with app.app_context():
        login_user(client, user.usuario, "password")
        response = client.get(f"/employee/edit/{employee_b.id}")

    assert response.status_code == 404


def test_company_scoped_concepts_keep_global_concepts_available(app, client, db_session):
    company_a = _company(db_session, "CA")
    company_b = _company(db_session, "CB")
    company_concept = Percepcion(codigo="ONLY-A", nombre="Only A")
    company_concept.empresas = [company_a]
    other_concept = Deduccion(codigo="ONLY-B", nombre="Only B")
    other_concept.empresas = [company_b]
    global_concept = Prestacion(codigo="GLOBAL", nombre="Global")
    db_session.add_all([company_concept, other_concept, global_concept])
    user = _user(db_session, "hr-concepts", company_a)
    db_session.commit()

    with app.app_context():
        login_user(client, user.usuario, "password")
        response = client.get("/percepciones/")

    assert response.status_code == 200
    assert b"ONLY-A" in response.data
    assert b"ONLY-B" not in response.data
