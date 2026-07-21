# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for AcumuladoRepository bootstrap behavior."""

from datetime import date
from decimal import Decimal

from coati_payroll.model import Empleado, Empresa, Moneda, TipoPlanilla, db
from coati_payroll.nomina_engine.repositories.acumulado_repository import AcumuladoRepository


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
