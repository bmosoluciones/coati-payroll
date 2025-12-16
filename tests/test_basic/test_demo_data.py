# Copyright 2025 BMO Soluciones, S.A.
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
"""Tests for demo data loading functionality."""

from datetime import date, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from coati_payroll.model import (
    db,
    Empresa,
    Empleado,
    Moneda,
    TipoPlanilla,
    Planilla,
    PlanillaEmpleado,
    PlanillaIngreso,
    PlanillaDeduccion,
    PlanillaPrestacion,
    Percepcion,
    Deduccion,
    Prestacion,
    Nomina,
    NominaNovedad,
)
from coati_payroll.demo_data import (
    load_demo_companies,
    load_demo_employees,
    load_demo_payrolls,
    create_demo_nomina,
    create_demo_novelties,
    load_demo_data,
)


def test_load_demo_companies(app, db_session):
    """
    Test that demo companies are created successfully.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_demo_companies()

    Verification:
        - Two companies are returned
        - Companies have correct codes and names
        - Companies are active
        - Companies exist in database
    """
    with app.app_context():
        empresa1, empresa2 = load_demo_companies()

        # Verify both companies are returned
        assert empresa1 is not None
        assert empresa2 is not None

        # Verify company 1 attributes
        assert empresa1.codigo == "DEMO001"
        assert empresa1.razon_social == "Tecnología y Soluciones S.A."
        assert empresa1.nombre_comercial == "TechSol"
        assert empresa1.ruc == "J0310000123456"
        assert empresa1.activo is True

        # Verify company 2 attributes
        assert empresa2.codigo == "DEMO002"
        assert empresa2.razon_social == "Servicios Profesionales BMO Ltda."
        assert empresa2.nombre_comercial == "BMO Services"
        assert empresa2.ruc == "J0310000654321"
        assert empresa2.activo is True

        # Verify companies exist in database
        found1 = db_session.execute(
            db.select(Empresa).filter_by(codigo="DEMO001")
        ).scalar_one_or_none()
        assert found1 is not None
        assert found1.id == empresa1.id

        found2 = db_session.execute(
            db.select(Empresa).filter_by(codigo="DEMO002")
        ).scalar_one_or_none()
        assert found2 is not None
        assert found2.id == empresa2.id


def test_load_demo_companies_idempotent(app, db_session):
    """
    Test that load_demo_companies is idempotent (can be called multiple times).

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_demo_companies() twice

    Verification:
        - Same companies are returned
        - No duplicate companies created
    """
    with app.app_context():
        # First call
        empresa1_first, empresa2_first = load_demo_companies()

        # Second call
        empresa1_second, empresa2_second = load_demo_companies()

        # Should return the same instances
        assert empresa1_first.id == empresa1_second.id
        assert empresa2_first.id == empresa2_second.id

        # Verify only 2 companies exist
        count = db_session.execute(
            db.select(db.func.count()).select_from(Empresa)
        ).scalar()
        assert count == 2


def test_load_demo_employees(app, db_session):
    """
    Test that demo employees are created successfully.

    Setup:
        - Use app and db_session fixtures
        - Create demo companies
        - Create required currency

    Action:
        - Call load_demo_employees()

    Verification:
        - 15 employees are created
        - Employees have correct attributes
        - Employees are assigned to correct companies
        - Employees exist in database
    """
    with app.app_context():
        # Create required data
        empresa1, empresa2 = load_demo_companies()

        # Create currency
        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        # Load employees
        empleados = load_demo_employees(empresa1, empresa2)

        # Verify 15 employees created
        assert len(empleados) == 15

        # Verify first employee attributes
        emp1 = empleados[0]
        assert emp1.codigo_empleado == "DEMO-EMP001"
        assert emp1.primer_nombre == "Juan"
        assert emp1.primer_apellido == "Pérez"
        assert emp1.cargo == "Gerente de Tecnología"
        assert emp1.salario_base == Decimal("35000.00")
        assert emp1.activo is True
        assert emp1.empresa_id == empresa1.id

        # Verify employees are distributed between companies
        emp1_count = sum(1 for e in empleados if e.empresa_id == empresa1.id)
        emp2_count = sum(1 for e in empleados if e.empresa_id == empresa2.id)
        assert emp1_count == 8  # First 8 employees for company 1
        assert emp2_count == 7  # Last 7 employees for company 2

        # Verify employees exist in database
        db_count = db_session.execute(
            db.select(db.func.count()).select_from(Empleado)
        ).scalar()
        assert db_count == 15


