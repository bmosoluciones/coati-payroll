# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Payroll execution service - main business logic orchestrator."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from coati_payroll.enums import NominaEstado
from coati_payroll.formula_engine import FormulaEngineError
from coati_payroll.log import log
from coati_payroll.model import Empleado, Nomina, Planilla, db
from sqlalchemy.exc import IntegrityError, OperationalError

from ..calculators.benefit_calculator import BenefitCalculator
from ..calculators.concept_calculator import ConceptCalculator
from ..calculators.deduction_calculator import DeductionCalculator
from ..calculators.exchange_rate_calculator import ExchangeRateCalculator
from ..calculators.perception_calculator import PerceptionCalculator
from ..calculators.salary_calculator import SalaryCalculator
from ..domain.employee_calculation import EmpleadoCalculo
from ..processors.accounting_processor import AccountingProcessor
from ..processors.accumulation_processor import AccumulationProcessor
from ..processors.loan_processor import LoanProcessor
from ..processors.novelty_processor import NoveltyProcessor
from ..processors.vacation_processor import VacationProcessor
from ..repositories.acumulado_repository import AcumuladoRepository
from ..repositories.config_repository import ConfigRepository
from ..repositories.exchange_rate_repository import ExchangeRateRepository
from ..repositories.novelty_repository import NoveltyRepository
from ..repositories.planilla_repository import PlanillaRepository
from ..results.warning_collector import WarningCollector
from ..services.accounting_voucher_service import AccountingVoucherService
from ..services.employee_processing_service import EmployeeProcessingService
from ..services.snapshot_service import SnapshotService
from ..utils.rounding import round_money
from ..validators import NominaEngineError, ValidationError
from ..validators.employee_validator import EmployeeValidator
from ..validators.planilla_validator import PlanillaValidator
from ..validators.period_validator import PeriodValidator


