# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for nomina_engine.py - CRITICAL payroll calculation engine.

This module tests the core payroll processing engine that handles:
- Salary calculations
- Perceptions (income additions)
- Deductions (salary subtractions)
- Benefits (employer costs)
- Exchange rates
- Accumulated annual values
- Automatic loan/advance deductions

These tests are CRITICAL as they validate money calculations affecting employees.
"""

from datetime import date
from decimal import Decimal


from coati_payroll.enums import FormulaType
from coati_payroll.nomina_engine import (
    NominaEngine,
    EmpleadoCalculo,
)
from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
from coati_payroll.nomina_engine.calculators.salary_calculator import SalaryCalculator
from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
from coati_payroll.model import db


class TestEmpleadoCalculo:
    """Tests for EmpleadoCalculo container class."""

    def test_empleado_calculo_initialization(self, app, db_session):
        """Test EmpleadoCalculo initializes with correct default values."""
        from coati_payroll.model import Empleado, Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            # Create minimal required entities
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Company SA", ruc="J-12345678")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="MENSUAL",
                descripcion="Mensual",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Juan",
                primer_apellido="Pérez",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("15000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            # Test EmpleadoCalculo initialization
            emp_calculo = EmpleadoCalculo(empleado, planilla)

            assert emp_calculo.empleado == empleado
            assert emp_calculo.planilla == planilla
            assert emp_calculo.salario_base == Decimal("15000.00")
            assert emp_calculo.salario_mensual == Decimal("15000.00")
            assert len(emp_calculo.percepciones) == 0
            assert len(emp_calculo.deducciones) == 0
            assert len(emp_calculo.prestaciones) == 0
            assert emp_calculo.total_percepciones == Decimal("0.00")
            assert emp_calculo.total_deducciones == Decimal("0.00")
            assert emp_calculo.total_prestaciones == Decimal("0.00")
            assert emp_calculo.salario_bruto == Decimal("0.00")
            assert emp_calculo.salario_neto == Decimal("0.00")
            assert emp_calculo.tipo_cambio == Decimal("1.00")
            assert emp_calculo.moneda_origen_id == moneda.id
            assert isinstance(emp_calculo.novedades, dict)
            assert isinstance(emp_calculo.variables_calculo, dict)


class TestNominaEngineInitialization:
    """Tests for NominaEngine initialization."""

    def test_nomina_engine_initialization(self, app, db_session):
        """Test NominaEngine initializes correctly."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="QUINCENAL",
                descripcion="Quincenal",
                periodicidad="biweekly",
                dias=15,
                periodos_por_anio=24,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Quincenal",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            periodo_inicio = date(2025, 1, 1)
            periodo_fin = date(2025, 1, 15)

            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=date(2025, 1, 15),
                usuario="testuser",
            )

            assert engine.planilla == planilla
            assert engine.periodo_inicio == periodo_inicio
            assert engine.periodo_fin == periodo_fin
            assert engine.fecha_calculo == date(2025, 1, 15)
            assert engine.usuario == "testuser"
            assert engine.nomina is None
            assert len(engine.empleados_calculo) == 0
            assert len(engine.errors) == 0
            assert len(engine.warnings) == 0

    def test_nomina_engine_default_fecha_calculo(self, app, db_session):
        """Test that fecha_calculo defaults to today."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            engine = NominaEngine(planilla=planilla, periodo_inicio=date(2025, 1, 1), periodo_fin=date(2025, 1, 31))

            assert engine.fecha_calculo == date.today()


class TestPlanillaValidation:
    """Tests for planilla validation before execution."""

    def test_validar_planilla_inactive(self, app, db_session):
        """Test validation fails for inactive planilla."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Inactive Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=False,  # Inactive!
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            engine = NominaEngine(planilla=planilla, periodo_inicio=date(2025, 1, 1), periodo_fin=date(2025, 1, 31))

            is_valid = engine.validar_planilla()
            assert is_valid is False
            assert len(engine.errors) >= 1
            # The validator may return multiple errors (inactive + no employees)
            assert any("no está activa" in e for e in engine.errors)

    def test_validar_planilla_no_employees(self, app, db_session):
        """Test validation fails when planilla has no employees."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Empty Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            engine = NominaEngine(planilla=planilla, periodo_inicio=date(2025, 1, 1), periodo_fin=date(2025, 1, 31))

            is_valid = engine.validar_planilla()
            assert is_valid is False
            assert len(engine.errors) == 1
            assert "no tiene empleados" in engine.errors[0]


class TestSalarioPeriodoCalculation:
    """Tests for salary period calculation (_calcular_salario_periodo)."""

    def test_calcular_salario_periodo_mensual_30_dias(self, app, db_session):
        """Test monthly salary for full 30-day period."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="MENSUAL",
                descripcion="Mensual",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Mensual",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            salario_mensual = Decimal("15000.00")

            # Use SalaryCalculator directly
            config_repo = ConfigRepository(db.session)
            calculator = SalaryCalculator(config_repo)

            salario_periodo = calculator.calculate_period_salary(
                salario_mensual, planilla, date(2025, 1, 1), date(2025, 1, 30), date(2025, 1, 30)
            )

            # Full month should return full salary
            assert salario_periodo == Decimal("15000.00")

    def test_calcular_salario_periodo_quincenal(self, app, db_session):
        """Test biweekly salary calculation."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="QUINCENAL",
                descripcion="Quincenal",
                periodicidad="biweekly",
                dias=15,
                periodos_por_anio=24,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Quincenal",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            salario_mensual = Decimal("30000.00")

            # Use SalaryCalculator directly
            config_repo = ConfigRepository(db.session)
            calculator = SalaryCalculator(config_repo)

            salario_periodo = calculator.calculate_period_salary(
                salario_mensual, planilla, date(2025, 1, 1), date(2025, 1, 15), date(2025, 1, 15)
            )

            # 15 days = half month: 30000 / 30 * 15 = 15000
            assert salario_periodo == Decimal("15000.00")

    def test_calcular_salario_periodo_partial_month(self, app, db_session):
        """Test salary calculation for partial month (new hire)."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="MENSUAL",
                descripcion="Mensual",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Mensual",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()
            db_session.commit()

            salario_mensual = Decimal("30000.00")

            # Use SalaryCalculator directly
            config_repo = ConfigRepository(db.session)
            calculator = SalaryCalculator(config_repo)

            salario_periodo = calculator.calculate_period_salary(
                salario_mensual, planilla, date(2025, 1, 20), date(2025, 1, 30), date(2025, 1, 30)
            )

            # 11 days: 30000 / 30 * 11 = 11000
            assert salario_periodo == Decimal("11000.00")

    def test_calcular_salario_periodo_prorrateado_por_fecha_alta(self, app, db_session):
        """Test monthly salary is prorated when employee starts mid-period."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="CÃ³rdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="MENSUAL",
                descripcion="Mensual",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Mensual Prorrateo Alta",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.commit()

            config_repo = ConfigRepository(db.session)
            calculator = SalaryCalculator(config_repo)

            salario_periodo = calculator.calculate_period_salary(
                Decimal("10000.00"),
                planilla,
                date(2025, 1, 1),
                date(2025, 1, 31),
                date(2025, 1, 31),
                fecha_alta=date(2025, 1, 15),
            )

            # 17 dÃ­as laborados (15-31) de 31 dÃ­as del perÃ­odo.
            assert salario_periodo == Decimal("5483.87")

    def test_calcular_salario_periodo_prorrateado_por_fecha_baja(self, app, db_session):
        """Test monthly salary is prorated when employee leaves mid-period."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="CÃ³rdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="MENSUAL",
                descripcion="Mensual",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Mensual Prorrateo Baja",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.commit()

            config_repo = ConfigRepository(db.session)
            calculator = SalaryCalculator(config_repo)

            salario_periodo = calculator.calculate_period_salary(
                Decimal("10000.00"),
                planilla,
                date(2025, 1, 1),
                date(2025, 1, 31),
                date(2025, 1, 31),
                fecha_baja=date(2025, 1, 10),
            )

            # 10 dÃ­as laborados (1-10) de 31 dÃ­as del perÃ­odo.
            assert salario_periodo == Decimal("3225.81")