def test_load_demo_employees_no_currency(app, db_session):
    """
    Test that load_demo_employees handles missing currency gracefully.

    Setup:
        - Use app and db_session fixtures
        - Create demo companies
        - Do NOT create currency

    Action:
        - Call load_demo_employees()

    Verification:
        - Empty list is returned
        - No employees are created
    """
    with app.app_context():
        empresa1, empresa2 = load_demo_companies()

        # Load employees without currency
        empleados = load_demo_employees(empresa1, empresa2)

        # Should return empty list
        assert len(empleados) == 0

        # Verify no employees in database
        db_count = db_session.execute(
            db.select(db.func.count()).select_from(Empleado)
        ).scalar()
        assert db_count == 0


def test_load_demo_employees_idempotent(app, db_session):
    """
    Test that load_demo_employees is idempotent.

    Setup:
        - Use app and db_session fixtures
        - Create demo companies and currency

    Action:
        - Call load_demo_employees() twice

    Verification:
        - Same employees are returned
        - No duplicate employees created
    """
    with app.app_context():
        empresa1, empresa2 = load_demo_companies()

        # Create currency
        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        # First call
        empleados_first = load_demo_employees(empresa1, empresa2)

        # Second call
        empleados_second = load_demo_employees(empresa1, empresa2)

        # Should return same count
        assert len(empleados_first) == len(empleados_second) == 15

        # Verify only 15 employees exist
        db_count = db_session.execute(
            db.select(db.func.count()).select_from(Empleado)
        ).scalar()
        assert db_count == 15


def test_load_demo_payrolls(app, db_session):
    """
    Test that demo payrolls are created successfully.

    Setup:
        - Use app and db_session fixtures
        - Create companies, currency, employees, and payroll type

    Action:
        - Call load_demo_payrolls()

    Verification:
        - Two payrolls are created
        - Payrolls have correct attributes
        - Employees are assigned to payrolls
        - Concepts are assigned to payrolls
    """
    with app.app_context():
        # Create required data
        empresa1, empresa2 = load_demo_companies()

        # Create currency
        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        # Create payroll type
        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = "MONTHLY"
        tipo_planilla.nombre = "Mensual"
        tipo_planilla.descripcion = "Planilla mensual"
        db_session.add(tipo_planilla)
        db_session.commit()

        # Load employees
        empleados = load_demo_employees(empresa1, empresa2)

        # Load payrolls
        planilla1, planilla2 = load_demo_payrolls(empresa1, empresa2, empleados)

        # Verify both payrolls created
        assert planilla1 is not None
        assert planilla2 is not None

        # Verify planilla1 attributes
        assert planilla1.nombre == "Planilla Demo - TechSol"
        assert planilla1.empresa_id == empresa1.id
        assert planilla1.activo is True

        # Verify planilla2 attributes
        assert planilla2.nombre == "Planilla Demo - BMO Services"
        assert planilla2.empresa_id == empresa2.id
        assert planilla2.activo is True

        # Verify employees are assigned
        asignaciones1 = db_session.execute(
            db.select(PlanillaEmpleado).filter_by(planilla_id=planilla1.id)
        ).scalars().all()
        assert len(asignaciones1) == 8  # Company 1 has 8 employees

        asignaciones2 = db_session.execute(
            db.select(PlanillaEmpleado).filter_by(planilla_id=planilla2.id)
        ).scalars().all()
        assert len(asignaciones2) == 7  # Company 2 has 7 employees


def test_load_demo_payrolls_missing_data(app, db_session):
    """
    Test that load_demo_payrolls handles missing required data gracefully.

    Setup:
        - Use app and db_session fixtures
        - Create companies and employees but NOT currency or payroll type

    Action:
        - Call load_demo_payrolls()

    Verification:
        - Returns (None, None)
        - No payrolls created
    """
    with app.app_context():
        empresa1, empresa2 = load_demo_companies()

        # Create currency but not payroll type
        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        empleados = load_demo_employees(empresa1, empresa2)

        # Load payrolls without payroll type
        planilla1, planilla2 = load_demo_payrolls(empresa1, empresa2, empleados)

        # Should return None
        assert planilla1 is None
        assert planilla2 is None


def test_create_demo_nomina(app, db_session):
    """
    Test that demo nomina is created successfully.

    Setup:
        - Use app and db_session fixtures
        - Create complete setup including payroll

    Action:
        - Call create_demo_nomina()

    Verification:
        - Nomina is created
        - Nomina has correct dates (next month)
        - Nomina has correct initial state
    """
    with app.app_context():
        # Create complete setup
        empresa1, empresa2 = load_demo_companies()

        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = "MONTHLY"
        tipo_planilla.nombre = "Mensual"
        tipo_planilla.descripcion = "Planilla mensual"
        db_session.add(tipo_planilla)
        db_session.commit()

        empleados = load_demo_employees(empresa1, empresa2)
        planilla1, planilla2 = load_demo_payrolls(empresa1, empresa2, empleados)

        # Create demo nomina
        nomina = create_demo_nomina(planilla1)

        # Verify nomina created
        assert nomina is not None
        assert nomina.planilla_id == planilla1.id
        assert nomina.estado == "generado"
        assert nomina.total_bruto == Decimal("0.00")
        assert nomina.total_deducciones == Decimal("0.00")
        assert nomina.total_neto == Decimal("0.00")

        # Verify dates are for next month
        today = date.today()
        next_month_start = today.replace(day=1) + relativedelta(months=1)
        next_month_end = (next_month_start + relativedelta(months=1)) - timedelta(days=1)

        assert nomina.periodo_inicio == next_month_start
        assert nomina.periodo_fin == next_month_end

        # Verify nomina exists in database
        found = db_session.execute(
            db.select(Nomina).filter_by(id=nomina.id)
        ).scalar_one_or_none()
        assert found is not None


