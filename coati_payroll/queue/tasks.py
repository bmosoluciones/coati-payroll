# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Background tasks for payroll processing.

This module defines tasks that can be executed in the background:
- Individual employee payroll calculations
- Bulk payroll processing for multiple employees
- Report generation
- Email notifications

Tasks are automatically registered with the available queue driver
(Dramatiq) and can be enqueued for background execution.
"""

from __future__ import annotations

import os
import json
from urllib.request import urlopen
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from coati_payroll.log import log
from coati_payroll.model import (
    db,
    Empleado,
    Planilla,
    Nomina as NominaModel,
    NominaEmpleado as NominaEmpleadoModel,
    NominaDetalle as NominaDetalleModel,
    NominaProgress as NominaProgressModel,
    PrestacionAcumulada,
    AdelantoAbono,
    InteresAdelanto,
    Moneda,
    TipoCambio,
)
from coati_payroll.nomina_engine import NominaEngine
from coati_payroll.nomina_engine.processors.loan_processor import LoanProcessor
from coati_payroll.nomina_engine.processors.vacation_processor import VacationProcessor
from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService
from coati_payroll.nomina_engine.services.payroll_execution_service import PayrollExecutionService
from coati_payroll.nomina_engine.validators import NominaEngineError, ValidationError as NominaValidationError
from coati_payroll.nomina_engine.results.warning_collector import WarningCollector
from coati_payroll.queue import get_queue_driver
from coati_payroll.schema_validator import ValidationError as SchemaValidationError

NOMINA_NOT_FOUND = "Nomina not found"

# Error messages
ERROR_PLANILLA_NOT_FOUND = "Planilla not found"
ERROR_NO_ACTIVE_EMPLOYEES = "No active employees found"

# Get the queue driver
queue = get_queue_driver()


def _get_payroll_retry_config() -> dict[str, int]:
    """Get payroll retry configuration from environment variables.

    Returns:
        Dictionary with retry configuration:
        {
            "max_retries": int,
            "min_backoff_ms": int,
            "max_backoff_ms": int
        }
    """
    return {
        "max_retries": int(os.getenv("PAYROLL_MAX_RETRIES", "3")),
        "min_backoff_ms": int(os.getenv("PAYROLL_MIN_BACKOFF_MS", "60000")),  # 60 seconds
        "max_backoff_ms": int(os.getenv("PAYROLL_MAX_BACKOFF_MS", "3600000")),  # 1 hour
    }


def _is_recoverable_error(error: Exception) -> bool:
    """Determine if an error is recoverable (can be retried).

    Recoverable errors are typically transient issues like:
    - Database connection problems
    - Network timeouts
    - Temporary resource unavailability

    Non-recoverable errors are typically:
    - Validation errors
    - Data integrity issues
    - Configuration problems

    Args:
        error: The exception that occurred

    Returns:
        True if error is recoverable, False otherwise
    """
    if isinstance(error, (IntegrityError, NominaValidationError, SchemaValidationError, NominaEngineError)):
        return False

    if isinstance(error, (OperationalError, TimeoutError, ConnectionError)):
        return True

    if isinstance(error, ValueError):
        return False

    message = str(error).lower()
    non_recoverable_keywords = (
        "validation",
        "integrity",
        "constraint",
        "missing required",
        "invalid",
        "schema",
    )
    recoverable_keywords = (
        "connection",
        "timeout",
        "network",
        "broken pipe",
        "temporar",
        "deadlock",
        "lock wait",
        "unavailable",
    )

    if any(keyword in message for keyword in non_recoverable_keywords):
        return False
    if any(keyword in message for keyword in recoverable_keywords):
        return True

    return True


def _get_tracking_session():
    """Get a separate SQLAlchemy session for tracking progress.

    We use a completely independent session bound to the same engine
    to avoid committing or dirtying the main db.session transaction.
    """
    if not hasattr(db, "engine") or db.engine is None:
        return db.session
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db.engine)
    return Session()


def _release_tracking_session(tracking_session) -> None:
    if tracking_session is not db.session:
        tracking_session.close()


def _resolve_job_id(nomina: NominaModel, job_id: str | None) -> str:
    if job_id:
        return job_id
    if nomina.job_id_activo:
        return nomina.job_id_activo
    return uuid4().hex


def _acquire_nomina_job_lock(nomina_id: str, job_id: str) -> bool:
    result = cast(
        Any,
        db.session.execute(
            db.update(NominaModel)
            .where(
                NominaModel.id == nomina_id,
                or_(NominaModel.job_id_activo.is_(None), NominaModel.job_id_activo == job_id),
            )
            .values(job_id_activo=job_id, job_started_at=datetime.now(timezone.utc))
        ),
    )
    db.session.flush()
    return bool(getattr(result, "rowcount", 0) == 1)


def _clear_nomina_job_lock(nomina_id: str) -> None:
    db.session.execute(
        db.update(NominaModel)
        .where(NominaModel.id == nomina_id)
        .values(job_id_activo=None, job_completed_at=datetime.now(timezone.utc))
    )


def _create_nomina_progress(
    tracking_session,
    nomina_id: str,
    job_id: str,
    total_empleados: int | None,
    empleados_procesados: int | None,
    empleados_con_error: int | None,
    errores_calculo: dict | None,
    log_procesamiento: list | None,
    empleado_actual: str | None,
) -> NominaProgressModel:
    progress = NominaProgressModel(
        nomina_id=nomina_id,
        job_id=job_id,
        total_empleados=total_empleados or 0,
        empleados_procesados=empleados_procesados or 0,
        empleados_con_error=empleados_con_error or 0,
        errores_calculo=errores_calculo or {},
        log_procesamiento=log_procesamiento or [],
        empleado_actual=empleado_actual,
        actualizado_en=datetime.now(timezone.utc),
    )
    tracking_session.add(progress)
    return progress


def _update_nomina_progress(
    progress: NominaProgressModel,
    job_id: str,
    total_empleados: int | None,
    empleados_procesados: int | None,
    empleados_con_error: int | None,
    errores_calculo: dict | None,
    log_procesamiento: list | None,
    empleado_actual: str | None,
) -> None:
    progress.job_id = job_id
    for field, value in (
        ("total_empleados", total_empleados),
        ("empleados_procesados", empleados_procesados),
        ("empleados_con_error", empleados_con_error),
        ("errores_calculo", errores_calculo),
        ("log_procesamiento", log_procesamiento),
        ("empleado_actual", empleado_actual),
    ):
        if value is not None:
            setattr(progress, field, value)
    progress.actualizado_en = datetime.now(timezone.utc)


def _upsert_nomina_progress(
    tracking_session,
    nomina_id: str,
    job_id: str,
    *,
    total_empleados: int | None = None,
    empleados_procesados: int | None = None,
    empleados_con_error: int | None = None,
    errores_calculo: dict | None = None,
    log_procesamiento: list | None = None,
    empleado_actual: str | None = None,
) -> None:
    progress = (
        tracking_session.execute(db.select(NominaProgressModel).filter(NominaProgressModel.nomina_id == nomina_id))
        .scalars()
        .first()
    )

    if not progress:
        _create_nomina_progress(
            tracking_session,
            nomina_id,
            job_id,
            total_empleados,
            empleados_procesados,
            empleados_con_error,
            errores_calculo,
            log_procesamiento,
            empleado_actual,
        )
    else:
        _update_nomina_progress(
            progress,
            job_id,
            total_empleados,
            empleados_procesados,
            empleados_con_error,
            errores_calculo,
            log_procesamiento,
            empleado_actual,
        )

    tracking_session.commit()


def retry_failed_nomina(nomina_id: str, usuario: str | None = None) -> dict[str, bool | str]:
    """Retry processing a failed nomina.

    This function allows manual retry of a nomina that failed during processing.
    It will reset the nomina state and attempt to process it again.

    Args:
        nomina_id: ID of the failed nomina to retry
        usuario: Username attempting the retry (optional)

    Returns:
        Dictionary with retry status:
        {
            "success": bool,
            "message": str,
            "error": str (if failed)
        }
    """
    from coati_payroll.enums import NominaEstado

    try:
        log.info("Retrying failed nomina %s", nomina_id)

        # Load the nomina
        nomina = db.session.get(NominaModel, nomina_id)
        if not nomina:
            return {
                "success": False,
                "error": NOMINA_NOT_FOUND,
            }

        if nomina.estado == NominaEstado.GENERADO_CON_ERRORES:
            return {
                "success": False,
                "error": "Nomina calculated with errors. Please recalculate failed employees before retrying.",
            }

        # Verify nomina is in ERROR state
        if nomina.estado != NominaEstado.ERROR:
            return {
                "success": False,
                "error": f"Nomina not in ERROR state (current: {nomina.estado}). Only failed nominas can be retried.",
            }

        if nomina.job_id_activo:
            return {
                "success": False,
                "error": "Nomina has an active job. Wait for completion before retrying.",
            }

        # Get planilla information
        planilla = db.session.get(Planilla, nomina.planilla_id)
        if not planilla:
            return {
                "success": False,
                "error": ERROR_PLANILLA_NOT_FOUND,
            }

        # Reset nomina state for retry
        nomina.estado = NominaEstado.CALCULANDO
        nomina.empleados_procesados = 0
        nomina.empleados_con_error = 0
        nomina.errores_calculo = {}
        nomina.log_procesamiento = []
        nomina.empleado_actual = None
        nomina.job_id_activo = None
        nomina.job_started_at = None
        nomina.job_completed_at = None

        # Clear any partial data from previous attempt
        _rollback_nomina_data(nomina_id)
        db.session.execute(db.delete(NominaProgressModel).filter(NominaProgressModel.nomina_id == nomina_id))

        db.session.commit()

        # Enqueue the processing task again
        job_id = uuid4().hex
        fecha_calculo_str = nomina.fecha_generacion.date().isoformat() if nomina.fecha_generacion else None
        periodo_inicio_str = nomina.periodo_inicio.isoformat()
        periodo_fin_str = nomina.periodo_fin.isoformat()

        task_id = queue.enqueue(
            "process_large_payroll",
            nomina_id=nomina_id,
            job_id=job_id,
            planilla_id=nomina.planilla_id,
            periodo_inicio=periodo_inicio_str,
            periodo_fin=periodo_fin_str,
            fecha_calculo=fecha_calculo_str,
            usuario=usuario or nomina.generado_por,
        )

        log.info("Retry task enqueued for nomina %s, task_id: %s", nomina_id, task_id)

        return {
            "success": True,
            "message": f"Retry task enqueued successfully. Task ID: {task_id}",
        }

    except Exception as e:
        log.error("Error retrying nomina %s: %s", nomina_id, e)
        db.session.rollback()
        return {
            "success": False,
            "error": str(e),
        }


def _rollback_nomina_data(nomina_id: str) -> None:
    """Rollback all data created for a nomina during payroll processing.

    This function removes all records created during payroll calculation:
    - NominaEmpleado records
    - NominaDetalle records
    - PrestacionAcumulada transactions
    - AdelantoAbono records
    - InteresAdelanto records
    - Reverts AcumuladoAnual changes

    Args:
        nomina_id: ID of the nomina to rollback
    """
    try:
        log.info("Rolling back all data for nomina %s", nomina_id)

        # Get all NominaEmpleado records for this nomina
        nomina_empleados = (
            db.session.execute(db.select(NominaEmpleadoModel).filter(NominaEmpleadoModel.nomina_id == nomina_id))
            .scalars()
            .all()
        )

        # Collect all IDs for cascading deletes
        nomina_empleado_ids = [ne.id for ne in nomina_empleados]

        if nomina_empleado_ids:
            # Delete NominaDetalle records (cascade from NominaEmpleado)
            db.session.execute(
                db.delete(NominaDetalleModel).filter(NominaDetalleModel.nomina_empleado_id.in_(nomina_empleado_ids))
            )

            # Delete NominaEmpleado records
            db.session.execute(db.delete(NominaEmpleadoModel).filter(NominaEmpleadoModel.nomina_id == nomina_id))

        # Delete PrestacionAcumulada transactions created for this nomina
        db.session.execute(db.delete(PrestacionAcumulada).filter(PrestacionAcumulada.nomina_id == nomina_id))

        # Delete AdelantoAbono records created for this nomina
        db.session.execute(db.delete(AdelantoAbono).filter(AdelantoAbono.nomina_id == nomina_id))

        # Delete InteresAdelanto records created for this nomina
        db.session.execute(db.delete(InteresAdelanto).filter(InteresAdelanto.nomina_id == nomina_id))

        # Note: AcumuladoAnual changes are reverted via transaction rollback
        # VacationLedger entries are also reverted via transaction rollback

        log.info("Successfully rolled back data for nomina %s", nomina_id)

    except Exception as e:
        log.error("Error during rollback for nomina %s: %s", nomina_id, e)
        raise


def calculate_employee_payroll(
    empleado_id: str,
    planilla_id: str,
    periodo_inicio: str,
    periodo_fin: str,
    fecha_calculo: str | None = None,
    usuario: str | None = None,
) -> dict[str, Any]:
    """Calculate payroll for a single employee (background task).

    This task can be enqueued for background processing to avoid
    blocking the main application when calculating large payrolls.

    Args:
        empleado_id: Employee ID (ULID string)
        planilla_id: Planilla ID (ULID string)
        periodo_inicio: Start date (ISO format: YYYY-MM-DD)
        periodo_fin: End date (ISO format: YYYY-MM-DD)
        fecha_calculo: Calculation date (ISO format, optional)
        usuario: Username executing the payroll (optional)

    Returns:
        Dictionary with calculation results:
        {
            "empleado_id": str,
            "salario_bruto": Decimal,
            "salario_neto": Decimal,
            "total_deducciones": Decimal,
            "success": bool,
            "error": str (if failed)
        }
    """
    try:
        log.info("Processing payroll for employee %s", empleado_id)

        # Convert date strings to date objects
        periodo_inicio_date = date.fromisoformat(periodo_inicio)
        periodo_fin_date = date.fromisoformat(periodo_fin)
        fecha_calculo_date = date.fromisoformat(fecha_calculo) if fecha_calculo else None

        # Load employee and planilla
        empleado = db.session.get(Empleado, empleado_id)
        if not empleado:
            return {
                "empleado_id": empleado_id,
                "success": False,
                "error": "Employee not found",
            }

        planilla = db.session.get(Planilla, planilla_id)
        if not planilla:
            return {
                "empleado_id": empleado_id,
                "success": False,
                "error": ERROR_PLANILLA_NOT_FOUND,
            }

        # Initialize engine for single employee
        engine = NominaEngine(
            planilla=planilla,
            periodo_inicio=periodo_inicio_date,
            periodo_fin=periodo_fin_date,
            fecha_calculo=fecha_calculo_date,
            usuario=usuario,
        )

        # Process only this employee
        procesar_empleado = getattr(engine, "_procesar_empleado", None)
        if not callable(procesar_empleado):
            raise AttributeError("NominaEngine does not expose '_procesar_empleado'")
        # Dynamic method resolution; validated as callable above.
        # pylint: disable=not-callable
        emp_calculo = cast(Any, cast(Any, procesar_empleado)(empleado))

        # Commit to database
        db.session.commit()

        log.info("Employee %s processed successfully. Net: %s", empleado_id, emp_calculo.salario_neto)

        return {
            "empleado_id": empleado_id,
            "salario_bruto": emp_calculo.salario_bruto,
            "salario_neto": emp_calculo.salario_neto,
            "total_deducciones": emp_calculo.total_deducciones,
            "success": True,
        }

    except Exception as e:
        log.error("Error processing employee %s: %s", empleado_id, e)
        db.session.rollback()
        return {
            "empleado_id": empleado_id,
            "success": False,
            "error": str(e),
        }


def process_payroll_parallel(
    planilla_id: str,
    periodo_inicio: str,
    periodo_fin: str,
    fecha_calculo: str | None = None,
    usuario: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Process payroll for all employees in parallel (background task).

    NOTE: This function now uses the same defensive mechanism as process_large_payroll
    to ensure atomicity. If any employee processing fails, all changes are rolled back.

    For true parallel processing with multiple workers, use process_large_payroll which
    processes employees sequentially but provides better error handling and rollback.

    Args:
        planilla_id: Planilla ID (ULID string)
        periodo_inicio: Start date (ISO format: YYYY-MM-DD)
        periodo_fin: End date (ISO format: YYYY-MM-DD)
        fecha_calculo: Calculation date (ISO format, optional)
        usuario: Username executing the payroll (optional)

    Returns:
        Dictionary with processing results:
        {
            "success": bool,
            "total_empleados": int,
            "empleados_procesados": int,
            "empleados_con_error": int,
            "errores": list[str]
        }
    """
    from coati_payroll.enums import NominaEstado

    try:
        log.info("Starting parallel payroll processing for planilla %s", planilla_id)

        # Load planilla
        planilla = db.session.get(Planilla, planilla_id)
        if not planilla:
            return {
                "success": False,
                "error": "Planilla not found",
            }

        # Get all active employees
        planilla_empleados = cast(list[Any], planilla.planilla_empleados)
        empleados = [pe.empleado for pe in planilla_empleados if pe.activo and pe.empleado.activo]

        if not empleados:
            return {
                "success": False,
                "error": ERROR_NO_ACTIVE_EMPLOYEES,
            }

        # Create nomina record first
        nomina = NominaModel(
            planilla_id=planilla_id,
            periodo_inicio=date.fromisoformat(periodo_inicio),
            periodo_fin=date.fromisoformat(periodo_fin),
            generado_por=usuario,
            estado=NominaEstado.CALCULANDO,
            total_bruto=Decimal("0.00"),
            total_deducciones=Decimal("0.00"),
            total_neto=Decimal("0.00"),
            total_empleados=len(empleados),
            empleados_procesados=0,
            empleados_con_error=0,
            procesamiento_en_background=True,
        )
        db.session.add(nomina)
        db.session.commit()

        # Use process_large_payroll which has the defensive rollback mechanism
        # This ensures atomicity: if any employee fails, all changes are rolled back
        result = process_large_payroll(
            nomina_id=nomina.id,
            job_id=job_id or uuid4().hex,
            planilla_id=planilla_id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            fecha_calculo=fecha_calculo,
            usuario=usuario,
        )

        return result

    except Exception as e:
        log.error("Error processing parallel payroll: %s", e)
        return {
            "success": False,
            "error": str(e),
        }