class TestCalculoConcepto:
    """Tests for _calcular_concepto method - calculates perception/deduction amounts."""

    def test_calcular_concepto_fijo(self, app, db_session):
        """Test fixed amount calculation."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.FIJO,
                monto_default=Decimal("500.00"),
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
            )

            assert monto == Decimal("500.00")

    def test_calcular_concepto_porcentaje_salario(self, app, db_session):
        """Test percentage of salary calculation."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.PORCENTAJE_SALARIO,
                monto_default=None,
                porcentaje=Decimal("10.00"),  # 10%
                formula=None,
                monto_override=None,
                porcentaje_override=None,
            )

            # 10% of 10000 = 1000
            assert monto == Decimal("1000.00")

    def test_calcular_concepto_with_override(self, app, db_session):
        """Test that override values take precedence."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            # Override should take precedence
            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.FIJO,
                monto_default=Decimal("500.00"),
                porcentaje=None,
                formula=None,
                monto_override=Decimal("750.00"),  # Override!
                porcentaje_override=None,
            )

            assert monto == Decimal("750.00")


class TestHorasYDiasCalculation:
    """Tests for hours and days based calculations."""

    def test_calcular_concepto_horas(self, app, db_session):
        """Test calculation based on hours (overtime)."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("24000.00"),  # Monthly salary
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("24000.00")
            emp_calculo.salario_mensual = Decimal("24000.00")
            emp_calculo.novedades = {"OVERTIME": Decimal("10")}  # 10 overtime hours
            emp_calculo.variables_calculo = {"novedad_HORAS_EXTRA": Decimal("10")}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.HORAS,
                monto_default=None,
                porcentaje=Decimal("150.00"),  # 150% overtime rate
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="OVERTIME",
            )

            # Hourly rate: 24000 / 30 / 8 = 100 per hour
            # 150% overtime: 100 * 1.5 = 150 per hour
            # 10 hours: 150 * 10 = 1500
            assert monto == Decimal("1500.00")

    def test_calcular_concepto_horas_no_novedad(self, app, db_session):
        """Test hours calculation returns 0 when no novedad exists."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("24000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("24000.00")
            emp_calculo.salario_mensual = Decimal("24000.00")
            emp_calculo.novedades = {}  # No hours recorded
            emp_calculo.variables_calculo = {}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.HORAS,
                monto_default=None,
                porcentaje=Decimal("150.00"),
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="OVERTIME",
            )

            assert monto == Decimal("0.00")

    def test_calcular_concepto_dias(self, app, db_session):
        """Test calculation based on days (absences, vacations)."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("30000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("30000.00")
            emp_calculo.salario_mensual = Decimal("30000.00")
            emp_calculo.novedades = {"VACATION": Decimal("5")}  # 5 vacation days
            emp_calculo.variables_calculo = {"novedad_VACACIONES": Decimal("5")}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.DIAS,
                monto_default=None,
                porcentaje=Decimal("100.00"),  # 100% of daily rate
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="VACATION",
            )

            # Daily rate: 30000 / 30 = 1000 per day
            # 5 days: 1000 * 5 = 5000
            assert monto == Decimal("5000.00")


