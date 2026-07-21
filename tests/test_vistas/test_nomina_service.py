# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for NominaService class."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from coati_payroll.enums import NominaEstado
from coati_payroll.model import (
    Empresa,
    Empleado,
    Moneda,
    Nomina,
    NominaDetalle,
    NominaEmpleado,
    NominaNovedad,
    AdelantoAbono,
    ComprobanteContable,
    Prestacion,
    PrestacionAcumulada,
    Planilla,
    PlanillaEmpleado,
    TipoPlanilla,
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService
from coati_payroll.queue.drivers.dramatiq_driver import DramatiqDriver


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def moneda(app, db_session):
    """Create a Moneda for testing."""
    with app.app_context():
        moneda = Moneda(codigo="USD", nombre="Dolar", simbolo="$", activo=True)
        db_session.add(moneda)
        db_session.commit()
        db_session.refresh(moneda)
        return moneda


@pytest.fixture
def empresa(app, db_session):
    """Create an Empresa for testing."""
    with app.app_context():
        empresa = Empresa(
            codigo="TEST",
            razon_social="Test Company S.A.",
            ruc="123456789",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()
        db_session.refresh(empresa)
        return empresa


@pytest.fixture
def tipo_planilla(app, db_session):
    """Create a TipoPlanilla for testing."""
    with app.app_context():
        tipo = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Planilla Mensual",
            periodicidad="monthly",
            dias=30,
            periodos_por_anio=12,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            activo=True,
        )
        db_session.add(tipo)
        db_session.commit()
        db_session.refresh(tipo)
        return tipo


@pytest.fixture
def planilla(app, db_session, tipo_planilla, moneda, empresa, admin_user):
    """Create a Planilla for testing."""
    with app.app_context():
        planilla = Planilla(
            nombre="Test Planilla",
            descripcion="Planilla de prueba",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            periodo_fiscal_inicio=date(2024, 1, 1),
            periodo_fiscal_fin=date(2024, 12, 31),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(planilla)
        db_session.commit()
        db_session.refresh(planilla)
        return planilla


@pytest.fixture
def empleado(app, db_session, moneda, empresa):
    """Create an Empleado for testing."""
    with app.app_context():
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
        db_session.commit()
        db_session.refresh(empleado)
        return empleado


@pytest.fixture
def planilla_empleado(app, db_session, planilla, empleado):
    """Create a PlanillaEmpleado for testing."""
    with app.app_context():
        pe = PlanillaEmpleado(
            planilla_id=planilla.id,
            empleado_id=empleado.id,
            activo=True,
        )
        db_session.add(pe)
        db_session.commit()
        db_session.refresh(pe)
        return pe


# ============================================================================
# TESTS FOR calcular_periodo_sugerido
# ============================================================================


class TestCalcularPeriodoSugerido:
    """Tests for NominaService.calcular_periodo_sugerido method."""

    def test_ignora_nominas_anuladas_para_sugerir_inicio(
        self, app, db_session, planilla, planilla_empleado, admin_user
    ):
        """Cancelled payrolls must not drive suggested start date."""
        with app.app_context():
            nomina_generada = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
            )
            nomina_anulada = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 2, 1),
                periodo_fin=date(2024, 2, 29),
                generado_por=admin_user.usuario,
                estado=NominaEstado.ANULADO,
            )
            db_session.add_all([nomina_generada, nomina_anulada])
            db_session.commit()

            inicio, fin = NominaService.calcular_periodo_sugerido(planilla)

            assert inicio == date(2024, 2, 1)
            assert fin == date(2024, 2, 29)

    def test_no_falla_con_multiples_nominas_activas(
        self, app, db_session, planilla, planilla_empleado, admin_user
    ):
        """Method must return latest period suggestion without MultipleResultsFound."""
        with app.app_context():
            nomina_enero = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
            )
            nomina_febrero = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 2, 1),
                periodo_fin=date(2024, 2, 29),
                generado_por=admin_user.usuario,
                estado=NominaEstado.APROBADO,
            )
            db_session.add_all([nomina_enero, nomina_febrero])
            db_session.commit()

            inicio, fin = NominaService.calcular_periodo_sugerido(planilla)

            assert inicio == date(2024, 3, 1)
            assert fin == date(2024, 3, 31)


