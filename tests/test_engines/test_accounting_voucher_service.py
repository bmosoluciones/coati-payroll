# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for AccountingVoucherService - accounting integration.

This module tests the accounting voucher generation service that handles:
- Accounting configuration validation
- Voucher generation from payroll calculations
- Base salary accounting entries
- Loan/advance accounting entries
- Concept (perception/deduction/benefit) accounting entries
- Cost center allocation
- Summarization and netting
- Audit trail tracking
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from coati_payroll.model import (
    db,
    Empresa,
    Moneda,
    TipoPlanilla,
    Planilla,
    Empleado,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    Percepcion,
    Deduccion,
    Adelanto,
    PlanillaIngreso,
    PlanillaDeduccion,
    ComprobanteContable,
    ComprobanteContableLinea,
    VacationPolicy,
    VacationAccount,
    VacationLedger,
    VacationNovelty,
    NominaNovedad,
)
from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService
from coati_payroll.enums import NominaEstado, AdelantoEstado


class TestAccountingConfigurationValidation:
    """Tests for accounting configuration validation."""

    def test_validate_complete_configuration(self, app, db_session):
        """Test validation passes when all accounts are configured."""
        with app.app_context():
            # Create test data with complete accounting configuration
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
                # Accounting configuration for base salary
                codigo_cuenta_debe_salario="5101",
                descripcion_cuenta_debe_salario="Gasto por Salario",
                codigo_cuenta_haber_salario="2101",
                descripcion_cuenta_haber_salario="Salario por Pagar",
            )
            db_session.add(planilla)
            db_session.flush()

            # Create percepcion with accounting config
            percepcion = Percepcion(
                codigo="BONO",
                nombre="Bono Producción",
                formula_tipo="fixed",
                activo=True,
                contabilizable=True,
                codigo_cuenta_debe="5102",
                descripcion_cuenta_debe="Gasto por Bono",
                codigo_cuenta_haber="2102",
                descripcion_cuenta_haber="Bonos por Pagar",
            )
            db_session.add(percepcion)
            db_session.flush()

            # Link percepcion to planilla
            planilla_ingreso = PlanillaIngreso(
                planilla_id=planilla.id,
                percepcion_id=percepcion.id,
                activo=True,
            )
            db_session.add(planilla_ingreso)
            db_session.commit()

            # Test validation
            service = AccountingVoucherService(db_session)
            is_valid, warnings = service.validate_accounting_configuration(planilla)

            assert is_valid is True
            assert len(warnings) == 0

    def test_validate_missing_base_salary_accounts(self, app, db_session):
        """Test validation fails when base salary accounts are missing."""
        with app.app_context():
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
                # Missing accounting configuration
                codigo_cuenta_debe_salario=None,
                codigo_cuenta_haber_salario=None,
            )
            db_session.add(planilla)
            db_session.commit()

            service = AccountingVoucherService(db_session)
            is_valid, warnings = service.validate_accounting_configuration(planilla)

            assert is_valid is False
            assert len(warnings) == 2
            assert any("débito para salario básico" in w for w in warnings)
            assert any("crédito para salario básico" in w for w in warnings)

    def test_validate_missing_concept_accounts(self, app, db_session):
        """Test validation detects missing accounts in concepts."""
        with app.app_context():
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
            )
            db_session.add(planilla)
            db_session.flush()

            # Create deduccion without accounting config
            deduccion = Deduccion(
                codigo="INSS",
                nombre="INSS Laboral",
                formula_tipo="percentage",
                activo=True,
                contabilizable=True,
                codigo_cuenta_debe=None,  # Missing
                codigo_cuenta_haber=None,  # Missing
            )
            db_session.add(deduccion)
            db_session.flush()

            planilla_deduccion = PlanillaDeduccion(
                planilla_id=planilla.id,
                deduccion_id=deduccion.id,
                activo=True,
                prioridad=100,
            )
            db_session.add(planilla_deduccion)
            db_session.commit()

            service = AccountingVoucherService(db_session)
            is_valid, warnings = service.validate_accounting_configuration(planilla)

            assert is_valid is False
            assert len(warnings) == 2
            assert any("INSS Laboral" in w and "débito" in w for w in warnings)
            assert any("INSS Laboral" in w and "crédito" in w for w in warnings)



    def test_validate_paid_vacation_policy_requires_accounts(self, app, db_session):
        """Paid vacation policy should warn when liability accounts are missing."""
        with app.app_context():
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
            )
            db_session.add(planilla)
            db_session.flush()

            policy = VacationPolicy(
                codigo="POL-PAID",
                nombre="Vacaciones Pagadas",
                planilla_id=planilla.id,
                empresa_id=empresa.id,
                son_vacaciones_pagadas=True,
                accrual_rate=Decimal("1.25"),
            )
            db_session.add(policy)
            db_session.commit()

            service = AccountingVoucherService(db_session)
            is_valid, warnings = service.validate_accounting_configuration(planilla)

            assert is_valid is False
            assert any("cuenta débito de vacaciones pagadas" in w for w in warnings)
            assert any("cuenta crédito de vacaciones pagadas" in w for w in warnings)


