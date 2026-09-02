# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Salary calculator for payroll processing."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from types import SimpleNamespace

from coati_payroll.model import Planilla, ConfiguracionCalculos
from ..repositories.config_repository import ConfigRepository


class SalaryCalculator:
    """Calculator for salary period calculations."""

    def __init__(self, config_repository: ConfigRepository):
        self.config_repo = config_repository

    def calculate_period_salary(
        self,
        salario_mensual: Decimal,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        _fecha_calculo: date,
        fecha_alta: date | None = None,
        fecha_baja: date | None = None,
        configuracion_snapshot: dict[str, Any] | None = None,
        rounding: bool = True,
    ) -> Decimal:
        """Calculate salary for the pay period based on actual days."""
        from ..validators import ValidationError

        if not planilla or not planilla.tipo_planilla:
            raise ValidationError("No se puede calcular salario: planilla o tipo_planilla no disponibles.")

        if not periodo_fin or not periodo_inicio:
            raise ValidationError("No se puede calcular salario: periodo_inicio o periodo_fin no disponibles.")

        dias_periodo = (periodo_fin - periodo_inicio).days + 1

        if dias_periodo <= 0:
            raise ValidationError(f"Período inválido: inicio ({periodo_inicio}) posterior a fin ({periodo_fin})")
        if dias_periodo > 366:
            raise ValidationError(
                f"Período excesivamente largo: {dias_periodo} días. Los períodos no deben exceder 366 días."
            )

        tipo_planilla = planilla.tipo_planilla
        periodicidad = tipo_planilla.periodicidad.lower() if tipo_planilla.periodicidad else ""

        # Support both English and Spanish terms for periodicidad
        # "mensual" and "monthly" both mean monthly payroll
        # "quincenal" and "biweekly" both mean biweekly payroll

        if periodicidad in ("mensual", "monthly"):
            is_first_of_month = periodo_inicio.day == 1
            next_day = periodo_fin + timedelta(days=1)
            is_last_of_month = next_day.day == 1
            same_month = periodo_inicio.year == periodo_fin.year and periodo_inicio.month == periodo_fin.month

            if is_first_of_month and is_last_of_month and same_month:
                salario_periodo = salario_mensual
            else:
                config = self._get_config(planilla.empresa_id, configuracion_snapshot)
                dias_base = Decimal(str(config.dias_mes_nomina))
                if dias_base <= 0:
                    raise ValidationError("Configuración inválida: dias_mes_nomina debe ser mayor a 0.")
                salario_diario = salario_mensual / dias_base
                salario_periodo = salario_diario * Decimal(str(dias_periodo))

        elif periodicidad in ("quincenal", "biweekly"):
            # A complete configured biweekly period pays half the monthly
            # salary. Short/catch-up periods must instead be prorated by days;
            # otherwise a 10-day period incorrectly pays a full fortnight.
            dias_quincena = int(getattr(tipo_planilla, "dias", 15) or 15)
            if dias_periodo == dias_quincena:
                salario_periodo = salario_mensual / Decimal("2")
            else:
                config = self._get_config(planilla.empresa_id, configuracion_snapshot)
                dias_base = Decimal(str(config.dias_mes_nomina))
                if dias_base <= 0:
                    raise ValidationError("Configuración inválida: dias_mes_nomina debe ser mayor a 0.")
                salario_periodo = (salario_mensual / dias_base) * Decimal(str(dias_periodo))

        else:
            config = self._get_config(planilla.empresa_id, configuracion_snapshot)
            dias_base = Decimal(str(config.dias_mes_nomina))
            if dias_base <= 0:
                raise ValidationError("Configuración inválida: dias_mes_nomina debe ser mayor a 0.")
            salario_diario = salario_mensual / dias_base
            salario_periodo = salario_diario * Decimal(str(dias_periodo))

        # Prorate by effective worked days in the payroll period.
        inicio_laborado = max(periodo_inicio, fecha_alta) if fecha_alta else periodo_inicio
        fin_laborado = min(periodo_fin, fecha_baja) if fecha_baja else periodo_fin
        dias_laborados = (fin_laborado - inicio_laborado).days + 1

        if dias_laborados <= 0:
            return Decimal("0.00")

        if dias_laborados < dias_periodo:
            factor_prorrateo = Decimal(str(dias_laborados)) / Decimal(str(dias_periodo))
            salario_periodo = salario_periodo * factor_prorrateo

        if rounding:
            salario_periodo = salario_periodo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return salario_periodo

    def _get_config(self, empresa_id: str, configuracion_snapshot: dict[str, Any] | None) -> Any:
        if configuracion_snapshot:
            return SimpleNamespace(**configuracion_snapshot)

        return self.config_repo.get_for_empresa(empresa_id)

    def calculate_hourly_rate(self, salario_mensual: Decimal, config: ConfiguracionCalculos) -> Decimal:
        """Calculate hourly rate from monthly salary."""
        from ..validators import ValidationError

        dias_base = Decimal(str(config.dias_mes_nomina))
        horas_dia = Decimal(str(config.horas_jornada_diaria))
        if dias_base <= 0 or horas_dia <= 0:
            raise ValidationError(
                "Configuración inválida: dias_mes_nomina y horas_jornada_diaria deben ser mayores a 0."
            )
        return (salario_mensual / dias_base / horas_dia).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