# ============================================================================
# TESTS FOR ejecutar_nomina
# ============================================================================


class TestEjecutarNomina:
    """Tests for NominaService.ejecutar_nomina method."""

    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_ejecutar_nomina_synchronous_small_payroll(
        self, mock_engine_class, app, db_session, planilla, planilla_empleado, admin_user
    ):
        """Test synchronous execution for small payroll (below threshold)."""
        with app.app_context():
            # Setup
            periodo_inicio = date(2024, 1, 1)
            periodo_fin = date(2024, 1, 31)
            fecha_calculo = date(2024, 1, 31)
            usuario = admin_user.usuario

            # Mock the engine
            mock_engine = MagicMock()
            mock_nomina = MagicMock(spec=Nomina)
            mock_nomina.id = 1
            mock_engine.ejecutar.return_value = mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = ["test warning"]
            mock_engine_class.return_value = mock_engine

            # Execute
            nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )

            # Assert
            assert nomina == mock_nomina
            assert errors == []
            assert warnings == ["test warning"]

            # Verify engine was instantiated with correct parameters
            mock_engine_class.assert_called_once_with(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )
            mock_engine.ejecutar.assert_called_once()

    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_ejecutar_nomina_warns_when_period_has_fewer_days_than_expected(
        self, mock_engine_class, app, db_session, planilla, planilla_empleado, admin_user
    ):
        """Monthly payroll with very short period should return an explicit warning."""
        with app.app_context():
            periodo_inicio = date(2024, 1, 1)
            periodo_fin = date(2024, 1, 1)
            fecha_calculo = date(2024, 1, 1)
            usuario = admin_user.usuario

            mock_engine = MagicMock()
            mock_nomina = MagicMock(spec=Nomina)
            mock_nomina.id = "NOM-TEST-SHORT-PERIOD"
            mock_engine.ejecutar.return_value = mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )

            assert nomina == mock_nomina
            assert errors == []
            assert len(warnings) == 1
            assert "WARNING: Este calculo de planilla tiene menos dias de lo esperado" in warnings[0]
            assert "periodicidad mensual" in warnings[0]
            assert "2024-01-01 a 2024-01-01" in warnings[0]

    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_ejecutar_nomina_warns_when_first_payroll_is_outside_fiscal_start(
        self, mock_engine_class, app, db_session, planilla, planilla_empleado, admin_user
    ):
        """First payroll outside fiscal start should warn for manual tax verification."""
        with app.app_context():
            periodo_inicio = date(2024, 2, 1)
            periodo_fin = date(2024, 2, 29)
            fecha_calculo = date(2024, 2, 29)
            usuario = admin_user.usuario

            mock_engine = MagicMock()
            mock_nomina = MagicMock(spec=Nomina)
            mock_nomina.id = "NOM-TEST-1"
            mock_engine.ejecutar.return_value = mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )

            assert nomina == mock_nomina
            assert errors == []
            assert len(warnings) == 1
            assert "primera nomina calculada no coincide con el inicio del periodo fiscal" in warnings[0]
            assert "Se recomienda verificacion manual de impuestos." in warnings[0]

    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_ejecutar_nomina_does_not_warn_when_not_first_payroll(
        self, mock_engine_class, app, db_session, planilla, planilla_empleado, admin_user
    ):
        """Fiscal-start warning should not be emitted when payroll already has history."""
        with app.app_context():
            existing_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
            )
            db_session.add(existing_nomina)
            db_session.commit()

            periodo_inicio = date(2024, 2, 1)
            periodo_fin = date(2024, 2, 29)
            fecha_calculo = date(2024, 2, 29)
            usuario = admin_user.usuario

            mock_engine = MagicMock()
            mock_nomina = MagicMock(spec=Nomina)
            mock_nomina.id = "NOM-TEST-2"
            mock_engine.ejecutar.return_value = mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            _nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )

            assert errors == []
            assert warnings == []

    @patch("coati_payroll.vistas.planilla.services.nomina_service.get_queue_driver")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_ejecutar_nomina_background_large_payroll(
        self, mock_engine_class, mock_get_queue, app, db_session, planilla, moneda, empresa, admin_user
    ):
        """Test background execution for large payroll (above threshold)."""
        with app.app_context():
            app.config["QUEUE_ENABLED"] = True
            # Create many employees to exceed threshold
            # Default threshold is 100, so create 101 employees
            for i in range(101):
                empleado = Empleado(
                    codigo_empleado=f"EMP{i:03d}",
                    primer_nombre=f"Empleado{i}",
                    primer_apellido="Test",
                    identificacion_personal=f"001-{i:06d}-0001A",
                    fecha_alta=date(2024, 1, 1),
                    salario_base=Decimal("10000.00"),
                    moneda_id=moneda.id,
                    empresa_id=empresa.id,
                    activo=True,
                )
                db_session.add(empleado)
                db_session.flush()

                pe = PlanillaEmpleado(
                    planilla_id=planilla.id,
                    empleado_id=empleado.id,
                    activo=True,
                )
                db_session.add(pe)

            db_session.commit()
            db_session.refresh(planilla)

            # Mock queue driver as Dramatiq available
            mock_queue = MagicMock(spec=DramatiqDriver)
            mock_queue.is_available.return_value = True
            mock_get_queue.return_value = mock_queue

            # Setup
            periodo_inicio = date(2024, 1, 1)
            periodo_fin = date(2024, 1, 31)
            fecha_calculo = date(2024, 1, 31)
            usuario = admin_user.usuario

            # Execute
            nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )

            # Assert
            assert nomina is not None
            assert nomina.estado == NominaEstado.CALCULANDO
            assert nomina.procesamiento_en_background is True
            assert nomina.total_empleados == 101
            assert errors == []
            assert warnings == []

            # Verify queue was called
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[0][0] == "process_large_payroll"
            assert call_args[1]["nomina_id"] == nomina.id
            assert "job_id" in call_args[1]
            assert call_args[1]["planilla_id"] == planilla.id

            # Verify engine was NOT called for background processing
            mock_engine_class.assert_not_called()

    @patch("coati_payroll.vistas.planilla.services.nomina_service.get_queue_driver")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_ejecutar_nomina_background_queue_error_falls_back_to_sync(
        self, mock_engine_class, mock_get_queue, app, db_session, planilla, moneda, empresa, admin_user
    ):
        """Test queue enqueue failure falls back to synchronous execution."""
        with app.app_context():
            app.config["QUEUE_ENABLED"] = True
            # Create many employees to exceed threshold
            for i in range(101):
                empleado = Empleado(
                    codigo_empleado=f"EMP{i:03d}",
                    primer_nombre=f"Empleado{i}",
                    primer_apellido="Test",
                    identificacion_personal=f"001-{i:06d}-0001A",
                    fecha_alta=date(2024, 1, 1),
                    salario_base=Decimal("10000.00"),
                    moneda_id=moneda.id,
                    empresa_id=empresa.id,
                    activo=True,
                )
                db_session.add(empleado)
                db_session.flush()

                pe = PlanillaEmpleado(
                    planilla_id=planilla.id,
                    empleado_id=empleado.id,
                    activo=True,
                )
                db_session.add(pe)

            db_session.commit()
            db_session.refresh(planilla)

            # Mock queue driver (Dramatiq) and force enqueue failure
            mock_queue = MagicMock(spec=DramatiqDriver)
            mock_queue.is_available.return_value = True
            mock_queue.enqueue.side_effect = Exception("Queue connection failed")
            mock_get_queue.return_value = mock_queue

            # Mock synchronous engine fallback
            mock_engine = MagicMock()
            mock_nomina = MagicMock(spec=Nomina)
            mock_engine.ejecutar.return_value = mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            # Setup
            periodo_inicio = date(2024, 1, 1)
            periodo_fin = date(2024, 1, 31)
            fecha_calculo = date(2024, 1, 31)
            usuario = admin_user.usuario

            # Execute
            nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                fecha_calculo=fecha_calculo,
                usuario=usuario,
            )

            # Assert fallback to sync happened
            assert nomina == mock_nomina
            assert errors == []
            assert warnings == []
            mock_queue.enqueue.assert_called_once()
            mock_engine.ejecutar.assert_called_once()


