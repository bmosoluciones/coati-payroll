"""Regression tests for safe report expressions and PDF output."""

from decimal import Decimal

from coati_payroll.model import Empleado, Report
from coati_payroll.report_engine import CustomReportBuilder
from coati_payroll.report_export import ReportExporter


def test_custom_report_expression_is_safe_and_calculated(app, db_session):
    with app.app_context():
        report = Report(
            name="Expression Report",
            base_entity="Employee",
            definition={"columns": [
                {"type": "field", "field": "salario_base"},
                {"type": "expression", "expression": "salario_base * 2", "label": "double"},
            ]},
        )
        builder = CustomReportBuilder(report)
        assert builder.validate_definition() == []
        employee = Empleado(salario_base=Decimal("100.00"))
        assert builder._serialize_results([employee]) == [{"salario_base": 100.0, "double": 200.0}]


def test_expression_can_use_allowed_hidden_field(app, db_session):
    report = Report(
        name="Hidden Field Expression Report",
        base_entity="Employee",
        definition={"columns": [{"type": "expression", "expression": "salario_base * 2", "label": "double"}]},
    )
    employee = Empleado(salario_base=Decimal("100.00"))
    assert CustomReportBuilder(report)._serialize_results([employee]) == [{"double": 200.0}]


def test_custom_report_rejects_unsafe_expression(app, db_session):
    report = Report(
        name="Unsafe Expression Report",
        base_entity="Employee",
        definition={"columns": [{"type": "expression", "expression": "__import__('os')"}]},
    )
    errors = CustomReportBuilder(report).validate_definition()
    assert any("Invalid expression" in error for error in errors)


def test_report_exporter_writes_pdf(tmpdir):
    path = str(tmpdir.join("report.pdf"))
    result = ReportExporter("Payroll", [{"Employee": "A", "Net": "100.00"}]).to_pdf(path)
    assert result == path
    assert open(path, "rb").read(4) == b"%PDF"
