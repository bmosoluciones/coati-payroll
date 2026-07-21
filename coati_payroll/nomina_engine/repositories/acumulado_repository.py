# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Repository for AcumuladoAnual operations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from coati_payroll.model import AcumuladoAnual, Empleado
from .base_repository import BaseRepository


class AcumuladoRepository(BaseRepository[AcumuladoAnual]):
    """Repository for AcumuladoAnual operations."""

    def get_by_id(self, acumulado_id: str) -> Optional[AcumuladoAnual]:
        """Get acumulado by ID."""
        return self.session.get(AcumuladoAnual, acumulado_id)

    def get_or_create(
        self,
        empleado: Empleado,
        tipo_planilla_id: str,
        empresa_id: str,
        periodo_fiscal_inicio: date,
        periodo_inicio: date | None = None,
        empresa_primer_mes_nomina: int | None = None,
        empresa_primer_anio_nomina: int | None = None,
        fiscal_start_month: int = 1,
        periodos_por_anio: int = 12,
    ) -> AcumuladoAnual:
        """Get or create acumulado for employee and fiscal period."""
        from sqlalchemy import select

        acumulado = (
            self.session.execute(
                select(AcumuladoAnual).filter(
                    AcumuladoAnual.empleado_id == empleado.id,
                    AcumuladoAnual.tipo_planilla_id == tipo_planilla_id,
                    AcumuladoAnual.empresa_id == empresa_id,
                    AcumuladoAnual.periodo_fiscal_inicio == periodo_fiscal_inicio,
                )
            )
            .unique()
            .scalar_one_or_none()
        )

        if not acumulado:
            from decimal import Decimal

            periodo_fiscal_fin = date(
                periodo_fiscal_inicio.year + 1, periodo_fiscal_inicio.month, periodo_fiscal_inicio.day
            )

            salario_inicial_acumulado = Decimal("0.00")
            impuesto_retenido_inicial = Decimal("0.00")
            periodos_iniciales = 0

            if self._is_initial_company_period(
                periodo_inicio=periodo_inicio,
                empresa_primer_mes_nomina=empresa_primer_mes_nomina,
                empresa_primer_anio_nomina=empresa_primer_anio_nomina,
            ):
                salario_inicial_acumulado = Decimal(str(empleado.salario_acumulado or 0))
                impuesto_retenido_inicial = Decimal(str(empleado.impuesto_acumulado or 0))
                periodos_iniciales = self._calculate_initial_processed_periods(
                    periodo_inicio=periodo_inicio,
                    fiscal_start_month=fiscal_start_month,
                    periodos_por_anio=periodos_por_anio,
                )

            acumulado = AcumuladoAnual(
                empleado_id=empleado.id,
                tipo_planilla_id=tipo_planilla_id,
                empresa_id=empresa_id,
                periodo_fiscal_inicio=periodo_fiscal_inicio,
                periodo_fiscal_fin=periodo_fiscal_fin,
                salario_bruto_acumulado=salario_inicial_acumulado,
                salario_gravable_acumulado=Decimal("0.00"),
                deducciones_antes_impuesto_acumulado=Decimal("0.00"),
                impuesto_retenido_acumulado=impuesto_retenido_inicial,
                periodos_procesados=periodos_iniciales,
                salario_acumulado_mes=Decimal("0.00"),
            )
            self.session.add(acumulado)

        return acumulado

    def save(self, acumulado: AcumuladoAnual) -> AcumuladoAnual:
        """Save acumulado."""
        self.session.add(acumulado)
        return acumulado

    def _is_initial_company_period(
        self,
        periodo_inicio: date | None,
        empresa_primer_mes_nomina: int | None,
        empresa_primer_anio_nomina: int | None,
    ) -> bool:
        """Return True when payroll period matches company's configured first period."""
        if periodo_inicio is None:
            return False

        if empresa_primer_mes_nomina is None or empresa_primer_anio_nomina is None:
            return False

        return periodo_inicio.month == int(empresa_primer_mes_nomina) and periodo_inicio.year == int(
            empresa_primer_anio_nomina
        )

    def _calculate_initial_processed_periods(
        self,
        periodo_inicio: date | None,
        fiscal_start_month: int,
        periodos_por_anio: int,
    ) -> int:
        """Calculate initial processed periods from fiscal calendar and periodicity."""
        if periodo_inicio is None:
            return 0

        if fiscal_start_month < 1 or fiscal_start_month > 12:
            return 0

        if periodos_por_anio <= 0:
            return 0

        fiscal_start_year = (
            periodo_inicio.year if periodo_inicio.month >= fiscal_start_month else periodo_inicio.year - 1
        )
        meses_cerrados_previos = max(
            0,
            (periodo_inicio.year - fiscal_start_year) * 12 + (periodo_inicio.month - fiscal_start_month),
        )
        return (meses_cerrados_previos * periodos_por_anio) // 12
