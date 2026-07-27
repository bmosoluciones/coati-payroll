# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for defensive payroll processing mechanism.

This module tests the defensive mechanisms that ensure payroll consistency:
- Rollback when any employee processing fails
- Retry functionality for failed nominas
- Error recovery detection
- Configuration via environment variables
"""

import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock


from coati_payroll.enums import NominaEstado
from coati_payroll.model import (
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    Planilla,
    PlanillaEmpleado,
    Empleado,
    TipoPlanilla,
    Moneda,
    Empresa,
)

# Import functions from tasks module
# Note: Some functions may need to be tested via the module path
from coati_payroll.queue import tasks


class TestRollbackMechanism:
    """Tests for rollback functionality when payroll processing fails."""

    def test_rollback_nomina_data_removes_all_records(self, app, db_session):
        """Test that _rollback_nomina_data removes all created records."""
        with app.app_context():
            # Create test data
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            empresa = Empresa(codigo="TEST", razon_social="Test Company", ruc="123", activo=True)
            db_session.add_all([moneda, empresa])
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

            # Create nomina
            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                estado=NominaEstado.GENERADO,
                total_bruto=Decimal("15000.00"),
                total_deducciones=Decimal("0.00"),
                total_neto=Decimal("15000.00"),
            )
            db_session.add(nomina)
            db_session.flush()

            # Create nomina_empleado
            nomina_empleado = NominaEmpleado(
                nomina_id=nomina.id,
                empleado_id=empleado.id,
                salario_bruto=Decimal("15000.00"),
                total_ingresos=Decimal("0.00"),
                total_deducciones=Decimal("0.00"),
                salario_neto=Decimal("15000.00"),
                sueldo_base_historico=Decimal("15000.00"),
            )
            db_session.add(nomina_empleado)
            db_session.flush()

            # Create nomina_detalle
            detalle = NominaDetalle(
                nomina_empleado_id=nomina_empleado.id,
                tipo="income",
                codigo="SALARIO",
                descripcion="Salario Base",
                monto=Decimal("15000.00"),
                orden=1,
            )
            db_session.add(detalle)
            db_session.commit()

            # Verify records exist
            assert db_session.get(NominaEmpleado, nomina_empleado.id) is not None
            assert db_session.get(NominaDetalle, detalle.id) is not None

            # Execute rollback
            tasks._rollback_nomina_data(nomina.id)
            db_session.commit()

            # Verify all records are removed
            assert db_session.get(NominaEmpleado, nomina_empleado.id) is None
            assert db_session.get(NominaDetalle, detalle.id) is None

    def test_rollback_handles_empty_nomina(self, app, db_session):
        """Test that rollback handles nominas with no data gracefully."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            empresa = Empresa(codigo="TEST", razon_social="Test", ruc="123", activo=True)
            db_session.add_all([moneda, empresa])
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
                nombre="Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                estado=NominaEstado.ERROR,
            )
            db_session.add(nomina)
            db_session.commit()

            # Should not raise exception
            tasks._rollback_nomina_data(nomina.id)
            db_session.commit()


class TestErrorRecoveryDetection:
    """Tests for error recovery detection."""

    def test_recoverable_error_detection_connection(self):
        """Test that connection errors are detected as recoverable."""
        error = Exception("Database connection timeout")
        assert tasks._is_recoverable_error(error) is True

    def test_recoverable_error_detection_network(self):
        """Test that network errors are detected as recoverable."""
        error = Exception("Network socket broken pipe")
        assert tasks._is_recoverable_error(error) is True

    def test_non_recoverable_error_detection_validation(self):
        """Test that validation errors are detected as non-recoverable."""
        error = Exception("Validation error: missing required field")
        assert tasks._is_recoverable_error(error) is False

    def test_non_recoverable_error_detection_integrity(self):
        """Test that integrity errors are detected as non-recoverable."""
        error = Exception("Data integrity constraint violation")
        assert tasks._is_recoverable_error(error) is False

    def test_unknown_error_defaults_to_recoverable(self):
        """Test that unknown errors default to recoverable (safer to retry)."""
        error = Exception("Some unknown error message")
        assert tasks._is_recoverable_error(error) is True


class TestRetryConfiguration:
    """Tests for retry configuration from environment variables."""

    def test_default_retry_config(self):
        """Test default retry configuration when no env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            config = tasks._get_payroll_retry_config()
            assert config["max_retries"] == 3
            assert config["min_backoff_ms"] == 60000
            assert config["max_backoff_ms"] == 3600000

    def test_custom_retry_config_from_env(self):
        """Test custom retry configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "PAYROLL_MAX_RETRIES": "5",
                "PAYROLL_MIN_BACKOFF_MS": "120000",
                "PAYROLL_MAX_BACKOFF_MS": "7200000",
            },
            clear=False,
        ):
            config = tasks._get_payroll_retry_config()
            assert config["max_retries"] == 5
            assert config["min_backoff_ms"] == 120000
            assert config["max_backoff_ms"] == 7200000


