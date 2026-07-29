# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for system reports."""

from datetime import date, timedelta

from coati_payroll.system_reports import (
    SYSTEM_REPORT_METADATA,
    SYSTEM_REPORTS,
    get_system_report,
    get_system_report_metadata,
)
from tests.factories.company_factory import create_company
from tests.factories.employee_factory import create_employee


def test_system_reports_registry_populated():
    """
    Test that system reports registry is populated.

    Setup:
        - None

    Action:
        - Check SYSTEM_REPORTS

    Verification:
        - Registry contains reports
    """
    assert len(SYSTEM_REPORTS) > 0


def test_system_report_metadata_populated():
    """
    Test that system report metadata is populated.

    Setup:
        - None

    Action:
        - Check SYSTEM_REPORT_METADATA

    Verification:
        - Metadata contains report info
    """
    assert len(SYSTEM_REPORT_METADATA) > 0


def test_get_system_report_exists():
    """
    Test getting an existing system report.

    Setup:
        - None

    Action:
        - Get employee_list report

    Verification:
        - Returns callable function
    """
    report_func = get_system_report("employee_list")
    assert report_func is not None
    assert callable(report_func)


def test_get_system_report_not_exists():
    """
    Test getting a non-existent system report.

    Setup:
        - None

    Action:
        - Get non-existent report

    Verification:
        - Returns None
    """
    report_func = get_system_report("non_existent_report")
    assert report_func is None


def test_get_system_report_metadata_exists():
    """
    Test getting metadata for an existing report.

    Setup:
        - None

    Action:
        - Get metadata for employee_list

    Verification:
        - Returns metadata dict
    """
    metadata = get_system_report_metadata("employee_list")
    assert metadata is not None
    assert "name" in metadata
    assert "category" in metadata


def test_employee_list_report(app, db_session):
    """
    Test employee list system report.

    Setup:
        - Create employees

    Action:
        - Execute employee_list report

    Verification:
        - Returns employee data
    """
    with app.app_context():
        empresa = create_company(db_session, "TEST_1", "Company 1", "J0001")
        emp1 = create_employee(
            db_session,
            empresa_id=empresa.id,
            primer_nombre="Juan",
            primer_apellido="Perez",
        )
        emp2 = create_employee(
            db_session,
            empresa_id=empresa.id,
            primer_nombre="Maria",
            primer_apellido="Garcia",
        )
        assert emp1
        assert emp2
        db_session.commit()

        report_func = get_system_report("employee_list")
        results = report_func({})

        assert len(results) == 2
        assert "Código" in results[0]
        assert "Nombres" in results[0]
        assert "Apellidos" in results[0]


def test_employee_list_report_with_filter(app, db_session):
    """
    Test employee list report with activo filter.

    Setup:
        - Create active and inactive employees

    Action:
        - Execute report with activo=True filter

    Verification:
        - Returns only active employees
    """
    with app.app_context():
        empresa = create_company(db_session, "TEST_2", "Company 2", "J0002")
        emp1 = create_employee(db_session, empresa_id=empresa.id, primer_nombre="Active")
        emp1.activo = True

        emp2 = create_employee(db_session, empresa_id=empresa.id, primer_nombre="Inactive")
        emp2.activo = False

        db_session.commit()

        report_func = get_system_report("employee_list")
        results = report_func({"activo": True})

        assert len(results) == 1
        assert "Active" in results[0]["Nombres"]


def test_employee_active_inactive_report(app, db_session):
    """
    Test employee active/inactive report.

    Setup:
        - Create active and inactive employees

    Action:
        - Execute report

    Verification:
        - Returns all employees with status
    """
    with app.app_context():
        empresa = create_company(db_session, "TEST_3", "Company 3", "J0003")
        emp1 = create_employee(db_session, empresa_id=empresa.id)
        emp1.activo = True

        emp2 = create_employee(db_session, empresa_id=empresa.id)
        emp2.activo = False

        db_session.commit()

        report_func = get_system_report("employee_active_inactive")
        results = report_func({})

        assert len(results) == 2
        assert "Estado" in results[0]
        # Active employees should be first (sorted by activo desc)
        assert results[0]["Estado"] == "Activo"
        assert results[1]["Estado"] == "Inactivo"


