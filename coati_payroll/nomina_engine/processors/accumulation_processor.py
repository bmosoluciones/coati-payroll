# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Accumulation processor for annual accumulated values."""

from __future__ import annotations

from datetime import date
from typing import Any

from coati_payroll.model import db, Deduccion
from coati_payroll.i18n import _
from ..domain.employee_calculation import EmpleadoCalculo
from ..repositories.acumulado_repository import AcumuladoRepository
from ..validators import ValidationError


class AccumulationProcessor:
    """Processor for updating accumulated annual values."""

    def __init__(self, acumulado_repository: AcumuladoRepository):
        self.acumulado_repo = acumulado_repository

    def update_accumulations(
        self,
        emp_calculo: EmpleadoCalculo,
        planilla: Any,
        periodo_inicio: date,
        periodo_fin: date,
        deducciones_snapshot: dict[str, dict] | None = None,
        empresa_primer_mes_nomina: int | None = None,
        empresa_primer_anio_nomina: int | None = None,
    ) -> None:
        """Update accumulated annual values for the employee."""
        if not planilla.tipo_planilla:
            return

        tipo_planilla = planilla.tipo_planilla
        empleado = emp_calculo.empleado

        # Calculate fiscal period based on period end (when earnings are realized)
        anio = periodo_fin.year
        mes_inicio = int(planilla.mes_inicio_fiscal or tipo_planilla.mes_inicio_fiscal)
        dia_inicio = tipo_planilla.dia_inicio_fiscal

        # A fiscal year can start in the middle of a month.  Comparing only
        # the month assigns (for example) July 1-14 to a fiscal year that
        # does not start until July 15, mixing that payroll with future
        # accumulations.
        if periodo_fin < date(anio, mes_inicio, dia_inicio):
            anio -= 1

        periodo_fiscal_inicio = date(anio, mes_inicio, dia_inicio)

        # Determine empresa_id
        empresa_id = planilla.empresa_id or empleado.empresa_id
        if not empresa_id:
            raise ValidationError(
                _("No se puede crear acumulado anual: ni la planilla ni el empleado tienen empresa_id asignado")
            )

        # Get or create accumulated record
        acumulado = self.acumulado_repo.get_or_create(
            empleado=empleado,
            tipo_planilla_id=tipo_planilla.id,
            empresa_id=empresa_id,
            periodo_fiscal_inicio=periodo_fiscal_inicio,
            periodo_inicio=periodo_inicio,
            empresa_primer_mes_nomina=empresa_primer_mes_nomina,
            empresa_primer_anio_nomina=empresa_primer_anio_nomina,
            fiscal_start_month=mes_inicio,
            periodos_por_anio=int(tipo_planilla.periodos_por_anio or 12),
        )

        # Reset monthly accumulation if entering a new month
        acumulado.reset_mes_acumulado_if_needed(periodo_fin)

        # Update accumulated values
        acumulado.salario_bruto_acumulado += emp_calculo.salario_bruto
        acumulado.salario_acumulado_mes += emp_calculo.salario_bruto
        acumulado.periodos_procesados += 1
        acumulado.ultimo_periodo_procesado = periodo_fin

        acumulado.salario_gravable_acumulado += emp_calculo.salario_gravable

        # Sum up before-tax deductions and taxes
        for deduccion in emp_calculo.deducciones:
            if not deduccion.deduccion_id:
                continue
            deduccion_metadata = deducciones_snapshot.get(deduccion.deduccion_id) if deducciones_snapshot else None
            if not deduccion_metadata:
                deduccion_obj = db.session.get(Deduccion, deduccion.deduccion_id)
                if deduccion_obj:
                    deduccion_metadata = {
                        "es_impuesto": deduccion_obj.es_impuesto,
                        "antes_impuesto": deduccion_obj.antes_impuesto,
                    }
            if not deduccion_metadata:
                continue
            if deduccion_metadata.get("es_impuesto"):
                acumulado.impuesto_retenido_acumulado += deduccion.monto
            elif deduccion_metadata.get("antes_impuesto"):
                acumulado.deducciones_antes_impuesto_acumulado += deduccion.monto