class TestBadInputNominaEngine:
    """Tests for handling bad input in nomina_engine - CRITICAL for production."""

    def test_calcular_concepto_with_none_porcentaje(self, app, db_session):
        """Test calculation handles None porcentaje gracefully."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            # None porcentaje should return 0
            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.PORCENTAJE_SALARIO,
                monto_default=None,
                porcentaje=None,  # None!
                formula=None,
                monto_override=None,
                porcentaje_override=None,
            )

            assert monto == Decimal("0.00")

    def test_calcular_concepto_with_zero_salario_base(self, app, db_session):
        """Test calculation with zero salary base."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("0.00"),  # Zero salary!
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("0.00")
            emp_calculo.salario_mensual = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.PORCENTAJE_SALARIO,
                monto_default=None,
                porcentaje=Decimal("10.00"),
                formula=None,
                monto_override=None,
                porcentaje_override=None,
            )

            # 10% of 0 = 0
            assert monto == Decimal("0.00")

    def test_calcular_concepto_with_negative_hours(self, app, db_session):
        """Test calculation handles negative hours (should return 0)."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)

            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("24000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("24000.00")
            emp_calculo.salario_mensual = Decimal("24000.00")
            emp_calculo.novedades = {"OVERTIME": Decimal("-5")}  # Negative hours!
            emp_calculo.variables_calculo = {"novedad_HORAS_EXTRA": Decimal("-5")}

            # Use ConceptCalculator directly
            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.HORAS,
                monto_default=None,
                porcentaje=Decimal("150.00"),
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="OVERTIME",
            )

            # Negative hours should return 0 (calculator should handle this)
            assert monto == Decimal("0.00")


class TestConceptCalculatorFormulaMethods:
    """Tests for _calculate_formula and _calculate_regla_calculo methods."""

    def test_calculate_formula_with_valid_formula(self, app, db_session):
        """Test _calculate_formula with valid formula."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10500.00")
            emp_calculo.total_percepciones = Decimal("500.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {"dias_trabajados": 30}

            # Create a simple formula: salario_bruto * 0.07
            formula = {
                "inputs": [{"name": "salario_bruto", "type": "decimal", "default": 0}],
                "steps": [
                    {
                        "name": "calculate_tax",
                        "type": "calculation",
                        "formula": "salario_bruto * 0.07",
                    }
                ],
                "output": "calculate_tax",
            }

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.FORMULA,
                monto_default=None,
                porcentaje=None,
                formula=formula,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="TAX_TEST",
            )

            # 10500 * 0.07 = 735.00
            assert monto == Decimal("735.00")
            assert len(warnings) == 0

    def test_calculate_formula_with_empty_formula(self, app, db_session):
        """Test _calculate_formula with None/empty formula returns 0."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            # Test with None formula
            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.FORMULA,
                monto_default=None,
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="TAX_TEST",
            )

            assert monto == Decimal("0.00")
            assert len(warnings) == 0

    def test_calculate_formula_with_invalid_formula(self, app, db_session):
        """Test _calculate_formula with invalid formula raises error and returns 0."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            # Create an invalid formula (missing output field)
            formula = {
                "inputs": [{"name": "salario_bruto", "type": "decimal", "default": 0}],
                "steps": [
                    {
                        "name": "calculate_tax",
                        "type": "calculation",
                        "formula": "undefined_variable * 0.07",
                    }
                ],
                "output": "calculate_tax",
            }

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.FORMULA,
                monto_default=None,
                porcentaje=None,
                formula=formula,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="TAX_TEST",
            )

            # Should return 0 and add a warning
            assert monto == Decimal("0.00")
            assert len(warnings) > 0
            assert "Error en fórmula" in warnings[0]

    def test_calculate_formula_with_before_tax_deductions(self, app, db_session):
        """Test _calculate_formula correctly includes before-tax deductions."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado, Deduccion
        from coati_payroll.nomina_engine.domain.calculation_items import DeduccionItem

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a before-tax deduction (INSS)
            deduccion_inss = Deduccion(
                codigo="INSS",
                nombre="INSS",
                descripcion="Seguro Social",
                formula_tipo="percentage",
                porcentaje=Decimal("7.00"),
                antes_impuesto=True,
                activo=True,
            )
            db_session.add(deduccion_inss)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("700.00")
            emp_calculo.variables_calculo = {}

            # Add a before-tax deduction
            deduccion_item = DeduccionItem(
                codigo="INSS",
                nombre="INSS",
                monto=Decimal("700.00"),
                prioridad=1,
                es_obligatoria=True,
                deduccion_id=deduccion_inss.id,
            )
            emp_calculo.deducciones.append(deduccion_item)

            # Formula that uses pre_tax_deductions: (salario_bruto - pre_tax_deductions) * 0.15
            formula = {
                "inputs": [
                    {"name": "salario_bruto", "type": "decimal", "default": 0},
                    {"name": "pre_tax_deductions", "type": "decimal", "default": 0},
                ],
                "steps": [
                    {
                        "name": "taxable_income",
                        "type": "calculation",
                        "formula": "salario_bruto - pre_tax_deductions",
                    },
                    {
                        "name": "calculate_tax",
                        "type": "calculation",
                        "formula": "taxable_income * 0.15",
                    },
                ],
                "output": "calculate_tax",
            }

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.FORMULA,
                monto_default=None,
                porcentaje=None,
                formula=formula,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="IR",
            )

            # (10000 - 700) * 0.15 = 9300 * 0.15 = 1395.00
            assert monto == Decimal("1395.00")
            assert len(warnings) == 0

    def test_calculate_regla_calculo_with_valid_rule(self, app, db_session):
        """Test _calculate_regla_calculo with valid ReglaCalculo."""
        from coati_payroll.model import (
            Planilla,
            TipoPlanilla,
            Moneda,
            Empresa,
            Empleado,
            Deduccion,
            ReglaCalculo,
        )

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a deduction with ReglaCalculo
            deduccion_ir = Deduccion(
                codigo="IR",
                nombre="Impuesto sobre la Renta",
                descripcion="Income Tax",
                formula_tipo="regla_calculo",
                activo=True,
            )
            db_session.add(deduccion_ir)
            db_session.flush()

            # Create ReglaCalculo for the deduction
            esquema = {
                "inputs": [{"name": "salario_bruto", "type": "decimal", "default": 0}],
                "steps": [
                    {
                        "name": "calculate_tax",
                        "type": "calculation",
                        "formula": "salario_bruto * 0.15",
                    }
                ],
                "output": "calculate_tax",
            }

            regla = ReglaCalculo(
                codigo="IR_RULE_001",
                nombre="Income Tax Rule",
                descripcion="Basic income tax calculation",
                tipo_regla="tax",
                esquema_json=esquema,
                vigente_desde=date(2024, 1, 1),
                activo=True,
                deduccion_id=deduccion_ir.id,
            )
            db_session.add(regla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.REGLA_CALCULO,
                monto_default=None,
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="IR",
            )

            # 10000 * 0.15 = 1500.00
            assert monto == Decimal("1500.00")
            assert len(warnings) == 0

    def test_calculate_regla_calculo_not_found(self, app, db_session):
        """Test _calculate_regla_calculo when ReglaCalculo is not found."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            # Try to calculate with non-existent ReglaCalculo
            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.REGLA_CALCULO,
                monto_default=None,
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="NON_EXISTENT",
            )

            # Should return 0 and add a warning
            assert monto == Decimal("0.00")
            assert len(warnings) > 0
            assert "ReglaCalculo no encontrada" in warnings[0]

    def test_calculate_regla_calculo_with_formula_error(self, app, db_session):
        """Test _calculate_regla_calculo handles FormulaEngineError."""
        from coati_payroll.model import (
            Planilla,
            TipoPlanilla,
            Moneda,
            Empresa,
            Empleado,
            Deduccion,
            ReglaCalculo,
        )

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a deduction with ReglaCalculo
            deduccion_ir = Deduccion(
                codigo="IR",
                nombre="Impuesto sobre la Renta",
                descripcion="Income Tax",
                formula_tipo="regla_calculo",
                activo=True,
            )
            db_session.add(deduccion_ir)
            db_session.flush()

            # Create ReglaCalculo with invalid formula
            esquema = {
                "inputs": [{"name": "salario_bruto", "type": "decimal", "default": 0}],
                "steps": [
                    {
                        "name": "calculate_tax",
                        "type": "calculation",
                        "formula": "undefined_var * 0.15",
                    }
                ],
                "output": "calculate_tax",
            }

            regla = ReglaCalculo(
                codigo="IR_RULE_001",
                nombre="Income Tax Rule",
                descripcion="Basic income tax calculation",
                tipo_regla="tax",
                esquema_json=esquema,
                vigente_desde=date(2024, 1, 1),
                activo=True,
                deduccion_id=deduccion_ir.id,
            )
            db_session.add(regla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10000.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.REGLA_CALCULO,
                monto_default=None,
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="IR",
            )

            # Should return 0 and add a warning about the error
            assert monto == Decimal("0.00")
            assert len(warnings) > 0
            assert "Error en ReglaCalculo" in warnings[0]

    def test_calculate_regla_calculo_by_deduccion_codigo(self, app, db_session):
        """Test _calculate_regla_calculo finds ReglaCalculo by deduccion codigo."""
        from coati_payroll.model import (
            Planilla,
            TipoPlanilla,
            Moneda,
            Empresa,
            Empleado,
            Deduccion,
            ReglaCalculo,
        )

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a deduction
            deduccion_ir = Deduccion(
                codigo="IR",
                nombre="Impuesto sobre la Renta",
                descripcion="Income Tax",
                formula_tipo="regla_calculo",
                activo=True,
            )
            db_session.add(deduccion_ir)
            db_session.flush()

            # Create ReglaCalculo linked to deduccion by ID (not by codigo)
            esquema = {
                "inputs": [{"name": "salario_bruto", "type": "decimal", "default": 0}],
                "steps": [
                    {
                        "name": "calculate_tax",
                        "type": "calculation",
                        "formula": "salario_bruto * 0.10",
                    }
                ],
                "output": "calculate_tax",
            }

            regla = ReglaCalculo(
                codigo="IR_RULE_002",
                nombre="Income Tax Rule 2",
                descripcion="Tax rule linked by deduccion ID",
                tipo_regla="tax",
                esquema_json=esquema,
                vigente_desde=date(2024, 1, 1),
                activo=True,
                deduccion_id=deduccion_ir.id,  # Linked by ID, not by codigo
            )
            db_session.add(regla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            # Search by deduccion codigo "IR" - should find the rule via deduccion lookup
            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.REGLA_CALCULO,
                monto_default=None,
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="IR",  # Using deduccion codigo
            )

            # 10000 * 0.10 = 1000.00
            assert monto == Decimal("1000.00")
            assert len(warnings) == 0

    def test_calculate_regla_calculo_by_prestacion_codigo(self, app, db_session):
        """Test _calculate_regla_calculo finds ReglaCalculo by prestacion codigo."""
        from coati_payroll.model import (
            Planilla,
            TipoPlanilla,
            Moneda,
            Empresa,
            Empleado,
            Prestacion,
            ReglaCalculo,
        )

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="CÃ³rdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST001", razon_social="Test Corp Inc", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST",
                descripcion="Test",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            prestacion = Prestacion(
                codigo="INATEC",
                nombre="INATEC",
                descripcion="Aporte INATEC",
                formula_tipo="regla_calculo",
                activo=True,
            )
            db_session.add(prestacion)
            db_session.flush()

            esquema = {
                "inputs": [{"name": "salario_bruto", "type": "decimal", "default": 0}],
                "steps": [
                    {
                        "name": "aporte",
                        "type": "calculation",
                        "formula": "salario_bruto * 0.02",
                    }
                ],
                "output": "aporte",
            }

            regla = ReglaCalculo(
                codigo="INATEC_RULE_001",
                nombre="INATEC Rule",
                descripcion="Regla ligada por prestacion_id",
                tipo_regla="prestacion",
                esquema_json=esquema,
                vigente_desde=date(2024, 1, 1),
                activo=True,
                prestacion_id=prestacion.id,
            )
            db_session.add(regla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db.session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo=FormulaType.REGLA_CALCULO,
                monto_default=None,
                porcentaje=None,
                formula=None,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="INATEC",
            )

            # 10000 * 0.02 = 200.00
            assert monto == Decimal("200.00")
            assert len(warnings) == 0


