# SPDX-License-Identifier: Apache-2.0 \r\n # SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
# Copyright 2025 - 2026 BMO Soluciones, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Concept calculator using Strategy pattern."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from coati_payroll.enums import FormulaType
from coati_payroll.formula_engine import FormulaEngine, FormulaEngineError
from coati_payroll.model import db, Deduccion, Prestacion, Percepcion, ReglaCalculo
from ..domain.employee_calculation import EmpleadoCalculo
from ..results.warning_collector import WarningCollectorProtocol


class ConceptCalculator:
    """Calculator for payroll concepts using Strategy pattern."""

    def __init__(self, config_repository, warnings: WarningCollectorProtocol):
        self.config_repo = config_repository
        self.warnings = warnings
        self.deducciones_snapshot: dict[str, Any] | None = None
        self.configuracion_snapshot: dict[str, Any] | None = None

    def calculate(
        self,
        emp_calculo: EmpleadoCalculo,
        formula_tipo: str,
        monto_default: Decimal | None,
        porcentaje: Decimal | None,
        formula: dict | None,
        monto_override: Decimal | None,
        porcentaje_override: Decimal | None,
        codigo_concepto: str | None = None,
        base_calculo: str | None = None,
        unidad_calculo: str | None = None,
    ) -> Decimal:
        """Calculate concept amount."""
        normalized_formula_tipo = FormulaType.normalize(formula_tipo)
        # Use overrides if provided
        if monto_override:
            monto_calculado = Decimal(str(monto_override))
        elif porcentaje_override:
            monto_calculado = (emp_calculo.salario_base * Decimal(str(porcentaje_override)) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            match normalized_formula_tipo or formula_tipo:
                case FormulaType.FIJO:
                    monto_calculado = Decimal(str(monto_default or 0))

                case FormulaType.PORCENTAJE_SALARIO | FormulaType.PORCENTAJE:
                    if porcentaje:
                        monto_calculado = (
                            emp_calculo.salario_base * Decimal(str(porcentaje)) / Decimal("100")
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        monto_calculado = Decimal("0.00")

                case FormulaType.PORCENTAJE_BRUTO:
                    if porcentaje:
                        monto_calculado = (
                            emp_calculo.salario_bruto * Decimal(str(porcentaje)) / Decimal("100")
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        monto_calculado = Decimal("0.00")

                case FormulaType.HORAS:
                    monto_calculado = self._calculate_hours(emp_calculo, porcentaje, codigo_concepto, base_calculo)

                case FormulaType.DIAS:
                    monto_calculado = self._calculate_days(emp_calculo, porcentaje, codigo_concepto, base_calculo)

                case FormulaType.FORMULA:
                    monto_calculado = self._calculate_formula(emp_calculo, formula, codigo_concepto)

                case FormulaType.REGLA_CALCULO:
                    monto_calculado = self._calculate_regla_calculo(emp_calculo, codigo_concepto)

                case _:
                    monto_calculado = Decimal(str(monto_default or 0))

        # Ensure calculated amounts are never negative
        if monto_calculado < 0:
            self.warnings.append(
                f"Concepto '{codigo_concepto or 'desconocido'}': ConfiguraciÃ³n incorrecta resultÃ³ en "
                f"monto negativo ({monto_calculado}). Ajustando a 0.00. "
                f"Verifique la configuraciÃ³n del concepto (porcentaje o monto)."
            )
            return Decimal("0.00")

        return monto_calculado

    def _calculate_hours(
        self,
        emp_calculo: EmpleadoCalculo,
        porcentaje: Decimal | None,
        codigo_concepto: str | None,
        base_calculo: str | None,
    ) -> Decimal:
        """Calculate based on hours."""
        if not codigo_concepto or codigo_concepto not in emp_calculo.novedades:
            return Decimal("0.00")

        horas = emp_calculo.novedades[codigo_concepto]
        if horas <= 0:
            return Decimal("0.00")

        # Determine base for calculation
        if base_calculo == "salario_bruto":
            base = emp_calculo.salario_bruto
        else:
            base = emp_calculo.salario_mensual

        # Calculate hourly rate using configuration
        config = self._get_config(emp_calculo.planilla.empresa_id)
        dias_base = Decimal(str(config.dias_mes_nomina))
        horas_dia = Decimal(str(config.horas_jornada_diaria))
        tasa_hora = (base / dias_base / horas_dia).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Apply percentage
        if porcentaje:
            tasa_hora = (tasa_hora * Decimal(str(porcentaje)) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Calculate total for hours
        return (tasa_hora * horas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _calculate_days(
        self,
        emp_calculo: EmpleadoCalculo,
        porcentaje: Decimal | None,
        codigo_concepto: str | None,
        base_calculo: str | None,
    ) -> Decimal:
        """Calculate based on days."""
        if not codigo_concepto or codigo_concepto not in emp_calculo.novedades:
            return Decimal("0.00")

        dias = emp_calculo.novedades[codigo_concepto]
        if dias <= 0:
            return Decimal("0.00")

        # Determine base for calculation
        if base_calculo == "salario_bruto":
            base = emp_calculo.salario_bruto
        else:
            base = emp_calculo.salario_mensual

        # Calculate daily rate using configuration
        config = self._get_config(emp_calculo.planilla.empresa_id)
        dias_base = Decimal(str(config.dias_mes_nomina))
        tasa_dia = (base / dias_base).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Apply percentage
        if porcentaje:
            tasa_dia = (tasa_dia * Decimal(str(porcentaje)) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Calculate total for days
        return (tasa_dia * dias).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _calculate_formula(
        self, emp_calculo: EmpleadoCalculo, formula: dict | None, codigo_concepto: str | None
    ) -> Decimal:
        """Calculate using formula engine."""
        if not formula or not isinstance(formula, dict):
            return Decimal("0.00")

        try:
            # Merge variables with formula inputs
            inputs = {**emp_calculo.variables_calculo}
            inputs["salario_bruto"] = emp_calculo.salario_bruto
            inputs["salario_gravable"] = emp_calculo.salario_gravable
            inputs["salario_gravable_periodo"] = emp_calculo.salario_gravable
            inputs["total_percepciones"] = emp_calculo.total_percepciones
            inputs["total_deducciones"] = emp_calculo.total_deducciones

            # Map generic formula input sources to input names when present
            for input_def in formula.get("inputs", []) if isinstance(formula.get("inputs"), list) else []:
                name = input_def.get("name")
                source = input_def.get("source")
                if not name or not source:
                    continue
                if source in inputs:
                    inputs[name] = inputs[source]
                    continue
                # Support dotted notation for potential namespaced sources (e.g., "novedad.HORAS_EXTRA")
                # Extract the last segment after the final dot as a fallback lookup key
                if "." in source:
                    source_key = source.split(".")[-1]
                    if source_key in inputs:
                        inputs[name] = inputs[source_key]

            # Calculate before-tax deductions already processed in this period
            deducciones_antes_impuesto_periodo = Decimal("0.00")
            for ded in emp_calculo.deducciones:
                if not ded.deduccion_id:
                    continue
                ded_metadata = self._get_deduccion_metadata(ded.deduccion_id)
                if ded_metadata and ded_metadata.get("antes_impuesto"):
                    deducciones_antes_impuesto_periodo += ded.monto
            inputs["deducciones_antes_impuesto_periodo"] = deducciones_antes_impuesto_periodo
            # Legacy alias for backward compatibility (deprecated but kept to avoid breaking existing schemas)
            inputs["inss_periodo"] = deducciones_antes_impuesto_periodo
            # New generic aliases (preferred for new schemas)
            inputs["pre_tax_deductions"] = deducciones_antes_impuesto_periodo
            inputs["social_security_deduction"] = deducciones_antes_impuesto_periodo

            engine = FormulaEngine(formula)
            result = engine.execute(inputs)
            return Decimal(str(result.get("output", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except FormulaEngineError as e:
            self.warnings.append(f"Error en f\u00f3rmula: {str(e)}")
            return Decimal("0.00")

    def _calculate_regla_calculo(self, emp_calculo: EmpleadoCalculo, codigo_concepto: str | None) -> Decimal:
        """Calculate using ReglaCalculo from snapshot (if available) or live DB."""
        # First try to get ReglaCalculo from snapshot (for reproducibility)
        regla_schema = None
        regla_codigo = None
        if self.deducciones_snapshot and codigo_concepto:
            deduccion_data = self.deducciones_snapshot.get(codigo_concepto)
            if deduccion_data and "regla_calculo" in deduccion_data:
                regla_schema = deduccion_data["regla_calculo"]["esquema_json"]
                regla_codigo = deduccion_data["regla_calculo"]["codigo"]
        # Fallback to live DB if not in snapshot (backward compatibility)
        if not regla_schema:
            from sqlalchemy import select, or_

            regla = None
            # If caller passed a concept ID, try direct FK matches first.
            if codigo_concepto:
                regla = db.session.execute(
                    select(ReglaCalculo).filter(
                        ReglaCalculo.activo.is_(True),
                        or_(
                            ReglaCalculo.deduccion_id == codigo_concepto,
                            ReglaCalculo.prestacion_id == codigo_concepto,
                            ReglaCalculo.percepcion_id == codigo_concepto,
                        ),
                    )
                ).scalar_one_or_none()
            if not regla and codigo_concepto:
                # Fallback by concept code -> concept ID -> linked ReglaCalculo.
                deduccion_obj = db.session.execute(
                    select(Deduccion).filter_by(codigo=codigo_concepto)
                ).scalar_one_or_none()
                if deduccion_obj:
                    regla = db.session.execute(
                        select(ReglaCalculo)
                        .filter_by(deduccion_id=deduccion_obj.id)
                        .filter(ReglaCalculo.activo.is_(True))
                    ).scalar_one_or_none()
            if not regla and codigo_concepto:
                prestacion_obj = db.session.execute(
                    select(Prestacion).filter_by(codigo=codigo_concepto)
                ).scalar_one_or_none()
                if prestacion_obj:
                    regla = db.session.execute(
                        select(ReglaCalculo)
                        .filter_by(prestacion_id=prestacion_obj.id)
                        .filter(ReglaCalculo.activo.is_(True))
                    ).scalar_one_or_none()
            if not regla and codigo_concepto:
                percepcion_obj = db.session.execute(
                    select(Percepcion).filter_by(codigo=codigo_concepto)
                ).scalar_one_or_none()
                if percepcion_obj:
                    regla = db.session.execute(
                        select(ReglaCalculo)
                        .filter_by(percepcion_id=percepcion_obj.id)
                        .filter(ReglaCalculo.activo.is_(True))
                    ).scalar_one_or_none()
            if regla and regla.esquema_json:
                regla_schema = regla.esquema_json
                regla_codigo = regla.codigo
        if not regla_schema:
            self.warnings.append(f"ReglaCalculo no encontrada para concepto {codigo_concepto}")
            return Decimal("0.00")
        try:
            # Prepare inputs for formula engine
            inputs = {**emp_calculo.variables_calculo}
            inputs["salario_bruto"] = emp_calculo.salario_bruto
            inputs["salario_gravable"] = emp_calculo.salario_gravable
            inputs["salario_gravable_periodo"] = emp_calculo.salario_gravable
            inputs["total_percepciones"] = emp_calculo.total_percepciones
            inputs["total_deducciones"] = emp_calculo.total_deducciones
            # Map generic schema input sources to input names when present.
            # This keeps parity with FormulaType.FORMULA behavior and allows
            # rules that declare sources such as "nomina.salario_bruto".
            if isinstance(regla_schema, dict):
                for input_def in regla_schema.get("inputs", []):
                    name = input_def.get("name")
                    source = input_def.get("source")
                    if not name or not source:
                        continue
                    if source in inputs:
                        inputs[name] = inputs[source]
                        continue
                    if "." in source:
                        source_key = source.split(".")[-1]
                        if source_key in inputs:
                            inputs[name] = inputs[source_key]
            # Calculate before-tax deductions already processed
            deducciones_antes_impuesto_periodo = Decimal("0.00")
            for ded in emp_calculo.deducciones:
                if not ded.deduccion_id:
                    continue
                ded_metadata = self._get_deduccion_metadata(ded.deduccion_id)
                if ded_metadata and ded_metadata.get("antes_impuesto"):
                    deducciones_antes_impuesto_periodo += ded.monto
            inputs["deducciones_antes_impuesto_periodo"] = deducciones_antes_impuesto_periodo
            # Legacy alias for backward compatibility (deprecated but kept to avoid breaking existing schemas)
            inputs["inss_periodo"] = deducciones_antes_impuesto_periodo
            # New generic aliases (preferred for new schemas)
            inputs["pre_tax_deductions"] = deducciones_antes_impuesto_periodo
            inputs["social_security_deduction"] = deducciones_antes_impuesto_periodo
            engine = FormulaEngine(regla_schema)
            result = engine.execute(inputs)
            return Decimal(str(result.get("output", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except FormulaEngineError as e:
            self.warnings.append(f"Error en ReglaCalculo {regla_codigo}: {str(e)}")
            return Decimal("0.00")

    def _get_deduccion_metadata(self, deduccion_id: str) -> dict[str, Any] | None:
        deducciones_snapshot = self.deducciones_snapshot
        # pylint: disable=unsupported-membership-test,unsubscriptable-object
        if isinstance(deducciones_snapshot, dict) and deduccion_id in deducciones_snapshot:
            return deducciones_snapshot[deduccion_id]

        deduccion_obj = db.session.get(Deduccion, deduccion_id)
        if not deduccion_obj:
            return None

        return {
            "antes_impuesto": deduccion_obj.antes_impuesto,
            "es_impuesto": deduccion_obj.es_impuesto,
        }

    def _get_config(self, empresa_id: str) -> Any:
        if self.configuracion_snapshot:
            from types import SimpleNamespace

            return SimpleNamespace(**self.configuracion_snapshot)

        return self.config_repo.get_for_empresa(empresa_id)