class PayrollExecutionService:
    """Main service for executing payroll runs."""

    def __init__(self, session):
        self.session = session

        # Initialize repositories
        self.planilla_repo = PlanillaRepository(session)
        self.config_repo = ConfigRepository(session)
        self.exchange_rate_repo = ExchangeRateRepository(session)
        self.novelty_repo = NoveltyRepository(session)
        self.acumulado_repo = AcumuladoRepository(session)

        # Initialize validators
        self.planilla_validator = PlanillaValidator(self.planilla_repo)
        self.period_validator = PeriodValidator()
        self.employee_validator = EmployeeValidator()

        # Initialize calculators (warnings list will be set later)
        self.salary_calculator = SalaryCalculator(self.config_repo)
        self.exchange_rate_calculator = ExchangeRateCalculator(self.exchange_rate_repo)
        self.concept_calculator = ConceptCalculator(self.config_repo, [])  # warnings set in execute_payroll
        self.perception_calculator = PerceptionCalculator(self.concept_calculator)
        self.deduction_calculator = DeductionCalculator(self.concept_calculator, [])  # warnings set in execute_payroll
        self.benefit_calculator = BenefitCalculator(self.concept_calculator)

        # Initialize processors
        self.novelty_processor = NoveltyProcessor(self.novelty_repo)
        self.accumulation_processor = AccumulationProcessor(self.acumulado_repo)
        self.accounting_processor = AccountingProcessor()

        # Initialize services
        self.employee_processing_service = EmployeeProcessingService(self.config_repo, self.acumulado_repo)
        self.snapshot_service = SnapshotService(session)
        self.accounting_voucher_service = AccountingVoucherService(session)

    def execute_payroll(
        self,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        fecha_calculo: date,
        usuario: str | None,
        excluded_nomina_id: str | None = None,
    ) -> tuple[Nomina | None, list[EmpleadoCalculo], list[str], list[str]]:
        """Execute a complete payroll run."""
        errors: list[str] = []
        warnings = WarningCollector()

        # Update warnings list for calculators (they need shared reference)
        self.concept_calculator.warnings = warnings
        self.deduction_calculator.warnings = warnings

        # Serialize concurrent executions for the same planilla. Locking the
        # planilla row (SELECT ... FOR UPDATE) makes the overlap/duplicate
        # checks and the Nomina INSERT an atomic critical section, preventing
        # two concurrent runs from both passing validation and creating
        # duplicate payrolls for the same period with duplicated side effects.
        self.session.execute(db.select(Planilla.id).where(Planilla.id == planilla.id).with_for_update())

        # Validate planilla
        from ..domain.payroll_context import PayrollContext

        context = PayrollContext(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            fecha_calculo=fecha_calculo,
            usuario=usuario,
            excluded_nomina_id=excluded_nomina_id,
        )

        validation_result = self.planilla_validator.validate(context)
        if not validation_result.is_valid:
            errors.extend(validation_result.errors)
            return None, [], errors, warnings.to_list()

        # Validate period boundaries
        period_result = self.period_validator.validate(context)
        if not period_result.is_valid:
            errors.extend(period_result.errors)
            return None, [], errors, warnings.to_list()

        # Capture configuration snapshots for recalculation consistency
        snapshot = self.snapshot_service.capture_complete_snapshot(
            planilla, periodo_inicio, periodo_fin, fecha_calculo, excluded_nomina_id=excluded_nomina_id
        )
        deducciones_snapshot = {
            deduccion["id"]: deduccion for deduccion in snapshot.get("catalogos", {}).get("deducciones", [])
        }
        self.concept_calculator.deducciones_snapshot = deducciones_snapshot
        self.concept_calculator.configuracion_snapshot = snapshot.get("configuracion") or None
        bootstrap_context = self._resolve_company_bootstrap_context(planilla, periodo_inicio, warnings)

        # Prevent duplicate execution for the same period
        # Exclude ERROR state to allow retries
        duplicate_query = db.select(Nomina).filter(
            Nomina.planilla_id == planilla.id,
            Nomina.periodo_inicio == periodo_inicio,
            Nomina.periodo_fin == periodo_fin,
            Nomina.estado.in_(
                [
                    NominaEstado.CALCULANDO,
                    NominaEstado.GENERADO,
                    NominaEstado.APROBADO,
                    NominaEstado.APLICADO,
                    NominaEstado.PAGADO,
                ]
            ),
        )
        if excluded_nomina_id:
            duplicate_query = duplicate_query.filter(Nomina.id != excluded_nomina_id)

        existing = self.planilla_repo.session.execute(duplicate_query).scalars().first()
        if existing:
            errors.append("Ya existe una nómina para este período.")
            return None, [], errors, warnings.to_list()

        # Create the Nomina record
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            generado_por=usuario,
            estado=NominaEstado.CALCULANDO,
            total_bruto=Decimal("0.00"),
            total_deducciones=Decimal("0.00"),
            total_neto=Decimal("0.00"),
            fecha_calculo_original=fecha_calculo,
            configuracion_snapshot=snapshot["configuracion"],
            tipos_cambio_snapshot=snapshot["tipos_cambio"],
            catalogos_snapshot=snapshot["catalogos"],
        )
        db.session.add(nomina)
        db.session.flush()

        # During recalculation, novelties remain bound to the source payroll
        # until the recalculation service relinks them after a successful run.
        # Use that source ID as the read context so bound novelties are not
        # omitted while the new payroll is being calculated.
        novelty_context_id = excluded_nomina_id or nomina.id

        # Initialize processors that need nomina
        loan_processor = LoanProcessor(
            nomina, fecha_calculo, periodo_inicio, periodo_fin, calcular_interes=True, apply_side_effects=False
        )

        # Update warnings reference for calculators (shared list)
        self.concept_calculator.warnings = warnings
        self.deduction_calculator.warnings = warnings

        # Process each employee
        empleados_calculo: list[EmpleadoCalculo] = []
        planilla_empleados = cast(list[Any], planilla.planilla_empleados)

        for planilla_empleado in planilla_empleados:
            if not planilla_empleado.activo:
                continue

            # Respect the employee's assignment window. An association that has
            # not started yet (fecha_inicio > periodo_fin) or already ended
            # (fecha_fin < periodo_inicio) must not be processed even if the
            # association is still marked active.
            if planilla_empleado.fecha_inicio and planilla_empleado.fecha_inicio > periodo_fin:
                warnings.append(
                    f"Empleado {planilla_empleado.empleado.primer_nombre} "
                    f"{planilla_empleado.empleado.primer_apellido} fuera de la ventana de asignación "
                    f"(inicio {planilla_empleado.fecha_inicio} posterior al fin del período {periodo_fin}); "
                    "será omitido."
                )
                continue
            if planilla_empleado.fecha_fin and planilla_empleado.fecha_fin < periodo_inicio:
                warnings.append(
                    f"Empleado {planilla_empleado.empleado.primer_nombre} "
                    f"{planilla_empleado.empleado.primer_apellido} fuera de la ventana de asignación "
                    f"(fin {planilla_empleado.fecha_fin} anterior al inicio del período {periodo_inicio}); "
                    "será omitido."
                )
                continue

            empleado = planilla_empleado.empleado
            if not empleado.activo:
                warnings.append(
                    f"Empleado {empleado.primer_nombre} {empleado.primer_apellido} no está activo y será omitido."
                )
                continue

            try:
                emp_calculo = self._process_employee(
                    empleado,
                    planilla,
                    periodo_inicio,
                    periodo_fin,
                    fecha_calculo,
                    loan_processor,
                    snapshot.get("configuracion"),
                    snapshot.get("tipos_cambio"),
                    bootstrap_context,
                    warnings,
                    nomina_id=novelty_context_id,
                    planilla_empleado=planilla_empleado,
                )
                empleados_calculo.append(emp_calculo)
            except (NominaEngineError, FormulaEngineError) as e:
                # Capture all payroll engine and formula errors
                errors.append(f"Error procesando empleado {empleado.primer_nombre} {empleado.primer_apellido}: {e!s}")
            except (IntegrityError, OperationalError) as e:
                # Database integrity/connection errors — these are serious and should not be swallowed
                log.error(
                    "Error de BD procesando empleado %s %s: %s",
                    empleado.primer_nombre,
                    empleado.primer_apellido,
                    str(e),
                    exc_info=True,
                )
                raise
            except (ValueError, TypeError, AttributeError) as e:
                # Capture programming/data errors that should not crash the entire run
                log.error(
                    "Error de datos procesando empleado %s %s: %s",
                    empleado.primer_nombre,
                    empleado.primer_apellido,
                    str(e),
                    exc_info=True,
                )
                errors.append(
                    f"Error inesperado procesando empleado {empleado.primer_nombre} {empleado.primer_apellido}: "
                    f"{type(e).__name__}: {e!s}"
                )

        # Calculate totals
        self._calculate_totals(nomina, empleados_calculo)

        if not errors:
            vacation_snapshot = snapshot.get("catalogos", {}).get("vacaciones", {}).copy()
            vacation_snapshot["configuracion"] = snapshot.get("configuracion")
            vacation_processor = VacationProcessor(
                planilla,
                periodo_inicio,
                periodo_fin,
                usuario,
                warnings,
                apply_side_effects=False,
                snapshot=vacation_snapshot,
                nomina_id=nomina.id,
            )

            for emp_calculo in empleados_calculo:
                self._apply_employee_side_effects(
                    emp_calculo,
                    nomina,
                    planilla,
                    periodo_inicio,
                    periodo_fin,
                    vacation_processor,
                    deducciones_snapshot,
                    bootstrap_context,
                )

            loan_processor.apply_pending_effects()

            # Update planilla last execution
            planilla.ultima_ejecucion = datetime.now(UTC)

            # Generate accounting voucher
            try:
                self.accounting_voucher_service.generate_audit_voucher(nomina, planilla, fecha_calculo, usuario)
                db.session.flush()
            except Exception as e:
                # Don't fail the payroll if voucher generation fails
                error_message = (
                    "Advertencia al generar comprobante contable de auditoría: " f"{type(e).__name__}: {e!s}"
                )
                warnings.append(error_message)
                log.error(
                    "Fallo al generar comprobante contable de auditoría",
                    extra={
                        "nomina_id": nomina.id,
                        "planilla_id": planilla.id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                nomina.errores_calculo = nomina.errores_calculo or {}
                nomina.errores_calculo["audit_voucher_error"] = error_message
                try:
                    from coati_payroll.queue import get_queue_driver

                    queue = get_queue_driver()
                    task_id = queue.enqueue(
                        "generate_audit_voucher",
                        nomina_id=nomina.id,
                        planilla_id=planilla.id,
                        fecha_calculo=(fecha_calculo.isoformat() if fecha_calculo else None),
                        usuario=usuario or nomina.generado_por,
                    )
                    nomina.errores_calculo["audit_voucher_retry_task_id"] = task_id
                except Exception as enqueue_error:
                    log.error(
                        "No se pudo encolar el reintento del comprobante contable de auditoría",
                        extra={
                            "nomina_id": nomina.id,
                            "planilla_id": planilla.id,
                            "error": str(enqueue_error),
                            "error_type": type(enqueue_error).__name__,
                        },
                    )

        if errors:
            nomina.estado = NominaEstado.ERROR
            # Save error logs for audit trail before any rollback
            self._save_log_entries(nomina, errors, warnings.to_list(), empleados_calculo)
            # Flush to persist the ERROR nomina and logs, but don't commit yet
            # Engine will decide whether to commit (for audit trail) or rollback
            db.session.flush()
        else:
            nomina.estado = NominaEstado.GENERADO
            # Save errors and warnings to log_procesamiento for transparency
            self._save_log_entries(nomina, errors, warnings.to_list(), empleados_calculo)

        return nomina, empleados_calculo, errors, warnings.to_list()

    def _save_log_entries(
        self,
        nomina: Nomina,
        errors: list[str],
        warnings: list[str],
        empleados_calculo: list[EmpleadoCalculo],
    ) -> None:
        """Save errors, warnings and processing info to nomina.log_procesamiento.

        This ensures all processing issues are visible in the nomina log,
        not just as flash messages.
        """
        log_entries: list[dict[str, Any]] = []
        timestamp = datetime.now(UTC).isoformat()

        # Log successful employee processing
        for emp_calculo in empleados_calculo:
            empleado = emp_calculo.empleado
            resumen_vacaciones = getattr(emp_calculo, "vacaciones_resumen", None)
            resumen_texto = ""
            if resumen_vacaciones and resumen_vacaciones.get("policy_codigo"):
                resumen_texto = (
                    " Vacaciones: accrued {accrued}, used {used}, "
                    "balance_before {balance_before}, balance_after {balance_after}, policy {policy}."
                ).format(
                    accrued=resumen_vacaciones.get("accrued"),
                    used=resumen_vacaciones.get("used"),
                    balance_before=resumen_vacaciones.get("balance_before"),
                    balance_after=resumen_vacaciones.get("balance_after"),
                    policy=resumen_vacaciones.get("policy_codigo"),
                )
            log_entries.append(
                {
                    "timestamp": timestamp,
                    "empleado": f"{empleado.primer_nombre} {empleado.primer_apellido}",
                    "status": "success",
                    "message": f"Procesado correctamente. Salario neto: {emp_calculo.salario_neto}.{resumen_texto}",
                }
            )

        # Log errors
        for error in errors:
            log_entries.append(
                {
                    "timestamp": timestamp,
                    "empleado": "SISTEMA",
                    "status": "error",
                    "message": error,
                }
            )

        # Log warnings
        for warning in warnings:
            log_entries.append(
                {
                    "timestamp": timestamp,
                    "empleado": "SISTEMA",
                    "status": "warning",
                    "message": warning,
                }
            )

        nomina.log_procesamiento = log_entries

    def _process_employee(
        self,
        empleado: Empleado,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        fecha_calculo: date,
        loan_processor: LoanProcessor,
        configuracion_snapshot: dict[str, Any] | None,
        tipos_cambio_snapshot: dict[str, Any] | None,
        bootstrap_context: dict[str, Any],
        warnings: WarningCollector,
        nomina_id: str | None = None,
        planilla_empleado=None,
    ) -> EmpleadoCalculo:
        """Process a single employee's payroll."""
        # Validate employee
        employee_validation = self.employee_validator.validate_employee(
            empleado, planilla.empresa_id, periodo_inicio, periodo_fin, planilla_empleado=planilla_empleado
        )
        if not employee_validation.is_valid:
            # Include specific validation errors (errors is already a list of strings)
            error_messages = employee_validation.errors
            raise ValidationError(f"Empleado {empleado.codigo_empleado}: {'; '.join(error_messages)}")

        emp_calculo = EmpleadoCalculo(empleado, planilla)

        # Get exchange rate
        emp_calculo.tipo_cambio = self.exchange_rate_calculator.get_exchange_rate(
            empleado, planilla, fecha_calculo, tipos_cambio_snapshot
        )

        salario_mensual_origen = emp_calculo.salario_base

        salario_periodo_origen = self.salary_calculator.calculate_period_salary(
            salario_mensual_origen,
            planilla,
            periodo_inicio,
            periodo_fin,
            fecha_calculo,
            fecha_alta=empleado.fecha_alta,
            fecha_baja=empleado.fecha_baja,
            configuracion_snapshot=configuracion_snapshot,
            rounding=False,
        )

        # Load employee novelties (including absence summaries)
        novelties, ausencia_resumen, codigos_descuento = self.novelty_processor.load_novelties_with_absences(
            empleado, periodo_inicio, periodo_fin, nomina_id=nomina_id
        )

        descuento_inasistencia = self._calculate_absence_discount(
            salario_mensual_origen,
            ausencia_resumen,
            planilla.empresa_id,
            configuracion_snapshot,
        )
        salario_periodo_origen_neto = max(Decimal("0.00"), salario_periodo_origen - descuento_inasistencia)
        if emp_calculo.tipo_cambio != Decimal("1.00"):
            descuento_inasistencia_planilla = round_money(descuento_inasistencia * emp_calculo.tipo_cambio)
            salario_mensual = round_money(salario_mensual_origen * emp_calculo.tipo_cambio)
            salario_periodo = round_money(salario_periodo_origen * emp_calculo.tipo_cambio)
            salario_periodo_neto = round_money(salario_periodo_origen_neto * emp_calculo.tipo_cambio)
        else:
            # Always quantize to ensure consistent decimal precision
            descuento_inasistencia_planilla = round_money(descuento_inasistencia)
            salario_mensual = round_money(salario_mensual_origen)
            salario_periodo = round_money(salario_periodo_origen)
            salario_periodo_neto = round_money(salario_periodo_origen_neto)

        emp_calculo.salario_base = salario_periodo
        emp_calculo.salario_mensual = salario_mensual
        emp_calculo.salario_neto_inasistencia = salario_periodo_neto

        # Persist novelties and absence summaries
        emp_calculo.novedades = novelties
        emp_calculo.inasistencia_dias = ausencia_resumen["dias"]
        emp_calculo.inasistencia_horas = ausencia_resumen["horas"]
        emp_calculo.inasistencia_descuento = descuento_inasistencia_planilla
        emp_calculo.inasistencia_codigos_descuento = codigos_descuento

        # Build calculation variables
        emp_calculo.variables_calculo = self.employee_processing_service.build_calculation_variables(
            emp_calculo,
            planilla,
            periodo_inicio,
            periodo_fin,
            fecha_calculo,
            configuracion_snapshot,
            bootstrap_context=bootstrap_context,
            warnings=warnings,
        )

        # Process perceptions
        percepciones = self.perception_calculator.calculate(emp_calculo, planilla, fecha_calculo)
        emp_calculo.percepciones = percepciones
        emp_calculo.total_percepciones = sum(p.monto for p in percepciones)

        # Calculate gross salary
        emp_calculo.salario_bruto = emp_calculo.salario_neto_inasistencia + emp_calculo.total_percepciones
        emp_calculo.salario_gravable = emp_calculo.salario_neto_inasistencia + sum(
            p.monto for p in emp_calculo.percepciones if p.gravable
        )
        emp_calculo.variables_calculo.update(
            {
                "salario_gravable": emp_calculo.salario_gravable,
                "salario_gravable_periodo": emp_calculo.salario_gravable,
            }
        )

        # Process deductions
        deducciones = self.deduction_calculator.calculate(emp_calculo, planilla, fecha_calculo)
        emp_calculo.deducciones = deducciones
        emp_calculo.total_deducciones = sum(d.monto for d in deducciones)

        # Apply automatic loan/advance deductions
        saldo_disponible = emp_calculo.salario_bruto - emp_calculo.total_deducciones

        loan_deductions = loan_processor.process_loans(
            empleado.id, saldo_disponible, planilla.aplicar_prestamos_automatico, planilla.prioridad_prestamos
        )
        emp_calculo.deducciones.extend(loan_deductions)
        emp_calculo.total_deducciones += sum(d.monto for d in loan_deductions)
        saldo_disponible -= sum(d.monto for d in loan_deductions)

        advance_deductions = loan_processor.process_advances(
            empleado.id, saldo_disponible, planilla.aplicar_adelantos_automatico, planilla.prioridad_adelantos
        )
        emp_calculo.deducciones.extend(advance_deductions)
        emp_calculo.total_deducciones += sum(d.monto for d in advance_deductions)

        # Calculate net salary
        emp_calculo.salario_neto = emp_calculo.salario_bruto - emp_calculo.total_deducciones

        # Ensure net salary is not negative
        # Note: warnings list is shared via loan_processor context, so warnings will be added there
        if emp_calculo.salario_neto < 0:
            raise NominaEngineError(
                f"Neto negativo para empleado {empleado.codigo_empleado}: {emp_calculo.salario_neto}"
            )

        # Process employer benefits
        prestaciones = self.benefit_calculator.calculate(emp_calculo, planilla, fecha_calculo)
        emp_calculo.prestaciones = prestaciones
        emp_calculo.total_prestaciones = sum(p.monto for p in prestaciones)

        return emp_calculo

    def _calculate_absence_discount(
        self,
        salario_mensual: Decimal,
        ausencia_resumen: dict[str, Decimal],
        empresa_id: str,
        configuracion_snapshot: dict[str, Any] | None,
    ) -> Decimal:
        dias = ausencia_resumen.get("dias", Decimal("0.00"))
        horas = ausencia_resumen.get("horas", Decimal("0.00"))
        if dias <= 0 and horas <= 0:
            return Decimal("0.00")

        config = self._resolve_config(empresa_id, configuracion_snapshot)
        dias_base = Decimal(str(config.dias_mes_nomina))
        horas_dia = Decimal(str(config.horas_jornada_diaria))
        if dias_base <= 0 or horas_dia <= 0:
            raise ValidationError(
                "Configuración inválida para cálculo de inasistencias: dias_mes_nomina y horas_jornada_diaria."
            )

        salario_diario = salario_mensual / dias_base
        salario_hora = salario_diario / horas_dia
        return (salario_diario * dias) + (salario_hora * horas)

    def _resolve_config(self, empresa_id: str, configuracion_snapshot: dict[str, Any] | None) -> Any:
        if configuracion_snapshot:
            return SimpleNamespace(**configuracion_snapshot)

        return self.config_repo.get_for_empresa(empresa_id)

    def _apply_employee_side_effects(
        self,
        emp_calculo: EmpleadoCalculo,
        nomina: Nomina,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        vacation_processor: VacationProcessor,
        deducciones_snapshot: dict[str, dict],
        bootstrap_context: dict[str, Any],
    ) -> None:
        """Apply persistence side effects for a successful payroll run."""
        nomina_empleado = self.accounting_processor.create_nomina_empleado(emp_calculo, nomina)
        self.accumulation_processor.update_accumulations(
            emp_calculo,
            planilla,
            periodo_inicio,
            periodo_fin,
            deducciones_snapshot,
            empresa_primer_mes_nomina=bootstrap_context.get("primer_mes_nomina"),
            empresa_primer_anio_nomina=bootstrap_context.get("primer_anio_nomina"),
        )
        emp_calculo.vacaciones_resumen = vacation_processor.process_vacations(
            emp_calculo.empleado, emp_calculo, nomina_empleado
        )

    def _resolve_company_bootstrap_context(
        self,
        planilla: Planilla,
        periodo_inicio: date,
        warnings: WarningCollector,
    ) -> dict[str, Any]:
        """Build company bootstrap context and emit one warning if config is missing."""
        empresa = planilla.empresa
        primer_mes = getattr(empresa, "primer_mes_nomina", None)
        primer_anio = getattr(empresa, "primer_anio_nomina", None)
        configurada = primer_mes is not None and primer_anio is not None
        es_periodo_inicial = False

        if configurada and primer_mes is not None and primer_anio is not None:
            primer_mes_int = int(primer_mes)
            primer_anio_int = int(primer_anio)
            es_periodo_inicial = periodo_inicio.month == primer_mes_int and periodo_inicio.year == primer_anio_int
        else:
            empresa_nombre = planilla.empresa.razon_social if planilla.empresa else planilla.empresa_id or "N/A"
            warnings.append(
                "Empresa %s sin configuración de Primer Mes/Año de Nómina; "
                "se continúa el cálculo sin bootstrap de acumulados." % empresa_nombre
            )

        return {
            "configured": configurada,
            "is_initial_period": es_periodo_inicial,
            "primer_mes_nomina": primer_mes,
            "primer_anio_nomina": primer_anio,
        }

    def _calculate_totals(self, nomina: Nomina, empleados_calculo: list[EmpleadoCalculo]) -> None:
        """Calculate grand totals for the nomina."""
        total_bruto = Decimal("0.00")
        total_deducciones = Decimal("0.00")
        total_neto = Decimal("0.00")

        for emp_calculo in empleados_calculo:
            total_bruto += emp_calculo.salario_bruto
            total_deducciones += emp_calculo.total_deducciones
            total_neto += emp_calculo.salario_neto

        nomina.total_bruto = round_money(total_bruto)
        nomina.total_deducciones = round_money(total_deducciones)
        nomina.total_neto = round_money(total_neto)
