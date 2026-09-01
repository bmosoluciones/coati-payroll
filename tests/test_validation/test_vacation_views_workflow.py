# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import re

import pytest

from coati_payroll.enums import TipoUsuario, VacationLedgerType
from coati_payroll.model import (
    Deduccion,
    Empleado,
    Empresa,
    Moneda,
    Percepcion,
    Planilla,
    TipoPlanilla,
    VacationAccount,
    VacationLedger,
    VacationNovelty,
    VacationPolicy,
)
from tests.helpers.auth import login_user
from tests.factories.user_factory import create_user


def test_vacation_policy_form_hides_unsupported_carryover_and_expiration_controls(app):
    """Unsupported policy fields are not configurable through the web form."""
    from coati_payroll.forms import VacationPolicyForm

    with app.app_context():
        form = VacationPolicyForm()

    assert "carryover_limit" not in form._fields
    assert "expiration_rule" not in form._fields
    assert "expiration_months" not in form._fields
    assert "expiration_date" not in form._fields


def _create_base_company_struct(db_session):
    empresa = Empresa(codigo="TEST001", razon_social="Test Company", ruc="J-123", activo=True)
    db_session.add(empresa)
    db_session.flush()

    moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
    db_session.add(moneda)
    db_session.flush()

    tipo_planilla = TipoPlanilla(
        codigo="MENSUAL",
        descripcion="Planilla Mensual",
        dias=30,
        periodicidad="monthly",
        activo=True,
    )
    db_session.add(tipo_planilla)
    db_session.flush()

    planilla = Planilla(
        nombre="Planilla Test",
        tipo_planilla_id=tipo_planilla.id,
        empresa_id=empresa.id,
        moneda_id=moneda.id,
        activo=True,
    )
    db_session.add(planilla)
    db_session.flush()

    return empresa, moneda, tipo_planilla, planilla


def _create_employee(db_session, empresa_id: str, moneda_id: str, codigo: str = "EMP001"):
    empleado = Empleado(
        empresa_id=empresa_id,
        codigo_empleado=codigo,
        primer_nombre="Juan",
        primer_apellido="Pérez",
        identificacion_personal="001-010101-0001A",
        salario_base=Decimal("10000.00"),
        moneda_id=moneda_id,
        activo=True,
    )
    db_session.add(empleado)
    db_session.flush()
    return empleado


@pytest.mark.validation
def test_vacation_dashboard_get_as_admin(app, client, admin_user, db_session):
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")
        response = client.get("/vacation/")
        assert response.status_code == 200


@pytest.mark.validation
def test_vacation_api_employee_balance_404_when_no_account(app, client, admin_user, db_session):
    with app.app_context():
        empresa, moneda, _, _ = _create_base_company_struct(db_session)
        empleado = _create_employee(db_session, empresa.id, moneda.id, codigo="EMP-NOACC")
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")
        response = client.get(f"/vacation/api/employee/{empleado.id}/balance")

        assert response.status_code == 404
        payload = response.get_json()
        assert payload is not None
        assert "error" in payload


@pytest.mark.validation
def test_vacation_policy_new_post_creates_policy(app, client, admin_user, db_session):
    with app.app_context():
        empresa, _, _, planilla = _create_base_company_struct(db_session)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/vacation/policies/new",
            data={
                "codigo": "POL-TEST",
                "nombre": "Política Test",
                "planilla_id": "",
                "empresa_id": "",
                "accrual_method": "periodic",
                "accrual_rate": "1.25",
                "accrual_frequency": "monthly",
                "accrual_basis": "",
                "min_service_days": "1",
                "expiration_rule": "never",
                "unit_type": "days",
                "rounding_rule": "nearest",
                "submit": "Guardar",
            },
            follow_redirects=False,
        )

        if response.status_code == 200:
            html = response.data.decode("utf-8", errors="ignore")
            patterns = [
                r"Not a valid choice",
                r"This field is required",
                r"Campo.*requerido",
                r"no es una opción válida",
                r"es requerido",
                r"invalid",
            ]
            hits: list[str] = []
            for pat in patterns:
                hits.extend(re.findall(pat, html, flags=re.IGNORECASE))

            # Also try to pull bootstrap invalid-feedback snippets (common WTForms rendering)
            invalid_snippets = re.findall(r"invalid-feedback[^>]*>.*?<", html, flags=re.IGNORECASE | re.DOTALL)
            if invalid_snippets:
                hits.extend([re.sub(r"\s+", " ", s)[:200] for s in invalid_snippets[:10]])

            # Attempt to map required-field errors to field names by looking backwards from invalid-feedback blocks
            field_hints: list[str] = []
            for m in re.finditer(r"invalid-feedback[^>]*>\s*This field is required\.", html, flags=re.IGNORECASE):
                start = max(0, m.start() - 800)
                window = html[start : m.start()]
                name_matches = list(re.finditer(r"name=\"([^\"]+)\"", window, flags=re.IGNORECASE))
                if name_matches:
                    field_hints.append(f"missing_required={name_matches[-1].group(1)}")

            if field_hints:
                hits.extend(field_hints)

            diagnostic = " | ".join(sorted(set(hits)))[:1500]
            assert False, f"VacationPolicyForm POST returned 200 (form invalid). Hints: {diagnostic}"

        assert response.status_code == 302

        created = db_session.query(VacationPolicy).filter(VacationPolicy.codigo == "POL-TEST").one_or_none()
        assert created is not None