# ============================================================================
# TESTS FOR recalcular_nomina
# ============================================================================


class TestRecalcularNomina:
    """Tests for NominaService.recalcular_nomina method."""

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_preserves_novedades_master_data_defensive(
        self, mock_engine_class, mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """DEFENSIVE: recalcular_nomina must preserve NominaNovedad master data."""
        with app.app_context():
            # Create original nomina with related records
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)
            original_nomina_id = original_nomina.id

            # Create NominaEmpleado
            nomina_empleado = NominaEmpleado(
                nomina_id=original_nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                total_ingresos=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                salario_neto=Decimal("13000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()
            db_session.refresh(nomina_empleado)

            # Create NominaDetalle
            nomina_detalle = NominaDetalle(
                nomina_empleado_id=nomina_empleado.id,
                tipo="income",
                codigo="SALARIO",
                descripcion="Salario Base",
                monto=Decimal("15000.00"),
            )
            db_session.add(nomina_detalle)
            db_session.commit()

            # Create NominaNovedad
            nomina_novedad = NominaNovedad(
                nomina_id=original_nomina.id,
                empleado_id=empleado.id,
                codigo_concepto="EXTRA",
                valor_cantidad=Decimal("100.00"),
            )
            db_session.add(nomina_novedad)
            db_session.commit()
            original_novedad_id = nomina_novedad.id

            # Mock the engine for recalculation
            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            new_mock_nomina.id = 999
            new_mock_nomina.estado = NominaEstado.GENERADO
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            # Execute recalculation
            new_nomina, errors, warnings = NominaService.recalcular_nomina(
                nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario
            )

            # Assert the new nomina is returned
            assert new_nomina == new_mock_nomina
            assert errors == []
            assert warnings == []

            # Verify old records were deleted
            assert db_session.query(Nomina).filter_by(id=original_nomina_id).first() is None
            assert db_session.query(NominaEmpleado).filter_by(nomina_id=original_nomina_id).first() is None
            assert db_session.query(NominaDetalle).filter_by(nomina_empleado_id=nomina_empleado.id).first() is None
            preserved_novedad = db_session.get(NominaNovedad, original_novedad_id)
            assert preserved_novedad is not None
            assert str(preserved_novedad.nomina_id) == str(new_mock_nomina.id)

            # Verify engine was called
            mock_engine_class.assert_called_once()
            mock_engine.ejecutar.assert_called_once()

            # Verify audit log was created
            mock_audit.assert_called_once()

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_sets_recalculo_flags(
        self, mock_engine_class, mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """Test that recalcular_nomina sets es_recalculo and nomina_original_id."""
        with app.app_context():
            # Create original nomina
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)
            original_nomina_id = original_nomina.id

            # Mock the engine
            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = ["test error"]
            mock_engine.warnings = ["test warning"]
            mock_engine_class.return_value = mock_engine

            # Execute recalculation
            new_nomina, errors, warnings = NominaService.recalcular_nomina(
                nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario
            )

            # Assert flags are set
            assert new_nomina.es_recalculo is True
            assert new_nomina.nomina_original_id == original_nomina_id
            assert errors == ["test error"]
            assert warnings == ["test warning"]

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_with_adelanto_abono(
        self, mock_engine_class, mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """Test that recalcular_nomina deletes AdelantoAbono records."""
        with app.app_context():
            # Create original nomina
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)
            original_nomina_id = original_nomina.id

            # Create AdelantoAbono linked to this nomina
            # Note: We need to create the related Adelanto first
            from coati_payroll.model import Adelanto

            adelanto = Adelanto(
                empleado_id=empleado.id,
                tipo="advance",
                monto_aprobado=Decimal("1000.00"),
                fecha_desembolso=date(2024, 1, 15),
                saldo_pendiente=Decimal("1000.00"),
            )
            db_session.add(adelanto)
            db_session.commit()
            db_session.refresh(adelanto)

            adelanto_abono = AdelantoAbono(
                adelanto_id=adelanto.id,
                nomina_id=original_nomina.id,
                monto_abonado=Decimal("500.00"),
                fecha_abono=date(2024, 1, 31),
            )
            db_session.add(adelanto_abono)
            db_session.commit()

            # Mock the engine
            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            # Execute recalculation
            new_nomina, errors, warnings = NominaService.recalcular_nomina(
                nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario
            )

            # Verify AdelantoAbono was deleted
            assert db_session.query(AdelantoAbono).filter_by(nomina_id=original_nomina_id).first() is None

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_deletes_legacy_prestacion_transactions(
        self, mock_engine_class, _mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """Recalculation removes legacy PrestacionAcumulada rows tied to the source nomina."""
        with app.app_context():
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)

            prestacion = Prestacion(
                codigo="PREST_RECALC_TEST",
                nombre="Prestacion Recalc Test",
                tipo="employer",
                formula_tipo="fixed",
                monto_default=Decimal("0.00"),
                tipo_acumulacion="annual",
                activo=True,
            )
            db_session.add(prestacion)
            db_session.commit()
            db_session.refresh(prestacion)

            legacy_transaccion = PrestacionAcumulada(
                empleado_id=empleado.id,
                prestacion_id=prestacion.id,
                fecha_transaccion=date(2024, 1, 31),
                tipo_transaccion="adicion",
                anio=2024,
                mes=1,
                moneda_id=planilla.moneda_id,
                monto_transaccion=Decimal("100.00"),
                saldo_anterior=Decimal("0.00"),
                saldo_nuevo=Decimal("100.00"),
                nomina_id=original_nomina.id,
                creado_por=admin_user.usuario,
                procesado_por=admin_user.usuario,
            )
            db_session.add(legacy_transaccion)
            db_session.commit()
            assert db_session.query(PrestacionAcumulada).filter_by(nomina_id=original_nomina.id).count() == 1

            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            new_mock_nomina.id = 999
            new_mock_nomina.estado = NominaEstado.GENERADO
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            new_nomina, errors, warnings = NominaService.recalcular_nomina(
                nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario
            )

            assert new_nomina == new_mock_nomina
            assert errors == []
            assert warnings == []
            assert db_session.query(PrestacionAcumulada).filter_by(nomina_id=original_nomina.id).count() == 0

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_uses_original_fecha_calculo(
        self, mock_engine_class, mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """Test that recalcular_nomina uses the original fecha_calculo."""
        with app.app_context():
            # Create original nomina with fecha_calculo_original
            fecha_calculo_original = date(2024, 1, 31)
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
                fecha_calculo_original=fecha_calculo_original,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)
            original_nomina_id = original_nomina.id

            # Mock the engine
            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            # Execute recalculation
            NominaService.recalcular_nomina(nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario)

            # Verify engine was called with original fecha_calculo
            call_args = mock_engine_class.call_args
            assert call_args[1]["fecha_calculo"] == fecha_calculo_original
            assert call_args[1]["excluded_nomina_id"] == original_nomina_id

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_creates_audit_log(
        self, mock_engine_class, mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """Test that recalcular_nomina creates an audit log entry."""
        with app.app_context():
            # Create original nomina
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)
            original_nomina_id = original_nomina.id

            # Mock the engine
            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            new_mock_nomina.estado = NominaEstado.GENERADO
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            # Execute recalculation
            NominaService.recalcular_nomina(nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario)

            # Verify audit log was created with correct parameters
            mock_audit.assert_called_once()
            call_args = mock_audit.call_args[1]
            assert call_args["nomina"] == new_mock_nomina
            assert call_args["accion"] == "recalculated"
            assert call_args["usuario"] == admin_user.usuario
            assert f"nómina original {original_nomina_id}" in call_args["descripcion"]
            assert call_args["cambios"]["nomina_original_id"] == original_nomina_id
            assert call_args["estado_anterior"] == "deleted"
            assert call_args["estado_nuevo"] == NominaEstado.GENERADO

    @patch("coati_payroll.audit_helpers.crear_log_auditoria_nomina")
    @patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
    def test_recalcular_nomina_deletes_comprobante_contable_before_nomina(
        self, mock_engine_class, mock_audit, app, db_session, planilla, empleado, admin_user
    ):
        """Test that recalcular_nomina deletes ComprobanteContable before deleting Nomina.

        This regression test ensures that the IntegrityError described in the patch
        does not occur. ComprobanteContable has a non-nullable FK to nomina_id,
        so it must be deleted before the Nomina record.
        """
        with app.app_context():
            # Create original nomina
            original_nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                generado_por=admin_user.usuario,
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                total_neto=Decimal("13000.00"),
                total_empleados=1,
                empleados_procesados=1,
                empleados_con_error=0,
            )
            db_session.add(original_nomina)
            db_session.commit()
            db_session.refresh(original_nomina)
            original_nomina_id = original_nomina.id

            # Create NominaEmpleado
            nomina_empleado = NominaEmpleado(
                nomina_id=original_nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                total_ingresos=Decimal("15000.00"),
                total_deducciones=Decimal("2000.00"),
                salario_neto=Decimal("13000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.commit()
            db_session.refresh(nomina_empleado)

            # Create ComprobanteContable linked to the nomina
            comprobante = ComprobanteContable(
                nomina_id=original_nomina.id,
                fecha_calculo=date(2024, 1, 31),
                concepto="Nómina Mensual Enero 2024",
                aplicado_por=admin_user.usuario,
                fecha_aplicacion=date(2024, 1, 31),
            )
            db_session.add(comprobante)
            db_session.commit()
            db_session.refresh(comprobante)
            comprobante_id = comprobante.id

            # Mock the engine for recalculation
            mock_engine = MagicMock()
            new_mock_nomina = MagicMock(spec=Nomina)
            new_mock_nomina.id = 999
            new_mock_nomina.estado = NominaEstado.GENERADO
            mock_engine.ejecutar.return_value = new_mock_nomina
            mock_engine.errors = []
            mock_engine.warnings = []
            mock_engine_class.return_value = mock_engine

            # Execute recalculation - this should NOT raise IntegrityError
            new_nomina, errors, warnings = NominaService.recalcular_nomina(
                nomina=original_nomina, planilla=planilla, usuario=admin_user.usuario
            )

            # Assert the new nomina is returned
            assert new_nomina == new_mock_nomina
            assert errors == []
            assert warnings == []

            # Verify old records were deleted
            assert db_session.query(Nomina).filter_by(id=original_nomina_id).first() is None
            assert db_session.query(ComprobanteContable).filter_by(id=comprobante_id).first() is None

            # Verify the operation completed without IntegrityError
            assert db_session.query(NominaEmpleado).filter_by(nomina_id=original_nomina_id).first() is None
