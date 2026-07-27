# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""CRITICAL tests for employee validation before payroll processing.

These tests ensure employees meet all requirements before processing payment.
Critical for:
- Legal compliance
- Data integrity
- Preventing incorrect payments
- Audit trail
"""

from datetime import date, timedelta
from decimal import Decimal


from coati_payroll.nomina_engine import NominaEngine


class TestValidacionEmpleadoActivo:
    """Tests for active employee validation."""

    def test_empleado_inactivo_rechazado(self, app, db_session):
        """Test that inactive employees are rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # INACTIVE employee
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Juan",
                primer_apellido="Pérez",
                identificacion_personal="001-010180-0001A",
                salario_base=Decimal("15000.00"),
                fecha_alta=date(2024, 1, 1),
                moneda_id=moneda.id,
                activo=False,  # INACTIVE!
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have warning about inactive employee
            assert nomina is not None
            warning_found = any("no está activo" in w for w in engine.warnings)
            assert warning_found

            # Should not have processed the employee
            assert len(engine.empleados_calculo) == 0


class TestValidacionFechaIngreso:
    """Tests for hire date validation."""

    def test_fecha_ingreso_futura_rechazada(self, app, db_session):
        """Test that future hire dates are rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee with FUTURE hire date
            future_date = date.today() + timedelta(days=30)
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="María",
                primer_apellido="López",
                identificacion_personal="001-020190-0002B",
                salario_base=Decimal("18000.00"),
                fecha_alta=future_date,  # Future date!
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have error about future hire date
            assert nomina is not None
            error_found = any("fecha de ingreso" in e and "posterior" in e for e in engine.errors)
            assert error_found

    def test_fecha_ingreso_posterior_a_periodo(self, app, db_session):
        """Test that hire date after period end is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee hired after period end
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Carlos",
                primer_apellido="Ruiz",
                identificacion_personal="001-030195-0003C",
                salario_base=Decimal("20000.00"),
                fecha_alta=date(2025, 2, 15),  # After period end (Jan 31)
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll for January
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have error
            assert nomina is not None
            error_found = any("fecha de ingreso" in e and "posterior al período" in e for e in engine.errors)
            assert error_found


class TestValidacionFechaSalida:
    """Tests for termination date validation."""

    def test_fecha_salida_antes_de_periodo(self, app, db_session):
        """Test that termination date before period is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee terminated before period
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Ana",
                primer_apellido="Martínez",
                identificacion_personal="001-040185-0004D",
                salario_base=Decimal("16000.00"),
                fecha_alta=date(2024, 1, 1),
                fecha_baja=date(2024, 12, 31),  # Terminated before period (Jan 2025)
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll for January 2025
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have error
            assert nomina is not None
            error_found = any("fecha de salida" in e and "anterior al inicio" in e for e in engine.errors)
            assert error_found


class TestValidacionDatosEmpleado:
    """Tests for employee data validation."""

    def test_sin_identificacion_personal(self, app, db_session):
        """Test that employee without identification is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee without identification - need to bypass DB constraint for test
            # Actually, the DB has a NOT NULL constraint, so this will fail at DB level
            # Let's test with empty string instead
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Luis",
                primer_apellido="García",
                identificacion_personal="",  # Empty!
                salario_base=Decimal("14000.00"),
                fecha_alta=date(2024, 1, 1),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have error
            assert nomina is not None
            error_found = any("identificación personal" in e for e in engine.errors)
            assert error_found

    def test_salario_base_invalido(self, app, db_session):
        """Test that employee with invalid salary is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee with zero/negative salary
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Pedro",
                primer_apellido="Sánchez",
                identificacion_personal="001-050192-0005E",
                salario_base=Decimal("0.00"),  # Invalid!
                fecha_alta=date(2024, 1, 1),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have error
            assert nomina is not None
            error_found = any("salario base inválido" in e for e in engine.errors)
            assert error_found

    def test_sin_empresa_asignada(self, app, db_session):
        """Test that employee without company is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            # Employee without company
            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Rosa",
                primer_apellido="Méndez",
                identificacion_personal="001-060188-0006F",
                salario_base=Decimal("17000.00"),
                fecha_alta=date(2024, 1, 1),
                moneda_id=moneda.id,
                empresa_id=None,  # No company!
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 1),
                periodo_fin=date(2025, 1, 31),
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            nomina = engine.ejecutar()

            # Should have error
            assert nomina is not None
            error_found = any("no está asignado a ninguna empresa" in e for e in engine.errors)
            assert error_found


class TestValidacionPeriodo:
    """Tests for period validation."""

    def test_periodo_invalido_fin_antes_de_inicio(self, app, db_session):
        """Test that invalid period (end before start) is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-070191-0007G",
                salario_base=Decimal("15000.00"),
                fecha_alta=date(2024, 1, 1),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll with INVALID period (end before start)
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2025, 1, 31),  # End
                periodo_fin=date(2025, 1, 1),  # Start - WRONG!
                fecha_calculo=date(2025, 1, 31),
                usuario="admin",
            )

            # Should have error about invalid period — no nomina created
            nomina = engine.ejecutar()
            assert nomina is None
            assert len(engine.errors) > 0
            error_found = any("Período inválido" in e or "posterior a fin" in e for e in engine.errors)
            assert error_found, f"Expected error about invalid period. Errors: {engine.errors}"

    def test_periodo_excesivamente_largo(self, app, db_session):
        """Test that excessively long period is rejected."""
        from coati_payroll.model import Empresa, Moneda, TipoPlanilla, Planilla, Empleado, PlanillaEmpleado

        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

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
                nombre="Planilla Test", tipo_planilla_id=tipo_planilla.id, moneda_id=moneda.id, activo=True
            )
            db_session.add(planilla)
            db_session.flush()

            empleado = Empleado(
                codigo_empleado="EMP001",
                primer_nombre="Test",
                primer_apellido="User",
                identificacion_personal="001-080193-0008H",
                salario_base=Decimal("15000.00"),
                fecha_alta=date(2024, 1, 1),
                moneda_id=moneda.id,
                empresa_id=empresa.id,
                activo=True,
            )
            db_session.add(empleado)
            db_session.flush()

            planilla_emp = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(planilla_emp)
            db_session.commit()

            # Execute payroll with period longer than a year
            engine = NominaEngine(
                planilla=planilla,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2025, 12, 31),  # 2 years!
                fecha_calculo=date(2025, 12, 31),
                usuario="admin",
            )

            # Should have error — no nomina created
            nomina = engine.ejecutar()
            assert nomina is None
            assert len(engine.errors) > 0
            error_found = any("excesivamente largo" in e for e in engine.errors)
            assert error_found, f"Expected error about excessive period. Errors: {engine.errors}"