def generate_audit_voucher(
    nomina_id: str,
    planilla_id: str,
    fecha_calculo: str | None = None,
    usuario: str | None = None,
) -> dict[str, bool | str]:
    """Generate audit accounting voucher in background."""
    try:
        log.info("Generating audit voucher for nomina %s", nomina_id)

        nomina = db.session.get(NominaModel, nomina_id)
        if not nomina:
            return {"success": False, "error": NOMINA_NOT_FOUND}

        planilla = db.session.get(Planilla, planilla_id)
        if not planilla:
            return {"success": False, "error": ERROR_PLANILLA_NOT_FOUND}

        fecha_calculo_date = date.fromisoformat(fecha_calculo) if fecha_calculo else None

        AccountingVoucherService(db.session).generate_audit_voucher(
            nomina,
            planilla,
            fecha_calculo=fecha_calculo_date,
            usuario=usuario,
        )
        db.session.commit()

        log.info("Audit voucher generated successfully for nomina %s", nomina_id)
        return {"success": True, "message": "Audit voucher generated"}
    except Exception as e:
        log.error("Error generating audit voucher for nomina %s: %s", nomina_id, e)
        db.session.rollback()
        return {"success": False, "error": str(e)}


def sync_exchange_rates(
    source_url: str | None = None,
    base_currency: str | None = None,
    primary_currencies: set[str] | None = None,
) -> dict[str, Any]:
    """Import the latest exchange rates from a configurable JSON provider.

    Providers compatible with the common ``{"base": "USD", "date": "...", "rates": {...}}``
    shape can be used. Only currencies already configured in the catalog are
    imported, preventing an external provider from silently changing master data.
    """
    base = (base_currency or os.getenv("EXCHANGE_RATES_BASE_CURRENCY") or "USD").upper()
    configured_primary = primary_currencies or {
        code.strip().upper()
        for code in os.getenv("EXCHANGE_RATES_PRIMARY_CURRENCIES", "EUR").split(",")
        if code.strip()
    }
    url = source_url or os.getenv("EXCHANGE_RATES_URL", "https://api.frankfurter.app/latest?from={base}").format(
        base=base
    )
    timeout = float(os.getenv("EXCHANGE_RATES_TIMEOUT_SECONDS", "15"))
    with urlopen(url, timeout=timeout) as response:  # noqa: S310 - URL is explicit configuration
        payload = json.load(response)
    rates = payload.get("rates") if isinstance(payload, dict) else None
    if not isinstance(rates, dict) or not rates:
        raise ValueError("Exchange-rate provider returned no rates")
    rate_date = date.fromisoformat(str(payload.get("date", date.today().isoformat())))
    origin = db.session.execute(db.select(Moneda).filter_by(codigo=base)).scalar_one_or_none()
    if origin is None:
        raise ValueError(f"Base currency '{base}' is not configured")

    synced = 0
    skipped = 0
    try:
        for code, raw_rate in rates.items():
            destination_code = str(code).upper()
            if destination_code not in configured_primary:
                skipped += 1
                continue
            destination = db.session.execute(db.select(Moneda).filter_by(codigo=destination_code)).scalar_one_or_none()
            if destination is None or destination.id == origin.id:
                skipped += 1
                continue
            try:
                rate = Decimal(str(raw_rate))
            except (ArithmeticError, ValueError, TypeError) as exc:
                raise ValueError(f"Invalid exchange rate for {code}") from exc
            if rate <= 0:
                raise ValueError(f"Exchange rate for {code} must be positive")
            record = db.session.execute(
                db.select(TipoCambio).filter_by(
                    moneda_origen_id=origin.id, moneda_destino_id=destination.id, fecha=rate_date
                )
            ).scalar_one_or_none()
            if record is None:
                record = TipoCambio(
                    moneda_origen_id=origin.id, moneda_destino_id=destination.id, fecha=rate_date, tasa=rate
                )
                db.session.add(record)
            else:
                record.tasa = rate
            synced += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"success": True, "base": base, "date": rate_date.isoformat(), "synced": synced, "skipped": skipped}


