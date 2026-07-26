# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Employee calculation domain models."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from coati_payroll.model import Empleado, Planilla
from .calculation_items import DeduccionItem, PercepcionItem, PrestacionItem


class EmpleadoCalculo:
    """Container for employee calculation data during payroll processing.

    This is a mutable container used during payroll processing.
    For backward compatibility, this class maintains the same interface
    as the original implementation.
    """

    def __init__(self, empleado: Empleado, planilla: Planilla):
        self.empleado = empleado
        self.planilla = planilla
        self.salario_base = Decimal(str(empleado.salario_base or 0))
        self.salario_mensual = Decimal(str(empleado.salario_base or 0))
        self.percepciones: list[PercepcionItem] = []
        self.deducciones: list[DeduccionItem] = []
        self.prestaciones: list[PrestacionItem] = []
        self.total_percepciones = Decimal("0.00")
        self.total_deducciones = Decimal("0.00")
        self.total_prestaciones = Decimal("0.00")
        self.salario_bruto = Decimal("0.00")
        self.salario_gravable = Decimal("0.00")
        self.salario_neto = Decimal("0.00")
        self.tipo_cambio = Decimal("1.00")
        self.moneda_origen_id = empleado.moneda_id
        self.inasistencia_dias = Decimal("0.00")
        self.inasistencia_horas = Decimal("0.00")
        self.inasistencia_descuento = Decimal("0.00")
        self.novedades: dict[str, Decimal] = {}
        self.inasistencia_dias = Decimal("0.00")
        self.inasistencia_horas = Decimal("0.00")
        self.inasistencia_descuento = Decimal("0.00")
        self.salario_neto_inasistencia = Decimal("0.00")
        self.inasistencia_codigos_descuento: set[str] = set()
        self.variables_calculo: dict[str, Any] = {}
        self.vacaciones_resumen: dict[str, Any] | None = None


# Alias for backward compatibility
EmployeeCalculation = EmpleadoCalculo
