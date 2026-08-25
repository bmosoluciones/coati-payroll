# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for perception calculation snapshots."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from coati_payroll.nomina_engine.calculators.perception_calculator import PerceptionCalculator


def test_perception_snapshot_preserves_taxability_after_catalog_change():
    """A recalculation must keep the tax treatment captured in its snapshot."""
    concept_calculator = Mock()
    concept_calculator.calculate.return_value = Decimal("100.00")
    calculator = PerceptionCalculator(concept_calculator)
    calculator.percepciones_snapshot = {"percepcion-1": {"gravable": False}}

    # The live catalog was subsequently changed to taxable.
    percepcion = SimpleNamespace(
        id="percepcion-1",
        codigo="BONO",
        nombre="Bono",
        activo=True,
        gravable=True,
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        porcentaje=None,
        formula=None,
        base_calculo=None,
    )
    association = SimpleNamespace(
        activo=True,
        percepcion=percepcion,
        monto_predeterminado=None,
        porcentaje=None,
        orden=1,
    )

    item = calculator._calculate_item(association, SimpleNamespace(), None)

    assert item is not None
    assert item.gravable is False


def test_perception_snapshot_preserves_calculation_unit_after_catalog_change():
    """The formula input unit must come from the historical catalog snapshot."""
    concept_calculator = Mock()
    concept_calculator.calculate.return_value = Decimal("100.00")
    calculator = PerceptionCalculator(concept_calculator)
    calculator.percepciones_snapshot = {"percepcion-1": {"unidad_calculo": "dias"}}

    percepcion = SimpleNamespace(
        id="percepcion-1",
        codigo="BONO",
        nombre="Bono",
        activo=True,
        gravable=True,
        formula_tipo="fixed",
        monto_default=Decimal("100.00"),
        porcentaje=None,
        formula=None,
        base_calculo=None,
        unidad_calculo="horas",
    )
    association = SimpleNamespace(
        activo=True,
        percepcion=percepcion,
        monto_predeterminado=None,
        porcentaje=None,
        orden=1,
    )

    calculator._calculate_item(association, SimpleNamespace(), None)

    assert concept_calculator.calculate.call_args.kwargs["unidad_calculo"] == "dias"