def test_create_demo_nomina_idempotent(app, db_session):
    """
    Test that create_demo_nomina is idempotent.

    Setup:
        - Use app and db_session fixtures
        - Create complete setup

    Action:
        - Call create_demo_nomina() twice

    Verification:
        - Same nomina is returned
        - No duplicate nominas created
    """
    with app.app_context():
        # Create complete setup
        empresa1, empresa2 = load_demo_companies()

        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = "MONTHLY"
        tipo_planilla.nombre = "Mensual"
        tipo_planilla.descripcion = "Planilla mensual"
        db_session.add(tipo_planilla)
        db_session.commit()

        empleados = load_demo_employees(empresa1, empresa2)
        planilla1, planilla2 = load_demo_payrolls(empresa1, empresa2, empleados)

        # First call
        nomina1 = create_demo_nomina(planilla1)

        # Second call
        nomina2 = create_demo_nomina(planilla1)

        # Should return same nomina
        assert nomina1.id == nomina2.id

        # Verify only one nomina exists for this period
        today = date.today()
        next_month_start = today.replace(day=1) + relativedelta(months=1)
        next_month_end = (next_month_start + relativedelta(months=1)) - timedelta(days=1)

        count = db_session.execute(
            db.select(db.func.count()).select_from(Nomina).filter_by(
                planilla_id=planilla1.id,
                periodo_inicio=next_month_start,
                periodo_fin=next_month_end
            )
        ).scalar()
        assert count == 1


def test_create_demo_novelties(app, db_session):
    """
    Test that demo novelties are created successfully.

    Setup:
        - Use app and db_session fixtures
        - Create complete setup including nomina and concepts

    Action:
        - Call create_demo_novelties()

    Verification:
        - Novelties are created
        - Overtime novelties created for specific employees
        - Absence novelties created for specific employees
    """
    with app.app_context():
        # Create complete setup
        empresa1, empresa2 = load_demo_companies()

        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = "MONTHLY"
        tipo_planilla.nombre = "Mensual"
        tipo_planilla.descripcion = "Planilla mensual"
        db_session.add(tipo_planilla)
        db_session.commit()

        # Create perception for overtime
        overtime = Percepcion()
        overtime.codigo = "OVERTIME"
        overtime.nombre = "Horas Extra"
        overtime.descripcion = "Pago por horas extra"
        db_session.add(overtime)

        # Create deduction for absences
        absence = Deduccion()
        absence.codigo = "UNPAID_ABSENCES"
        absence.nombre = "Ausencias sin justificar"
        absence.descripcion = "Descuento por ausencias"
        db_session.add(absence)
        db_session.commit()

        empleados = load_demo_employees(empresa1, empresa2)
        planilla1, planilla2 = load_demo_payrolls(empresa1, empresa2, empleados)
        nomina = create_demo_nomina(planilla1)

        # Create novelties
        create_demo_novelties(empleados)

        # Verify overtime novelties created
        overtime_novelties = db_session.execute(
            db.select(NominaNovedad).filter_by(
                nomina_id=nomina.id,
                codigo_concepto="OVERTIME"
            )
        ).scalars().all()
        # Should create overtime for employees at indices 0, 1, 4
        assert len(overtime_novelties) == 3

        # Verify absence novelties created
        absence_novelties = db_session.execute(
            db.select(NominaNovedad).filter_by(
                nomina_id=nomina.id,
                codigo_concepto="UNPAID_ABSENCES"
            )
        ).scalars().all()
        # Should create absences for employees at indices 2, 3
        assert len(absence_novelties) == 2