def test_employee_by_department_report(app, db_session):
    """
    Test employee by department report.

    Setup:
        - Create employees in different areas

    Action:
        - Execute report

    Verification:
        - Returns employees grouped by area
    """
    with app.app_context():
        empresa = create_company(db_session, "TEST_4", "Company 4", "J0004")
        emp1 = create_employee(db_session, empresa_id=empresa.id)
        emp1.area = "IT"
        emp1.activo = True

        emp2 = create_employee(db_session, empresa_id=empresa.id)
        emp2.area = "HR"
        emp2.activo = True

        db_session.commit()

        report_func = get_system_report("employee_by_department")
        results = report_func({})

        assert len(results) == 2
        assert "Área" in results[0]
        areas = [r["Área"] for r in results]
        assert "IT" in areas
        assert "HR" in areas


def test_employee_hires_terminations_report(app, db_session):
    """
    Test employee hires and terminations report.

    Setup:
        - Create employees with hire and termination dates

    Action:
        - Execute report with date range

    Verification:
        - Returns hires and terminations
    """
    with app.app_context():
        empresa = create_company(db_session, "TEST_5", "Company 5", "J0005")

        # Employee hired in date range
        emp1 = create_employee(db_session, empresa_id=empresa.id)
        emp1.fecha_alta = date.today() - timedelta(days=10)

        # Employee terminated in date range
        emp2 = create_employee(db_session, empresa_id=empresa.id)
        emp2.fecha_alta = date.today() - timedelta(days=100)
        emp2.fecha_baja = date.today() - timedelta(days=5)

        db_session.commit()

        report_func = get_system_report("employee_hires_terminations")
        results = report_func(
            {
                "fecha_inicio": (date.today() - timedelta(days=30)).isoformat(),
                "fecha_fin": date.today().isoformat(),
            }
        )

        assert len(results) == 2
        assert "Tipo" in results[0]
        tipos = [r["Tipo"] for r in results]
        assert "Alta" in tipos
        assert "Baja" in tipos


def test_all_system_reports_have_metadata():
    """
    Test that all registered system reports have metadata.

    Setup:
        - None

    Action:
        - Check each report in registry

    Verification:
        - Each has corresponding metadata
    """
    for report_id in SYSTEM_REPORTS.keys():
        metadata = get_system_report_metadata(report_id)
        assert metadata is not None, f"Report {report_id} missing metadata"
        assert "name" in metadata
        assert "category" in metadata
        assert "base_entity" in metadata


def test_system_report_categories():
    """
    Test that system reports have proper categories.

    Setup:
        - None

    Action:
        - Check categories in metadata

    Verification:
        - Categories are valid
    """
    valid_categories = ["employee", "payroll", "vacation"]

    for report_id, metadata in SYSTEM_REPORT_METADATA.items():
        assert "category" in metadata
        assert metadata["category"] in valid_categories, f"Invalid category for {report_id}"


def test_employee_list_report_returns_list(app, db_session):
    """
    Test that employee list report returns a list.

    Setup:
        - None

    Action:
        - Call report with empty parameters

    Verification:
        - Returns empty list (no data)
    """
    with app.app_context():
        report_func = get_system_report("employee_list")
        results = report_func({})

        assert isinstance(results, list)


def test_system_reports_accept_parameters(app, db_session):
    """
    Test that system reports accept parameters dict.

    Setup:
        - None

    Action:
        - Call reports with parameters

    Verification:
        - No errors raised
    """
    with app.app_context():
        report_func = get_system_report("employee_list")

        # Should accept empty parameters
        results1 = report_func({})
        assert isinstance(results1, list)

        # Should accept parameters
        results2 = report_func({"activo": True})
        assert isinstance(results2, list)


def test_vacation_balance_report_structure():
    """
    Test vacation balance report has correct structure.

    Setup:
        - None

    Action:
        - Get metadata

    Verification:
        - Metadata has correct structure
    """
    metadata = get_system_report_metadata("vacation_balance_by_employee")

    assert metadata is not None
    assert metadata["name"] == "Balance de Vacaciones por Empleado"
    assert metadata["category"] == "vacation"
    assert metadata["base_entity"] == "VacationAccount"


def test_payroll_by_period_report_structure():
    """
    Test payroll by period report has correct structure.

    Setup:
        - None

    Action:
        - Get metadata

    Verification:
        - Metadata has correct structure
    """
    metadata = get_system_report_metadata("payroll_by_period")

    assert metadata is not None
    assert metadata["name"] == "Nómina por Período"
    assert metadata["category"] == "payroll"
    assert "parameters" in metadata


