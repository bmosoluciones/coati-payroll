# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for report engine functionality."""

from decimal import Decimal

from coati_payroll.enums import ReportExecutionStatus, ReportStatus, ReportType
from coati_payroll.model import Report, ReportRole
from coati_payroll.report_engine import (
    ALLOWED_ENTITIES,
    ALLOWED_FIELDS,
    ALLOWED_OPERATORS,
    CustomReportBuilder,
    ReportExecutionManager,
    can_execute_report,
    can_export_report,
    can_view_report,
)
from tests.factories.company_factory import create_company
from tests.factories.employee_factory import create_employee


def test_allowed_entities_defined():
    """
    Test that allowed entities are properly defined.

    Setup:
        - None

    Action:
        - Check ALLOWED_ENTITIES

    Verification:
        - Dictionary is not empty
        - Contains expected entities
    """
    assert len(ALLOWED_ENTITIES) > 0
    assert "Employee" in ALLOWED_ENTITIES
    assert "Nomina" in ALLOWED_ENTITIES


def test_allowed_fields_defined():
    """
    Test that allowed fields are properly defined.

    Setup:
        - None

    Action:
        - Check ALLOWED_FIELDS

    Verification:
        - Dictionary is not empty
        - Employee has fields defined
    """
    assert len(ALLOWED_FIELDS) > 0
    assert "Employee" in ALLOWED_FIELDS
    assert len(ALLOWED_FIELDS["Employee"]) > 0
    assert "codigo_empleado" in ALLOWED_FIELDS["Employee"]


def test_allowed_operators_defined():
    """
    Test that allowed operators are properly defined.

    Setup:
        - None

    Action:
        - Check ALLOWED_OPERATORS

    Verification:
        - Dictionary is not empty
        - Contains basic operators
    """
    assert len(ALLOWED_OPERATORS) > 0
    assert "=" in ALLOWED_OPERATORS
    assert "!=" in ALLOWED_OPERATORS
    assert ">" in ALLOWED_OPERATORS
    assert "like" in ALLOWED_OPERATORS


