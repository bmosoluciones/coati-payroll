# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for vacation_service module."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from coati_payroll.enums import (
    AccrualFrequency,
    AccrualMethod,
    VacationLedgerType,
    VacationUnitType,
)
from coati_payroll.model import (
    Empleado,
    Empresa,
    Moneda,
    NominaEmpleado,
    Planilla,
    PlanillaEmpleado,
    TipoPlanilla,
    VacationAccount,
    VacationLedger,
    VacationPolicy,
    Nomina,
)
from coati_payroll.vacation_service import VacationService


@pytest.fixture
def empresa(db_session):
    """Create a test empresa."""
    empresa = Empresa(
        codigo="TEST_VAC",
        razon_social="Test Vacation Company",
        nombre_comercial="Test Vac",
        ruc="J0310000999999",
        activo=True,
    )
    db_session.add(empresa)
    db_session.flush()
    return empresa


@pytest.fixture
def moneda(db_session):
    """Create a test currency."""
    moneda = Moneda(codigo="USD", nombre="Dollar", simbolo="$", activo=True)
    db_session.add(moneda)
    db_session.flush()
    return moneda


@pytest.fixture
def tipo_planilla(db_session):
    """Create a test planilla type."""
    tipo = TipoPlanilla(
        codigo="MONTHLY_VAC",
        descripcion="Monthly payroll for vacation tests",
        dias=30,
        periodicidad="monthly",
        activo=True,
    )
    db_session.add(tipo)
    db_session.flush()
    return tipo


@pytest.fixture
def planilla(db_session, empresa, moneda, tipo_planilla):
    """Create a test planilla."""
    planilla = Planilla(
        empresa_id=empresa.id,
        nombre="Test Planilla Vacation",
        tipo_planilla_id=tipo_planilla.id,
        moneda_id=moneda.id,
        activo=True,
    )
    db_session.add(planilla)
    db_session.flush()
    return planilla


@pytest.fixture
def periodic_policy(db_session, planilla):
    """Create a periodic vacation policy."""
    policy = VacationPolicy(
        planilla_id=planilla.id,
        codigo="PERIODIC-TEST",
        nombre="Periodic Accrual Policy",
        descripcion="Test periodic accrual",
        accrual_method=AccrualMethod.PERIODIC,
        accrual_rate=Decimal("1.25"),
        accrual_frequency=AccrualFrequency.MONTHLY,
        unit_type=VacationUnitType.DAYS,
        min_service_days=0,
        max_balance=Decimal("30.00"),
        allow_negative=False,
        partial_units_allowed=True,  # Allow fractions for testing
        activo=True,
        creado_por="test_system",
    )
    db_session.add(policy)
    db_session.flush()
    return policy


@pytest.fixture
def proportional_policy(db_session, planilla):
    """Create a proportional vacation policy."""
    policy = VacationPolicy(
        planilla_id=planilla.id,
        codigo="PROP-TEST",
        nombre="Proportional Accrual Policy",
        descripcion="Test proportional accrual",
        accrual_method=AccrualMethod.PROPORTIONAL,
        accrual_rate=Decimal("0.05"),  # 5% per day
        accrual_frequency=AccrualFrequency.MONTHLY,
        accrual_basis="days_worked",
        unit_type=VacationUnitType.DAYS,
        min_service_days=0,
        allow_negative=False,
        partial_units_allowed=True,  # Allow fractions for testing
        activo=True,
        creado_por="test_system",
    )
    db_session.add(policy)
    db_session.flush()
    return policy


@pytest.fixture
def seniority_policy(db_session, planilla):
    """Create a seniority-based vacation policy."""
    policy = VacationPolicy(
        planilla_id=planilla.id,
        codigo="SENIOR-TEST",
        nombre="Seniority Accrual Policy",
        descripcion="Test seniority-based accrual",
        accrual_method=AccrualMethod.SENIORITY,
        accrual_rate=Decimal("15.00"),  # Base rate
        accrual_frequency=AccrualFrequency.ANNUAL,
        unit_type=VacationUnitType.DAYS,
        min_service_days=0,
        partial_units_allowed=True,  # Allow fractions for testing
        seniority_tiers=[
            {"years": 0, "rate": 15.0},
            {"years": 5, "rate": 20.0},
            {"years": 10, "rate": 25.0},
        ],
        allow_negative=False,
        activo=True,
        creado_por="test_system",
    )
    db_session.add(policy)
    db_session.flush()
    return policy