@pytest.mark.validation
def test_vacation_policy_new_post_allows_empty_accrual_rate_and_min_service_days(app, client, admin_user, db_session):
    with app.app_context():
        _create_base_company_struct(db_session)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/vacation/policies/new",
            data={
                "codigo": "POL-OPTIONAL",
                "nombre": "Política Opcional",
                "planilla_id": "",
                "empresa_id": "",
                "accrual_method": "periodic",
                "accrual_rate": "",
                "accrual_frequency": "monthly",
                "accrual_basis": "",
                "min_service_days": "",
                "expiration_rule": "never",
                "unit_type": "days",
                "rounding_rule": "nearest",
                "submit": "Guardar",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        created = db_session.query(VacationPolicy).filter(VacationPolicy.codigo == "POL-OPTIONAL").one_or_none()
        assert created is not None
        assert created.accrual_rate == Decimal("0.0000")
        assert created.min_service_days == 0

@pytest.mark.validation
def test_vacation_leave_request_approve_only_marks_approved_until_payroll_execution(app, client, admin_user, db_session):
    with app.app_context():
        empresa, moneda, _, planilla = _create_base_company_struct(db_session)
        empleado = _create_employee(db_session, empresa.id, moneda.id)

        policy = VacationPolicy(
            codigo="POL001",
            nombre="Test Policy",
            empresa_id=empresa.id,
            planilla_id=planilla.id,
            accrual_rate=Decimal("15.0000"),
            allow_negative=False,
            activo=True,
        )
        db_session.add(policy)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("10.0000"),
            activo=True,
        )
        db_session.add(account)
        db_session.flush()

        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=4)

        leave_request = VacationNovelty(
            empleado_id=empleado.id,
            account_id=account.id,
            start_date=start_date,
            end_date=end_date,
            units=Decimal("5"),
            estado="pending",
        )
        db_session.add(leave_request)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/vacation/leave-requests/{leave_request.id}/approve",
            follow_redirects=False,
        )
        assert response.status_code == 302

        updated_request = db_session.get(VacationNovelty, leave_request.id)
        assert updated_request.estado == "approved"

        updated_account = db_session.get(VacationAccount, account.id)
        assert updated_account.current_balance == Decimal("10.0000")

        ledger_entry = (
            db_session.query(VacationLedger)
            .filter(
                VacationLedger.account_id == account.id,
                VacationLedger.reference_id == leave_request.id,
            )
            .one_or_none()
        )
        assert ledger_entry is None