class TestAccountingVoucherGeneration:
    """Tests for accounting voucher generation."""

    def test_generate_voucher_includes_paid_vacation_liability_lines(self, app, db_session):
        """Voucher must include paid vacation liability lines when policy flag is enabled."""
        with app.app_context():
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                empresa_id=empresa.id,
                codigo_empleado="EMP001",
                primer_nombre="Juan",
                primer_apellido="Pérez",
                identificacion_personal="001-010101-0001A",
                salario_base=Decimal("9000.00"),
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2026, 1, 1),
                periodo_fin=date(2026, 1, 31),
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("9000.00"),
                total_deducciones=Decimal("0.00"),
                total_neto=Decimal("9000.00"),
            )
            db_session.add(nomina)
            db_session.flush()

            ne = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("9000.00"),
                total_ingresos=Decimal("9000.00"),
                total_deducciones=Decimal("0.00"),
                salario_neto=Decimal("9000.00"),
                sueldo_base_historico=Decimal("9000.00"),
            )
            db_session.add(ne)
            db_session.flush()

            policy = VacationPolicy(
                codigo="POL-PAID",
                nombre="Vacaciones Pagadas",
                planilla_id=planilla.id,
                empresa_id=empresa.id,
                son_vacaciones_pagadas=True,
                cuenta_debito_vacaciones_pagadas="5201",
                descripcion_cuenta_debito_vacaciones_pagadas="Gasto Vacaciones Pagadas",
                cuenta_credito_vacaciones_pagadas="2205",
                descripcion_cuenta_credito_vacaciones_pagadas="Pasivo Vacaciones",
                accrual_rate=Decimal("1.25"),
            )
            db_session.add(policy)
            db_session.flush()

            account = VacationAccount(
                empleado_id=empleado.id,
                policy_id=policy.id,
                current_balance=Decimal("0.00"),
                activo=True,
            )
            db_session.add(account)
            db_session.flush()

            db_session.add(
                VacationLedger(
                    account_id=account.id,
                    empleado_id=empleado.id,
                    fecha=nomina.periodo_fin,
                    entry_type="accrual",
                    quantity=Decimal("1.2500"),
                    source="payroll",
                    reference_type="nomina_empleado",
                    reference_id=ne.id,
                )
            )
            db_session.commit()

            service = AccountingVoucherService(db_session)
            comprobante = service.generate_audit_voucher(nomina, planilla)
            db_session.flush()

            lineas = (
                db_session.query(ComprobanteContableLinea)
                .filter(ComprobanteContableLinea.comprobante_id == comprobante.id)
                .all()
            )
            vac_lines = [l for l in lineas if l.tipo_concepto == "vacation_liability"]

            assert len(vac_lines) == 2
            assert any(l.codigo_cuenta == "5201" and l.debito > 0 for l in vac_lines)
            assert any(l.codigo_cuenta == "2205" and l.credito > 0 for l in vac_lines)


    def test_generate_voucher_reverses_paid_vacation_liability_on_usage(self, app, db_session):
        """Usage entries (vacation_novelty) must reverse liability in same payroll voucher."""
        with app.app_context():
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                empresa_id=empresa.id,
                codigo_empleado="EMP002",
                primer_nombre="Ana",
                primer_apellido="López",
                identificacion_personal="001-020202-0002B",
                salario_base=Decimal("9000.00"),
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2026, 2, 1),
                periodo_fin=date(2026, 2, 28),
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("9000.00"),
                total_deducciones=Decimal("0.00"),
                total_neto=Decimal("9000.00"),
            )
            db_session.add(nomina)
            db_session.flush()

            ne = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("9000.00"),
                total_ingresos=Decimal("9000.00"),
                total_deducciones=Decimal("0.00"),
                salario_neto=Decimal("9000.00"),
                sueldo_base_historico=Decimal("9000.00"),
            )
            db_session.add(ne)
            db_session.flush()

            policy = VacationPolicy(
                codigo="POL-PAID-USE",
                nombre="Vacaciones Pagadas Uso",
                planilla_id=planilla.id,
                empresa_id=empresa.id,
                son_vacaciones_pagadas=True,
                cuenta_debito_vacaciones_pagadas="5201",
                descripcion_cuenta_debito_vacaciones_pagadas="Gasto Vacaciones Pagadas",
                cuenta_credito_vacaciones_pagadas="2205",
                descripcion_cuenta_credito_vacaciones_pagadas="Pasivo Vacaciones",
                accrual_rate=Decimal("1.25"),
            )
            db_session.add(policy)
            db_session.flush()

            account = VacationAccount(
                empleado_id=empleado.id,
                policy_id=policy.id,
                current_balance=Decimal("1.25"),
                activo=True,
            )
            db_session.add(account)
            db_session.flush()

            novelty = VacationNovelty(
                empleado_id=empleado.id,
                account_id=account.id,
                start_date=nomina.periodo_inicio,
                end_date=nomina.periodo_inicio,
                units=Decimal("1.00"),
                estado="applied",
            )
            db_session.add(novelty)
            db_session.flush()

            db_session.add(
                NominaNovedad(
                    nomina_id=nomina.id,
                    empleado_id=empleado.id,
                    codigo_concepto="VAC",
                    valor_cantidad=Decimal("1.00"),
                    es_descanso_vacaciones=True,
                    vacation_novelty_id=novelty.id,
                )
            )

            db_session.add(
                VacationLedger(
                    account_id=account.id,
                    empleado_id=empleado.id,
                    fecha=nomina.periodo_fin,
                    entry_type="usage",
                    quantity=Decimal("-1.0000"),
                    source="novelty",
                    reference_type="vacation_novelty",
                    reference_id=novelty.id,
                )
            )
            db_session.commit()

            service = AccountingVoucherService(db_session)
            comprobante = service.generate_audit_voucher(nomina, planilla)
            db_session.flush()

            lineas = (
                db_session.query(ComprobanteContableLinea)
                .filter(ComprobanteContableLinea.comprobante_id == comprobante.id)
                .all()
            )
            vac_lines = [l for l in lineas if l.tipo_concepto == "vacation_liability"]

            assert len(vac_lines) == 2
            # usage should reverse: debit liability, credit expense
            assert any(l.codigo_cuenta == "2205" and l.debito > 0 for l in vac_lines)
            assert any(l.codigo_cuenta == "5201" and l.credito > 0 for l in vac_lines)

    def test_generate_voucher_base_salary(self, app, db_session):
        """Test voucher generation for base salary."""
        with app.app_context():
            # Setup
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
                codigo_cuenta_debe_salario="5101",
                descripcion_cuenta_debe_salario="Gasto por Salario",
                codigo_cuenta_haber_salario="2101",
                descripcion_cuenta_haber_salario="Salario por Pagar",
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
                centro_costos="CC-01",
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("0.00"),
                total_neto=Decimal("15000.00"),
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                total_ingresos=Decimal("15000.00"),
                total_deducciones=Decimal("0.00"),
                salario_neto=Decimal("15000.00"),
                centro_costos_snapshot="CC-01",
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # Generate voucher
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla, date(2024, 12, 31), "test_user")

            assert comprobante is not None
            assert comprobante.nomina_id == nomina.id
            assert comprobante.total_debitos == Decimal("15000.00")
            assert comprobante.total_creditos == Decimal("15000.00")
            assert comprobante.balance == Decimal("0.00")

            # Check lines
            lineas = db_session.query(ComprobanteContableLinea).filter_by(comprobante_id=comprobante.id).all()
            assert len(lineas) == 2  # Debit and credit

            linea_debe = [l for l in lineas if l.tipo_debito_credito == "debito"][0]
            assert linea_debe.codigo_cuenta == "5101"
            assert linea_debe.debito == Decimal("15000.00")
            assert linea_debe.centro_costos == "CC-01"
            assert linea_debe.empleado_codigo == "EMP001"

            linea_haber = [l for l in lineas if l.tipo_debito_credito == "credito"][0]
            assert linea_haber.codigo_cuenta == "2101"
            assert linea_haber.credito == Decimal("15000.00")
            assert linea_haber.centro_costos == "CC-01"

    def test_generate_voucher_with_null_cost_center(self, app, db_session):
        """Test voucher generation when employee has no cost center."""
        with app.app_context():
            # Setup similar to previous test but without cost center
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP002",
                primer_nombre="Maria",
                primer_apellido="Lopez",
                identificacion_personal="002-020290-0002B",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("10000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                centro_costos=None,  # No cost center
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.GENERADO,
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("10000.00"),
                sueldo_base_historico=Decimal("10000.00"),
                centro_costos_snapshot=None,
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # Generate voucher
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla)

            # Check that lines have null cost center
            lineas = db_session.query(ComprobanteContableLinea).filter_by(comprobante_id=comprobante.id).all()
            assert all(l.centro_costos is None for l in lineas)

    def test_generate_voucher_with_loan(self, app, db_session):
        """Test voucher generation with loan deductions."""
        with app.app_context():
            # Setup
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP003",
                primer_nombre="Carlos",
                primer_apellido="Martinez",
                identificacion_personal="003-030390-0003C",
                fecha_alta=date(2024, 1, 1),
                salario_base=Decimal("15000.00"),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                centro_costos="CC-02",
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            # Create loan deduction
            deduccion_prestamo = Deduccion(
                codigo="PREST",
                nombre="Préstamo",
                formula_tipo="fixed",
                activo=True,
                contabilizable=True,
            )
            db_session.add(deduccion_prestamo)
            db_session.flush()

            # Create active loan
            adelanto = Adelanto(
                empleado_id=empleado.id,
                deduccion_id=deduccion_prestamo.id,
                tipo="loan",
                monto_aprobado=Decimal("10000.00"),
                saldo_pendiente=Decimal("8000.00"),
                cuotas_pactadas=10,
                monto_por_cuota=Decimal("1000.00"),
                estado=AdelantoEstado.APLICADO,
                cuenta_haber="1301",  # Loan control account
            )
            db_session.add(adelanto)
            db_session.flush()

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.GENERADO,
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("1000.00"),
                salario_neto=Decimal("14000.00"),
                sueldo_base_historico=Decimal("15000.00"),
                centro_costos_snapshot="CC-02",
            )
            db_session.add(nomina_empleado)
            db_session.flush()

            # Add loan deduction detail
            nomina_detalle = NominaDetalle(
                nomina_empleado_id=nomina_empleado.id,
                tipo="deduction",
                codigo="PREST",
                descripcion="Cuota Préstamo",
                monto=Decimal("1000.00"),
                orden=1,
                deduccion_id=deduccion_prestamo.id,
            )
            db_session.add(nomina_detalle)
            db_session.commit()

            # Generate voucher
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla)

            # Check lines include loan entries
            lineas = db_session.query(ComprobanteContableLinea).filter_by(comprobante_id=comprobante.id).all()

            # Should have base salary (2 lines) + loan (2 lines) = 4 lines
            assert len(lineas) >= 4

            # Find loan lines
            loan_lines = [l for l in lineas if l.tipo_concepto == "loan"]
            assert len(loan_lines) == 2

            # Check loan debit (salary payable)
            loan_debe = [l for l in loan_lines if l.tipo_debito_credito == "debito"][0]
            assert loan_debe.codigo_cuenta == "2101"  # Salary payable
            assert loan_debe.debito == Decimal("1000.00")

            # Check loan credit (loan control)
            loan_haber = [l for l in loan_lines if l.tipo_debito_credito == "credito"][0]
            assert loan_haber.codigo_cuenta == "1301"  # Loan control
            assert loan_haber.credito == Decimal("1000.00")


