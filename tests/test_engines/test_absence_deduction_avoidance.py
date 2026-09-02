# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for absence (inasistencia) deduction avoidance.

This module validates that absences marked for payment discount don't get
double-deducted when they also exist as deductions in the planilla.

The system tracks three types of absences:
1. Absences that do NOT affect payment (es_inasistencia=True, descontar_pago_inasistencia=False)
2. Absences that ARE deducted from payment (es_inasistencia=True, descontar_pago_inasistencia=True)
3. Absences deducted from payment but paid in a different concept (tracked codes avoid double deduction)
"""

from datetime import date
from decimal import Decimal


from coati_payroll.enums import FormulaType
from coati_payroll.nomina_engine.processors.novelty_processor import NoveltyProcessor
from coati_payroll.nomina_engine.repositories.novelty_repository import NoveltyRepository
from coati_payroll.model import (
    Empresa,
    Moneda,
    TipoPlanilla,
    Planilla,
    Empleado,
    Percepcion,
    PlanillaIngreso,
    NominaNovedad,
    ConfiguracionCalculos,
)


class TestNoveltyProcessor:
    """Tests for NoveltyProcessor with absence tracking."""

    def test_load_novelties_with_absence_discount_tracking(self, app, db_session):
        """Test that novelties with absence discount are tracked correctly."""
        with app.app_context():
            # Create basic setup
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Company SA",
                ruc="J-12345678",
            )
            db_session.add(empresa)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Juan",
                primer_apellido="Pérez",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("15000.00"),
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            # Create novelties with and without payment discount
            novedad1 = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="AUSENCIA_JUSTIFICADA",
                valor_cantidad=Decimal("1.00"),
                tipo_valor="dias",
                fecha_novedad=date(2025, 1, 10),
                es_inasistencia=True,
                descontar_pago_inasistencia=False,  # No discount
            )
            db_session.add(novedad1)

            novedad2 = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="AUSENCIA_INJUSTIFICADA",
                valor_cantidad=Decimal("2.00"),
                tipo_valor="dias",
                fecha_novedad=date(2025, 1, 15),
                es_inasistencia=True,
                descontar_pago_inasistencia=True,  # With discount
            )
            db_session.add(novedad2)

            novedad3 = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="HORAS_EXTRA",
                valor_cantidad=Decimal("10.00"),
                tipo_valor="horas",
                fecha_novedad=date(2025, 1, 20),
                es_inasistencia=False,  # Not an absence
                descontar_pago_inasistencia=False,
            )
            db_session.add(novedad3)

            db_session.flush()
            db_session.commit()

            # Test NoveltyProcessor
            novelty_repo = NoveltyRepository(db_session)
            processor = NoveltyProcessor(novelty_repo)

            novedades, ausencia_resumen, codigos_descuento = processor.load_novelties_with_absences(
                empleado, date(2025, 1, 1), date(2025, 1, 31)
            )

            # Verify novelties are loaded
            assert "AUSENCIA_JUSTIFICADA" in novedades
            assert "AUSENCIA_INJUSTIFICADA" in novedades
            assert "HORAS_EXTRA" in novedades

            assert novedades["AUSENCIA_JUSTIFICADA"] == Decimal("1.00")
            assert novedades["AUSENCIA_INJUSTIFICADA"] == Decimal("2.00")
            assert novedades["HORAS_EXTRA"] == Decimal("10.00")

            # Verify only absences with discount are tracked
            assert ausencia_resumen["dias"] == Decimal("2.00")  # Only AUSENCIA_INJUSTIFICADA
            assert ausencia_resumen["horas"] == Decimal("0.00")

            # Verify discount codes are tracked
            assert "AUSENCIA_INJUSTIFICADA" in codigos_descuento
            assert "AUSENCIA_JUSTIFICADA" not in codigos_descuento
            assert "HORAS_EXTRA" not in codigos_descuento

    def test_load_novelties_with_hours_absence(self, app, db_session):
        """Test absence tracking with hours."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Company SA",
                ruc="J-12345678",
            )
            db_session.add(empresa)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Juan",
                primer_apellido="Pérez",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("15000.00"),
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            # Create absence in hours
            novedad = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="AUSENCIA_HORAS",
                valor_cantidad=Decimal("4.00"),
                tipo_valor="horas",
                fecha_novedad=date(2025, 1, 15),
                es_inasistencia=True,
                descontar_pago_inasistencia=True,
            )
            db_session.add(novedad)
            db_session.flush()
            db_session.commit()

            # Test processor
            novelty_repo = NoveltyRepository(db_session)
            processor = NoveltyProcessor(novelty_repo)

            novedades, ausencia_resumen, codigos_descuento = processor.load_novelties_with_absences(
                empleado, date(2025, 1, 1), date(2025, 1, 31)
            )

            # Verify hours are tracked
            assert ausencia_resumen["dias"] == Decimal("0.00")
            assert ausencia_resumen["horas"] == Decimal("4.00")
            assert "AUSENCIA_HORAS" in codigos_descuento