def test_custom_report_builder_valid_definition(app, db_session):
    """
    Test CustomReportBuilder with valid definition.

    Setup:
        - Create a custom report with valid definition

    Action:
        - Create builder and validate

    Verification:
        - Validation returns no errors
    """
    with app.app_context():
        definition = {
            "columns": [
                {"type": "field", "entity": "Employee", "field": "codigo_empleado"},
                {"type": "field", "entity": "Employee", "field": "primer_nombre"},
            ],
            "filters": [{"field": "activo", "operator": "=", "value": True}],
            "sorting": [{"field": "primer_apellido", "direction": "asc"}],
        }

        report = Report(
            name="Valid Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )

        builder = CustomReportBuilder(report)
        errors = builder.validate_definition()

        assert len(errors) == 0


def test_custom_report_builder_invalid_entity(app, db_session):
    """
    Test CustomReportBuilder with invalid entity.

    Setup:
        - Create report with invalid base entity

    Action:
        - Create builder and validate

    Verification:
        - Validation returns error
    """
    with app.app_context():
        report = Report(
            name="Invalid Entity Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="InvalidEntity",
            definition={"columns": []},
        )

        try:
            builder = CustomReportBuilder(report)
            assert builder
            assert False, "Should raise ValueError for invalid entity"
        except ValueError as e:
            assert "Invalid base entity" in str(e)


def test_custom_report_builder_invalid_field(app, db_session):
    """
    Test CustomReportBuilder with invalid field.

    Setup:
        - Create report with invalid field

    Action:
        - Validate definition

    Verification:
        - Validation returns error about invalid field
    """
    with app.app_context():
        definition = {
            "columns": [
                {"type": "field", "entity": "Employee", "field": "invalid_field"},
            ],
        }

        report = Report(
            name="Invalid Field Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )

        builder = CustomReportBuilder(report)
        errors = builder.validate_definition()

        assert len(errors) > 0
        assert any("invalid_field" in error for error in errors)


def test_custom_report_builder_invalid_operator(app, db_session):
    """
    Test CustomReportBuilder with invalid operator.

    Setup:
        - Create report with invalid operator

    Action:
        - Validate definition

    Verification:
        - Validation returns error about invalid operator
    """
    with app.app_context():
        definition = {
            "columns": [
                {"type": "field", "entity": "Employee", "field": "codigo_empleado"},
            ],
            "filters": [{"field": "activo", "operator": "invalid_op", "value": True}],
        }

        report = Report(
            name="Invalid Operator Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )

        builder = CustomReportBuilder(report)
        errors = builder.validate_definition()

        assert len(errors) > 0
        assert any("invalid_op" in error for error in errors)


def test_custom_report_execute_with_data(app, db_session):
    """
    Test executing a custom report with actual data.

    Setup:
        - Create company and employees
        - Create custom report

    Action:
        - Execute report

    Verification:
        - Results contain employee data
    """
    with app.app_context():
        # Create test data
        empresa = create_company(db_session, "TEST_COMP", "Test Company", "J1234")
        emp1 = create_employee(
            db_session,
            empresa_id=empresa.id,
            primer_nombre="Juan",
            primer_apellido="Perez",
            salario_base=Decimal("10000.00"),
        )
        emp2 = create_employee(
            db_session,
            empresa_id=empresa.id,
            primer_nombre="Maria",
            primer_apellido="Garcia",
            salario_base=Decimal("12000.00"),
        )
        assert emp1
        assert emp2
        db_session.commit()

        # Create report
        definition = {
            "columns": [
                {"type": "field", "entity": "Employee", "field": "primer_nombre", "label": "Nombre"},
                {"type": "field", "entity": "Employee", "field": "primer_apellido", "label": "Apellido"},
            ],
            "filters": [],
            "sorting": [{"field": "primer_apellido", "direction": "asc"}],
        }

        report = Report(
            name="Employee List",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )

        builder = CustomReportBuilder(report)
        results, total_count = builder.execute()

        assert total_count == 2
        assert len(results) == 2
        assert results[0]["Apellido"] == "Garcia"  # Sorted by apellido
        assert results[1]["Apellido"] == "Perez"


def test_can_view_report_admin():
    """
    Test admin can view any report.

    Setup:
        - Create report without permissions

    Action:
        - Check if admin can view

    Verification:
        - Returns True
    """
    report = Report(
        name="Test Report",
        type=ReportType.SYSTEM,
        status=ReportStatus.ENABLED,
        base_entity="Employee",
    )

    assert can_view_report(report, "admin") is True


def test_can_view_report_with_permission(app, db_session):
    """
    Test user with permission can view report.

    Setup:
        - Create report with hhrr view permission

    Action:
        - Check if hhrr can view

    Verification:
        - Returns True
    """
    with app.app_context():
        report = Report(
            name="Test Report",
            type=ReportType.SYSTEM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
        )
        db_session.add(report)
        db_session.commit()

        role = ReportRole(
            report_id=report.id,
            role="hhrr",
            can_view=True,
            can_execute=False,
            can_export=False,
        )
        db_session.add(role)
        db_session.commit()

        db_session.refresh(report)

        assert can_view_report(report, "hhrr") is True


def test_can_view_report_without_permission(app, db_session):
    """
    Test user without permission cannot view report.

    Setup:
        - Create report without audit permission

    Action:
        - Check if audit can view

    Verification:
        - Returns False
    """
    with app.app_context():
        report = Report(
            name="Test Report",
            type=ReportType.SYSTEM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
        )
        db_session.add(report)
        db_session.commit()

        assert can_view_report(report, "audit") is False


def test_can_execute_report_admin():
    """
    Test admin can execute any report.

    Setup:
        - Create report

    Action:
        - Check if admin can execute

    Verification:
        - Returns True
    """
    report = Report(
        name="Test Report",
        type=ReportType.SYSTEM,
        status=ReportStatus.ENABLED,
        base_entity="Employee",
    )

    assert can_execute_report(report, "admin") is True


def test_can_export_report_admin():
    """
    Test admin can export any report.

    Setup:
        - Create report

    Action:
        - Check if admin can export

    Verification:
        - Returns True
    """
    report = Report(
        name="Test Report",
        type=ReportType.SYSTEM,
        status=ReportStatus.ENABLED,
        base_entity="Employee",
    )

    assert can_export_report(report, "admin") is True


def test_report_execution_manager(app, db_session):
    """
    Test ReportExecutionManager creates execution records.

    Setup:
        - Create report with data

    Action:
        - Execute report via manager

    Verification:
        - Execution record is created
        - Results are returned
    """
    with app.app_context():
        # Create test data
        empresa = create_company(db_session, "TEST_COMP2", "Test Company 2", "J5678")
        emp1 = create_employee(db_session, empresa_id=empresa.id)
        assert emp1
        db_session.commit()

        # Create report
        definition = {
            "columns": [
                {"type": "field", "entity": "Employee", "field": "codigo_empleado", "label": "Código"},
            ],
            "filters": [],
            "sorting": [],
        }

        report = Report(
            name="Test Execution",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )
        db_session.add(report)
        db_session.commit()

        # Execute via manager
        manager = ReportExecutionManager(report, "test_user")
        results, total_count, execution = manager.execute()

        assert execution.id is not None
        assert execution.status == ReportExecutionStatus.COMPLETED
        assert execution.executed_by == "test_user"
        assert execution.row_count == 1
        assert execution.execution_time_ms > 0
        assert len(results) == 1


# ============================================================================
# EXTENDED REPORT ENGINE COVERAGE TESTS
# ============================================================================


def test_custom_report_builder_invalid_columns(app, db_session):
    """Test validate_definition with non-field columns, invalid entities and fields."""
    with app.app_context():
        definition = {
            "columns": [
                {"type": "expression", "expression": "salario_base * 2", "label": "Double Salary"},
                {"type": "field", "entity": "NonExistentEntity", "field": "invalid_field"},
            ],
            "filters": [{"field": "invalid_filter_field", "operator": "=", "value": "xyz"}],
        }

        report = Report(
            name="Invalid Defs Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )

        builder = CustomReportBuilder(report)
        errors = builder.validate_definition()

        assert len(errors) > 0
        assert not any("Custom expressions are not yet supported" in error for error in errors)
        assert any("Entity 'NonExistentEntity' is not allowed" in error for error in errors)
        assert any("Filter field 'invalid_filter_field' is not allowed" in error for error in errors)


def test_custom_report_builder_invalid_sorting(app, db_session):
    """Test custom report build_query sorts only on allowed fields and pagination."""
    with app.app_context():
        definition = {
            "columns": [{"type": "field", "entity": "Employee", "field": "codigo_empleado", "label": "Code"}],
            "sorting": [
                {"field": "invalid_sort_field", "direction": "asc"},
                {"field": "primer_apellido", "direction": "desc"},
            ],
        }

        report = Report(
            name="Sorting Check Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition=definition,
        )

        builder = CustomReportBuilder(report)
        stmt = builder.build_query(page=2, per_page=5)
        # Query builds successfully without raising exceptions for the invalid sort field
        assert stmt is not None


def test_report_execution_manager_error_tracking(app, db_session, monkeypatch):
    """Test ReportExecutionManager error tracking and message truncation."""
    with app.app_context():
        # Create a report that points to a non-existent system report ID to trigger failure
        report = Report(
            name="Broken System Report",
            type=ReportType.SYSTEM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            system_report_id="extremely_long_unregistered_id_xyz_123",
        )
        db_session.add(report)
        db_session.commit()

        manager = ReportExecutionManager(report, "failing_user")

        # Expect manager.execute to raise ValueError and save FAILED status
        import pytest

        with pytest.raises(ValueError, match="System report .* not found"):
            manager.execute()

        from coati_payroll.model import ReportExecution

        execution = db_session.query(ReportExecution).filter_by(executed_by="failing_user").first()
        assert execution is not None
        assert execution.status == ReportExecutionStatus.FAILED
        assert "not found" in execution.error_message


def test_report_execution_scope_is_preserved_for_sync_and_async_jobs(app, db_session):
    """A report run cannot expose employees from another company."""
    from coati_payroll.queue.tasks import generate_report

    with app.app_context():
        first = create_company(db_session, "REPORT_SCOPE_A", "Report A", "R-SCOPE-A")
        second = create_company(db_session, "REPORT_SCOPE_B", "Report B", "R-SCOPE-B")
        first_employee = create_employee(db_session, first.id, codigo="REPORT-A")
        create_employee(db_session, second.id, codigo="REPORT-B")
        report = Report(
            name="Scoped employees",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
            definition={
                "columns": [{"type": "field", "field": "codigo_empleado", "label": "Código"}],
            },
        )
        db_session.add(report)
        db_session.commit()

        manager_result, manager_total, _execution = ReportExecutionManager(report, "scoped-user", {first.id}).execute()
        async_result = generate_report(report.id, "scoped-user", {}, [first.id])

        assert manager_total == 1
        assert manager_result == [{"Código": first_employee.codigo_empleado}]
        assert async_result["success"] is True
        assert async_result["rows"] == 1


def test_non_admin_report_permissions(app, db_session):
    """Test non-admin view, execute, and export role permissions."""
    with app.app_context():
        report = Report(
            name="Perm Restricted Report",
            type=ReportType.CUSTOM,
            status=ReportStatus.ENABLED,
            base_entity="Employee",
        )
        db_session.add(report)
        db_session.commit()

        # No roles added yet, non-admin should have no permissions
        assert can_view_report(report, "hhrr") is False
        assert can_execute_report(report, "hhrr") is False
        assert can_export_report(report, "hhrr") is False

        # Add explicit permissions
        role_perm = ReportRole(report_id=report.id, role="hhrr", can_view=True, can_execute=True, can_export=True)
        db_session.add(role_perm)
        db_session.commit()
        db_session.refresh(report)

        assert can_view_report(report, "hhrr") is True
        assert can_execute_report(report, "hhrr") is True
        assert can_export_report(report, "hhrr") is True