class TestRetryFailedNomina:
    """Tests for retry_failed_nomina function."""

    def test_retry_failed_nomina_success(self, app, db_session):
        """Test successful retry of a failed nomina."""
        with app.app_context():
            # Create test data
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            empresa = Empresa(codigo="TEST", razon_social="Test", ruc="123", activo=True)
            db_session.add_all([moneda, empresa])
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
                nombre="Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create failed nomina
            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                estado=NominaEstado.ERROR,
                errores_calculo={"critical_error": "Test error"},
                total_empleados=10,
                empleados_procesados=5,
            )
            db_session.add(nomina)
            db_session.commit()

            # Mock queue.enqueue to avoid actual queue processing
            with patch("coati_payroll.queue.tasks.queue") as mock_queue:
                mock_queue.enqueue.return_value = "task-123"

                result = tasks.retry_failed_nomina(nomina.id, "test_user")

                assert result["success"] is True
                assert "task-123" in result["message"]

                # Verify nomina state was reset
                db_session.refresh(nomina)
                assert nomina.estado == NominaEstado.CALCULANDO
                assert nomina.empleados_procesados == 0
                assert nomina.errores_calculo == {}

    def test_retry_failed_nomina_wrong_state(self, app, db_session):
        """Test that retry fails if nomina is not in ERROR state."""
        with app.app_context():
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            empresa = Empresa(codigo="TEST", razon_social="Test", ruc="123", activo=True)
            db_session.add_all([moneda, empresa])
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
                nombre="Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create nomina in GENERADO state (not ERROR)
            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                estado=NominaEstado.GENERADO,
            )
            db_session.add(nomina)
            db_session.commit()

            result = tasks.retry_failed_nomina(nomina.id, "test_user")

            assert result["success"] is False
            assert "not in ERROR state" in result["error"]

    def test_retry_failed_nomina_not_found(self, app, db_session):
        """Test that retry fails if nomina doesn't exist."""
        with app.app_context():
            result = tasks.retry_failed_nomina("non-existent-id", "test_user")

            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestProcessLargePayrollRollback:
    """Tests for rollback behavior in process_large_payroll."""

    def test_process_large_payroll_sets_error_state_on_critical_failure(self, app, db_session):
        """Test that process_large_payroll sets ERROR state when critical failure occurs."""
        with app.app_context():
            # Create test data
            moneda = Moneda(codigo="NIO", nombre="Córdoba", simbolo="C$", activo=True)
            empresa = Empresa(codigo="TEST", razon_social="Test", ruc="123", activo=True)
            db_session.add_all([moneda, empresa])
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
                nombre="Test",
                tipo_planilla_id=tipo_planilla.id,
                empresa_id=empresa.id,
                moneda_id=moneda.id,
                activo=True,
            )
            db_session.add(planilla)
            db_session.flush()

            # Create employee
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

            # Associate employee with planilla
            pe = PlanillaEmpleado(planilla_id=planilla.id, empleado_id=empleado.id, activo=True)
            db_session.add(pe)
            db_session.flush()

            # Create nomina in CALCULANDO state
            nomina = Nomina(
                planilla_id=planilla.id,
                periodo_inicio=date(2024, 1, 1),
                periodo_fin=date(2024, 1, 31),
                estado=NominaEstado.CALCULANDO,
                total_empleados=1,
                procesamiento_en_background=True,
            )
            db_session.add(nomina)
            db_session.commit()

            # Mock NominaEngine to raise exception
            with patch("coati_payroll.queue.tasks.NominaEngine") as mock_engine_class:
                mock_engine = MagicMock()
                mock_engine_class.return_value = mock_engine
                mock_engine._procesar_empleado.side_effect = Exception("Critical database error")

                # Execute process_large_payroll - should catch exception and mark as generated with errors
                tasks.process_large_payroll(
                    nomina_id=nomina.id,
                    job_id="job-test-1",
                    planilla_id=planilla.id,
                    periodo_inicio="2024-01-01",
                    periodo_fin="2024-01-31",
                    usuario="test_user",
                )

                # Verify nomina is in GENERATED_WITH_ERRORS state
                db_session.refresh(nomina)
                assert nomina.estado == NominaEstado.GENERADO_CON_ERRORES
                assert len(nomina.errores_calculo) > 0


class TestTrackingSessionIsolation:
    """Tests for tracking session isolation in tasks.py."""

    def test_get_tracking_session_no_engine(self, app):
        with app.app_context():
            with patch("coati_payroll.queue.tasks.db") as mock_db:
                mock_db.engine = None
                mock_db.session = "fallback_session"
                session = tasks._get_tracking_session()
                assert session == "fallback_session"
                tasks._release_tracking_session(session)

    def test_get_tracking_session_with_engine(self, app):
        with app.app_context():
            # Real engine exists, should return a new Session
            session = tasks._get_tracking_session()
            assert session is not tasks.db.session
            tasks._release_tracking_session(session)