@pytest.fixture
def empleado(db_session, empresa, moneda):
    """Create a test employee."""
    emp = Empleado(
        empresa_id=empresa.id,
        codigo_empleado="VAC-001",
        primer_nombre="John",
        primer_apellido="Doe",
        identificacion_personal="VAC-111111-1111A",
        fecha_alta=date.today() - timedelta(days=365),
        salario_base=Decimal("1000.00"),
        moneda_id=moneda.id,
        activo=True,
    )
    db_session.add(emp)
    db_session.flush()
    return emp


def test_vacation_service_initialization(app, db_session, planilla):
    """Test VacationService initialization."""
    with app.app_context():
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        assert service.planilla == planilla
        assert service.periodo_inicio == periodo_inicio
        assert service.periodo_fin == periodo_fin


def test_acumular_vacaciones_no_account(app, db_session, planilla, empleado, moneda):
    """Test vacation accrual when employee has no vacation account."""
    with app.app_context():
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        # Assign employee to payroll
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=periodo_inicio,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create nomina and nomina_empleado
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Should return 0 when no account exists
        accrued = service.acumular_vacaciones_empleado(empleado, nomina_empleado, "test_user")

        assert accrued == Decimal("0.00")


def test_acumular_vacaciones_autocreate_account_for_bound_policy(
    app, db_session, planilla, empleado, moneda, periodic_policy
):
    """Auto-create vacation account when payroll has an explicit bound vacation policy."""
    with app.app_context():
        from sqlalchemy import select

        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        planilla.vacation_policy_id = periodic_policy.id
        db_session.flush()

        # Assign employee to payroll
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=periodo_inicio,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create nomina and nomina_empleado
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrued = service.acumular_vacaciones_empleado(empleado, nomina_empleado, "test_user")

        assert accrued > Decimal("0.00")

        account = db_session.execute(
            select(VacationAccount).filter(
                VacationAccount.empleado_id == empleado.id,
                VacationAccount.policy_id == periodic_policy.id,
            )
        ).scalar_one_or_none()
        assert account is not None
        assert account.activo is True

        ledger_entry = db_session.execute(
            select(VacationLedger).filter(
                VacationLedger.account_id == account.id,
                VacationLedger.entry_type == VacationLedgerType.ACCRUAL,
                VacationLedger.reference_type == "nomina_empleado",
                VacationLedger.reference_id == nomina_empleado.id,
            )
        ).scalar_one_or_none()
        assert ledger_entry is not None