# ============================================================================
# EXTENDED SYSTEM REPORTS COVERAGE TESTS
# ============================================================================


def test_payroll_by_period_report_filters_and_coercion(app, db_session):
    """Test date conversion and filtering in payroll_by_period_report."""
    from coati_payroll.model import Nomina

    with app.app_context():
        # Create a Nomina record
        nomina = Nomina(
            id="NOM-2026-07",
            periodo_inicio=date(2026, 7, 1),
            periodo_fin=date(2026, 7, 31),
            estado="Borrador",
            planilla_id="PLANILLA_XYZ",
            total_bruto=1000.0,
            total_deducciones=200.0,
            total_neto=800.0,
        )
        db_session.add(nomina)
        db_session.commit()

        report_func = get_system_report("payroll_by_period")

        # Call with date ISO strings and planilla_id filter
        params = {
            "periodo_inicio": "2026-07-01",
            "periodo_fin": "2026-07-31",
            "planilla_id": "PLANILLA_XYZ"
        }
        results = report_func(params)
        assert len(results) == 1
        assert results[0]["Código"] == "NOM-2026-07"
        assert results[0]["Total Neto"] == 800.0


def test_payroll_employee_detail_report_empty_and_success(app, db_session):
    """Test payroll_employee_detail_report under empty and valid scenarios."""
    from coati_payroll.model import NominaEmpleado, Empleado, Empresa

    with app.app_context():
        report_func = get_system_report("payroll_employee_detail")

        # Test empty/None parameters
        assert report_func({}) == []
        assert report_func({"nomina_id": ""}) == []

        # Create valid test data
        empresa = create_company(db_session, "COMP_EMP_DETAIL", "Comp", "J009")
        emp = create_employee(db_session, empresa_id=empresa.id, primer_nombre="John", primer_apellido="Doe")
        db_session.commit()

        nomina_emp = NominaEmpleado(
            nomina_id="NOM_EMP_DETAIL_ID",
            empleado_id=emp.id,
            sueldo_base_historico=1500.0,
            total_ingresos=200.0,
            salario_bruto=1700.0,
            total_deducciones=100.0,
            salario_neto=1600.0,
        )
        db_session.add(nomina_emp)
        db_session.commit()

        # Test with valid ID
        results = report_func({"nomina_id": "NOM_EMP_DETAIL_ID"})
        assert len(results) == 1
        assert results[0]["Nombre"] == "John Doe"
        assert results[0]["Salario Neto"] == 1600.0


def test_payroll_perceptions_deductions_summaries(app, db_session):
    """Test aggregated perceptions and deductions reports."""
    from coati_payroll.model import NominaDetalle, NominaEmpleado, Empresa
    from coati_payroll.enums import TipoDetalle

    with app.app_context():
        perceptions_func = get_system_report("payroll_perceptions_summary")
        deductions_func = get_system_report("payroll_deductions_summary")

        # Empty parameters
        assert perceptions_func({}) == []
        assert deductions_func({}) == []

        # Create employee, NominaEmpleado, and NominaDetalle
        empresa = create_company(db_session, "COMP_SUMM", "Comp", "J012")
        emp = create_employee(db_session, empresa_id=empresa.id, primer_nombre="Summ", primer_apellido="Test")
        db_session.commit()

        nomina_emp = NominaEmpleado(
            nomina_id="NOM_SUMM_ID",
            empleado_id=emp.id,
            sueldo_base_historico=1000.0,
            salario_bruto=1000.0,
            total_deducciones=0.0,
            salario_neto=1000.0,
        )
        db_session.add(nomina_emp)
        db_session.commit()

        # Create details linked to NominaEmpleado
        det1 = NominaDetalle(
            nomina_empleado_id=nomina_emp.id,
            codigo="PERC_01",
            descripcion="Bonus",
            tipo=TipoDetalle.INGRESO,
            monto=500.0
        )
        det2 = NominaDetalle(
            nomina_empleado_id=nomina_emp.id,
            codigo="DED_01",
            descripcion="Tax",
            tipo=TipoDetalle.DEDUCCION,
            monto=150.0
        )
        db_session.add(det1)
        db_session.add(det2)
        db_session.commit()

        # Test valid perceptions
        perc_results = perceptions_func({"nomina_id": "NOM_SUMM_ID"})
        assert len(perc_results) == 1
        assert perc_results[0]["Código Concepto"] == "PERC_01"
        assert perc_results[0]["Total"] == 500.0

        # Test valid deductions
        ded_results = deductions_func({"nomina_id": "NOM_SUMM_ID"})
        assert len(ded_results) == 1
        assert ded_results[0]["Código Concepto"] == "DED_01"
        assert ded_results[0]["Total"] == 150.0


