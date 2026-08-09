#!/usr/bin/env python
"""Run a real Redis/Dramatiq/PostgreSQL payroll validation with 1,000 employees.

The script intentionally starts a separate Dramatiq worker process and validates
the completed payroll through a second SQLAlchemy session. It is an operational
smoke/load test, not a unit test and must be run against an isolated database.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MONTHLY_SALARY = Decimal("1000.00")
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 1, 31)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _start_worker() -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.setdefault("PAYROLL_MAX_RETRIES", "0")
    return subprocess.Popen(
        [sys.executable, "-m", "dramatiq", "coati_payroll.queue.tasks", "--processes", "1", "--threads", "4"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def _stop_worker(worker: subprocess.Popen[str]) -> str:
    if worker.poll() is None:
        os.killpg(worker.pid, signal.SIGTERM)
    try:
        output, _ = worker.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(worker.pid, signal.SIGKILL)
        output, _ = worker.communicate()
    return output


def main() -> int:
    required = ("DATABASE_URL", "REDIS_URL")
    missing = [name for name in required if not os.environ.get(name)]
    _assert(not missing, f"Missing required environment variables: {', '.join(missing)}")
    employee_count = int(os.environ.get("PAYROLL_EMPLOYEE_COUNT", "1000"))
    expect_background = os.environ.get("EXPECT_BACKGROUND", "1").strip().lower() not in {"0", "false", "no", "off"}
    expected_queue_backend = os.environ.get("EXPECTED_QUEUE_BACKEND", "dramatiq").strip().lower()

    from coati_payroll import create_app, ensure_database_initialized
    from coati_payroll.config import configuration
    from coati_payroll.enums import NominaEstado
    from coati_payroll.model import (
        Empresa,
        Empleado,
        ConfiguracionCalculos,
        Moneda,
        Nomina,
        NominaEmpleado,
        NominaProgress,
        Planilla,
        PlanillaEmpleado,
        TipoPlanilla,
        db,
    )
    from coati_payroll.queue import get_queue_driver
    from coati_payroll.vistas.planilla.services.nomina_service import NominaService

    app = create_app(dict(configuration))
    app.config.update(
        BACKGROUND_PAYROLL_THRESHOLD=100,
        QUEUE_ENABLED=True,
        TESTING=False,
    )
    worker: subprocess.Popen[str] | None = None
    try:
        with app.app_context():
            ensure_database_initialized(app)
            db.drop_all()
            db.create_all()

            queue = get_queue_driver()
            queue_backend = queue.__class__.__name__.replace("QueueDriver", "").lower()
            _assert(queue_backend == expected_queue_backend, f"Expected {expected_queue_backend}, got {queue!r}")
            if expected_queue_backend == "dramatiq":
                _assert(queue.is_available(), "Dramatiq driver is not available")

            empresa = Empresa(
                codigo="LOAD1000",
                razon_social="Coati Payroll Load Test S.A.",
                ruc="LOADTEST-1000",
                activo=True,
                primer_mes_nomina=1,
                primer_anio_nomina=2026,
            )
            moneda = Moneda(codigo="USD", nombre="US Dollar", simbolo="$", activo=True)
            tipo = TipoPlanilla(
                codigo="MONTHLY-LOAD1000",
                descripcion="Monthly background load validation",
                periodicidad="monthly",
                dias=30,
                periodos_por_anio=12,
                mes_inicio_fiscal=1,
                dia_inicio_fiscal=1,
                activo=True,
            )
            db.session.add_all([empresa, moneda, tipo])
            db.session.flush()

            planilla = Planilla(
                nombre="Payroll Load Test 1000",
                descripcion="Isolated reproducible background payroll test",
                tipo_planilla=tipo,
                moneda=moneda,
                empresa=empresa,
                periodo_fiscal_inicio=date(2026, 1, 1),
                periodo_fiscal_fin=date(2026, 12, 31),
                mes_inicio_fiscal=1,
                activo=True,
                aplicar_prestamos_automatico=False,
                aplicar_adelantos_automatico=False,
            )
            db.session.add(planilla)
            db.session.flush()
            db.session.add(
                ConfiguracionCalculos(
                    empresa_id=empresa.id,
                    dias_mes_nomina=30,
                    dias_anio_nomina=365,
                    horas_jornada_diaria=Decimal("8.00"),
                    dias_mes_vacaciones=30,
                    dias_anio_vacaciones=365,
                    dias_anio_financiero=365,
                    meses_anio_financiero=12,
                    dias_quincena=15,
                    dias_mes_antiguedad=30,
                    dias_anio_antiguedad=365,
                    activo=True,
                )
            )
            db.session.flush()

            employees = [
                Empleado(
                    codigo_empleado=f"LOAD-{index:04d}",
                    primer_nombre="Employee",
                    primer_apellido=f"{index:04d}",
                    identificacion_personal=f"LOAD-ID-{index:04d}",
                    fecha_alta=date(2025, 1, 1),
                    salario_base=MONTHLY_SALARY,
                    moneda=moneda,
                    empresa=empresa,
                    activo=True,
                )
                for index in range(1, employee_count + 1)
            ]
            db.session.add_all(employees)
            db.session.flush()
            db.session.add_all(
                [PlanillaEmpleado(planilla=planilla, empleado=employee, activo=True) for employee in employees]
            )
            db.session.commit()

            if os.environ.get("START_WORKER", "1").strip().lower() not in {"0", "false", "no", "off"}:
                worker = _start_worker()
                time.sleep(2)
                _assert(worker.poll() is None, "Dramatiq worker exited before dispatch")

            started = time.monotonic()
            nomina, errors, warnings = NominaService.ejecutar_nomina(
                planilla=planilla,
                periodo_inicio=PERIOD_START,
                periodo_fin=PERIOD_END,
                fecha_calculo=PERIOD_END,
                usuario="load-test",
            )
            dispatch_seconds = time.monotonic() - started
            _assert(nomina is not None, f"Nomina was not created: {errors}")
            _assert(not errors, f"Dispatch returned errors: {errors}")
            _assert(
                nomina.procesamiento_en_background is expect_background,
                f"Background mode mismatch: expected {expect_background}, got {nomina.procesamiento_en_background}",
            )
            if expect_background:
                _assert(nomina.estado == NominaEstado.CALCULANDO, f"Unexpected initial state: {nomina.estado}")
            nomina_id = nomina.id
            db.session.expire_all()

            deadline = time.monotonic() + 180
            observed_states: list[str] = []
            while time.monotonic() < deadline:
                current = db.session.get(Nomina, nomina_id)
                _assert(current is not None, "Nomina disappeared during processing")
                state = str(current.estado)
                if not observed_states or observed_states[-1] != state:
                    observed_states.append(state)
                if current.estado in {NominaEstado.GENERADO, NominaEstado.GENERADO_CON_ERRORES, NominaEstado.ERROR}:
                    break
                db.session.expire_all()
                time.sleep(1)

            current = db.session.get(Nomina, nomina_id)
            progress = db.session.execute(
                db.select(NominaProgress).filter(NominaProgress.nomina_id == nomina_id)
            ).scalar_one_or_none()
            row_count = db.session.scalar(
                db.select(func.count(NominaEmpleado.id)).filter(NominaEmpleado.nomina_id == nomina_id)
            )
            gross_sum = db.session.scalar(
                db.select(func.sum(NominaEmpleado.salario_bruto)).filter(NominaEmpleado.nomina_id == nomina_id)
            )
            deductions_sum = db.session.scalar(
                db.select(func.sum(NominaEmpleado.total_deducciones)).filter(NominaEmpleado.nomina_id == nomina_id)
            )
            net_sum = db.session.scalar(
                db.select(func.sum(NominaEmpleado.salario_neto)).filter(NominaEmpleado.nomina_id == nomina_id)
            )

            expected_total = MONTHLY_SALARY * employee_count
            _assert(current is not None and current.estado == NominaEstado.GENERADO, f"Final state: {current}")
            _assert(current.empleados_procesados == employee_count, "Nomina processed count mismatch")
            _assert(current.empleados_con_error == 0, "Nomina contains employee errors")
            if expect_background:
                _assert(progress is not None, "Background progress row was not persisted")
                _assert(progress.total_empleados == employee_count, "Progress total mismatch")
                _assert(progress.empleados_procesados == employee_count, "Progress processed count mismatch")
                _assert(progress.empleados_con_error == 0, "Progress contains employee errors")
            else:
                _assert(progress is None, "Synchronous payroll unexpectedly created progress row")
            _assert(row_count == employee_count, f"Expected {employee_count} detail rows, got {row_count}")
            _assert(Decimal(str(gross_sum)) == expected_total, f"Gross oracle mismatch: {gross_sum}")
            _assert(Decimal(str(deductions_sum or 0)) == Decimal("0.00"), f"Unexpected deductions: {deductions_sum}")
            _assert(Decimal(str(net_sum)) == expected_total, f"Net oracle mismatch: {net_sum}")
            _assert(current.total_bruto == expected_total, "Nomina gross total mismatch")
            _assert(current.total_deducciones == Decimal("0.00"), "Nomina deductions total mismatch")
            _assert(current.total_neto == expected_total, "Nomina net total mismatch")

            print(
                "BACKGROUND_PAYROLL_VALIDATION=PASS "
                f"nomina_id={nomina_id} employees={row_count} state={current.estado} "
                f"gross={current.total_bruto} deductions={current.total_deducciones} net={current.total_neto} "
                f"dispatch_seconds={dispatch_seconds:.3f} mode={'background' if expect_background else 'synchronous'} "
                f"states={','.join(observed_states)} "
                f"warnings={len(warnings)}"
            )
            return 0
    finally:
        if worker is not None:
            output = _stop_worker(worker)
            if output:
                print("--- DRAMATIQ WORKER OUTPUT ---", file=sys.stderr)
                print(output[-12000:], file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