class TestDeductionsCalculationImprovements:
    """Tests for deduction and accumulated variables calculation improvements."""

    def test_non_initial_period_with_acumulado_anual(self, app, db_session):
        """Test loading an existing annual accumulation without overwriting it."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado, AcumuladoAnual
        from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
        from coati_payroll.nomina_engine.repositories.acumulado_repository import AcumuladoRepository
        from coati_payroll.nomina_engine.services.employee_processing_service import EmployeeProcessingService
        from coati_payroll.nomina_engine.domain.employee_calculation import EmpleadoCalculo

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            # Company first payroll period is Jan 2024
            empresa = Empresa(
                codigo="TEST_ACC_EX",
                razon_social="Test Acc Ex Corp",
                ruc="1234567-8",
                primer_mes_nomina=1,
                primer_anio_nomina=2024,
            )
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_TP_EX",
                descripcion="Test TP Ex",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla Acc Ex",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                mes_inicio_fiscal=1,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP_ACC_EX_01",
                primer_nombre="Jane",
                primer_apellido="Smith",
                identificacion_personal="001-010180-0005E",
                fecha_alta=date(2023, 6, 1),
                salario_base=Decimal("20000.00"),
                salario_acumulado=Decimal("0.00"),
                impuesto_acumulado=Decimal("0.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            # Create an actual AcumuladoAnual record for period fiscal start Jan 2024
            acumulado_db = AcumuladoAnual(
                empleado_id=empleado.id,
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                periodo_fiscal_inicio=date(2024, 1, 1),
                periodo_fiscal_fin=date(2024, 12, 31),
                salario_bruto_acumulado=Decimal("120000.00"),
                salario_gravable_acumulado=Decimal("110000.00"),
                deducciones_antes_impuesto_acumulado=Decimal("8000.00"),
                impuesto_retenido_acumulado=Decimal("5000.00"),
                periodos_procesados=6,
                ultimo_periodo_procesado=date(2024, 6, 30),
            )
            db_session.add(acumulado_db)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("20000.00")
            emp_calculo.salario_mensual = Decimal("20000.00")
            emp_calculo.salario_bruto = Decimal("20000.00")
            emp_calculo.salario_neto_inasistencia = Decimal("20000.00")
            emp_calculo.salario_gravable = Decimal("20000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db_session)
            acumulado_repo = AcumuladoRepository(db_session)
            proc_service = EmployeeProcessingService(config_repo, acumulado_repo)

            # Non-initial period: July 2024
            variables = proc_service.build_calculation_variables(
                emp_calculo=emp_calculo,
                planilla=planilla,
                periodo_inicio=date(2024, 7, 1),
                periodo_fin=date(2024, 7, 31),
                fecha_calculo=date(2024, 7, 31),
                bootstrap_context={"is_initial_period": False},
            )

            # Values must be loaded from accumulated_db exactly! No overwriting to 0!
            assert variables["salario_bruto_acumulado"] == Decimal("120000.00")
            assert variables["salario_gravable_acumulado"] == Decimal("110000.00")
            assert variables["deducciones_antes_impuesto_acumulado"] == Decimal("8000.00")
            assert variables["ir_retenido_acumulado"] == Decimal("5000.00")
            assert variables["periodos_procesados"] == Decimal("6")
            assert variables["meses_trabajados"] == Decimal(
                "6"
            )  # reference July -> 6 months elapsed transcurridos before July
            assert variables["salario_neto_acumulado"] == Decimal("112000.00")  # 120000 - 8000

    def test_initial_period_accumulated_variables_defaults(self, app, db_session):
        """Test defaults and initial period values for accumulated variables."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado
        from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
        from coati_payroll.nomina_engine.repositories.acumulado_repository import AcumuladoRepository
        from coati_payroll.nomina_engine.services.employee_processing_service import EmployeeProcessingService
        from coati_payroll.nomina_engine.domain.employee_calculation import EmpleadoCalculo

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            # Let's say company first payroll period is Jan 2024
            empresa = Empresa(
                codigo="TEST_ACC",
                razon_social="Test Acc Corp",
                ruc="1234567-9",
                primer_mes_nomina=1,
                primer_anio_nomina=2024,
            )
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_TP",
                descripcion="Test TP",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla Acc",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                mes_inicio_fiscal=1,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee with starting historical accumulated values
            empleado = Empleado(
                codigo_empleado="EMP_ACC_01",
                primer_nombre="John",
                primer_apellido="Doe",
                identificacion_personal="001-010180-0002B",
                fecha_alta=date(2023, 6, 1),
                salario_base=Decimal("15000.00"),
                salario_acumulado=Decimal("90000.00"),  # starts with 90k accumulated salary
                impuesto_acumulado=Decimal("4500.00"),  # starts with 4.5k accumulated tax
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("15000.00")
            emp_calculo.salario_mensual = Decimal("15000.00")
            emp_calculo.salario_bruto = Decimal("15000.00")
            emp_calculo.salario_neto_inasistencia = Decimal("15000.00")
            emp_calculo.salario_gravable = Decimal("15000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db_session)
            acumulado_repo = AcumuladoRepository(db_session)
            proc_service = EmployeeProcessingService(config_repo, acumulado_repo)

            # Calculate for initial company period: Jan 2024
            variables = proc_service.build_calculation_variables(
                emp_calculo=emp_calculo,
                planilla=planilla,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                fecha_calculo=date(2024, 1, 31),
            )

            # Assert that progressive tax accumulated variables got populated from initial fields!
            assert variables["salario_acumulado"] == Decimal("90000.00")
            assert variables["impuesto_acumulado"] == Decimal("4500.00")
            assert variables["salario_bruto_acumulado"] == Decimal("90000.00")
            assert variables["salario_gravable_acumulado"] == Decimal("90000.00")
            assert variables["impuesto_retenido_acumulado"] == Decimal("4500.00")
            assert variables["deducciones_antes_impuesto_acumulado"] == Decimal("0.00")
            assert variables["salario_neto_acumulado"] == Decimal("90000.00")
            assert variables["meses_trabajados"] == Decimal("0.00")

            # Calculate for non-initial company period with no AcumuladoAnual record
            variables_feb = proc_service.build_calculation_variables(
                emp_calculo=emp_calculo,
                planilla=planilla,
                periodo_inicio=date(2024, 2, 1),
                periodo_fin=date(2024, 2, 29),
                fecha_calculo=date(2024, 2, 29),
                bootstrap_context={"is_initial_period": False},
            )

            # Should default to 0.00 and NOT cause KeyError or crash
            assert variables_feb["salario_bruto_acumulado"] == Decimal("0.00")
            assert variables_feb["salario_gravable_acumulado"] == Decimal("0.00")
            assert variables_feb["deducciones_antes_impuesto_acumulado"] == Decimal("0.00")
            assert variables_feb["salario_neto_acumulado"] == Decimal("0.00")
            assert variables_feb["meses_trabajados"] == Decimal("1.00")

    def test_dynamic_total_deducciones_during_calculation(self, app, db_session):
        """Test that sequential formulas receive up-to-date total_deducciones during calculation."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado
        from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
        from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
        from coati_payroll.nomina_engine.domain.employee_calculation import EmpleadoCalculo
        from coati_payroll.nomina_engine.domain.calculation_items import DeduccionItem

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST_DED_01", razon_social="Test Ded Corp", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_TP",
                descripcion="Test TP",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP_DED_01",
                primer_nombre="John",
                primer_apellido="Smith",
                identificacion_personal="001-010180-0003C",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("10000.00")
            emp_calculo.salario_mensual = Decimal("10000.00")
            emp_calculo.salario_bruto = Decimal("10000.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {
                "salario_bruto_acumulado": Decimal("0.00"),
                "salario_gravable_acumulado": Decimal("0.00"),
                "deducciones_antes_impuesto_acumulado": Decimal("0.00"),
                "periodos_procesados": Decimal("0.00"),
                "meses_trabajados": Decimal("0.00"),
                "salario_neto_acumulado": Decimal("0.00"),
            }

            # Prepopulate one deduction already applied in deduction sequence
            ded1 = DeduccionItem(
                codigo="DED1",
                nombre="First Deduction",
                monto=Decimal("1200.00"),
                prioridad=1,
                es_obligatoria=True,
            )
            emp_calculo.deducciones.append(ded1)

            # A formula that references total_deducciones
            formula = {
                "inputs": [
                    {"name": "total_deducciones", "type": "decimal", "default": 0},
                ],
                "steps": [
                    {
                        "name": "double_deductions",
                        "type": "calculation",
                        "formula": "total_deducciones * 2",
                    },
                ],
                "output": "double_deductions",
            }

            config_repo = ConfigRepository(db_session)
            warnings = []
            calculator = ConceptCalculator(config_repo, warnings)

            monto = calculator.calculate(
                emp_calculo=emp_calculo,
                formula_tipo="formula",
                monto_default=None,
                porcentaje=None,
                formula=formula,
                monto_override=None,
                porcentaje_override=None,
                codigo_concepto="DED2",
            )

            assert monto == Decimal("2400.00")
            assert len(warnings) == 0

    def test_deduction_amount_clamping_for_negative_balance(self, app, db_session):
        """Test that deductions are clamped and never result in negative deduction amounts."""
        from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa, Empleado, Deduccion, PlanillaDeduccion
        from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
        from coati_payroll.nomina_engine.calculators.concept_calculator import ConceptCalculator
        from coati_payroll.nomina_engine.calculators.deduction_calculator import DeductionCalculator
        from coati_payroll.nomina_engine.domain.employee_calculation import EmpleadoCalculo

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(codigo="TEST_CLAMP", razon_social="Test Clamp Corp", ruc="1234567")
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="TEST_TP",
                descripcion="Test TP",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Test Planilla",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create a deduction
            deduccion = Deduccion(
                codigo="DED_CLAMP",
                nombre="Clamp Deduction",
                formula_tipo="fixed",
                monto_default=Decimal("500.00"),
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
                codigo_empleado="EMP_CLAMP_01",
                primer_nombre="Clamp",
                primer_apellido="User",
                identificacion_personal="001-010180-0004D",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("1000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()
            db_session.commit()

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_base = Decimal("0.00")
            emp_calculo.salario_mensual = Decimal("0.00")
            emp_calculo.salario_bruto = Decimal("-50.00")
            emp_calculo.salario_neto_inasistencia = Decimal("-50.00")
            emp_calculo.total_percepciones = Decimal("0.00")
            emp_calculo.total_deducciones = Decimal("0.00")
            emp_calculo.variables_calculo = {}

            config_repo = ConfigRepository(db_session)
            warnings = []
            concept_calc = ConceptCalculator(config_repo, warnings)
            deduction_calc = DeductionCalculator(concept_calc, warnings)

            ded_items = deduction_calc.calculate(
                emp_calculo=emp_calculo,
                planilla=planilla,
                fecha_calculo=date(2024, 1, 31),
            )

            assert len(ded_items) == 1
            assert ded_items[0].monto == Decimal("0.00")