@pytest.mark.validation
def test_vacation_leave_request_reject_sets_reason(app, client, admin_user, db_session):
    with app.app_context():
        empresa, moneda, _, planilla = _create_base_company_struct(db_session)
        empleado = _create_employee(db_session, empresa.id, moneda.id)

        policy = VacationPolicy(
            codigo="POL001",
            nombre="Test Policy",
            empresa_id=empresa.id,
            planilla_id=planilla.id,
            accrual_rate=Decimal("15.0000"),
            allow_negative=False,
            activo=True,
        )
        db_session.add(policy)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("10.0000"),
            activo=True,
        )
        db_session.add(account)
        db_session.flush()

        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=4)

        leave_request = VacationNovelty(
            empleado_id=empleado.id,
            account_id=account.id,
            start_date=start_date,
            end_date=end_date,
            units=Decimal("5"),
            estado="pending",
        )
        db_session.add(leave_request)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/vacation/leave-requests/{leave_request.id}/reject",
            data={"motivo_rechazo": "Período no disponible"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        updated_request = db_session.get(VacationNovelty, leave_request.id)
        assert updated_request.estado == "rejected"
        assert updated_request.motivo_rechazo == "Período no disponible"


@pytest.mark.validation
def test_vacation_register_taken_post_requires_concept_selection(app, client, admin_user, db_session):
    with app.app_context():
        empresa, moneda, _, planilla = _create_base_company_struct(db_session)
        empleado = _create_employee(db_session, empresa.id, moneda.id)

        policy = VacationPolicy(
            codigo="POL001",
            nombre="Test Policy",
            empresa_id=empresa.id,
            planilla_id=planilla.id,
            accrual_rate=Decimal("15.0000"),
            allow_negative=False,
            activo=True,
        )
        db_session.add(policy)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("10.0000"),
            activo=True,
        )
        db_session.add(account)

        percepcion = Percepcion(codigo="VAC", nombre="Vacaciones", activo=True)
        deduccion = Deduccion(codigo="AUS", nombre="Ausencia", activo=True)
        db_session.add(percepcion)
        db_session.add(deduccion)

        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        novelty_before = db_session.query(VacationNovelty).count()
        ledger_before = db_session.query(VacationLedger).count()

        response = client.post(
            "/vacation/register-taken",
            data={
                "empleado_id": empleado.id,
                "fecha_inicio": date.today().isoformat(),
                "fecha_fin": (date.today() + timedelta(days=2)).isoformat(),
                "dias_descontados": "2.00",
                "tipo_concepto": "income",
                "percepcion_id": "",
                "deduccion_id": "",
                "observaciones": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 200

        novelty_after = db_session.query(VacationNovelty).count()
        ledger_after = db_session.query(VacationLedger).count()
        assert novelty_after == novelty_before
        assert ledger_after == ledger_before


@pytest.mark.validation
def test_vacation_initial_balance_bulk_post_rejects_non_excel_file(app, client, db_session):
    with app.app_context():
        audit_user = create_user(db_session, "admin_bulk", "password", tipo=TipoUsuario.ADMIN)
        login_user(client, audit_user.usuario, "password")

        response = client.post(
            "/vacation/initial-balance/bulk",
            data={"file": (BytesIO(b"not excel"), "balances.txt")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302


@pytest.mark.validation
def test_vacation_initial_balance_bulk_post_applies_balance_from_excel(app, client, db_session):
    with app.app_context():
        admin = create_user(db_session, "admin_excel", "password", tipo=TipoUsuario.ADMIN)

        empresa, moneda, _, planilla = _create_base_company_struct(db_session)
        empleado = _create_employee(db_session, empresa.id, moneda.id, codigo="EMP-XL")

        policy = VacationPolicy(
            codigo="POL001",
            nombre="Test Policy",
            empresa_id=empresa.id,
            planilla_id=planilla.id,
            accrual_rate=Decimal("15.0000"),
            allow_negative=False,
            activo=True,
        )
        db_session.add(policy)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
        )
        db_session.add(account)
        db_session.commit()

        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["EMP-XL", 7.5, "27/12/2025", "Carga inicial"])

        file_obj = BytesIO()
        wb.save(file_obj)
        file_obj.seek(0)

        login_user(client, admin.usuario, "password")

        response = client.post(
            "/vacation/initial-balance/bulk",
            data={"file": (file_obj, "balances.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        assert response.status_code == 302

        updated_account = db_session.get(VacationAccount, account.id)
        assert updated_account.current_balance == Decimal("7.5")

        ledger_entries = (
            db_session.query(VacationLedger)
            .filter(
                VacationLedger.account_id == account.id,
                VacationLedger.entry_type == VacationLedgerType.ADJUSTMENT,
                VacationLedger.source == "initial_balance_bulk",
            )
            .all()
        )
        assert len(ledger_entries) == 1
        assert ledger_entries[0].quantity == Decimal("7.5")
        assert ledger_entries[0].balance_after == Decimal("7.5")


@pytest.mark.validation
def test_vacation_register_taken_success(app, client, admin_user, db_session):
    """Test successful POST to vacation taken registration, creating VacationNovelty and NominaNovedad with null nomina_id."""
    with app.app_context():
        empresa, moneda, _, planilla = _create_base_company_struct(db_session)
        empleado = _create_employee(db_session, empresa.id, moneda.id)

        policy = VacationPolicy(
            codigo="POL001",
            nombre="Test Policy",
            empresa_id=empresa.id,
            planilla_id=planilla.id,
            accrual_rate=Decimal("15.0000"),
            allow_negative=False,
            activo=True,
        )
        db_session.add(policy)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("10.0000"),
            activo=True,
        )
        db_session.add(account)

        percepcion = Percepcion(codigo="VAC", nombre="Vacaciones", activo=True)
        db_session.add(percepcion)
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/vacation/register-taken",
            data={
                "empleado_id": empleado.id,
                "fecha_inicio": date.today().isoformat(),
                "fecha_fin": (date.today() + timedelta(days=2)).isoformat(),
                "dias_descontados": "2.00",
                "tipo_concepto": "income",
                "percepcion_id": percepcion.id,
                "deduccion_id": "",
                "observaciones": "Vacaciones disfrutadas de prueba",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify VacationNovelty was created
        vacation_novelty = db_session.query(VacationNovelty).filter_by(empleado_id=empleado.id).one_or_none()
        assert vacation_novelty is not None
        assert vacation_novelty.units == Decimal("2.00")

        # Verify NominaNovedad was created with floating/null nomina_id
        from coati_payroll.model import NominaNovedad
        nomina_novedad = db_session.query(NominaNovedad).filter_by(empleado_id=empleado.id).one_or_none()
        assert nomina_novedad is not None
        assert nomina_novedad.nomina_id is None
        assert nomina_novedad.valor_cantidad == Decimal("2.00")
        assert nomina_novedad.codigo_concepto == "VAC"
