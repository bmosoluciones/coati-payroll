# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for taxable-base deduction classification."""

from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.domain.calculation_items import DeduccionItem


def test_tax_with_before_tax_flag_does_not_reduce_the_taxable_base_again():
    """A retained tax is not a pre-tax deduction even when its default flag is true."""
    calculator = ConceptCalculator(config_repository=None, warnings=[])
    calculator.deducciones_snapshot = {
        "seguro": {"antes_impuesto": True, "es_impuesto": False},
        "impuesto": {"antes_impuesto": True, "es_impuesto": True},
    }
    employee_calculation = SimpleNamespace(
        deducciones=[
            DeduccionItem(
                codigo="SEGURO",
                nombre="Seguro social",
                monto=Decimal("100.00"),
                prioridad=1,
                es_obligatoria=True,
                deduccion_id="seguro",
            ),
            DeduccionItem(
                codigo="IR",
                nombre="Impuesto",
                monto=Decimal("50.00"),
                prioridad=2,
                es_obligatoria=True,
                deduccion_id="impuesto",
            ),
        ]
    )

    assert calculator._calculate_pre_tax_deductions(employee_calculation) == Decimal("100.00")
