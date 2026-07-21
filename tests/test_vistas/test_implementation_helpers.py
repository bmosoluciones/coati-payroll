# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for implementation helper services."""

from coati_payroll.model import Deduccion, Empresa, Percepcion, Prestacion, VacationPolicy
from coati_payroll.vistas.implementation_helpers import import_accounting_configuration_rows


def test_import_accounting_configuration_uses_visible_names_and_updates_accounts(app, db_session):
    """Import should map rows by visible names and update accounting fields."""
    with app.app_context():
        company = Empresa(codigo="COMP01", razon_social="Empresa Visible", ruc="RUC-001")
        earning = Percepcion(codigo="ING01", nombre="Salario Base")
        deduction = Deduccion(codigo="DED01", nombre="Seguro Social")
        benefit = Prestacion(codigo="PRE01", nombre="INSS Patronal")
        policy = VacationPolicy(codigo="VAC01", nombre="Vacaciones Administrativas")

        db_session.add_all([company, earning, deduction, benefit, policy])
        db_session.commit()

        rows = [
            [
                "type",
                "id",
                "debit account",
                "debit account description",
                "credit account",
                "credit account description",
            ],
            ["company", "Empresa Visible", "111", "Debe Empresa", "211", "Haber Empresa"],
            ["earnings", "Salario Base", "112", "Debe Ingreso", "212", "Haber Ingreso"],
            ["deductions", "Seguro Social", "113", "Debe Deduccion", "213", "Haber Deduccion"],
            ["benefits", "INSS Patronal", "114", "Debe Prestacion", "214", "Haber Prestacion"],
            ["vacation_policy", "Vacaciones Administrativas", "115", "Debe Vac", "215", "Haber Vac"],
            ["earnings", "No Existe", "199", "Skip", "299", "Skip"],
        ]

        result = import_accounting_configuration_rows(rows)

        assert result.updated_rows == 5
        assert result.skipped_rows == 1

        db_session.refresh(company)
        db_session.refresh(earning)
        db_session.refresh(deduction)
        db_session.refresh(benefit)
        db_session.refresh(policy)

        assert company.codigo_cuenta_debe_salario == "111"
        assert company.descripcion_cuenta_debe_salario == "Debe Empresa"
        assert company.codigo_cuenta_haber_salario == "211"
        assert company.descripcion_cuenta_haber_salario == "Haber Empresa"

        assert earning.codigo_cuenta_debe == "112"
        assert earning.descripcion_cuenta_debe == "Debe Ingreso"
        assert earning.codigo_cuenta_haber == "212"
        assert earning.descripcion_cuenta_haber == "Haber Ingreso"

        assert deduction.codigo_cuenta_debe == "113"
        assert deduction.descripcion_cuenta_debe == "Debe Deduccion"
        assert deduction.codigo_cuenta_haber == "213"
        assert deduction.descripcion_cuenta_haber == "Haber Deduccion"

        assert benefit.codigo_cuenta_debe == "114"
        assert benefit.descripcion_cuenta_debe == "Debe Prestacion"
        assert benefit.codigo_cuenta_haber == "214"
        assert benefit.descripcion_cuenta_haber == "Haber Prestacion"

        assert policy.cuenta_debito_vacaciones_pagadas == "115"
        assert policy.descripcion_cuenta_debito_vacaciones_pagadas == "Debe Vac"
        assert policy.cuenta_credito_vacaciones_pagadas == "215"
        assert policy.descripcion_cuenta_credito_vacaciones_pagadas == "Haber Vac"