def test_acumular_vacaciones_periodic_prorated_for_partial_period(
    app, db_session, planilla, moneda, periodic_policy, empresa
):
    """Periodic accrual must prorate when employee joins mid-period."""
    with app.app_context():
        periodo_inicio = date(2026, 1, 1)
        periodo_fin = date(2026, 1, 30)  # 30-day commercial month reference

        empleado_parcial = Empleado(
            empresa_id=empresa.id,
            codigo_empleado="VAC-PARTIAL-001",
            primer_nombre="Partial",
            primer_apellido="Worker",
            identificacion_personal="VAC-333333-3333C",
            fecha_alta=date(2026, 1, 15),  # 16 worked days in period
            salario_base=Decimal("1000.00"),
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(empleado_parcial)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado_parcial.id,
            policy_id=periodic_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado_parcial.id,
            fecha_inicio=periodo_inicio,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado_parcial.id,
            sueldo_base_historico=Decimal("533.33"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrued = service.acumular_vacaciones_empleado(empleado_parcial, nomina_empleado, "test_user")

        # 1.25 * (16/30) = 0.6667, rounded to 2 decimals = 0.67
        assert accrued == Decimal("0.67")


def test_acumular_vacaciones_periodic_method(app, db_session, planilla, empleado, periodic_policy, moneda):
    """Test periodic vacation accrual calculation."""
    with app.app_context():
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        # Create vacation account
        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=periodic_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        # Link employee to planilla
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=empleado.fecha_alta,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create nomina and nomina_empleado
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Accrue vacation
        accrued = service.acumular_vacaciones_empleado(empleado, nomina_empleado, "test_user")

        # Should accrue based on period (31 days ≈ 1 month, so close to 1.25)
        assert accrued > Decimal("0.00")
        assert accrued <= Decimal("1.30")  # Prorated for 31 days

        from sqlalchemy import select

        # Verify ledger entry created
        ledger_entries = (
            db_session.execute(
                select(VacationLedger).filter(
                    VacationLedger.account_id == account.id,
                    VacationLedger.entry_type == VacationLedgerType.ACCRUAL,
                )
            )
            .scalars()
            .all()
        )
        assert len(ledger_entries) == 1
        assert ledger_entries[0].quantity == accrued


def test_acumular_vacaciones_min_service_days(app, db_session, planilla, moneda, periodic_policy):
    """Test vacation accrual respects minimum service days requirement."""
    with app.app_context():
        # Update policy to require 90 days minimum service
        periodic_policy.min_service_days = 90
        db_session.flush()

        # Create employee hired only 30 days ago
        recent_employee = Empleado(
            empresa_id=planilla.empresa_id,
            codigo_empleado="VAC-002",
            primer_nombre="Jane",
            primer_apellido="Smith",
            identificacion_personal="VAC-222222-2222B",
            fecha_alta=date.today() - timedelta(days=30),
            salario_base=Decimal("1000.00"),
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(recent_employee)
        db_session.flush()

        # Assign employee to payroll
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=recent_employee.id,
            fecha_inicio=date.today() - timedelta(days=30),
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create vacation account
        account = VacationAccount(
            empleado_id=recent_employee.id,
            policy_id=periodic_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        # Create nomina and nomina_empleado
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=recent_employee.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Should not accrue because employee hasn't met minimum service days
        accrued = service.acumular_vacaciones_empleado(recent_employee, nomina_empleado, "test_user")

        assert accrued == Decimal("0.00")


def test_acumular_vacaciones_max_balance_limit(app, db_session, planilla, empleado, periodic_policy, moneda):
    """Test vacation accrual respects maximum balance limit."""
    with app.app_context():
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        # Create vacation account with balance near max (30.00)
        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=periodic_policy.id,
            current_balance=Decimal("29.50"),  # Very close to max of 30.00
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        # Create ledger entry to establish balance
        from coati_payroll.model import VacationLedger

        ledger = VacationLedger(
            account_id=account.id,
            empleado_id=empleado.id,
            fecha=date.today() - timedelta(days=60),
            entry_type=VacationLedgerType.ACCRUAL,
            quantity=Decimal("29.50"),
            source="initial",
            reference_id="initial-balance",
            reference_type="initial",
            creado_por="test_system",
        )
        db_session.add(ledger)
        db_session.flush()

        # Link employee to planilla
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=empleado.fecha_alta,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create nomina and nomina_empleado
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Accrue vacation
        accrued = service.acumular_vacaciones_empleado(empleado, nomina_empleado, "test_user")

        # Should be capped to not exceed max balance
        db_session.refresh(account)
        assert account.current_balance <= periodic_policy.max_balance
        assert accrued == Decimal("0.50")  # Capped to reach 30.00


def test_acumular_vacaciones_proportional_method(app, db_session, planilla, empleado, proportional_policy, moneda):
    """Test proportional vacation accrual based on days worked."""
    with app.app_context():
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        # Create vacation account
        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=proportional_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        # Link employee to planilla
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=empleado.fecha_alta,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create nomina and nomina_empleado
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Accrue vacation
        accrued = service.acumular_vacaciones_empleado(empleado, nomina_empleado, "test_user")

        # Should calculate based on days worked (31 days * 0.05 = 1.55)
        assert accrued > Decimal("0.00")
        expected = Decimal("31") * proportional_policy.accrual_rate
        assert accrued == expected.quantize(Decimal("0.0001"))


def test_acumular_vacaciones_seniority_method(app, db_session, planilla, moneda, seniority_policy):
    """Test seniority-based vacation accrual with tiered rates."""
    with app.app_context():
        # Create employee with 6 years of service (should get tier 2: 20 days)
        employee_6yrs = Empleado(
            empresa_id=planilla.empresa_id,
            codigo_empleado="VAC-003",
            primer_nombre="Senior",
            primer_apellido="Employee",
            identificacion_personal="VAC-333333-3333C",
            fecha_alta=date.today() - timedelta(days=365 * 6),
            salario_base=Decimal("1000.00"),
            moneda_id=moneda.id,
            activo=True,
        )
        db_session.add(employee_6yrs)
        db_session.flush()

        # Create vacation account
        account = VacationAccount(
            empleado_id=employee_6yrs.id,
            policy_id=seniority_policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        # Link employee to planilla
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=employee_6yrs.id,
            fecha_inicio=employee_6yrs.fecha_alta,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        # Create nomina and nomina_empleado
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=employee_6yrs.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Accrue vacation
        accrued = service.acumular_vacaciones_empleado(employee_6yrs, nomina_empleado, "test_user")

        # Should accrue based on 20 days/year (tier 2) prorated for the period
        assert accrued > Decimal("0.00")
        # Annual rate is 20, prorated for 31 days
        expected_monthly = Decimal("20.00") * Decimal("31") / Decimal("365")
        assert abs(accrued - expected_monthly) < Decimal("0.01")


def test_procesar_novedades_vacaciones_no_novelties(app, db_session, planilla, empleado):
    """Test vacation novelty processing when there are no novelties."""
    with app.app_context():
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        # Link employee to planilla
        planilla_empleado = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            fecha_inicio=empleado.fecha_alta,
            activo=True,
        )
        db_session.add(planilla_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)

        # Process with no novelties
        total_usado = service.procesar_novedades_vacaciones(empleado, "test_user")

        assert total_usado == Decimal("0.00")


def test_calcular_acumulacion_periodic_biweekly(app, db_session, planilla):
    """Test periodic accrual calculation for biweekly frequency."""
    with app.app_context():
        # Create biweekly policy
        policy = VacationPolicy(
            planilla_id=planilla.id,
            codigo="BIWEEKLY",
            nombre="Biweekly Policy",
            descripcion="Test biweekly",
            accrual_method=AccrualMethod.PERIODIC,
            accrual_rate=Decimal("0.625"),  # Half of monthly
            accrual_frequency=AccrualFrequency.BIWEEKLY,
            unit_type=VacationUnitType.DAYS,
            activo=True,
            creado_por="test_system",
        )
        db_session.add(policy)
        db_session.flush()

        # Test with 15-day period (should match biweekly frequency exactly)
        periodo_inicio = date.today() - timedelta(days=14)
        periodo_fin = date.today()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrual = service._calcular_acumulacion_periodica(policy)

        # Should return the rate directly for matching period, rounded to 2 decimals = 0.63
        assert accrual == Decimal("0.63")


def test_calcular_acumulacion_proportional_hours(app, db_session, planilla, empleado, moneda):
    """Test proportional accrual based on hours worked."""
    with app.app_context():
        # Create hours-based policy
        policy = VacationPolicy(
            planilla_id=planilla.id,
            codigo="HOURLY",
            nombre="Hourly Policy",
            descripcion="Test hours",
            accrual_method=AccrualMethod.PROPORTIONAL,
            accrual_rate=Decimal("0.01"),  # 1% per hour
            accrual_frequency=AccrualFrequency.MONTHLY,
            accrual_basis="hours_worked",
            unit_type=VacationUnitType.HOURS,
            activo=True,
            creado_por="test_system",
        )
        db_session.add(policy)
        db_session.flush()

        # Create nomina_empleado
        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrual = service._calcular_acumulacion_proporcional(empleado, policy, nomina_empleado)

        # Should calculate based on standard hours (8 * 31 days = 248 hours)
        expected = Decimal("8.0") * Decimal("31") * policy.accrual_rate
        assert accrual == expected.quantize(Decimal("0.0001"))


def test_calcular_acumulacion_seniority_no_tiers(app, db_session, planilla, empleado):
    """Test seniority accrual when no tiers are defined."""
    with app.app_context():
        # Create policy without seniority tiers
        policy = VacationPolicy(
            planilla_id=planilla.id,
            codigo="NO-TIERS",
            nombre="No Tiers Policy",
            descripcion="Test no tiers",
            accrual_method=AccrualMethod.SENIORITY,
            accrual_rate=Decimal("15.00"),
            accrual_frequency=AccrualFrequency.ANNUAL,
            unit_type=VacationUnitType.DAYS,
            seniority_tiers=None,  # No tiers
            activo=True,
            creado_por="test_system",
        )
        db_session.add(policy)
        db_session.flush()

        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrual = service._calcular_acumulacion_antiguedad(empleado, policy)

        # Should return 0 when no tiers defined
        assert accrual == Decimal("0.00")


def test_calcular_acumulacion_seniority_proratado_por_frecuencia(app, db_session, planilla, empleado):
    """Seniority rate is annual: prorate it by the actual period length regardless
    of frequency. A biweekly policy must not divide by a fixed 12 months, which
    would accumulate twice the annual rate over 24 biweekly periods a year."""
    with app.app_context():
        policy = VacationPolicy(
            planilla_id=planilla.id,
            codigo="SENIOR-BIWEEKLY",
            nombre="Seniority Biweekly Policy",
            descripcion="Test seniority proration",
            accrual_method=AccrualMethod.SENIORITY,
            accrual_rate=Decimal("15.00"),
            accrual_frequency=AccrualFrequency.BIWEEKLY,
            unit_type=VacationUnitType.DAYS,
            min_service_days=0,
            partial_units_allowed=True,
            seniority_tiers=[{"years": 0, "rate": 15.0}],
            activo=True,
            creado_por="test_system",
        )
        db_session.add(policy)
        db_session.flush()

        periodo_inicio = date.today() - timedelta(days=14)
        periodo_fin = date.today()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrual = service._calcular_acumulacion_antiguedad(empleado, policy)

        dias_periodo = (periodo_fin - periodo_inicio).days + 1
        expected = (Decimal("15.00") * Decimal(dias_periodo) / Decimal("365")).quantize(Decimal("0.01"))
        assert accrual == expected
        # The old behavior (rate / 12 = 1.25 per period) would exceed one unit.
        assert accrual < Decimal("1.00")


def test_calcular_acumulacion_unknown_method(app, db_session, planilla, empleado, moneda):
    """Test vacation accrual with unknown method returns zero."""
    with app.app_context():
        # Create policy with invalid method (simulated)
        policy = VacationPolicy(
            planilla_id=planilla.id,
            codigo="INVALID",
            nombre="Invalid Method",
            descripcion="Test invalid",
            accrual_method="INVALID_METHOD",  # Invalid
            accrual_rate=Decimal("1.00"),
            accrual_frequency=AccrualFrequency.MONTHLY,
            unit_type=VacationUnitType.DAYS,
            activo=True,
            creado_por="test_system",
        )
        db_session.add(policy)
        db_session.flush()

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=policy.id,
            current_balance=Decimal("0.00"),
            activo=True,
            creado_por="test_system",
        )
        db_session.add(account)
        db_session.flush()

        periodo_inicio = date.today() - timedelta(days=30)
        periodo_fin = date.today()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
        )
        db_session.add(nomina)
        db_session.flush()

        nomina_empleado = NominaEmpleado(
            nomina_id=nomina.id,
            empleado_id=empleado.id,
            sueldo_base_historico=Decimal("1000.00"),
            moneda_origen_id=moneda.id,
        )
        db_session.add(nomina_empleado)
        db_session.flush()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrual = service._calcular_acumulacion(empleado, account, nomina_empleado)

        # Should return 0 for unknown method
        assert accrual == Decimal("0.00")


def test_calcular_acumulacion_annual_frequency(app, db_session, planilla):
    """Test periodic accrual with annual frequency."""
    with app.app_context():
        policy = VacationPolicy(
            planilla_id=planilla.id,
            codigo="ANNUAL",
            nombre="Annual Policy",
            descripcion="Test annual",
            accrual_method=AccrualMethod.PERIODIC,
            accrual_rate=Decimal("15.00"),
            accrual_frequency=AccrualFrequency.ANNUAL,
            unit_type=VacationUnitType.DAYS,
            activo=True,
            creado_por="test_system",
        )
        db_session.add(policy)
        db_session.flush()

        # Test with 365-day period
        periodo_inicio = date.today() - timedelta(days=364)
        periodo_fin = date.today()

        service = VacationService(planilla, periodo_inicio, periodo_fin)
        accrual = service._calcular_acumulacion_periodica(policy)

        # Should return full annual rate
        assert accrual == Decimal("15.00")


def test_consecutive_payroll_vacation_novelty_no_cross_processing(app, db_session, planilla, empleado):
    """Verify that a vacation novelty bound to one payroll is not cross-processed or loaded by a consecutive run."""
    with app.app_context():
        from coati_payroll.model import NominaNovedad, PlanillaEmpleado
        from coati_payroll.enums import NovedadEstado

        periodo_inicio = date(2025, 1, 1)
        periodo_fin = date(2025, 1, 15)

        # Make sure employee is active in the planilla
        from coati_payroll.model import db
        pe = db_session.execute(
            db.select(PlanillaEmpleado).filter_by(planilla_id=planilla.id, empleado_id=empleado.id)
        ).scalars().first()
        if not pe:
            pe = PlanillaEmpleado(
                planilla_id=planilla.id,
                empleado_id=empleado.id,
                activo=True,
                creado_por="test",
            )
            db_session.add(pe)
        else:
            pe.activo = True
        db_session.commit()

        # Create two consecutive/overlapping Nominas
        nomina_a = Nomina(
            id="NOMINA_A_001",
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
            estado="draft",
        )
        nomina_b = Nomina(
            id="NOMINA_B_002",
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
            estado="draft",
        )
        db_session.add_all([nomina_a, nomina_b])
        db_session.commit()

        # Create a vacation novelty bound explicitly to Nomina A
        novedad_a = NominaNovedad(
            nomina_id=nomina_a.id,
            empleado_id=empleado.id,
            codigo_concepto="VAC",
            tipo_valor="dias",
            valor_cantidad=Decimal("5.00"),
            fecha_novedad=date(2025, 1, 5),
            es_descanso_vacaciones=True,
            estado=NovedadEstado.PENDIENTE,
            creado_por="test_user",
        )
        # Create a floating vacation novelty (not bound to any nomina_id)
        novedad_floating = NominaNovedad(
            nomina_id=None,
            empleado_id=empleado.id,
            codigo_concepto="VAC",
            tipo_valor="dias",
            valor_cantidad=Decimal("3.00"),
            fecha_novedad=date(2025, 1, 10),
            es_descanso_vacaciones=True,
            estado=NovedadEstado.PENDIENTE,
            creado_por="test_user",
        )
        db_session.add_all([novedad_a, novedad_floating])
        db_session.commit()

        # Instantiate VacationService for Nomina B - it should NOT load novedad_a, but should load novedad_floating
        service_b = VacationService(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            nomina_id=nomina_b.id,
            apply_side_effects=False,
        )

        usage_b = service_b._build_vacation_usage_query(empleado)
        assert len(usage_b) == 1
        assert usage_b[0].id == novedad_floating.id

        # Instantiate VacationService for Nomina A - it should load BOTH novelty_a and novelty_floating
        service_a = VacationService(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            nomina_id=nomina_a.id,
            apply_side_effects=False,
        )

        usage_a = service_a._build_vacation_usage_query(empleado)
        assert len(usage_a) == 2
        usage_ids = {u.id for u in usage_a}
        assert novedad_a.id in usage_ids
        assert novedad_floating.id in usage_ids

        # Test _empleado_tiene_vacaciones_en_periodo
        assert service_b._empleado_tiene_vacaciones_en_periodo(empleado) is True
        assert service_a._empleado_tiene_vacaciones_en_periodo(empleado) is True

        # Test with a third service having NO matching novelties (different period)
        service_c = VacationService(
            planilla=planilla,
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 15),
            nomina_id="NOMINA_C_003",
            apply_side_effects=False,
        )
        assert service_c._empleado_tiene_vacaciones_en_periodo(empleado) is False
        assert len(service_c._build_vacation_usage_query(empleado)) == 0

        # Test with no nomina_id (e.g. general service) - should only match floating
        service_none = VacationService(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            nomina_id=None,
            apply_side_effects=False,
        )
        assert service_none._empleado_tiene_vacaciones_en_periodo(empleado) is True
        assert len(service_none._build_vacation_usage_query(empleado)) == 1
        assert service_none._build_vacation_usage_query(empleado)[0].id == novedad_floating.id


def test_recalculation_context_keeps_source_bound_vacation_novelties(
    app, db_session, planilla, empleado
):
    """A recalculation must read source-bound novelties before relinking them."""
    with app.app_context():
        from coati_payroll.model import NominaNovedad, PlanillaEmpleado
        from coati_payroll.enums import NovedadEstado

        periodo_inicio = date(2025, 3, 1)
        periodo_fin = date(2025, 3, 31)
        db_session.add(
            PlanillaEmpleado(
                planilla_id=planilla.id,
                empleado_id=empleado.id,
                activo=True,
                creado_por="test",
            )
        )
        source = Nomina(
            id="NOMINA_SOURCE_01",
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por="test_user",
            estado="draft",
        )
        db_session.add(source)
        db_session.flush()
        novelty = NominaNovedad(
            nomina_id=source.id,
            empleado_id=empleado.id,
            codigo_concepto="VAC",
            tipo_valor="dias",
            valor_cantidad=Decimal("2.00"),
            fecha_novedad=date(2025, 3, 10),
            es_descanso_vacaciones=True,
            estado=NovedadEstado.PENDIENTE,
            creado_por="test_user",
        )
        db_session.add(novelty)
        db_session.commit()

        # The execution context must remain the source ID until relinking.
        service = VacationService(
            planilla=planilla,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            nomina_id=source.id,
            apply_side_effects=False,
        )
        usage = service._build_vacation_usage_query(empleado)

        assert [item.id for item in usage] == [novelty.id]
