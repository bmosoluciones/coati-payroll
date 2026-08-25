# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for AcumuladoRepository bootstrap behavior."""

from datetime import date
from decimal import Decimal

from coati_payroll.model import (
    AcumuladoAnual,
    Empleado,
    Empresa,
    Moneda,
    Nomina,
    NominaDetalle,
    NominaEmpleado,
    Percepcion,
    Planilla,
    TipoPlanilla,
    db,
)
from coati_payroll.nomina_engine.domain.employee_calculation import EmpleadoCalculo
from coati_payroll.nomina_engine.processors.accumulation_processor import AccumulationProcessor
from coati_payroll.nomina_engine.repositories.acumulado_repository import AcumuladoRepository
from coati_payroll.nomina_engine.services.employee_processing_service import EmployeeProcessingService
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


class TestAcumuladoRepository:
    """Tests for annual accumulation bootstrap behavior."""

    def test_get_or_create_bootstraps_only_in_company_initial_period(self, app, db_session):
        """It should bootstrap balances only when payroll period matches company start period."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Cordoba", simbolo="C$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Corp Inc",
                ruc="1234567",
                primer_mes_nomina=8,
                primer_anio_nomina=2025,
            )
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

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Ir",
                primer_apellido="Midyear",
                identificacion_personal="001-010180-0001A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
                salario_acumulado=Decimal("70416.67"),
                impuesto_acumulado=Decimal("1073.67"),
            )
            db_session.add(empleado)
            db_session.commit()

            repo = AcumuladoRepository(db.session)
            acumulado_inicial = repo.get_or_create(
                empleado=empleado,
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                periodo_fiscal_inicio=date(2025, 1, 1),
                periodo_inicio=date(2025, 8, 1),
                empresa_primer_mes_nomina=empresa.primer_mes_nomina,
                empresa_primer_anio_nomina=empresa.primer_anio_nomina,
                fiscal_start_month=1,
                periodos_por_anio=12,
            )

            assert acumulado_inicial.salario_bruto_acumulado == Decimal("70416.67")
            assert acumulado_inicial.impuesto_retenido_acumulado == Decimal("1073.67")
            assert acumulado_inicial.deducciones_antes_impuesto_acumulado == Decimal("0.00")
            assert acumulado_inicial.periodos_procesados == 7

            acumulado_fuera_periodo = repo.get_or_create(
                empleado=empleado,
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                periodo_fiscal_inicio=date(2026, 1, 1),
                periodo_inicio=date(2026, 9, 1),
                empresa_primer_mes_nomina=empresa.primer_mes_nomina,
                empresa_primer_anio_nomina=empresa.primer_anio_nomina,
                fiscal_start_month=1,
                periodos_por_anio=12,
            )

            assert acumulado_fuera_periodo.salario_bruto_acumulado == Decimal("0.00")
            assert acumulado_fuera_periodo.impuesto_retenido_acumulado == Decimal("0.00")
            assert acumulado_fuera_periodo.deducciones_antes_impuesto_acumulado == Decimal("0.00")
            assert acumulado_fuera_periodo.periodos_procesados == 0

    def test_get_or_create_derives_initial_periods_for_biweekly(self, app, db_session):
        """It should derive bootstrap period count from fiscal start and periodicity."""
        with app.app_context():
            moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
            db_session.add(moneda)

            empresa = Empresa(
                codigo="TEST002",
                razon_social="Test Corp 2",
                ruc="7654321",
                primer_mes_nomina=7,
                primer_anio_nomina=2025,
            )
            db_session.add(empresa)
            db_session.flush()

            tipo_planilla = TipoPlanilla(
                codigo="QUINC",
                descripcion="Quincenal",
                periodicidad="biweekly",
                dias=15,
                periodos_por_anio=24,
                mes_inicio_fiscal=4,
                dia_inicio_fiscal=1,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP002",
                primer_nombre="Ir",
                primer_apellido="Biweekly",
                identificacion_personal="001-010180-0002A",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
                salario_acumulado=Decimal("50000.00"),
                impuesto_acumulado=Decimal("700.00"),
            )
            db_session.add(empleado)
            db_session.commit()

            repo = AcumuladoRepository(db.session)
            acumulado = repo.get_or_create(
                empleado=empleado,
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                periodo_fiscal_inicio=date(2025, 4, 1),
                periodo_inicio=date(2025, 7, 1),
                empresa_primer_mes_nomina=empresa.primer_mes_nomina,
                empresa_primer_anio_nomina=empresa.primer_anio_nomina,
                fiscal_start_month=4,
                periodos_por_anio=24,
            )

            assert acumulado.periodos_procesados == 6

    def test_mid_month_fiscal_start_uses_previous_year_before_cutoff(self, app, db_session):
        """A period before the fiscal day cutoff must not use a future accumulation year."""
        with app.app_context():
            moneda = Moneda(codigo="FSC", nombre="Fiscal", simbolo="F$", activo=True)
            empresa = Empresa(codigo="FISCAL15", razon_social="Fiscal Corp", ruc="543210")
            tipo_planilla = TipoPlanilla(
                codigo="FISCAL15",
                descripcion="Mensual con corte día 15",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=7,
                dia_inicio_fiscal=15,
            )
            db_session.add_all([moneda, empresa, tipo_planilla])
            db_session.flush()
            planilla = Planilla(
                nombre="Planilla fiscal",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                mes_inicio_fiscal=7,
                activo=True,
            )
            empleado = Empleado(
                codigo_empleado="FISCAL-EMP",
                primer_nombre="Fiscal",
                primer_apellido="Empleado",
                identificacion_personal="001-010180-0100A",
                fecha_alta=date(2020, 1, 1),
                salario_base=Decimal("1000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add_all([planilla, empleado])
            db_session.flush()

            acumulado_previo = AcumuladoAnual(
                empleado_id=empleado.id,
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                periodo_fiscal_inicio=date(2024, 7, 15),
                periodo_fiscal_fin=date(2025, 7, 15),
                salario_bruto_acumulado=Decimal("500.00"),
            )
            db_session.add(acumulado_previo)
            db_session.flush()

            periodo_inicio, periodo_fin = date(2025, 7, 1), date(2025, 7, 14)
            service = EmployeeProcessingService(None, AcumuladoRepository(db.session))
            assert service._get_acumulado_anual(empleado, planilla, periodo_inicio) == acumulado_previo

            emp_calculo = EmpleadoCalculo(empleado, planilla)
            emp_calculo.salario_bruto = Decimal("100.00")
            emp_calculo.salario_gravable = Decimal("100.00")
            AccumulationProcessor(AcumuladoRepository(db.session)).update_accumulations(
                emp_calculo, planilla, periodo_inicio, periodo_fin
            )

            assert acumulado_previo.salario_bruto_acumulado == Decimal("600.00")
            assert db_session.query(AcumuladoAnual).count() == 1

            # Recalculation/anulación must locate that very same fiscal
            # accumulation even if the operator calculated the payroll after
            # the July 15 boundary.
            percepcion = Percepcion(
                codigo="GRAVABLE_HISTORICA",
                nombre="Percepción gravable histórica",
                formula_tipo="fixed",
                monto_default=Decimal("100.00"),
                gravable=True,
                activo=True,
            )
            db_session.add(percepcion)
            db_session.flush()
            acumulado_previo.salario_bruto_acumulado = Decimal("700.00")
            acumulado_previo.salario_gravable_acumulado = Decimal("200.00")
            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo_original=date(2025, 7, 20),
                catalogos_snapshot={"percepciones": [{"id": percepcion.id, "gravable": True}]},
            )
            db_session.add(nomina)
            db_session.flush()
            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("200.00"),
                sueldo_base_historico=Decimal("100.00"),
                inasistencia_descuento=Decimal("0.00"),
            )
            db_session.add(nomina_empleado)
            db_session.flush()
            db_session.add(
                NominaDetalle(
                    nomina_empleado_id=nomina_empleado.id,
                    tipo="income",
                    codigo=percepcion.codigo,
                    monto=Decimal("100.00"),
                    percepcion_id=percepcion.id,
                )
            )
            # The catalog changed after payroll generation. Rollback must use
            # the frozen ``gravable=True`` metadata, not this live value.
            percepcion.gravable = False
            db_session.flush()

            NominaService._rollback_accumulations_for_nomina(nomina, planilla)

            assert acumulado_previo.salario_bruto_acumulado == Decimal("500.00")
            assert acumulado_previo.salario_gravable_acumulado == Decimal("0.00")