def generate_report(report_id: str, user: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a report through the queue for long-running integrations."""
    from coati_payroll.model import Report
    from coati_payroll.report_engine import ReportExecutionManager

    report = db.session.get(Report, report_id)
    if report is None:
        return {"success": False, "error": "Report not found"}
    try:
        results, total_count, execution = ReportExecutionManager(report, user).execute(parameters or {}, 1, 50000)
        return {"success": True, "execution_id": execution.id, "rows": len(results), "total_count": total_count}
    except Exception as exc:
        db.session.rollback()
        return {"success": False, "error": str(exc)}


def process_large_payroll(
    nomina_id: str,
    job_id: str | None,
    planilla_id: str,
    periodo_inicio: str,
    periodo_fin: str,
    fecha_calculo: str | None = None,
    usuario: str | None = None,
) -> dict[str, Any]:
    """Process large payroll in background with progress tracking.

    This task processes a payroll for all employees sequentially,
    updating progress in the database after each employee.
    Designed for large payrolls (>100 employees) to provide
    real-time feedback to users.

    Args:
        nomina_id: Nomina ID (ULID string)
        job_id: Job ID for idempotent retries (optional)
        planilla_id: Planilla ID (ULID string)
        periodo_inicio: Start date (ISO format: YYYY-MM-DD)
        periodo_fin: End date (ISO format: YYYY-MM-DD)
        fecha_calculo: Calculation date (ISO format, optional)
        usuario: Username executing the payroll (optional)

    Returns:
        Dictionary with processing results:
        {
            "success": bool,
            "total_empleados": int,
            "empleados_procesados": int,
            "empleados_con_error": int,
            "errores": list[str]
        }
    """
    from coati_payroll.enums import NominaEstado

    try:
        log.info("Starting background processing for nomina %s", nomina_id)

        # Convert date strings to date objects
        periodo_inicio_date = date.fromisoformat(periodo_inicio)
        periodo_fin_date = date.fromisoformat(periodo_fin)
        fecha_calculo_date = date.fromisoformat(fecha_calculo) if fecha_calculo else None

        # Load nomina and planilla
        nomina = db.session.get(NominaModel, nomina_id)
        if not nomina:
            log.error("Nomina %s not found", nomina_id)
            return {
                "success": False,
                "error": NOMINA_NOT_FOUND,
            }

        if nomina.estado != NominaEstado.CALCULANDO:
            return {
                "success": False,
                "error": f"Nomina is not in CALCULANDO state (current: {nomina.estado})",
            }

        job_id = _resolve_job_id(nomina, job_id)

        if not _acquire_nomina_job_lock(nomina_id, job_id):
            db.session.rollback()
            return {
                "success": False,
                "error": "Nomina is already being processed by another job.",
            }

        # Load planilla with eager loading of tipo_planilla and moneda
        planilla = db.session.execute(
            db.select(Planilla)
            .options(joinedload(cast(Any, Planilla.tipo_planilla)), joinedload(cast(Any, Planilla.moneda)))
            .filter_by(id=planilla_id)
        ).scalar_one_or_none()

        if not planilla:
            log.error("Planilla %s not found", planilla_id)
            nomina.estado = NominaEstado.ERROR
            nomina.errores_calculo = {"error": ERROR_PLANILLA_NOT_FOUND}
            _clear_nomina_job_lock(nomina_id)
            db.session.commit()
            return {
                "success": False,
                "error": ERROR_PLANILLA_NOT_FOUND,
            }

        # Get all active employees
        planilla_empleados = cast(list[Any], planilla.planilla_empleados)
        empleados = [pe.empleado for pe in planilla_empleados if pe.activo and pe.empleado.activo]

        if not empleados:
            log.warning("No active employees found for planilla %s", planilla_id)
            nomina.estado = NominaEstado.ERROR
            nomina.errores_calculo = {"error": ERROR_NO_ACTIVE_EMPLOYEES}
            _clear_nomina_job_lock(nomina_id)
            db.session.commit()
            return {
                "success": False,
                "error": ERROR_NO_ACTIVE_EMPLOYEES,
            }

        nomina.total_empleados = len(empleados)
        nomina.empleados_procesados = 0
        nomina.empleados_con_error = 0
        nomina.errores_calculo = {}
        nomina.log_procesamiento = []

        # Use the current payroll execution service. The old queue path called
        # NominaEngine._procesar_empleado, which was removed during the engine
        # refactor; using the service keeps validation, concepts and persistence
        # aligned with synchronous payroll execution.
        # These service helpers are intentionally reused here so queued and
        # synchronous payrolls share the same execution semantics.
        # pylint: disable=protected-access
        execution_service = PayrollExecutionService(db.session)
        snapshot = {
            "configuracion": nomina.configuracion_snapshot or None,
            "tipos_cambio": nomina.tipos_cambio_snapshot or None,
            "catalogos": nomina.catalogos_snapshot or {},
        }
        if not snapshot["catalogos"]:
            snapshot = execution_service.snapshot_service.capture_complete_snapshot(
                planilla, periodo_inicio_date, periodo_fin_date, fecha_calculo_date
            )
            nomina.configuracion_snapshot = snapshot["configuracion"]
            nomina.tipos_cambio_snapshot = snapshot["tipos_cambio"]
            nomina.catalogos_snapshot = snapshot["catalogos"]

        catalogos = cast(dict[str, Any], snapshot["catalogos"] or {})
        execution_service.concept_calculator.warnings = WarningCollector()
        execution_service.deduction_calculator.warnings = execution_service.concept_calculator.warnings
        execution_service.concept_calculator.deducciones_snapshot = {
            item["id"]: item for item in catalogos.get("deducciones", [])
        }
        execution_service.concept_calculator.strict_formulas = True
        execution_service.concept_calculator.reglas_snapshot = {
            concept["id"]: concept["regla_calculo"]
            for concept_type in ("percepciones", "deducciones", "prestaciones")
            for concept in catalogos.get(concept_type, [])
            if concept.get("regla_calculo")
        }
        execution_service.concept_calculator.configuracion_snapshot = snapshot["configuracion"]
        execution_service.perception_calculator.percepciones_snapshot = {
            item["id"]: item for item in catalogos.get("percepciones", [])
        }
        execution_service.benefit_calculator.prestaciones_snapshot = {
            item["id"]: item for item in catalogos.get("prestaciones", [])
        }
        warnings = execution_service.concept_calculator.warnings
        bootstrap_context = execution_service._resolve_company_bootstrap_context(
            planilla, periodo_inicio_date, warnings
        )
        loan_processor = LoanProcessor(
            nomina,
            fecha_calculo_date or periodo_fin_date,
            periodo_inicio_date,
            periodo_fin_date,
            calcular_interes=True,
            apply_side_effects=True,
        )
        vacation_snapshot = catalogos.get("vacaciones", {}).copy()
        vacation_snapshot["configuracion"] = snapshot["configuracion"]
        vacation_processor = VacationProcessor(
            planilla,
            periodo_inicio_date,
            periodo_fin_date,
            usuario,
            warnings,
            apply_side_effects=False,
            snapshot=vacation_snapshot,
            nomina_id=nomina.id,
        )
        planilla_empleado_by_id = {pe.empleado_id: pe for pe in planilla_empleados}

        # Initialize progress tracking in separate session
        tracking_session = _get_tracking_session()
        try:
            _upsert_nomina_progress(
                tracking_session,
                nomina_id,
                job_id,
                total_empleados=len(empleados),
                empleados_procesados=0,
                empleados_con_error=0,
                errores_calculo={},
                log_procesamiento=[],
                empleado_actual=None,
            )
        finally:
            _release_tracking_session(tracking_session)

        # CRITICAL: Use savepoints for safer transaction management
        # Process employees with periodic commits to reduce risk of losing all work
        # If ANY employee fails, rollback ALL changes to maintain consistency
        log_entries = []
        failed_employees: dict[str, dict[str, str]] = {}
        BATCH_SIZE = 10  # Commit progress every N employees to reduce risk
        processed_count = 0
        error_count = 0

        try:
            # Create initial savepoint for the entire operation
            savepoint = db.session.begin_nested()

            # Process each employee
            for idx, empleado in enumerate(empleados, 1):
                empleado_nombre = f"{empleado.primer_nombre} {empleado.primer_apellido}"

                try:
                    # Create savepoint for this employee
                    emp_savepoint = db.session.begin_nested()

                    # Update current employee being processed (for progress tracking)
                    log_entries.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "empleado": empleado_nombre,
                            "status": "processing",
                            "message": f"Calculando empleado {idx}/{len(empleados)}: {empleado_nombre}",
                        }
                    )
                    tracking_session = _get_tracking_session()
                    try:
                        _upsert_nomina_progress(
                            tracking_session,
                            nomina_id,
                            job_id,
                            empleados_procesados=idx - 1,
                            empleados_con_error=error_count,
                            log_procesamiento=log_entries,
                            empleado_actual=empleado_nombre,
                        )
                    finally:
                        _release_tracking_session(tracking_session)

                    emp_calculo = execution_service._process_employee(
                        empleado,
                        planilla,
                        periodo_inicio_date,
                        periodo_fin_date,
                        fecha_calculo_date or periodo_fin_date,
                        loan_processor,
                        snapshot["configuracion"],
                        snapshot["tipos_cambio"],
                        bootstrap_context,
                        warnings,
                        nomina_id=nomina.id,
                        planilla_empleado=planilla_empleado_by_id.get(empleado.id),
                    )
                    execution_service._apply_employee_side_effects(
                        emp_calculo,
                        nomina,
                        planilla,
                        periodo_inicio_date,
                        periodo_fin_date,
                        vacation_processor,
                        execution_service.concept_calculator.deducciones_snapshot,
                        bootstrap_context,
                    )
                    # pylint: enable=protected-access

                    # Commit this employee's savepoint (employee processed successfully)
                    emp_savepoint.commit()

                    # Update progress with success
                    log_entries.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "empleado": empleado_nombre,
                            "status": "success",
                            "message": f"✓ Completado: {empleado_nombre} - Neto: {emp_calculo.salario_neto}",
                        }
                    )

                    log.info("Employee %s processed successfully (%s/%s)", empleado.id, idx, nomina.total_empleados)

                except Exception as e:
                    # Rollback this employee's savepoint (undoes only this employee)
                    emp_savepoint.rollback()

                    error_msg = str(e)
                    error_count += 1
                    failed_employees[str(empleado.id)] = {
                        "empleado": empleado_nombre,
                        "error": error_msg,
                    }
                    log.error("Error processing employee %s: %s", empleado.id, error_msg)
                    log_entries.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "empleado": empleado_nombre,
                            "status": "error",
                            "message": f"✗ Error en empleado {empleado_nombre}: {error_msg}",
                        }
                    )
                    tracking_session = _get_tracking_session()
                    try:
                        _upsert_nomina_progress(
                            tracking_session,
                            nomina_id,
                            job_id,
                            empleados_procesados=idx - 1,
                            empleados_con_error=error_count,
                            log_procesamiento=log_entries,
                            empleado_actual=None,
                        )
                    finally:
                        _release_tracking_session(tracking_session)

                finally:
                    processed_count = idx

                if idx % BATCH_SIZE == 0 or idx == len(empleados):
                    tracking_session = _get_tracking_session()
                    try:
                        _upsert_nomina_progress(
                            tracking_session,
                            nomina_id,
                            job_id,
                            empleados_procesados=processed_count,
                            empleados_con_error=error_count,
                            log_procesamiento=log_entries,
                            empleado_actual=None,
                        )
                        log.info("Progress committed: %s/%s employees processed", idx, len(empleados))
                    finally:
                        _release_tracking_session(tracking_session)

            # All employees processed successfully - commit the main savepoint
            savepoint.commit()

            # Calculate totals
            nomina_empleados = cast(list[Any], nomina.nomina_empleados)
            total_bruto = sum(ne.salario_bruto for ne in nomina_empleados)
            total_deducciones = sum(ne.total_deducciones for ne in nomina_empleados)
            total_neto = sum(ne.salario_neto for ne in nomina_empleados)

            nomina.total_bruto = total_bruto
            nomina.total_deducciones = total_deducciones
            nomina.total_neto = total_neto
            if error_count > 0:
                nomina.estado = NominaEstado.GENERADO_CON_ERRORES
                nomina.errores_calculo = {"empleados_fallidos": failed_employees}
            else:
                nomina.estado = NominaEstado.GENERADO
                nomina.errores_calculo = {}
            nomina.empleados_procesados = processed_count
            nomina.empleados_con_error = error_count
            nomina.log_procesamiento = log_entries
            nomina.empleado_actual = None  # Clear current employee
            _clear_nomina_job_lock(nomina_id)

            # Final commit (this is smaller now since we've been committing progress)
            db.session.commit()
            tracking_session = _get_tracking_session()
            try:
                _upsert_nomina_progress(
                    tracking_session,
                    nomina_id,
                    job_id,
                    empleados_procesados=processed_count,
                    empleados_con_error=error_count,
                    errores_calculo=nomina.errores_calculo,
                    log_procesamiento=log_entries,
                    empleado_actual=None,
                )
            finally:
                _release_tracking_session(tracking_session)

            if error_count > 0:
                log.warning("Payroll completed with %s employee errors for nomina %s", error_count, nomina_id)
            else:
                log.info("All employees processed successfully for nomina %s", nomina_id)

        except Exception as e:
            # CRITICAL: Rollback all changes if any employee fails
            error_msg = str(e)
            error_type = type(e).__name__

            # Determine if error is recoverable (can be retried)
            # Recoverable: database connection issues, temporary network problems, etc.
            # Non-recoverable: validation errors, data integrity issues, etc.
            is_recoverable = _is_recoverable_error(e)

            log.error(
                "Critical error during payroll processing: %s (Type: %s, Recoverable: %s)",
                error_msg,
                error_type,
                is_recoverable,
            )

            # Rollback the main savepoint (undoes all employee processing)
            try:
                savepoint.rollback()
            except Exception:
                # If savepoint doesn't exist or already rolled back, do full rollback
                db.session.rollback()

            # Rollback any remaining data that might have been created
            _rollback_nomina_data(nomina_id)

            # Mark nomina as ERROR with detailed error information
            nomina.errores_calculo = {
                "critical_error": error_msg,
                "error_type": error_type,
                "is_recoverable": is_recoverable,
                "empleados_procesados_antes_fallo": processed_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            nomina.estado = NominaEstado.GENERADO_CON_ERRORES
            _clear_nomina_job_lock(nomina_id)
            nomina.empleados_procesados = processed_count
            nomina.empleados_con_error = error_count
            log_entries.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "empleado": "SISTEMA",
                    "status": "error",
                    "message": (
                        f"✗ ERROR CRÍTICO: La nómina falló. Todos los cambios fueron revertidos. "
                        f"Error: {error_msg} "
                        f"(Puede reintentarse: {'Sí' if is_recoverable else 'No'})"
                    ),
                }
            )
            nomina.empleado_actual = None
            db.session.commit()
            tracking_session = _get_tracking_session()
            try:
                _upsert_nomina_progress(
                    tracking_session,
                    nomina_id,
                    job_id,
                    empleados_procesados=processed_count,
                    empleados_con_error=nomina.empleados_con_error,
                    errores_calculo=nomina.errores_calculo,
                    log_procesamiento=log_entries,
                    empleado_actual=None,
                )
            finally:
                _release_tracking_session(tracking_session)

            # Re-raise to signal failure (queue system will handle retries if configured)
            raise

        log.info(
            "Background processing completed for nomina %s. Processed: %s/%s, Errors: %s",
            nomina_id,
            nomina.empleados_procesados,
            nomina.total_empleados,
            nomina.empleados_con_error,
        )

        return {
            "success": True,
            "total_empleados": nomina.total_empleados,
            "empleados_procesados": nomina.empleados_procesados,
            "empleados_con_error": nomina.empleados_con_error,
            "errores": nomina.errores_calculo or {},
        }

    except Exception as e:
        log.error("Critical error in background payroll processing: %s", e)
        try:
            nomina = db.session.get(NominaModel, nomina_id)
            if nomina:
                nomina.estado = NominaEstado.GENERADO_CON_ERRORES
                nomina.errores_calculo = {"critical_error": str(e)}
                _clear_nomina_job_lock(nomina_id)
                db.session.commit()
        except Exception:
            pass
        return {
            "success": False,
            "error": str(e),
        }


# Get retry configuration from environment
_retry_config = _get_payroll_retry_config()

# Register tasks with the queue driver
calculate_employee_payroll_task = queue.register_task(
    calculate_employee_payroll,
    name="calculate_employee_payroll",
    max_retries=int(os.getenv("PAYROLL_EMPLOYEE_MAX_RETRIES", "3")),
    min_backoff=int(os.getenv("PAYROLL_EMPLOYEE_MIN_BACKOFF_MS", "15000")),  # 15 seconds
    max_backoff=int(os.getenv("PAYROLL_EMPLOYEE_MAX_BACKOFF_MS", "3600000")),  # 1 hour
)

process_payroll_parallel_task = queue.register_task(
    process_payroll_parallel,
    name="process_payroll_parallel",
    max_retries=int(os.getenv("PAYROLL_PARALLEL_MAX_RETRIES", "2")),
    min_backoff=int(os.getenv("PAYROLL_PARALLEL_MIN_BACKOFF_MS", "30000")),  # 30 seconds
    max_backoff=int(os.getenv("PAYROLL_PARALLEL_MAX_BACKOFF_MS", "7200000")),  # 2 hours
)

process_large_payroll_task = queue.register_task(
    process_large_payroll,
    name="process_large_payroll",
    max_retries=_retry_config["max_retries"],
    min_backoff=_retry_config["min_backoff_ms"],
    max_backoff=_retry_config["max_backoff_ms"],
)

retry_failed_nomina_task = queue.register_task(
    retry_failed_nomina,
    name="retry_failed_nomina",
    max_retries=1,  # Manual retry, no automatic retries needed
    min_backoff=0,
    max_backoff=0,
)

generate_audit_voucher_task = queue.register_task(
    generate_audit_voucher,
    name="generate_audit_voucher",
    max_retries=2,
    min_backoff=60000,  # 1 minute
    max_backoff=3600000,  # 1 hour
)

sync_exchange_rates_task = queue.register_task(
    sync_exchange_rates,
    name="sync_exchange_rates",
    max_retries=3,
    min_backoff=60000,
    max_backoff=3600000,
)

generate_report_task = queue.register_task(
    generate_report,
    name="generate_report",
    max_retries=2,
    min_backoff=60000,
    max_backoff=3600000,
)
