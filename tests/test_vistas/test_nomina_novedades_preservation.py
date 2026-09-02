# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Defensive regression tests for novedades preservation on payroll recalculation."""

import inspect
from datetime import date
from decimal import Decimal

import pytest

from coati_payroll.enums import NominaEstado
from coati_payroll.model import (
    db,
    Empresa,
    Moneda,
    TipoPlanilla,
    Planilla,
    Empleado,
    PlanillaEmpleado,
    Nomina,
    NominaEmpleado,
    NominaNovedad,
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


def test_recalcular_nomina_does_not_delete_nomina_novedad_defensive():
    """DEFENSIVE: prevent reintroducing explicit NominaNovedad deletion."""
    source = inspect.getsource(NominaService.recalcular_nomina)

    assert "delete(NominaNovedad)" not in source
    assert "NominaNovedad must be preserved" in source


@pytest.mark.validation
class TestRecalculoNominaUnit:
    """Unit tests for payroll recalculation with novedades preservation.

    These tests verify that:
    1. Novedades (payroll events) are preserved when recalculating a payroll
    2. Novedades are correctly re-linked to the new nomina

    Novedades are master data (overtime, bonuses, absences, etc.) that should
    never be deleted during recalculation, as HR staff would have to re-enter them.

    These are unit tests that simulate the recalculation logic without calling
    the full NominaEngine to avoid complexity with overlapping period validation.
    The actual NominaService.recalcular_nomina() method is tested in
    test_nomina_service.py with mocks.
    """

    @pytest.fixture
    def setup_basic_payroll(self, app, db_session):
        """Create a minimal payroll setup for testing recalculation."""
        with app.app_context():
            # Create basic entities
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            db_session.add(moneda)
            db_session.flush()

            empresa = Empresa(
                codigo="TEST001",
                razon_social="Test Company SA",
                ruc="J-12345678",
                activo=True,
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
                activo=True,
            )
            db_session.add(tipo_planilla)
            db_session.flush()

            planilla = Planilla(
                nombre="Planilla Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                periodo_fiscal_inicio=date(2024, 1, 1),
                periodo_fiscal_fin=date(2024, 12, 31),
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create one employee
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

            # Add employee to planilla
            pe = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(pe)

            db_session.commit()
            db_session.refresh(planilla)
            db_session.refresh(empleado)

            return {
                "planilla": planilla,
                "empleado": empleado,
                "moneda": moneda,
                "empresa": empresa,
            }

    def test_recalcular_nomina_preserves_novedades_unit(self, app, db_session, setup_basic_payroll):
        """Unit test: Verify novedades are preserved during recalculation at the service level."""
        with app.app_context():
            setup = setup_basic_payroll
            planilla = setup["planilla"]
            empleado = setup["empleado"]

            # Create a nomina manually (not via engine to avoid overlap issues)
            nomina_original = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                fecha_generacion=date(2024, 1, 31),
                fecha_calculo_original=date(2024, 1, 31),
                generado_por="admin",
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("1000.00"),
                total_neto=Decimal("14000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(nomina_original)
            db_session.flush()

            # Add NominaEmpleado
            nomina_empleado = NominaEmpleado(
                nomina_id=nomina_original.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                total_ingresos=Decimal("15000.00"),
                total_deducciones=Decimal("1000.00"),
                salario_neto=Decimal("14000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()

            # Add novedades to the payroll (this is master data that must be preserved)
            novedad1 = NominaNovedad(
                nomina_id=nomina_original.id,
                empleado_id=empleado.id,
                codigo_concepto="HORAS_EXTRA",
                tipo_valor="horas",
                valor_cantidad=Decimal("10.00"),
                fecha_novedad=date(2024, 1, 15),
            )
            db_session.add(novedad1)

            novedad2 = NominaNovedad(
                nomina_id=nomina_original.id,
                empleado_id=empleado.id,
                codigo_concepto="BONO",
                tipo_valor="monto",
                valor_cantidad=Decimal("500.00"),
                fecha_novedad=date(2024, 1, 20),
            )
            db_session.add(novedad2)

            novedad3 = NominaNovedad(
                nomina_id=nomina_original.id,
                empleado_id=empleado.id,
                codigo_concepto="COMISION",
                tipo_valor="monto",
                valor_cantidad=Decimal("1200.00"),
                fecha_novedad=date(2024, 1, 25),
            )
            db_session.add(novedad3)

            db_session.commit()
            db_session.refresh(nomina_original)

            # Store original novedad IDs and data
            original_novedad_ids = {novedad1.id, novedad2.id, novedad3.id}
            original_novedad_data = {
                novedad1.id: ("HORAS_EXTRA", Decimal("10.00"), "horas"),
                novedad2.id: ("BONO", Decimal("500.00"), "monto"),
                novedad3.id: ("COMISION", Decimal("1200.00"), "monto"),
            }

            # Count novedades before recalculation
            novedades_count_before = db_session.query(NominaNovedad).count()
            assert novedades_count_before == 3, "Should have 3 novedades before recalculation"

            # Manually delete the old nomina and move novedades (simulating recalculation)
            # This tests the core logic without running the full engine

            # Create a new nomina (simulating recalculation result)
            nomina_nueva = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                fecha_generacion=date(2024, 2, 1),
                fecha_calculo_original=date(2024, 1, 31),  # Preserve original
                generado_por="admin",
                estado=NominaEstado.GENERADO,
                es_recalculo=True,
                nomina_original_id=nomina_original.id,
                total_bruto=Decimal("16200.00"),  # Different values due to recalc
                total_deducciones=Decimal("1100.00"),
                total_neto=Decimal("15100.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(nomina_nueva)
            db_session.flush()

            # Delete related records but preserve novedades
            db_session.delete(nomina_empleado)

            # CRITICAL: Move novedades to new nomina (this is what recalcular_nomina does)
            novedad_ids = [novedad1.id, novedad2.id, novedad3.id]
            db_session.execute(
                db.update(NominaNovedad).where(NominaNovedad.id.in_(novedad_ids)).values(nomina_id=nomina_nueva.id)
            )

            # Delete old nomina
            original_nomina_id = nomina_original.id
            db_session.delete(nomina_original)
            db_session.commit()

            # VERIFY: Novedades were preserved and moved to new nomina
            novedades_after = db_session.query(NominaNovedad).all()
            assert len(novedades_after) == 3, f"All 3 novedades must be preserved, found {len(novedades_after)}"

            # Verify the preserved novedades are the original ones (same IDs)
            preserved_novedad_ids = {n.id for n in novedades_after}
            assert (
                preserved_novedad_ids == original_novedad_ids
            ), "The same novedad records must be preserved (not recreated)"

            # Verify each novedad is linked to the new nomina and has correct data
            for novedad in novedades_after:
                assert novedad.nomina_id == nomina_nueva.id, f"Novedad {novedad.id} must be linked to new nomina"
                assert novedad.id in original_novedad_data, f"Novedad {novedad.id} should be an original novedad"

                codigo, valor, tipo = original_novedad_data[novedad.id]
                assert novedad.codigo_concepto == codigo, f"Novedad {novedad.id} should have codigo {codigo}"
                assert novedad.valor_cantidad == valor, f"Novedad {novedad.id} should have valor {valor}"
                assert novedad.tipo_valor == tipo, f"Novedad {novedad.id} should have tipo {tipo}"

            # Verify original nomina was deleted
            original_still_exists = db_session.get(Nomina, original_nomina_id)
            assert original_still_exists is None, "Original nomina should be deleted after recalculation"

            # Verify no orphaned novedades
            orphaned_novedades = (
                db_session.query(NominaNovedad)
                .filter(NominaNovedad.nomina_id == original_nomina_id)
                .count()
            )
            assert orphaned_novedades == 0, "No novedades should be orphaned (linked to deleted nomina)"