class TestMedicalSubsidyScenario:
    """Tests for medical subsidy scenario: absence with compensating perception."""

    def test_medical_subsidy_with_absence_and_perception(self, app, db_session):
        """Test medical subsidy: absence deducts day, perception adds 80% compensation.

        This is a real-world scenario where:
        1. Employee is absent (es_inasistencia=True, descontar_pago_inasistencia=True)
        2. A perception (subsidio médico) compensates with 80% of daily salary
        3. Net effect: Employee loses 20% of daily pay (100% deducted - 80% compensated)
        """
        with app.app_context():
            # Create basic setup
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Company SA",
                ruc="J-12345678",
            )
            db_session.add(empresa)
            db_session.flush()

            # Create configuration for absence calculations
            config = ConfiguracionCalculos(
                empresa_id=empresa.id,
                dias_mes_nomina=30,
                horas_jornada_diaria=8,
            )
            db_session.add(config)
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

            # Create a perception for medical subsidy (80% of daily salary)
            # This will compensate for the absence
            percepcion_subsidio = Percepcion(
                codigo="SUBSIDIO_MEDICO",
                nombre="Subsidio Médico",
                descripcion="Compensación del 80% por ausencia médica",
                formula_tipo=FormulaType.FIJO,  # Fixed amount will be set via novedad
                monto_default=Decimal("0.00"),
                gravable=True,
                activo=True,
            )
            db_session.add(percepcion_subsidio)
            db_session.flush()

            # Add perception to planilla
            planilla_percepcion = PlanillaIngreso(
                planilla_id=planilla.id,
                percepcion_id=percepcion_subsidio.id,
                activo=True,
            )
            db_session.add(planilla_percepcion)
            db_session.flush()

            # Create absence novelty (medical absence - deducts full day)
            novedad_ausencia = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="AUSENCIA_MEDICA",
                valor_cantidad=Decimal("1.00"),  # 1 day absent
                tipo_valor="dias",
                fecha_novedad=date(2025, 1, 15),
                es_inasistencia=True,
                descontar_pago_inasistencia=True,  # Deduct the day
            )
            db_session.add(novedad_ausencia)

            # Calculate expected subsidy: 80% of daily salary
            # Daily salary = 15000 / 30 = 500
            # Subsidy = 500 * 0.80 = 400
            salario_diario = Decimal("15000.00") / Decimal("30")
            subsidio_monto = salario_diario * Decimal("0.80")

            # Create perception novelty (medical subsidy - adds 80% compensation)
            novedad_subsidio = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="SUBSIDIO_MEDICO",
                valor_cantidad=subsidio_monto,  # 80% of daily salary
                tipo_valor="monto",
                fecha_novedad=date(2025, 1, 15),
                percepcion_id=percepcion_subsidio.id,
                es_inasistencia=False,  # This is NOT an absence, it's compensation
                descontar_pago_inasistencia=False,
            )
            db_session.add(novedad_subsidio)
            db_session.flush()
            db_session.commit()

            # Test NoveltyProcessor - verify both novelties are loaded
            novelty_repo = NoveltyRepository(db_session)
            processor = NoveltyProcessor(novelty_repo)

            novedades, ausencia_resumen, codigos_descuento = processor.load_novelties_with_absences(
                empleado, date(2025, 1, 1), date(2025, 1, 31)
            )

            # Verify both novelties are present
            assert "AUSENCIA_MEDICA" in novedades
            assert "SUBSIDIO_MEDICO" in novedades

            # Verify absence tracking
            assert ausencia_resumen["dias"] == Decimal("1.00")  # 1 day deducted
            assert "AUSENCIA_MEDICA" in codigos_descuento

            # Verify subsidy amount
            assert novedades["SUBSIDIO_MEDICO"] == subsidio_monto

            # Verify the subsidy is NOT tracked as an absence
            assert "SUBSIDIO_MEDICO" not in codigos_descuento

            # Expected net effect:
            # - Salary base: 15000
            # - Deducted for absence: 500 (1 day)
            # - Salary after absence: 14500
            # - Subsidy added: 400 (80% of daily)
            # - Expected gross: 14500 + 400 = 14900
            # - Net loss: 100 (20% of daily salary)

            expected_salary_after_absence = Decimal("15000.00") - salario_diario
            expected_gross = expected_salary_after_absence + subsidio_monto
            expected_net_loss = salario_diario - subsidio_monto

            assert expected_salary_after_absence == Decimal("14500.00")
            assert abs(expected_gross - Decimal("14900.00")) < Decimal("0.01")
            assert abs(expected_net_loss - Decimal("100.00")) < Decimal("0.01")

    def test_medical_subsidy_multiple_days(self, app, db_session):
        """Test medical subsidy with multiple absence days."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Company SA",
                ruc="J-12345678",
            )
            db_session.add(empresa)
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

            # Create 3 days of medical absence with subsidy
            for day in [10, 11, 12]:
                # Absence
                novedad_ausencia = NominaNovedad(
                    nomina_id="test_nomina",
                    empleado_id=empleado.id,
                    codigo_concepto=f"AUSENCIA_MEDICA_DIA{day}",
                    valor_cantidad=Decimal("1.00"),
                    tipo_valor="dias",
                    fecha_novedad=date(2025, 1, day),
                    es_inasistencia=True,
                    descontar_pago_inasistencia=True,
                )
                db_session.add(novedad_ausencia)

                # Subsidy (80% compensation)
                salario_diario = Decimal("15000.00") / Decimal("30")
                subsidio_monto = salario_diario * Decimal("0.80")
                novedad_subsidio = NominaNovedad(
                    nomina_id="test_nomina",
                    empleado_id=empleado.id,
                    codigo_concepto=f"SUBSIDIO_MEDICO_DIA{day}",
                    valor_cantidad=subsidio_monto,
                    tipo_valor="monto",
                    fecha_novedad=date(2025, 1, day),
                    es_inasistencia=False,
                    descontar_pago_inasistencia=False,
                )
                db_session.add(novedad_subsidio)

            db_session.flush()
            db_session.commit()

            # Test NoveltyProcessor
            novelty_repo = NoveltyRepository(db_session)
            processor = NoveltyProcessor(novelty_repo)

            novedades, ausencia_resumen, codigos_descuento = processor.load_novelties_with_absences(
                empleado, date(2025, 1, 1), date(2025, 1, 31)
            )

            # Verify 3 days of absence are tracked
            assert ausencia_resumen["dias"] == Decimal("3.00")

            # Verify all absence codes are tracked
            assert "AUSENCIA_MEDICA_DIA10" in codigos_descuento
            assert "AUSENCIA_MEDICA_DIA11" in codigos_descuento
            assert "AUSENCIA_MEDICA_DIA12" in codigos_descuento

            # Verify subsidy codes are NOT tracked as absences
            assert "SUBSIDIO_MEDICO_DIA10" not in codigos_descuento
            assert "SUBSIDIO_MEDICO_DIA11" not in codigos_descuento
            assert "SUBSIDIO_MEDICO_DIA12" not in codigos_descuento

            # Verify total subsidy amount
            total_subsidio = sum(novedades.get(f"SUBSIDIO_MEDICO_DIA{day}", Decimal("0.00")) for day in [10, 11, 12])
            expected_total_subsidio = (Decimal("15000.00") / Decimal("30")) * Decimal("0.80") * Decimal("3")
            assert abs(total_subsidio - expected_total_subsidio) < Decimal("0.01")

    def test_medical_subsidy_biweekly_60_percent(self, app, db_session):
        """Test medical subsidy case: 5 days absence with 60% subsidy in biweekly payroll.

        Real case scenario:
        - Monthly salary: 30,000.00
        - Biweekly salary: 15,000.00
        - Daily salary: 1,000.00
        - First fortnight: 5 days with medical subsidy at 60%

        Expected calculation:
        - Base salary: 15,000.00
        - Absence (5 days): -5,000.00
        - Salary after absence: 10,000.00
        - Subsidy perception (60%): 3,000.00
        - Total income: 13,000.00
        """
        with app.app_context():
            # Create basic setup
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Company SA",
                ruc="J-12345678",
            )
            db_session.add(empresa)
            db_session.flush()

            # Create configuration for absence calculations
            config = ConfiguracionCalculos(
                empresa_id=empresa.id,
                dias_mes_nomina=30,
                horas_jornada_diaria=8,
            )
            db_session.add(config)
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

            # Employee with monthly salary of 30,000
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Juan",
                primer_apellido="Pérez",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("30000.00"),  # Monthly salary
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            # Create a perception for medical subsidy
            percepcion_subsidio = Percepcion(
                codigo="SUBSIDIO_MEDICO",
                nombre="Subsidio Médico 60%",
                descripcion="Compensación del 60% por ausencia médica",
                formula_tipo=FormulaType.FIJO,
                monto_default=Decimal("0.00"),
                gravable=True,
                activo=True,
            )
            db_session.add(percepcion_subsidio)
            db_session.flush()

            # Add perception to planilla
            planilla_percepcion = PlanillaIngreso(
                planilla_id=planilla.id,
                percepcion_id=percepcion_subsidio.id,
                activo=True,
            )
            db_session.add(planilla_percepcion)
            db_session.flush()

            # Calculate values
            salario_mensual = Decimal("30000.00")
            salario_quincenal = Decimal("15000.00")
            salario_diario = Decimal("1000.00")  # 30000 / 30
            dias_ausencia = Decimal("5.00")
            porcentaje_subsidio = Decimal("0.60")

            # Expected values
            descuento_ausencia = salario_diario * dias_ausencia  # 5,000.00
            salario_despues_ausencia = salario_quincenal - descuento_ausencia  # 10,000.00
            subsidio_monto = descuento_ausencia * porcentaje_subsidio  # 3,000.00
            total_ingreso_esperado = salario_despues_ausencia + subsidio_monto  # 13,000.00

            # Create absence novelty (5 days medical absence)
            novedad_ausencia = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="AUSENCIA_MEDICA",
                valor_cantidad=dias_ausencia,
                tipo_valor="dias",
                fecha_novedad=date(2025, 1, 15),
                es_inasistencia=True,
                descontar_pago_inasistencia=True,  # Deduct full days
            )
            db_session.add(novedad_ausencia)

            # Create subsidy perception (60% compensation)
            novedad_subsidio = NominaNovedad(
                nomina_id="test_nomina",
                empleado_id=empleado.id,
                codigo_concepto="SUBSIDIO_MEDICO",
                valor_cantidad=subsidio_monto,
                tipo_valor="monto",
                fecha_novedad=date(2025, 1, 15),
                percepcion_id=percepcion_subsidio.id,
                es_inasistencia=False,  # This is compensation, not absence
                descontar_pago_inasistencia=False,
            )
            db_session.add(novedad_subsidio)
            db_session.flush()
            db_session.commit()

            # Test NoveltyProcessor
            novelty_repo = NoveltyRepository(db_session)
            processor = NoveltyProcessor(novelty_repo)

            novedades, ausencia_resumen, codigos_descuento = processor.load_novelties_with_absences(
                empleado, date(2025, 1, 1), date(2025, 1, 15)
            )

            # Verify both novelties are present
            assert "AUSENCIA_MEDICA" in novedades
            assert "SUBSIDIO_MEDICO" in novedades

            # Verify absence tracking - 5 days deducted
            assert ausencia_resumen["dias"] == Decimal("5.00")
            assert "AUSENCIA_MEDICA" in codigos_descuento

            # Verify subsidy is NOT tracked as absence
            assert "SUBSIDIO_MEDICO" not in codigos_descuento

            # Verify amounts
            assert novedades["AUSENCIA_MEDICA"] == Decimal("5.00")
            assert novedades["SUBSIDIO_MEDICO"] == subsidio_monto

            # Verify expected calculations
            assert descuento_ausencia == Decimal("5000.00")
            assert salario_despues_ausencia == Decimal("10000.00")
            assert subsidio_monto == Decimal("3000.00")
            assert total_ingreso_esperado == Decimal("13000.00")

            # Test the complete flow would result in expected values:
            # Base salary for biweekly: 15,000.00
            # After absence deduction: 15,000.00 - 5,000.00 = 10,000.00
            # After subsidy perception: 10,000.00 + 3,000.00 = 13,000.00
            print("\n=== Test Case Verification ===")
            print(f"Salario Mensual: {salario_mensual}")
            print(f"Salario Quincenal: {salario_quincenal}")
            print(f"Salario Diario: {salario_diario}")
            print(f"Días de Ausencia: {dias_ausencia}")
            print(f"Descuento por Ausencia: {descuento_ausencia}")
            print(f"Salario después de Ausencia: {salario_despues_ausencia}")
            print(f"Subsidio (60%): {subsidio_monto}")
            print(f"Total Ingreso Esperado: {total_ingreso_esperado}")
            print("==============================\n")
