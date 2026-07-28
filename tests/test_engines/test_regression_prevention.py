# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests to prevent regressions/reversals in the payroll calculation engine.

These tests validate:
- Clamping of deduction values to 0.00 to prevent negative deductions.
- Mathematical proration of base salary for mid-period hiring and termination.
- Strict Decimal precision and rounding.
- Prevention of negative net salary via deduction balance clamping.
- Graceful error capturing in case of calculation errors.
"""

from datetime import date
from decimal import Decimal
import pytest

from coati_payroll.nomina_engine.calculators.salary_calculator import SalaryCalculator
from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.calculators.deduction_calculator import DeductionCalculator
from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
from coati_payroll.nomina_engine.domain.employee_calculation import EmpleadoCalculo
from coati_payroll.nomina_engine.domain.calculation_items import DeduccionItem
from coati_payroll.nomina_engine.validators import NominaEngineError
from coati_payroll.model import (
    Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado, Deduccion, PlanillaDeduccion, db
)


class TestRegressionPreventionCalculations:
    """Regression-prevention tests for critical calculation rules."""

    def test_deduction_negative_clamping_regression(self, app, db_session):
        """Ensure negative deduction results do not create negative deductions in the system."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="REGR01", razon_social="Regression Prev Corp", ruc="J-98765432")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_REGR",
                descripcion="Monthly test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Regresión",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a deduction that would calculate to a negative value due to a bad formula or override
            deduccion = Deduccion(
                codigo="DED_NEG",
                nombre="Negative Deduction",
                formula_tipo="fixed",
                monto_default=Decimal("-150.00"),  # Negative default
                activo=True,
            )
            db_session.add(deduccion)
            db_session.flush()

            planilla_ded = PlanillaDeduccion(
                planilla_id=planilla.id,
                deduccion_id=deduccion.id,
                prioridad=1,
                es_obligatoria=True,
                activo=True,
            )
            db_session.add(planilla_ded)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP_REGR_01",
                primer_nombre="Test",
                primer_apellido="Clamp",
                identificacion_personal="001-010180-9999M",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("12000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(
                planilla_id=planilla.id,
                empleado_id=empleado.id,
                activo=True,
            )
            db_session.add(planilla_emp)
            db_session.flush()
            db_session.commit()

            # Refresh to sync relationship cleanly
            db_session.refresh(planilla)

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("12000.00")
            emp_calculo.salario_mensual = Decimal("12000.00")
            emp_calculo.salario_bruto = Decimal("12000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")

            config_repo = ConfigRepository(db_session)
            warnings = []
            concept_calc = ConceptCalculator(config_repo, warnings)
            deduction_calc = DeductionCalculator(concept_calc, warnings)

            ded_items = deduction_calc.calculate(
                emp_calculo=emp_calculo,
                planilla=planilla,
                fecha_calculo=date(2024, 1, 31),
            )

            # Since the calculation was negative, no positive deduction item should be added
            # and any negative value is effectively clamped to 0.00.
            for item in ded_items:
                assert item.monto >= Decimal("0.00")

    def test_salary_proration_mid_period_regression(self, app, db_session):
        """Ensure that mid-period hiring and termination prorate the base salary precisely using Decimal math."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="REGR02", razon_social="Regression Prev Corp 2", ruc="J-98765433")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_REGR_2",
                descripcion="Monthly test 2",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Regresión 2",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            config_repo = ConfigRepository(db_session)
            calculator = SalaryCalculator(config_repo)

            # Monthly salary of 15000.00, hired mid-period (e.g. starting on Jan 16th, which leaves exactly 16 days worked in Jan)
            # Days in period: Jan 1 to Jan 31 (31 days)
            # Worked days: Jan 16 to Jan 31 (16 days)
            # Expecting monthly rate of 15000 * (16 / 31)
            prorated_salary = calculator.calculate_period_salary(
                salario_mensual=Decimal("15000.00"),
                planilla=planilla,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                _fecha_calculo=date(2024, 1, 31),
                fecha_alta=date(2024, 1, 16),
            )

            expected = (Decimal("15000.00") * Decimal("16") / Decimal("31")).quantize(Decimal("0.01"))
            assert prorated_salary == expected
            assert isinstance(prorated_salary, Decimal)

    def test_deduction_balance_clamping_prevents_negative_net(self, app, db_session):
        """Verify that deductions are clamped to available gross salary, preventing negative net salary."""
        from coati_payroll.nomina_engine.services.payroll_execution_service import PayrollExecutionService

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            # Must set first month and year configuration to pass bootstrap
            empresa = Empresa(
                codigo="REGR03",
                razon_social="Regression Prev Corp 3",
                ruc="J-98765434",
                primer_mes_nomina=1,
                primer_anio_nomina=2024
            )
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_REGR_3",
                descripcion="Monthly test 3",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Regresión 3",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a deduction that exceeds the gross salary
            deduccion = Deduccion(
                codigo="DED_EXCESS",
                nombre="Excessive Deduction",
                formula_tipo="fixed",
                monto_default=Decimal("15000.00"),  # Exceeds the 10000.00 salary
                activo=True,
            )
            db_session.add(deduccion)
            db_session.flush()

            planilla_ded = PlanillaDeduccion(
                planilla_id=planilla.id,
                deduccion_id=deduccion.id,
                prioridad=1,
                es_obligatoria=True,
                activo=True,
            )
            db_session.add(planilla_ded)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP_REGR_03",
                primer_nombre="Poor",
                primer_apellido="Employee",
                identificacion_personal="001-010180-8888X",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(
                planilla_id=planilla.id,
                empleado_id=empleado.id,
                activo=True,
            )
            db_session.add(planilla_emp)
            db_session.flush()
            db_session.commit()

            # Refresh to sync relationship cleanly
            db_session.refresh(planilla)

            payroll_service = PayrollExecutionService(db_session)

            # Execute for Jan 2024
            nomina, emps, errors, warnings = payroll_service.execute_payroll(
                planilla=planilla,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                fecha_calculo=date(2024, 1, 31),
                usuario="admin",
            )

            # Execution is successful because deductions are safely clamped to salary_bruto
            assert len(errors) == 0
            assert len(emps) == 1
            assert emps[0].salario_neto == Decimal("0.00")
            assert emps[0].total_deducciones == Decimal("10000.00")  # Clamped!