def test_vacation_taken_by_period_report_iso_conversion(app, db_session):
    """Test date parsing and custom query parameters on vacation taken report."""
    from coati_payroll.model import VacationLedger, VacationAccount, VacationPolicy, Empleado, Empresa

    with app.app_context():
        # Create employee and ledger usage entry
        empresa = create_company(db_session, "COMP_VAC", "Comp", "J010")
        emp = create_employee(db_session, empresa_id=empresa.id, primer_nombre="Vac", primer_apellido="Tester")
        db_session.commit()

        policy = VacationPolicy(nombre="Standard Policy", codigo="STD_VAC")
        db_session.add(policy)
        db_session.commit()

        acc = VacationAccount(
            empleado_id=emp.id,
            policy_id=policy.id,
            current_balance=5.0
        )
        db_session.add(acc)
        db_session.commit()

        ledger = VacationLedger(
            account_id=acc.id,
            empleado_id=emp.id,
            entry_type="usage",
            fecha=date(2026, 8, 15),
            quantity=-5.0,
            source="manual",
            observaciones="Summer vacation"
        )
        ledger_accrual = VacationLedger(
            account_id=acc.id,
            empleado_id=emp.id,
            entry_type="accrual",
            fecha=date(2026, 8, 1),
            quantity=10.0,
            source="manual",
            observaciones="Standard Accrual"
        )
        db_session.add(ledger)
        db_session.add(ledger_accrual)
        db_session.commit()

        report_func = get_system_report("vacation_taken_by_period")

        # Test with date ISO strings
        params = {
            "fecha_inicio": "2026-08-01",
            "fecha_fin": "2026-08-31"
        }
        results = report_func(params)
        assert len(results) == 1
        assert results[0]["Días Usados"] == 5.0
        assert results[0]["Descripción"] == "Summer vacation"


def test_vacation_balance_report_execution(app, db_session):
    """Test execution of vacation_balance_by_employee system report."""
    from coati_payroll.model import VacationAccount, VacationPolicy, Empleado, Empresa, VacationLedger
    from decimal import Decimal

    with app.app_context():
        # Create employee, policy, and account
        empresa = create_company(db_session, "COMP_VAC_BAL", "Comp", "J011")
        emp = create_employee(db_session, empresa_id=empresa.id, primer_nombre="Alice", primer_apellido="Tester")
        db_session.commit()

        policy = VacationPolicy(nombre="Standard Policy", codigo="STD_VAC_BAL")
        db_session.add(policy)
        db_session.commit()

        acc = VacationAccount(
            empleado_id=emp.id,
            policy_id=policy.id,
            current_balance=Decimal("12.5")
        )
        db_session.add(acc)
        db_session.commit()

        # Add an accrual and a usage ledger entry
        ledger_accrual = VacationLedger(
            account_id=acc.id,
            empleado_id=emp.id,
            entry_type="accrual",
            fecha=date(2026, 8, 1),
            quantity=Decimal("15.0"),
            source="manual",
            observaciones="Initial Accrual"
        )
        ledger_usage = VacationLedger(
            account_id=acc.id,
            empleado_id=emp.id,
            entry_type="usage",
            fecha=date(2026, 8, 5),
            quantity=Decimal("-2.5"),
            source="manual",
            observaciones="Taken"
        )
        db_session.add_all([ledger_accrual, ledger_usage])
        db_session.commit()

        report_func = get_system_report("vacation_balance_by_employee")
        results = report_func({})

        assert len(results) == 1
        assert results[0]["Nombre"] == "Alice Tester"
        assert results[0]["Días Acumulados"] == 15.0
        assert results[0]["Días Usados"] == 2.5
        assert results[0]["Balance Días"] == 12.5
