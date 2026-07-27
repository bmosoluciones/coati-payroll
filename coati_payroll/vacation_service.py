# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Vacation service for integration with payroll engine.

This module provides the service layer for vacation accrual and usage
during payroll execution.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.enums import AccrualFrequency, AccrualMethod, VacationLedgerType
from coati_payroll.log import log
from coati_payroll.nomina_engine.validators import NominaEngineError, ValidationError

if TYPE_CHECKING:
    from coati_payroll.model import (
        ConfiguracionCalculos,
        Empleado,
        NominaEmpleado,
        Planilla,
        VacationAccount,
        VacationPolicy,
    )


class VacationService:
    """Service for vacation accrual and usage during payroll execution."""

    ACCRUAL_PRECISION = Decimal("0.01")
    ROUNDING_RULES = {
        "up": ROUND_UP,
        "down": ROUND_DOWN,
        "nearest": ROUND_HALF_UP,
        None: ROUND_HALF_UP,
    }
    SUPPORTED_ACCRUAL_BASIS = {"days_worked", "hours_worked"}
    SUPPORTED_ROUNDING_RULES = {None, "up", "down", "nearest"}

    def __init__(
        self,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        snapshot: dict | None = None,
        apply_side_effects: bool = True,
        nomina_id: str | None = None,
    ):
        """Initialize vacation service.

        Args:
            planilla: The payroll being executed
            periodo_inicio: Start date of payroll period
            periodo_fin: End date of payroll period
            snapshot: Optional snapshot data for reproducible processing
            apply_side_effects: Whether to write ledger entries and update balances
            nomina_id: Optional Nomina ID to filter explicitly bound novelties
        """
        self.planilla = planilla
        self.periodo_inicio = periodo_inicio
        self.periodo_fin = periodo_fin
        self.snapshot = snapshot
        self.apply_side_effects = apply_side_effects
        self.nomina_id = nomina_id
        self._temp_accrued = {}
        if self.periodo_inicio and self.periodo_fin and self.periodo_inicio > self.periodo_fin:
            raise ValidationError(f"Período inválido: inicio {self.periodo_inicio} posterior a fin {self.periodo_fin}.")

    def _quantize_amount(self, amount: Decimal) -> Decimal:
        """Normalize amounts to the configured precision."""
        return amount.quantize(self.ACCRUAL_PRECISION, rounding=ROUND_HALF_UP)

    def _config_from_snapshot(self, snapshot_config: dict) -> ConfiguracionCalculos:
        """Build a ConfiguracionCalculos-like object from snapshot data."""
        return cast(
            "ConfiguracionCalculos",
            SimpleNamespace(
                empresa_id=snapshot_config.get("empresa_id"),
                pais_id=snapshot_config.get("pais_id"),
                dias_mes_nomina=snapshot_config.get("dias_mes_nomina"),
                dias_anio_nomina=snapshot_config.get("dias_anio_nomina"),
                horas_jornada_diaria=Decimal(str(snapshot_config.get("horas_jornada_diaria"))),
                dias_mes_vacaciones=snapshot_config.get("dias_mes_vacaciones"),
                dias_anio_vacaciones=snapshot_config.get("dias_anio_vacaciones"),
                considerar_bisiesto_vacaciones=snapshot_config.get("considerar_bisiesto_vacaciones"),
                dias_anio_financiero=snapshot_config.get("dias_anio_financiero"),
                meses_anio_financiero=snapshot_config.get("meses_anio_financiero"),
                dias_quincena=snapshot_config.get("dias_quincena"),
                dias_mes_antiguedad=snapshot_config.get("dias_mes_antiguedad"),
                dias_anio_antiguedad=snapshot_config.get("dias_anio_antiguedad"),
                activo=snapshot_config.get("activo", True),
            ),
        )

    def _validar_configuracion(self, config: ConfiguracionCalculos) -> None:
        if config.dias_mes_vacaciones <= 0:
            raise ValidationError("Configuración inválida: dias_mes_vacaciones debe ser mayor que cero.")
        if config.dias_anio_vacaciones <= 0:
            raise ValidationError("Configuración inválida: dias_anio_vacaciones debe ser mayor que cero.")
        if config.dias_quincena <= 0:
            raise ValidationError("Configuración inválida: dias_quincena debe ser mayor que cero.")
        if config.meses_anio_financiero <= 0:
            raise ValidationError("Configuración inválida: meses_anio_financiero debe ser mayor que cero.")
        if config.dias_anio_antiguedad <= 0:
            raise ValidationError("Configuración inválida: dias_anio_antiguedad debe ser mayor que cero.")

    def _obtener_config_calculos(self) -> ConfiguracionCalculos:
        """Get calculation configuration for the current planilla.

        Returns configuration specific to the planilla's company, or global defaults.
        Always returns a valid configuration object with defaults if none exists.

        Returns:
            ConfiguracionCalculos instance with appropriate values
        """
        from coati_payroll.model import ConfiguracionCalculos, db

        if self.snapshot and self.snapshot.get("configuracion"):
            snapshot_config = self._config_from_snapshot(self.snapshot["configuracion"])
            self._validar_configuracion(snapshot_config)
            return snapshot_config

        empresa_id = self.planilla.empresa_id if self.planilla else None

        # Try to find company-specific configuration
        if empresa_id:
            config = cast(
                ConfiguracionCalculos | None,
                (
                    db.session.execute(
                        db.select(ConfiguracionCalculos).filter(
                            ConfiguracionCalculos.empresa_id == empresa_id,
                            ConfiguracionCalculos.activo.is_(True),
                        )
                    )
                    .scalars()
                    .first()
                ),
            )
            if config:
                self._validar_configuracion(config)
                return config

        # Try to find global default (no empresa_id, no pais_id)
        config = cast(
            ConfiguracionCalculos | None,
            (
                db.session.execute(
                    db.select(ConfiguracionCalculos).filter(
                        ConfiguracionCalculos.empresa_id.is_(None),
                        ConfiguracionCalculos.pais_id.is_(None),
                        ConfiguracionCalculos.activo.is_(True),
                    )
                )
                .scalars()
                .first()
            ),
        )
        if config:
            self._validar_configuracion(config)
            return config

        # If no configuration exists, return a default instance (not saved to DB)
        # This ensures backward compatibility with existing tests
        return ConfiguracionCalculos(
            empresa_id=None,
            pais_id=None,
            dias_mes_nomina=30,
            dias_anio_nomina=365,
            horas_jornada_diaria=Decimal("8.00"),
            dias_mes_vacaciones=30,
            dias_anio_vacaciones=365,
            considerar_bisiesto_vacaciones=True,
            dias_anio_financiero=365,
            meses_anio_financiero=12,
            dias_quincena=15,
            dias_mes_antiguedad=30,
            dias_anio_antiguedad=365,
            activo=True,
        )

    def _obtener_balance(self, account: VacationAccount) -> Decimal:
        from coati_payroll.model import VacationLedger, db

        balance = db.session.execute(
            db.select(db.func.coalesce(db.func.sum(VacationLedger.quantity), 0)).filter(
                VacationLedger.account_id == account.id
            )
        ).scalar_one()
        return self._quantize_amount(Decimal(str(balance)))

    def _recalcular_balance(self, account: VacationAccount) -> Decimal:
        balance_decimal = self._obtener_balance(account)
        account.current_balance = balance_decimal
        return balance_decimal

    def _resolve_bound_policy_account(self, empleado, filtros_base):
        """Resolve vacation account via planilla-bound policy."""
        from coati_payroll.model import VacationAccount, VacationPolicy, db

        bound_accounts = (
            db.session.execute(
                db.select(VacationAccount)
                .join(VacationAccount.policy)
                .filter(*filtros_base)
                .filter(VacationPolicy.id == self.planilla.vacation_policy_id)
            )
            .scalars()
            .all()
        )
        if len(bound_accounts) > 1:
            raise ValidationError(
                f"Más de una cuenta de vacaciones encontrada para empleado {empleado.codigo_empleado} "
                f"y política vinculada de planilla."
            )
        if len(bound_accounts) == 1:
            return bound_accounts[0], "planilla_bound"

        if not self.apply_side_effects:
            return None, None

        bound_policy = (
            db.session.execute(
                db.select(VacationPolicy).filter(
                    VacationPolicy.id == self.planilla.vacation_policy_id,
                    VacationPolicy.activo.is_(True),
                )
            )
            .scalars()
            .first()
        )
        if not bound_policy:
            return None, None

        if bound_policy.planilla_id and bound_policy.planilla_id != self.planilla.id:
            raise ValidationError(f"Policy {bound_policy.codigo} does not belong to planilla {self.planilla.id}.")
        if bound_policy.empresa_id and self.planilla.empresa_id and bound_policy.empresa_id != self.planilla.empresa_id:
            raise ValidationError(f"Policy {bound_policy.codigo} belongs to another empresa.")

        existing_account = (
            db.session.execute(
                db.select(VacationAccount).filter(
                    VacationAccount.empleado_id == empleado.id,
                    VacationAccount.policy_id == bound_policy.id,
                )
            )
            .scalars()
            .first()
        )
        if existing_account:
            if not existing_account.activo:
                existing_account.activo = True
            return existing_account, "planilla_bound_reactivated"

        account = VacationAccount(
            empleado_id=empleado.id,
            policy_id=bound_policy.id,
            current_balance=Decimal("0.0000"),
            activo=True,
        )
        db.session.add(account)
        db.session.flush()
        log.info(
            "Vacation account auto-created for employee %s with policy %s (planilla=%s).",
            empleado.codigo_empleado,
            bound_policy.codigo,
            self.planilla.id,
        )
        return account, "planilla_bound_auto_created"

    def _resolve_scoped_account(self, empleado, filtros_base):
        """Resolve vacation account via scope-based fallback."""
        from coati_payroll.model import VacationAccount, VacationPolicy, db

        scopes = [
            (
                "planilla",
                VacationPolicy.planilla_id == self.planilla.id,
                db.or_(VacationPolicy.empresa_id.is_(None), VacationPolicy.empresa_id == self.planilla.empresa_id),
            ),
            ("empresa", VacationPolicy.planilla_id.is_(None), VacationPolicy.empresa_id == self.planilla.empresa_id),
            (
                "global",
                VacationPolicy.planilla_id.is_(None),
                VacationPolicy.empresa_id.is_(None),
            ),
        ]

        for scope_name, *scope_filters in scopes:
            accounts = (
                db.session.execute(
                    db.select(VacationAccount).join(VacationAccount.policy).filter(*filtros_base).filter(*scope_filters)
                )
                .scalars()
                .all()
            )
            if len(accounts) > 1:
                raise ValidationError(
                    f"Más de una cuenta/política de vacaciones encontrada para empleado {empleado.codigo_empleado} "
                    f"en scope {scope_name}."
                )
            if len(accounts) == 1:
                account = accounts[0]
                log.info(
                    "Vacation policy/account resolved: policy_id=%s policy_codigo=%s account_id=%s "
                    "scope=%s planilla_id=%s empresa_id=%s",
                    account.policy_id,
                    account.policy.codigo,
                    account.id,
                    scope_name,
                    self.planilla.id,
                    self.planilla.empresa_id,
                )
                return account, scope_name

        return None, None

    def _resolver_cuenta_vacaciones(self, empleado: Empleado) -> tuple[VacationAccount | None, str | None]:
        from coati_payroll.model import VacationAccount, VacationPolicy

        if not self.planilla:
            return None, None

        if empleado.empresa_id and self.planilla.empresa_id and empleado.empresa_id != self.planilla.empresa_id:
            raise ValidationError(f"Empleado {empleado.codigo_empleado} pertenece a empresa distinta a la planilla.")

        filtros_base = [
            VacationAccount.empleado_id == empleado.id,
            VacationAccount.activo.is_(True),
            VacationPolicy.activo.is_(True),
        ]

        if self.planilla.vacation_policy_id:
            account, scope = self._resolve_bound_policy_account(empleado, filtros_base)
            return account, scope

        return self._resolve_scoped_account(empleado, filtros_base)

    def _validar_empleado_en_planilla(self, empleado: Empleado) -> None:
        from coati_payroll.model import PlanillaEmpleado, db

        if not self.planilla:
            raise ValidationError("No hay planilla activa para validar el empleado.")

        existe = db.session.execute(
            db.select(db.func.count())
            .select_from(PlanillaEmpleado)
            .filter(
                PlanillaEmpleado.planilla_id == self.planilla.id,
                PlanillaEmpleado.empleado_id == empleado.id,
                PlanillaEmpleado.activo.is_(True),
            )
        ).scalar_one()
        if existe <= 0:
            raise ValidationError(
                f"Empleado {empleado.codigo_empleado} no está asignado a la planilla {self.planilla.id}."
            )

    def _validar_policy(self, policy: VacationPolicy) -> None:
        if policy.accrual_rate is not None and Decimal(str(policy.accrual_rate)) < 0:
            raise ValidationError(f"Policy {policy.codigo}: accrual_rate no puede ser negativo.")
        if policy.max_balance is not None and Decimal(str(policy.max_balance)) < 0:
            raise ValidationError(f"Policy {policy.codigo}: max_balance no puede ser negativo.")
        if not policy.partial_units_allowed and policy.rounding_rule not in self.SUPPORTED_ROUNDING_RULES:
            raise ValidationError(f"Policy {policy.codigo}: rounding_rule inválido ({policy.rounding_rule}).")
        if policy.accrual_method == AccrualMethod.PROPORTIONAL:
            if policy.accrual_basis not in self.SUPPORTED_ACCRUAL_BASIS:
                raise ValidationError(f"Policy {policy.codigo}: accrual_basis inválido ({policy.accrual_basis}).")

    def _empleado_tiene_vacaciones_en_periodo(self, empleado: Empleado) -> bool:
        from sqlalchemy import and_, or_

        from coati_payroll.model import NominaNovedad, db

        stmt = (
            db.select(db.func.count())
            .select_from(NominaNovedad)
            .filter(
                NominaNovedad.empleado_id == empleado.id,
                NominaNovedad.es_descanso_vacaciones.is_(True),
            )
        )

        if self.nomina_id:
            stmt = stmt.filter(
                or_(
                    NominaNovedad.nomina_id == self.nomina_id,
                    and_(
                        NominaNovedad.nomina_id.is_(None),
                        NominaNovedad.fecha_novedad >= self.periodo_inicio,
                        NominaNovedad.fecha_novedad <= self.periodo_fin,
                    ),
                )
            )
        else:
            stmt = stmt.filter(
                NominaNovedad.nomina_id.is_(None),
                NominaNovedad.fecha_novedad >= self.periodo_inicio,
                NominaNovedad.fecha_novedad <= self.periodo_fin,
            )

        existe = db.session.execute(stmt).scalar_one()
        return existe > 0

    def obtener_resumen_vacaciones(self, empleado: Empleado) -> dict[str, Decimal | str] | None:
        self._validar_empleado_en_planilla(empleado)
        account, _scope = self._resolver_cuenta_vacaciones(empleado)
        if not account:
            return None
        balance = self._obtener_balance(account)
        return {
            "policy_codigo": account.policy.codigo,
            "balance": balance,
        }

    def acumular_vacaciones_empleado(
        self, empleado: Empleado, nomina_empleado: NominaEmpleado, usuario: str | None = None
    ) -> Decimal:
        """Accumulate vacation for an employee during payroll execution.

        This method is called during payroll processing to automatically
        accrue vacation time based on the employee's vacation policy.

        Args:
            empleado: The employee to accrue vacation for
            nomina_empleado: The payroll record for this employee
            usuario: Username executing the payroll

        Returns:
            The amount of vacation accrued
        """
        from coati_payroll.model import VacationAccount, VacationLedger, db

        self._validar_empleado_en_planilla(empleado)

        account, scope = self._resolver_cuenta_vacaciones(empleado)

        if not account:
            log.debug(
                "No active vacation account found for employee %s in payroll %s",
                empleado.codigo_empleado,
                self.planilla.nombre,
            )
            return Decimal("0.00")

        policy = cast("VacationPolicy", account.policy)
        self._validar_policy(policy)
        if not self._eligible_for_accrual(empleado, nomina_empleado, account, policy):
            return Decimal("0.00")

        # Calculate accrual amount based on policy
        accrual_amount = self._calcular_acumulacion(empleado, account, nomina_empleado)

        if accrual_amount <= 0:
            return Decimal("0.00")

        if self.apply_side_effects:
            account = db.session.execute(
                db.select(VacationAccount).filter(VacationAccount.id == account.id).with_for_update()
            ).scalar_one()
            balance_before = self._recalcular_balance(account)
        else:
            balance_before = self._obtener_balance(account)

        accrual_amount = self._normalize_accrual_amount(
            accrual_amount, balance_before, policy, empleado.codigo_empleado
        )
        if accrual_amount <= 0:
            return Decimal("0.00")

        if not self.apply_side_effects:
            self._temp_accrued[empleado.id] = accrual_amount
            log.trace(
                "Accrual calculated (no side effects) for employee %s policy=%s amount=%s balance_before=%s",
                empleado.codigo_empleado,
                policy.codigo,
                accrual_amount,
                balance_before,
            )
            return accrual_amount

        # Create ledger entry for accrual
        ledger_entry = VacationLedger(
            account_id=account.id,
            empleado_id=empleado.id,
            fecha=self.periodo_fin,
            entry_type=VacationLedgerType.ACCRUAL,
            quantity=accrual_amount,
            source="payroll",
            reference_id=nomina_empleado.id,
            reference_type="nomina_empleado",
            observaciones=f"Acumulación automática en nómina del {self.periodo_inicio} al {self.periodo_fin}",
            creado_por=usuario,
        )

        # Update account balance (derived from ledger)
        account.last_accrual_date = self.periodo_fin
        account.modificado_por = usuario

        db.session.add(ledger_entry)
        db.session.flush()

        balance_after = self._recalcular_balance(account)
        ledger_entry.balance_after = balance_after

        log.info(
            "Accrued %s %s vacation for employee %s policy=%s scope=%s balance_before=%s balance_after=%s",
            accrual_amount,
            policy.unit_type,
            empleado.codigo_empleado,
            policy.codigo,
            scope,
            balance_before,
            balance_after,
        )

        return accrual_amount

    def _eligible_for_accrual(self, empleado, nomina_empleado, account, policy) -> bool:
        """Check policy, leave, idempotency, and seniority prerequisites."""
        from coati_payroll.model import VacationLedger, db

        if policy.unit_type not in ("days", "hours"):
            raise ValidationError(f"Tipo de unidad inválida en policy {policy.codigo}: {policy.unit_type}.")
        if not policy.accrue_during_leave and self._empleado_tiene_vacaciones_en_periodo(empleado):
            log.info(
                "Skipping accrual for employee %s due to vacation leave in period (policy=%s).",
                empleado.codigo_empleado,
                policy.codigo,
            )
            return False
        existing_entry = (
            db.session.execute(
                db.select(VacationLedger).filter(
                    VacationLedger.entry_type == VacationLedgerType.ACCRUAL,
                    VacationLedger.source == "payroll",
                    VacationLedger.reference_type == "nomina_empleado",
                    VacationLedger.reference_id == nomina_empleado.id,
                    VacationLedger.account_id == account.id,
                )
            )
            .scalars()
            .first()
        )
        if existing_entry:
            log.info(
                "Accrual already applied for employee %s on nomina %s (ledger=%s).",
                empleado.codigo_empleado,
                nomina_empleado.id,
                existing_entry.id,
            )
            return False
        if empleado.fecha_alta:
            dias_servicio = (self.periodo_fin - empleado.fecha_alta).days
            if dias_servicio < policy.min_service_days:
                log.debug(
                    "Employee %s has not met minimum service days (%s < %s)",
                    empleado.codigo_empleado,
                    dias_servicio,
                    policy.min_service_days,
                )
                return False
        return True

    def _normalize_accrual_amount(self, amount, balance_before, policy, employee_code) -> Decimal:
        """Apply vacation balance caps and unit rounding."""
        if policy.max_balance:
            max_balance = self._quantize_amount(Decimal(str(policy.max_balance)))
            if balance_before + amount > max_balance:
                amount = max_balance - balance_before
                if amount <= 0:
                    log.debug(
                        "Employee %s has reached max vacation balance (%s >= %s)",
                        employee_code,
                        balance_before,
                        max_balance,
                    )
                    return Decimal("0.00")
        amount = self._quantize_amount(amount)
        if not policy.partial_units_allowed:
            rounding = self.ROUNDING_RULES.get(policy.rounding_rule, ROUND_HALF_UP)
            amount = amount.quantize(Decimal(1), rounding=rounding)
        return amount

    def _calcular_acumulacion(
        self, empleado: Empleado, account: VacationAccount, nomina_empleado: NominaEmpleado
    ) -> Decimal:
        """Calculate vacation accrual amount based on policy.

        Args:
            empleado: The employee
            account: The vacation account
            nomina_empleado: The payroll record

        Returns:
            Amount to accrue
        """
        policy = cast("VacationPolicy", account.policy)

        if policy.accrual_method == AccrualMethod.PERIODIC:
            return self._calcular_acumulacion_periodica(policy, empleado)
        if policy.accrual_method == AccrualMethod.PROPORTIONAL:
            return self._calcular_acumulacion_proporcional(empleado, policy, nomina_empleado)
        if policy.accrual_method == AccrualMethod.SENIORITY:
            return self._calcular_acumulacion_antiguedad(empleado, policy)
        log.warning("Unknown accrual method: %s", policy.accrual_method)
        return Decimal("0.00")

    def _calcular_acumulacion_periodica(self, policy: VacationPolicy, empleado: Empleado | None = None) -> Decimal:
        """Calculate periodic accrual (fixed amount per period).

        Args:
            policy: The vacation policy

        Returns:
            Accrual amount
        """
        # For periodic accrual, treat accrual_rate as the amount for a full frequency cycle
        # and prorate by worked days only when employee did not cover the full payroll period.
        dias_periodo = (self.periodo_fin - self.periodo_inicio).days + 1

        # Get configuration for vacation calculations
        config = self._obtener_config_calculos()

        dias_esperados = self._expected_period_days(policy, config)

        if dias_esperados <= 0:
            raise ValidationError("ConfiguraciÃ³n invÃ¡lida: dias esperados de acumulaciÃ³n debe ser mayor que cero.")

        # Backward-compatible path for direct method calls without employee context.
        if empleado is None:
            return self._periodic_accrual_without_employee(policy, dias_periodo, dias_esperados)

        # Determine worked days inside payroll period (respecting hire/termination dates).
        alta = empleado.fecha_alta
        baja = empleado.fecha_baja
        inicio_efectivo = self.periodo_inicio if not alta or alta <= self.periodo_inicio else alta
        fin_efectivo = self.periodo_fin if not baja or baja >= self.periodo_fin else baja
        if inicio_efectivo > fin_efectivo:
            return Decimal("0.00")

        dias_trabajados = (fin_efectivo - inicio_efectivo).days + 1
        if dias_trabajados <= 0:
            return Decimal("0.00")

        # If proration by period days is disabled and the employee covered the full period,
        # apply the full accrual rate for the cycle (e.g., monthly accrual in February).
        if (
            not policy.prorate_by_period_days
            and inicio_efectivo == self.periodo_inicio
            and fin_efectivo == self.periodo_fin
        ):
            return self._quantize_amount(policy.accrual_rate)

        # Prorate using policy frequency cycle (e.g., monthly policy on biweekly payroll => 15/30).
        dias_prorrata = min(dias_trabajados, dias_esperados)
        return self._quantize_amount(policy.accrual_rate * Decimal(dias_prorrata) / Decimal(dias_esperados))

    @staticmethod
    def _expected_period_days(policy: VacationPolicy, config) -> int:
        """Return configured days for a vacation accrual frequency."""
        configured_days = {
            AccrualFrequency.MONTHLY: config.dias_mes_vacaciones,
            AccrualFrequency.BIWEEKLY: config.dias_quincena,
            AccrualFrequency.ANNUAL: config.dias_anio_vacaciones,
        }
        return configured_days.get(policy.accrual_frequency, config.dias_mes_vacaciones)

    def _periodic_accrual_without_employee(
        self, policy: VacationPolicy, dias_periodo: int, dias_esperados: int
    ) -> Decimal:
        """Calculate periodic accrual when no employee dates are available."""
        if not policy.prorate_by_period_days or dias_periodo == dias_esperados:
            return self._quantize_amount(policy.accrual_rate)
        return self._quantize_amount(policy.accrual_rate * Decimal(dias_periodo) / Decimal(dias_esperados))

    def _calcular_acumulacion_proporcional(self, policy: VacationPolicy | Empleado, *legacy_context) -> Decimal:
        """Calculate proportional accrual (based on worked days/hours).

        Args:
            policy: The vacation policy. Legacy callers may still pass employee and
                payroll context before the policy.

        Returns:
            Accrual amount
        """
        # For proportional accrual, calculate based on actual worked days/hours
        # This requires tracking in the payroll record

        if not hasattr(policy, "accrual_basis"):
            policy = legacy_context[0]

        dias_periodo = (self.periodo_fin - self.periodo_inicio).days + 1

        if policy.accrual_basis == "days_worked":
            # Assume full days worked for now (could be enhanced to track absences)
            dias_trabajados = Decimal(dias_periodo)
            return self._quantize_amount(policy.accrual_rate * dias_trabajados)
        if policy.accrual_basis == "hours_worked":
            # Calculate based on hours (would need hours tracking in payroll)
            # For now, estimate based on standard hours from configuration
            config = self._obtener_config_calculos()
            horas_estandar = Decimal(str(config.horas_jornada_diaria)) * Decimal(dias_periodo)
            return self._quantize_amount(policy.accrual_rate * horas_estandar)
        raise ValidationError(f"Policy {policy.codigo}: accrual_basis inválido ({policy.accrual_basis}).")

    def _calcular_acumulacion_antiguedad(self, empleado: Empleado, policy: VacationPolicy) -> Decimal:
        """Calculate seniority-based accrual (tiered by years of service).

        Args:
            empleado: The employee
            policy: The vacation policy

        Returns:
            Accrual amount
        """
        if not empleado.fecha_alta or not policy.seniority_tiers:
            return Decimal("0.00")

        # Get configuration for seniority calculations
        config = self._obtener_config_calculos()

        # Calculate years of service
        # Use configured days per year, with leap year consideration if enabled
        dias_anio = Decimal(str(config.dias_anio_antiguedad))
        if config.considerar_bisiesto_vacaciones:
            # Use 365.25 to account for leap years
            dias_anio = Decimal("365.25")
        anos_servicio = Decimal((self.periodo_fin - empleado.fecha_alta).days) / dias_anio

        # Find applicable tier
        rate = Decimal("0.00")
        for tier in sorted(policy.seniority_tiers, key=lambda t: t.get("years", 0), reverse=True):
            if anos_servicio >= Decimal(str(tier.get("years", 0))):
                rate = Decimal(str(tier.get("rate", 0)))
                break

        if rate == 0:
            return Decimal("0.00")

        # For seniority, rate is typically annual, so prorate for period
        if policy.accrual_frequency == AccrualFrequency.ANNUAL:
            dias_periodo = (self.periodo_fin - self.periodo_inicio).days + 1
            dias_anio = Decimal(str(config.dias_anio_vacaciones))
            return self._quantize_amount(rate * Decimal(dias_periodo) / dias_anio)
        # If frequency is monthly/biweekly, divide rate accordingly
        meses_anio = Decimal(str(config.meses_anio_financiero))
        return self._quantize_amount(rate / meses_anio)

    def _build_vacation_usage_query(self, empleado):
        """Build query for vacation-related novedades."""
        from coati_payroll.model import NominaNovedad, db

        if self.snapshot and self.snapshot.get("vacation_novelty_ids"):
            vacation_novelty_ids = self.snapshot["vacation_novelty_ids"]
            stmt = db.select(NominaNovedad).filter(
                NominaNovedad.vacation_novelty_id.in_(vacation_novelty_ids),
                NominaNovedad.empleado_id == empleado.id,
            )
        else:
            from coati_payroll.model import PlanillaEmpleado

            stmt = (
                db.select(NominaNovedad)
                .join(PlanillaEmpleado, PlanillaEmpleado.empleado_id == NominaNovedad.empleado_id)
                .filter(
                    PlanillaEmpleado.planilla_id == self.planilla.id,
                    PlanillaEmpleado.activo.is_(True),
                    NominaNovedad.empleado_id == empleado.id,
                    NominaNovedad.es_descanso_vacaciones.is_(True),
                )
            )
            if self.nomina_id:
                from sqlalchemy import and_, or_

                stmt = stmt.filter(
                    or_(
                        NominaNovedad.nomina_id == self.nomina_id,
                        and_(
                            NominaNovedad.nomina_id.is_(None),
                            NominaNovedad.fecha_novedad >= self.periodo_inicio,
                            NominaNovedad.fecha_novedad <= self.periodo_fin,
                        ),
                    )
                )
            else:
                stmt = stmt.filter(
                    NominaNovedad.nomina_id.is_(None),
                    NominaNovedad.fecha_novedad >= self.periodo_inicio,
                    NominaNovedad.fecha_novedad <= self.periodo_fin,
                )
        if self.apply_side_effects:
            stmt = stmt.with_for_update()
        return db.session.execute(stmt).scalars().all()

    def _get_vacation_novelty(self, nomina_novedad):
        """Get vacation novelty with optional row locking."""
        from coati_payroll.enums import VacacionEstado
        from coati_payroll.model import VacationNovelty, db

        if not nomina_novedad.vacation_novelty_id:
            return None

        if self.apply_side_effects:
            vac_novelty = (
                db.session.execute(
                    db.select(VacationNovelty)
                    .filter(VacationNovelty.id == nomina_novedad.vacation_novelty_id)
                    .with_for_update()
                )
                .scalars()
                .first()
            )
        else:
            vac_novelty = db.session.get(VacationNovelty, nomina_novedad.vacation_novelty_id)

        if not vac_novelty or vac_novelty.estado not in (VacacionEstado.APROBADO, VacacionEstado.APLICADO):
            return None
        return vac_novelty

    def _validate_vacation_novelty(self, vac_novelty, empleado, policy):
        """Validate vacation novelty data."""
        if vac_novelty.start_date > vac_novelty.end_date:
            raise ValidationError(
                f"Vacaciones inválidas para empleado {empleado.codigo_empleado}: fecha inicio mayor a fin."
            )
        if vac_novelty.units <= 0:
            raise ValidationError(f"Vacaciones inválidas para empleado {empleado.codigo_empleado}: unidades <= 0.")
        if policy.unit_type not in ("days", "hours"):
            raise ValidationError(f"Tipo de unidad inválida en policy {policy.codigo}: {policy.unit_type}.")

    def _quantize_vacation_units(self, units, policy, empleado):
        """Quantize vacation units based on policy rounding rules."""
        units = self._quantize_amount(Decimal(str(units)))
        if not policy.partial_units_allowed:
            rounding = self.ROUNDING_RULES.get(policy.rounding_rule, ROUND_HALF_UP)
            units = units.quantize(Decimal(1), rounding=rounding)
            if units <= 0:
                raise ValidationError(
                    f"Vacaciones inválidas para empleado {empleado.codigo_empleado}: unidades redondeadas <= 0."
                )
        return units

    def _process_single_vacation_usage(self, vac_novelty, empleado, policy, usuario):
        """Process a single vacation usage entry."""
        from coati_payroll.enums import VacacionEstado
        from coati_payroll.model import VacationAccount, VacationLedger, db

        account = vac_novelty.account
        existing_usage = (
            db.session.execute(
                db.select(VacationLedger).filter(
                    VacationLedger.entry_type == VacationLedgerType.USAGE,
                    VacationLedger.source == "novelty",
                    VacationLedger.reference_type == "vacation_novelty",
                    VacationLedger.reference_id == vac_novelty.id,
                    VacationLedger.account_id == account.id,
                )
            )
            .scalars()
            .first()
        )
        if vac_novelty.ledger_entry_id or existing_usage:
            return Decimal("0.00")

        self._validate_vacation_novelty(vac_novelty, empleado, policy)
        units = self._quantize_vacation_units(vac_novelty.units, policy, empleado)

        if self.apply_side_effects:
            account = db.session.execute(
                db.select(VacationAccount).filter(VacationAccount.id == account.id).with_for_update()
            ).scalar_one()
            balance_before = self._recalcular_balance(account)
        else:
            balance_before = self._obtener_balance(account) + self._temp_accrued.get(empleado.id, Decimal("0.00"))

        if not policy.allow_negative and balance_before - units < 0:
            raise NominaEngineError(
                f"Saldo insuficiente para vacaciones en empleado {empleado.codigo_empleado} "
                f"(policy {policy.codigo})."
            )

        if not self.apply_side_effects:
            log.info(
                "Usage calculated (no side effects) for employee %s policy=%s units=%s balance_before=%s",
                empleado.codigo_empleado,
                policy.codigo,
                units,
                balance_before,
            )
            return units

        ledger_entry = VacationLedger(
            account_id=account.id,
            empleado_id=empleado.id,
            fecha=self.periodo_fin,
            entry_type=VacationLedgerType.USAGE,
            quantity=-abs(units),
            source="novelty",
            reference_id=vac_novelty.id,
            reference_type="vacation_novelty",
            observaciones=f"Vacaciones del {vac_novelty.start_date} al {vac_novelty.end_date}",
            creado_por=usuario,
        )
        account.modificado_por = usuario
        db.session.add(ledger_entry)
        db.session.flush()

        vac_novelty.ledger_entry_id = ledger_entry.id
        vac_novelty.estado = VacacionEstado.DISFRUTADO
        balance_after = self._recalcular_balance(account)
        ledger_entry.balance_after = balance_after

        log.info(
            "Processed vacation usage of %s for employee %s policy=%s balance_before=%s balance_after=%s",
            abs(units),
            empleado.codigo_empleado,
            policy.codigo,
            balance_before,
            balance_after,
        )
        return abs(units)

    def procesar_novedades_vacaciones(self, empleado: Empleado, usuario: str | None = None) -> Decimal:
        """Process vacation novelties (leave taken) during payroll execution."""
        total_usado = Decimal("0.00")
        self._validar_empleado_en_planilla(empleado)

        nomina_novedades = self._build_vacation_usage_query(empleado)

        for nomina_novedad in nomina_novedades:
            vac_novelty = self._get_vacation_novelty(nomina_novedad)
            if not vac_novelty:
                continue

            policy = cast("VacationPolicy", vac_novelty.account.policy)
            self._validar_policy(policy)

            used = self._process_single_vacation_usage(vac_novelty, empleado, policy, usuario)
            total_usado = total_usado + used

        return total_usado