def test_create_demo_novelties_insufficient_employees(app, db_session):
    """
    Test that create_demo_novelties handles insufficient employees gracefully.

    Setup:
        - Use app and db_session fixtures
        - Provide fewer than 5 employees

    Action:
        - Call create_demo_novelties()

    Verification:
        - Function returns without error
        - No novelties created
    """
    with app.app_context():
        # Create minimal setup with only 2 employees
        empresa1, empresa2 = load_demo_companies()

        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)
        db_session.commit()

        # Create only 2 employees manually
        emp1 = Empleado()
        emp1.codigo_empleado = "TEST001"
        emp1.primer_nombre = "Test"
        emp1.primer_apellido = "User"
        emp1.identificacion_personal = "001-010190-0001X"
        emp1.fecha_alta = date.today()
        emp1.salario_base = Decimal("10000.00")
        emp1.moneda_id = moneda.id
        emp1.empresa_id = empresa1.id
        emp1.activo = True
        db_session.add(emp1)

        emp2 = Empleado()
        emp2.codigo_empleado = "TEST002"
        emp2.primer_nombre = "Test"
        emp2.primer_apellido = "User2"
        emp2.identificacion_personal = "001-010190-0002Y"
        emp2.fecha_alta = date.today()
        emp2.salario_base = Decimal("10000.00")
        emp2.moneda_id = moneda.id
        emp2.empresa_id = empresa1.id
        emp2.activo = True
        db_session.add(emp2)
        db_session.commit()

        empleados = [emp1, emp2]

        # Should not raise error
        create_demo_novelties(empleados)

        # Verify no novelties created
        count = db_session.execute(
            db.select(db.func.count()).select_from(NominaNovedad)
        ).scalar()
        assert count == 0


def test_load_demo_data(app, db_session):
    """
    Test that load_demo_data orchestrates all demo data loading.

    Setup:
        - Use app and db_session fixtures
        - Create required base data (currency, payroll type, concepts)

    Action:
        - Call load_demo_data()

    Verification:
        - Companies are created
        - Employees are created
        - Payrolls are created
        - Nomina is created
        - All components work together
    """
    with app.app_context():
        # Create required base data
        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)

        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = "MONTHLY"
        tipo_planilla.nombre = "Mensual"
        tipo_planilla.descripcion = "Planilla mensual"
        db_session.add(tipo_planilla)

        # Create some concepts
        overtime = Percepcion()
        overtime.codigo = "OVERTIME"
        overtime.nombre = "Horas Extra"
        db_session.add(overtime)

        absence = Deduccion()
        absence.codigo = "UNPAID_ABSENCES"
        absence.nombre = "Ausencias"
        db_session.add(absence)

        db_session.commit()

        # Load all demo data
        load_demo_data()

        # Verify companies created
        companies_count = db_session.execute(
            db.select(db.func.count()).select_from(Empresa)
        ).scalar()
        assert companies_count == 2

        # Verify employees created
        employees_count = db_session.execute(
            db.select(db.func.count()).select_from(Empleado)
        ).scalar()
        assert employees_count == 15

        # Verify payrolls created
        payrolls_count = db_session.execute(
            db.select(db.func.count()).select_from(Planilla)
        ).scalar()
        assert payrolls_count == 2

        # Verify nomina created
        nomina_count = db_session.execute(
            db.select(db.func.count()).select_from(Nomina)
        ).scalar()
        assert nomina_count == 1  # Only one nomina is created for planilla1


def test_load_demo_data_idempotent(app, db_session):
    """
    Test that load_demo_data is idempotent and can be called multiple times.

    Setup:
        - Use app and db_session fixtures
        - Create required base data

    Action:
        - Call load_demo_data() twice

    Verification:
        - Same counts after both calls
        - No duplicates created
    """
    with app.app_context():
        # Create required base data
        moneda = Moneda()
        moneda.codigo = "NIO"
        moneda.nombre = "Córdoba"
        moneda.simbolo = "C$"
        db_session.add(moneda)

        tipo_planilla = TipoPlanilla()
        tipo_planilla.codigo = "MONTHLY"
        tipo_planilla.nombre = "Mensual"
        tipo_planilla.descripcion = "Planilla mensual"
        db_session.add(tipo_planilla)
        db_session.commit()

        # First call
        load_demo_data()

        # Get counts after first call
        companies_count1 = db_session.execute(
            db.select(db.func.count()).select_from(Empresa)
        ).scalar()
        employees_count1 = db_session.execute(
            db.select(db.func.count()).select_from(Empleado)
        ).scalar()
        payrolls_count1 = db_session.execute(
            db.select(db.func.count()).select_from(Planilla)
        ).scalar()

        # Second call
        load_demo_data()

        # Get counts after second call
        companies_count2 = db_session.execute(
            db.select(db.func.count()).select_from(Empresa)
        ).scalar()
        employees_count2 = db_session.execute(
            db.select(db.func.count()).select_from(Empleado)
        ).scalar()
        payrolls_count2 = db_session.execute(
            db.select(db.func.count()).select_from(Planilla)
        ).scalar()

        # Counts should be the same
        assert companies_count1 == companies_count2 == 2
        assert employees_count1 == employees_count2 == 15
        assert payrolls_count1 == payrolls_count2 == 2
