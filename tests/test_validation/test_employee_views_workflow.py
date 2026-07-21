# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


from coati_payroll.enums import TipoUsuario
from coati_payroll.model import Empleado, Empresa, HistorialSalario, Moneda
from tests.factories.user_factory import create_user
from tests.helpers.auth import login_user


def _create_empresa_moneda(db_session):
    empresa = Empresa(codigo="EMPVAL", razon_social="Employee Co", ruc="J-EMP", activo=True)
    moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
    db_session.add(empresa)
    db_session.add(moneda)
    db_session.commit()
    return empresa, moneda


@pytest.mark.validation
def test_employee_index_get(app, client, admin_user, db_session):
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        resp = client.get("/employee/")
        assert resp.status_code == 200


@pytest.mark.validation
def test_employee_new_post_creates_employee(app, client, db_session):
    with app.app_context():
        # Use HHRR user (write access)
        hr_user = create_user(db_session, "hr-emp", "password", tipo=TipoUsuario.HHRR)
        empresa, moneda = _create_empresa_moneda(db_session)

        login_user(client, hr_user.usuario, "password")

        resp = client.post(
            "/employee/new",
            data={
                "codigo_empleado": "EMP-VAL-001",
                "primer_nombre": "Ana",
                "segundo_nombre": "",
                "primer_apellido": "García",
                "segundo_apellido": "",
                "identificacion_personal": "001-020202-0002B",
                "fecha_alta": date.today().isoformat(),
                "salario_base": "1234.56",
                # Optional select fields: send empty or valid IDs to avoid "Not a valid choice"
                "moneda_id": str(moneda.id),
                "empresa_id": str(empresa.id),
                "submit": "Guardar",
            },
            follow_redirects=False,
        )

        assert resp.status_code == 302

        created = db_session.query(Empleado).filter(Empleado.codigo_empleado == "EMP-VAL-001").one_or_none()
        assert created is not None


@pytest.mark.validation
def test_employee_edit_and_delete_workflow(app, client, db_session):
    with app.app_context():
        hr_user = create_user(db_session, "hr-emp2", "password", tipo=TipoUsuario.HHRR)
        empresa, moneda = _create_empresa_moneda(db_session)

        emp = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP-VAL-002",
            primer_nombre="Luis",
            primer_apellido="Pérez",
            identificacion_personal="001-030303-0003C",
            fecha_alta=date.today(),
            salario_base=Decimal("1000.00"),
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(emp)
        db_session.commit()

        login_user(client, hr_user.usuario, "password")

        # Edit
        resp = client.post(
            f"/employee/edit/{emp.id}",
            data={
                "codigo_empleado": "EMP-VAL-002",
                "primer_nombre": "Luis Updated",
                "segundo_nombre": "",
                "primer_apellido": "Pérez",
                "segundo_apellido": "",
                "identificacion_personal": "001-030303-0003C",
                "fecha_alta": date.today().isoformat(),
                "empresa_id": str(empresa.id),
                "submit": "Guardar",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        updated = db_session.query(Empleado).filter(Empleado.id == emp.id).one()
        assert updated.primer_nombre == "Luis Updated"
        # Salary and currency must not change from regular employee edit flow
        assert updated.salario_base == Decimal("1000.00")
        assert updated.moneda_id == moneda.id

        # Basic smoke check that list page still renders after update
        resp = client.get("/employee/")
        assert resp.status_code == 200

        # Delete
        resp = client.post(f"/employee/delete/{emp.id}", follow_redirects=False)
        assert resp.status_code == 302

        # Smoke check that list page still renders after delete
        resp = client.get("/employee/")
        assert resp.status_code == 200


@pytest.mark.validation
def test_employee_edit_view_shows_salary_change_button(app, client, db_session):
    with app.app_context():
        hr_user = create_user(db_session, "hr-emp3", "password", tipo=TipoUsuario.HHRR)
        empresa, moneda = _create_empresa_moneda(db_session)
        emp = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP-VAL-003",
            primer_nombre="Maria",
            primer_apellido="Ruiz",
            identificacion_personal="001-040404-0004D",
            fecha_alta=date.today(),
            salario_base=Decimal("1500.00"),
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(emp)
        db_session.commit()

        login_user(client, hr_user.usuario, "password")

        resp = client.get(f"/employee/edit/{emp.id}")
        assert resp.status_code == 200

        html = resp.data.decode("utf-8")
        assert "Autorizar Cambio Salarial" in html
        assert f"/employee/salary-changes/new/{emp.id}" in html


@pytest.mark.validation
def test_employee_salary_change_flow_updates_and_creates_history(app, client, db_session):
    """Small-company flow: same user creates, approves and applies the salary change."""
    with app.app_context():
        hr_user = create_user(db_session, "hr-emp4", "password", tipo=TipoUsuario.HHRR)
        empresa, moneda_nio = _create_empresa_moneda(db_session)

        emp = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP-VAL-004",
            primer_nombre="Carlos",
            primer_apellido="Lopez",
            identificacion_personal="001-050505-0005E",
            fecha_alta=date.today(),
            salario_base=Decimal("1000.00"),
            moneda_id=moneda_nio.id,
            activo=True,
        )
        db_session.add(emp)
        db_session.commit()

        login_user(client, hr_user.usuario, "password")

        # Step 1: create draft
        resp = client.post(
            f"/employee/salary-changes/new/{emp.id}",
            data={
                "fecha_efectiva": date.today().isoformat(),
                "salario_nuevo": "2200.00",
                "motivo": "Ajuste anual",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        history = db_session.query(HistorialSalario).filter(HistorialSalario.empleado_id == emp.id).all()
        assert len(history) == 1
        cambio = history[0]
        assert cambio.salario_anterior == Decimal("1000.00")
        assert cambio.salario_nuevo == Decimal("2200.00")
        assert cambio.estado == "draft"

        # Step 2: approve (same user allowed in small company)
        resp = client.post(f"/employee/salary-changes/{cambio.id}/approve", follow_redirects=False)
        assert resp.status_code == 302
        db_session.refresh(cambio)
        assert cambio.estado == "approved"
        assert cambio.autorizado_por == hr_user.usuario

        # Step 3: apply — salary is updated on the employee record
        resp = client.post(f"/employee/salary-changes/{cambio.id}/apply", follow_redirects=False)
        assert resp.status_code == 302
        db_session.refresh(cambio)
        db_session.refresh(emp)
        assert cambio.estado == "applied"
        assert emp.salario_base == Decimal("2200.00")


@pytest.mark.validation
def test_employee_salary_change_flow_requires_admin_or_hr(app, client, db_session):
    with app.app_context():
        audit_user = create_user(db_session, "audit-emp", "password", tipo=TipoUsuario.AUDIT)
        empresa, moneda = _create_empresa_moneda(db_session)
        emp = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="EMP-VAL-005",
            primer_nombre="Pablo",
            primer_apellido="Arias",
            identificacion_personal="001-060606-0006F",
            fecha_alta=date.today(),
            salario_base=Decimal("1200.00"),
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(emp)
        db_session.commit()

        login_user(client, audit_user.usuario, "password")

        resp = client.get(f"/employee/salary-changes/new/{emp.id}", follow_redirects=False)
        assert resp.status_code == 403