class TestAccountingVoucherSummarization:
    """Tests for voucher summarization and netting."""

    def test_summarize_voucher_by_account_and_cost_center(self, app, db_session):
        """Test summarization groups by account and cost center."""
        with app.app_context():
            # Create comprobante with multiple lines for same account/cost center
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

            comprobante = ComprobanteContable(
                nomina_id="test_nomina_id",
                fecha_calculo=date(2024, 12, 31),
                concepto="Test Voucher",
                moneda_id=moneda.id,
                total_debitos=Decimal("30000.00"),
                total_creditos=Decimal("30000.00"),
                balance=Decimal("0.00"),
            )
            db_session.add(comprobante)
            db_session.flush()

            # Add multiple debits to same account
            linea1 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="5101",
                descripcion_cuenta="Gasto por Salario",
                centro_costos="CC-01",
                tipo_debito_credito="debito",
                debito=Decimal("15000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("15000.00"),
                concepto="Salario Base",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=1,
            )
            db_session.add(linea1)

            linea2 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne2",
                empleado_id="emp2",
                empleado_codigo="EMP002",
                empleado_nombre="Maria Lopez",
                codigo_cuenta="5101",  # Same account
                descripcion_cuenta="Gasto por Salario",
                centro_costos="CC-01",  # Same cost center
                tipo_debito_credito="debito",
                debito=Decimal("15000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("15000.00"),
                concepto="Salario Base",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=2,
            )
            db_session.add(linea2)

            # Add credit
            linea3 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="2101",
                descripcion_cuenta="Salario por Pagar",
                centro_costos="CC-01",
                tipo_debito_credito="credito",
                debito=Decimal("0.00"),
                credito=Decimal("15000.00"),
                monto_calculado=Decimal("15000.00"),
                concepto="Salario Base",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=3,
            )
            db_session.add(linea3)

            linea4 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne2",
                empleado_id="emp2",
                empleado_codigo="EMP002",
                empleado_nombre="Maria Lopez",
                codigo_cuenta="2101",  # Same account
                descripcion_cuenta="Salario por Pagar",
                centro_costos="CC-01",  # Same cost center
                tipo_debito_credito="credito",
                debito=Decimal("0.00"),
                credito=Decimal("15000.00"),
                monto_calculado=Decimal("15000.00"),
                concepto="Salario Base",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=4,
            )
            db_session.add(linea4)
            db_session.commit()

            # Summarize
            service = AccountingVoucherService(db_session)
            summarized = service.summarize_voucher(comprobante)

            # Should have 2 entries (one debit, one credit)
            assert len(summarized) == 2

            # Check debit summarization
            debit_entry = [e for e in summarized if e["codigo_cuenta"] == "5101"][0]
            assert debit_entry["debito"] == Decimal("30000.00")
            assert debit_entry["credito"] == Decimal("0.00")
            assert debit_entry["centro_costos"] == "CC-01"

            # Check credit summarization
            credit_entry = [e for e in summarized if e["codigo_cuenta"] == "2101"][0]
            assert credit_entry["debito"] == Decimal("0.00")
            assert credit_entry["credito"] == Decimal("30000.00")
            assert credit_entry["centro_costos"] == "CC-01"

    def test_summarize_voucher_nets_debits_and_credits(self, app, db_session):
        """Test summarization nets debits and credits for same account/cost center."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

            comprobante = ComprobanteContable(
                nomina_id="test_nomina_id",
                fecha_calculo=date(2024, 12, 31),
                concepto="Test Voucher",
                moneda_id=moneda.id,
                total_debitos=Decimal("20000.00"),
                total_creditos=Decimal("20000.00"),
                balance=Decimal("0.00"),
            )
            db_session.add(comprobante)
            db_session.flush()

            # Add debit
            linea1 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="2101",  # Same account for both debit and credit
                descripcion_cuenta="Salario por Pagar",
                centro_costos="CC-01",
                tipo_debito_credito="debito",
                debito=Decimal("5000.00"),  # Loan payment debits salary payable
                credito=Decimal("0.00"),
                monto_calculado=Decimal("5000.00"),
                concepto="Préstamo",
                tipo_concepto="prestamo",
                concepto_codigo="PREST",
                orden=1,
            )
            db_session.add(linea1)

            # Add credit to same account
            linea2 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="2101",  # Same account
                descripcion_cuenta="Salario por Pagar",
                centro_costos="CC-01",  # Same cost center
                tipo_debito_credito="credito",
                debito=Decimal("0.00"),
                credito=Decimal("20000.00"),  # Salary credits salary payable
                monto_calculado=Decimal("20000.00"),
                concepto="Salario Base",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=2,
            )
            db_session.add(linea2)
            db_session.commit()

            # Summarize
            service = AccountingVoucherService(db_session)
            summarized = service.summarize_voucher(comprobante)

            # Should have 1 entry with netted amount
            assert len(summarized) == 1

            entry = summarized[0]
            assert entry["codigo_cuenta"] == "2101"
            # Credit (20000) - Debit (5000) = 15000 net credit
            assert entry["debito"] == Decimal("0.00")
            assert entry["credito"] == Decimal("15000.00")


class TestAccountingAuditTrail:
    """Tests for audit trail tracking."""

    def test_audit_trail_on_creation(self, app, db_session):
        """Test audit trail is set correctly on creation."""
        with app.app_context():
            # Setup
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
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

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.APLICADO,  # Applied state
                aplicado_por="admin_user",
                aplicado_en=datetime(2024, 12, 31, 10, 0, 0, tzinfo=timezone.utc),
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # Generate voucher
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla, usuario="test_user")

            # Check audit trail
            assert comprobante.aplicado_por == "admin_user"
            assert comprobante.fecha_aplicacion is not None
            assert comprobante.veces_modificado == 0
            assert comprobante.modificado_por is None

    def test_audit_trail_on_regeneration(self, app, db_session):
        """Test audit trail is updated on regeneration."""
        with app.app_context():
            # Setup with existing comprobante
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
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

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.APLICADO,
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # First generation
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla, usuario="first_user")
            db_session.commit()

            original_aplicado_por = comprobante.aplicado_por
            assert comprobante.veces_modificado == 0

            # Regenerate
            comprobante = service.generate_accounting_voucher(nomina, planilla, usuario="second_user")
            db_session.commit()

            # Check audit trail updated
            assert comprobante.aplicado_por == original_aplicado_por  # Immutable
            assert comprobante.modificado_por == "second_user"
            assert comprobante.fecha_modificacion is not None
            assert comprobante.veces_modificado == 1

            # Regenerate again
            comprobante = service.generate_accounting_voucher(nomina, planilla, usuario="third_user")
            db_session.commit()

            assert comprobante.veces_modificado == 2
            assert comprobante.modificado_por == "third_user"


class TestAccountingBalanceValidation:
    """Tests for balance validation and zero-line exclusion."""

    def test_balance_validation_warns_on_unbalanced_voucher(self, app, db_session):
        """Test that unbalanced vouchers generate warnings."""
        with app.app_context():
            # Setup
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
                codigo_cuenta_debe_salario="5101",
                codigo_cuenta_haber_salario="2101",
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

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.GENERADO,
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # Generate voucher - should be balanced
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla)

            # Verify balanced voucher has no balance warning
            assert comprobante.balance == Decimal("0.00")
            balance_warnings = [w for w in comprobante.advertencias if "no está balanceado" in w]
            assert len(balance_warnings) == 0

            # Now manually create an unbalanced scenario by adding a debit-only line
            db_session.flush()
            orden_max = (
                db_session.query(db.func.max(ComprobanteContableLinea.orden))
                .filter_by(comprobante_id=comprobante.id)
                .scalar()
                or 0
            )

            unbalanced_line = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id=nomina_empleado.id,
                empleado_id=empleado.id,
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="6101",
                descripcion_cuenta="Gasto Extra",
                centro_costos=None,
                tipo_debito_credito="debito",
                debito=Decimal("1000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("1000.00"),
                concepto="Extra",
                tipo_concepto="income",
                concepto_codigo="EXTRA",
                orden=orden_max + 1,
            )
            db_session.add(unbalanced_line)
            db_session.commit()

            # Regenerate to recalculate balance
            comprobante = service.generate_accounting_voucher(nomina, planilla)
            db_session.commit()

            # After regeneration with proper accounting, should still be balanced
            # (because our service creates proper debit/credit pairs)
            assert comprobante.balance == Decimal("0.00")

    def test_summarize_excludes_zero_balance_lines(self, app, db_session):
        """Test that summarization excludes lines where debits equal credits."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

            comprobante = ComprobanteContable(
                nomina_id="test_nomina_id",
                fecha_calculo=date(2024, 12, 31),
                concepto="Test Voucher",
                moneda_id=moneda.id,
                total_debitos=Decimal("10000.00"),
                total_creditos=Decimal("10000.00"),
                balance=Decimal("0.00"),
            )
            db_session.add(comprobante)
            db_session.flush()

            # Add lines that will net to zero for same account
            linea1 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="2101",  # This account will have equal debits and credits
                descripcion_cuenta="Cuenta Test",
                centro_costos="CC-01",
                tipo_debito_credito="debito",
                debito=Decimal("5000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("5000.00"),
                concepto="Test Debit",
                tipo_concepto="deduction",
                concepto_codigo="TEST_D",
                orden=1,
            )
            db_session.add(linea1)

            linea2 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="2101",  # Same account - will net to zero
                descripcion_cuenta="Cuenta Test",
                centro_costos="CC-01",  # Same cost center
                tipo_debito_credito="credito",
                debito=Decimal("0.00"),
                credito=Decimal("5000.00"),
                monto_calculado=Decimal("5000.00"),
                concepto="Test Credit",
                tipo_concepto="income",
                concepto_codigo="TEST_C",
                orden=2,
            )
            db_session.add(linea2)

            # Add another account with non-zero balance
            linea3 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="5101",
                descripcion_cuenta="Gasto por Salario",
                centro_costos="CC-01",
                tipo_debito_credito="debito",
                debito=Decimal("10000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("10000.00"),
                concepto="Salario",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=3,
            )
            db_session.add(linea3)

            linea4 = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta="2102",
                descripcion_cuenta="Salario por Pagar",
                centro_costos="CC-01",
                tipo_debito_credito="credito",
                debito=Decimal("0.00"),
                credito=Decimal("10000.00"),
                monto_calculado=Decimal("10000.00"),
                concepto="Salario",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=4,
            )
            db_session.add(linea4)
            db_session.commit()

            # Summarize
            service = AccountingVoucherService(db_session)
            summarized = service.summarize_voucher(comprobante)

            # Should only have 2 entries (5101 debit and 2102 credit)
            # Account 2101 should be excluded because it nets to zero
            assert len(summarized) == 2

            # Verify account 2101 is not in summary
            account_codes = [entry["codigo_cuenta"] for entry in summarized]
            assert "2101" not in account_codes

            # Verify the other two accounts are present
            assert "5101" in account_codes
            assert "2102" in account_codes

            # Verify amounts
            entry_5101 = [e for e in summarized if e["codigo_cuenta"] == "5101"][0]
            assert entry_5101["debito"] == Decimal("10000.00")
            assert entry_5101["credito"] == Decimal("0.00")

            entry_2102 = [e for e in summarized if e["codigo_cuenta"] == "2102"][0]
            assert entry_2102["debito"] == Decimal("0.00")
            assert entry_2102["credito"] == Decimal("10000.00")


