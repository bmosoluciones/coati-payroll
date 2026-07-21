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

    def _build_formula_inputs(self, emp_calculo: EmpleadoCalculo, schema: dict | None) -> dict:
        """Build input variables for formula engine."""
        inputs = {**emp_calculo.variables_calculo}
        inputs["salario_bruto"] = emp_calculo.salario_bruto
        inputs["total_percepciones"] = emp_calculo.total_percepciones
        inputs["total_deducciones"] = emp_calculo.total_deducciones

        if isinstance(schema, dict):
            for input_def in schema.get("inputs", []):
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

        deducciones_antes_impuesto_periodo = Decimal("0.00")
        for ded in emp_calculo.deducciones:
            if not ded.deduccion_id:
                continue
            ded_metadata = self._get_deduccion_metadata(ded.deduccion_id)
            if ded_metadata and ded_metadata.get("antes_impuesto"):
                deducciones_antes_impuesto_periodo += ded.monto
        inputs["deducciones_antes_impuesto_periodo"] = deducciones_antes_impuesto_periodo
        inputs["inss_periodo"] = deducciones_antes_impuesto_periodo
        inputs["pre_tax_deductions"] = deducciones_antes_impuesto_periodo
        inputs["social_security_deduction"] = deducciones_antes_impuesto_periodo

        return inputs

    def _execute_formula(self, emp_calculo: EmpleadoCalculo, schema: dict, label: str) -> Decimal:
        """Execute formula engine with shared input preparation."""
        try:
            inputs = self._build_formula_inputs(emp_calculo, schema)
            engine = FormulaEngine(schema)
            result = engine.execute(inputs)
            return Decimal(str(result.get("output", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except FormulaEngineError as e:
            self.warnings.append(f"Error en {label}: {str(e)}")
            return Decimal("0.00")

    def _calculate_formula(
        self, emp_calculo: EmpleadoCalculo, formula: dict | None, codigo_concepto: str | None
    ) -> Decimal:
        """Calculate using formula engine."""
        if not formula or not isinstance(formula, dict):
            return Decimal("0.00")
        return self._execute_formula(emp_calculo, formula, "fórmula")

    def _resolve_regla_from_snapshot(self, codigo_concepto: str | None) -> tuple[dict | None, str | None]:
        """Try to get ReglaCalculo from snapshot."""
        if not self.deducciones_snapshot or not codigo_concepto:
            return None, None
        deduccion_data = self.deducciones_snapshot.get(codigo_concepto)
        if deduccion_data and "regla_calculo" in deduccion_data:
            return deduccion_data["regla_calculo"]["esquema_json"], deduccion_data["regla_calculo"]["codigo"]
        return None, None

    def _find_regla_by_concept_id(self, codigo_concepto: str):
        """Find ReglaCalculo by direct FK matches."""
        from sqlalchemy import select, or_
        return db.session.execute(
            select(ReglaCalculo).filter(
                ReglaCalculo.activo.is_(True),
                or_(
                    ReglaCalculo.deduccion_id == codigo_concepto,
                    ReglaCalculo.prestacion_id == codigo_concepto,
                    ReglaCalculo.percepcion_id == codigo_concepto,
                ),
            )
        ).scalar_one_or_none()

    def _find_regla_by_model(self, model_class, codigo_concepto: str, fk_field: str):
        """Find ReglaCalculo by looking up concept ID via a model class."""
        from sqlalchemy import select
        obj = db.session.execute(
            select(model_class).filter_by(codigo=codigo_concepto)
        ).scalar_one_or_none()
        if not obj:
            return None
        return db.session.execute(
            select(ReglaCalculo)
            .filter_by(**{fk_field: obj.id})
            .filter(ReglaCalculo.activo.is_(True))
        ).scalar_one_or_none()

    def _resolve_regla_from_db(self, codigo_concepto: str | None) -> tuple[dict | None, str | None]:
        """Fallback: find ReglaCalculo from live DB."""
        if not codigo_concepto:
            return None, None
        regla = self._find_regla_by_concept_id(codigo_concepto)
        if not regla:
            regla = self._find_regla_by_model(Deduccion, codigo_concepto, "deduccion_id")
        if not regla:
            regla = self._find_regla_by_model(Prestacion, codigo_concepto, "prestacion_id")
        if not regla:
            regla = self._find_regla_by_model(Percepcion, codigo_concepto, "percepcion_id")
        if regla and regla.esquema_json:
            return regla.esquema_json, regla.codigo
        return None, None

    def _calculate_regla_calculo(self, emp_calculo: EmpleadoCalculo, codigo_concepto: str | None) -> Decimal:
        """Calculate using ReglaCalculo from snapshot (if available) or live DB."""
        regla_schema, regla_codigo = self._resolve_regla_from_snapshot(codigo_concepto)
        if not regla_schema:
            regla_schema, regla_codigo = self._resolve_regla_from_db(codigo_concepto)
        if not regla_schema:
            self.warnings.append(f"ReglaCalculo no encontrada para concepto {codigo_concepto}")
            return Decimal("0.00")
        return self._execute_formula(emp_calculo, regla_schema, f"ReglaCalculo {regla_codigo}")

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