class TestIncompleteAccountingConfiguration:
    """Tests for handling incomplete accounting configuration."""

    def test_generate_voucher_with_missing_accounts(self, app, db_session):
        """Test that voucher generates with NULL accounts when configuration is missing."""
        with app.app_context():
            # Setup without account configuration
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

            # Planilla WITHOUT accounting configuration
            planilla = Planilla(
                nombre="Planilla Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
                # NO codigo_cuenta_debe_salario
                # NO codigo_cuenta_haber_salario
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

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 12, 1),
                periodo_fin=date(2024, 12, 31),
                estado=NominaEstado.GENERADO,
            )
            db_session.add(nomina)
            db_session.flush()

            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # Generate voucher - should work even without accounts
            service = AccountingVoucherService(db_session)
            comprobante = service.generate_accounting_voucher(nomina, planilla)
            db_session.commit()

            # Verify comprobante was created
            assert comprobante is not None
            assert comprobante.advertencias  # Should have warnings about missing config

            # Verify lines were created with NULL accounts
            lineas = (
                db_session.execute(db.select(ComprobanteContableLinea).filter_by(comprobante_id=comprobante.id))
                .scalars()
                .all()
            )

            assert len(lineas) == 2  # Debit and credit for base salary

            # Both lines should have NULL accounts
            for linea in lineas:
                assert linea.codigo_cuenta is None
                assert linea.descripcion_cuenta is None
                assert linea.monto_calculado == Decimal("15000.00")

    def test_summarize_fails_with_null_accounts(self, app, db_session):
        """Test that summarization fails when accounts are NULL."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

            comprobante = ComprobanteContable(
                nomina_id="test_nomina_id",
                fecha_calculo=date(2024, 12, 31),
                concepto="Test Voucher",
                moneda_id=moneda.id,
                total_debitos=Decimal("10000.00"),
                total_creditos=Decimal("10000.00"),
                balance=Decimal("0.00"),
            )
            db_session.add(comprobante)
            db_session.flush()

            # Add line with NULL account
            linea = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta=None,  # NULL account
                descripcion_cuenta=None,
                centro_costos="CC-01",
                tipo_debito_credito="debito",
                debito=Decimal("10000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("10000.00"),
                concepto="Test",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=1,
            )
            db_session.add(linea)
            db_session.commit()

            # Try to summarize - should fail
            service = AccountingVoucherService(db_session)
            with pytest.raises(ValueError, match="No se puede generar comprobante sumarizado"):
                service.summarize_voucher(comprobante)

    def test_detailed_view_works_with_null_accounts(self, app, db_session):
        """Test that detailed audit view works even with NULL accounts."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

            comprobante = ComprobanteContable(
                nomina_id="test_nomina_id",
                fecha_calculo=date(2024, 12, 31),
                concepto="Test Voucher",
                moneda_id=moneda.id,
                total_debitos=Decimal("10000.00"),
                total_creditos=Decimal("10000.00"),
                balance=Decimal("0.00"),
            )
            db_session.add(comprobante)
            db_session.flush()

            # Add line with NULL account
            linea = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id="ne1",
                empleado_id="emp1",
                empleado_codigo="EMP001",
                empleado_nombre="Juan Pérez",
                codigo_cuenta=None,  # NULL account
                descripcion_cuenta=None,
                centro_costos="CC-01",
                tipo_debito_credito="debito",
                debito=Decimal("10000.00"),
                credito=Decimal("0.00"),
                monto_calculado=Decimal("10000.00"),
                concepto="Test",
                tipo_concepto="salario_base",
                concepto_codigo="SALARIO",
                orden=1,
            )
            db_session.add(linea)
            db_session.commit()

            # Get detailed view - should work with NULL accounts
            service = AccountingVoucherService(db_session)
            detailed = service.get_detailed_voucher_by_employee(comprobante)

            # Should have one employee entry
            assert len(detailed) == 1
            assert detailed[0]["empleado_codigo"] == "EMP001"
            assert len(detailed[0]["lineas"]) == 1

            # Line should show NULL account
            linea_detail = detailed[0]["lineas"][0]
            assert linea_detail["codigo_cuenta"] is None
            assert linea_detail["descripcion_cuenta"] is None
            assert linea_detail["debito"] == Decimal("10000.00")
