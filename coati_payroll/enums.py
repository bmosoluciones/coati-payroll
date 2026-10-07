# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Enumerations for type safety using Python 3.11+ StrEnum.

This module defines string-based enums using Python 3.11's StrEnum class,
which provides better type safety and autocompletion compared to plain strings.

StrEnum was introduced in Python 3.11 and automatically generates string values
from member names when values aren't explicitly provided.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from enum import StrEnum

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #


# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #


class FormulaType(StrEnum):
    """Types of formulas for calculating payroll concepts."""

    FIJO = "fixed"  # Fixed amount
    PORCENTAJE = "percentage"  # Percentage
    PORCENTAJE_SALARIO = "salary_percentage"  # Percentage of salary
    PORCENTAJE_BRUTO = "gross_percentage"  # Percentage of gross
    FORMULA = "formula"  # Complex formula using FormulaEngine
    REGLA_CALCULO = "calculation_rule"  # Uses linked ReglaCalculo for calculation
    HORAS = "hours"  # Based on hours
    DIAS = "days"  # Based on days

    @classmethod
    def normalize(cls, value: str | FormulaType | None) -> FormulaType | None:
        """Normalize legacy/Spanish values to the current enum values."""
        if value is None:
            return None
        if isinstance(value, FormulaType):
            return value
        val_str = str(value).lower()
        legacy_map = {
            "fijo": cls.FIJO,
            "porcentaje": cls.PORCENTAJE,
            "porcentaje_salario": cls.PORCENTAJE_SALARIO,
            "porcentaje_bruto": cls.PORCENTAJE_BRUTO,
            "formula": cls.FORMULA,
            "formula_personalizada": cls.REGLA_CALCULO,
            "custom_formula": cls.REGLA_CALCULO,
            "regla_calculo": cls.REGLA_CALCULO,
            "horas": cls.HORAS,
            "dias": cls.DIAS,
        }
        if val_str in legacy_map:
            return legacy_map[val_str]
        if str(value).upper() in cls._member_map_:
            return cls[str(value).upper()]
        return cls(value) if value in cls._value2member_map_ else None


class StepType(StrEnum):
    """Types of calculation steps in FormulaEngine schemas."""

    CALCULATION = "calculation"  # Mathematical calculation
    CONDITIONAL = "conditional"  # If/else logic
    TAX_LOOKUP = "tax_lookup"  # Tax table lookup
    ASSIGNMENT = "assignment"  # Variable assignment


class NominaEstado(StrEnum):
    """States of a payroll run (Nomina).

    All states are valid and permanent. Once a nomina reaches a state, it remains
    in that state unless explicitly changed (e.g., ERROR can be retried, which
    changes it to CALCULATING).
    """

    CALCULANDO = "calculating"  # Calculating in background
    GENERADO = "generated"  # Generated but not approved
    GENERADO_CON_ERRORES = "generated_with_errors"  # Generated with employee errors
    APROBADO = "approved"  # Approved and ready to apply
    APLICADO = "applied"  # Applied/executed
    PAGADO = "paid"  # Paid out (synonym for APLICADO, for compatibility)
    ANULADO = "cancelled"  # Cancelled/voided
    ERROR = "error"  # Error during calculation (valid permanent state, can be retried)


class LiquidacionEstado(StrEnum):
    """States of a termination settlement (Liquidacion)."""

    BORRADOR = "draft"  # Draft - not yet applied
    CALCULADA = "calculated"  # Calculated - ready to apply
    ERROR = "error"  # Error during calculation
    APLICADO = "applied"  # Applied/executed
    PAGADO = "paid"  # Paid out


class AdelantoEstado(StrEnum):
    """States of a loan or salary advance."""

    BORRADOR = "draft"  # Draft - not yet submitted
    PENDIENTE = "pending"  # Pending approval
    APROBADO = "approved"  # Approved and active
    APLICADO = "applied"  # Applied/disbursed (paid out to employee)
    PAGADO = "paid"  # Fully paid off (all installments completed)
    RECHAZADO = "rejected"  # Rejected
    CANCELADO = "cancelled"  # Cancelled


class AdelantoTipo(StrEnum):
    """Types of advances/loans."""

    ADELANTO = "advance"  # Salary advance
    PRESTAMO = "loan"  # Loan with optional interest


class TipoInteres(StrEnum):
    """Interest rate types for loans."""

    NINGUNO = "none"  # No interest
    SIMPLE = "simple"  # Simple interest
    COMPUESTO = "compound"  # Compound interest


class MetodoAmortizacion(StrEnum):
    """Amortization methods for loans with interest."""

    FRANCES = "french"  # French method - constant payment (cuota constante)
    ALEMAN = "german"  # German method - constant amortization (amortización constante)


class VacacionEstado(StrEnum):
    """States of vacation requests."""

    PENDIENTE = "pending"  # Pending approval
    APROBADO = "approved"  # Approved
    APLICADO = "applied"  # Applied to payroll novelties
    RECHAZADO = "rejected"  # Rejected
    DISFRUTADO = "taken"  # Taken/enjoyed


class TipoUsuario(StrEnum):
    """User types in the system."""

    ADMIN = "admin"  # Administrator
    HHRR = "hr"  # Human Resources
    AUDIT = "audit"  # Auditor


class EstadoAprobacion(StrEnum):
    """Approval states for payroll concepts (percepciones, deducciones, prestaciones)."""

    BORRADOR = "draft"  # Draft - not yet approved
    APROBADO = "approved"  # Approved and ready for use


class TipoDetalle(StrEnum):
    """Types of payroll detail entries."""

    INGRESO = "income"  # Income/perception
    DEDUCCION = "deduction"  # Deduction
    PRESTACION = "benefit"  # Employer benefit


class Periodicidad(StrEnum):
    """Payroll periodicities."""

    MENSUAL = "monthly"  # Monthly
    QUINCENAL = "biweekly"  # Biweekly
    SEMANAL = "weekly"  # Weekly
    DIARIO = "daily"  # Daily


class NovedadEstado(StrEnum):
    """States of a payroll novelty (novedad)."""

    PENDIENTE = "pending"  # Pending - not yet executed
    EJECUTADA = "executed"  # Executed - nomina has been applied


class TipoAcumulacionPrestacion(StrEnum):
    """Types of benefit accumulation periods."""

    MENSUAL = "monthly"  # Settled monthly (e.g., INSS, INATEC)
    ANUAL = "annual"  # Accumulated annually (e.g., 13th month)
    VIDA_LABORAL = "lifetime"  # Accumulated over employment lifetime (e.g., severance)


class CargaInicialEstado(StrEnum):
    """States for initial benefit balance loading."""

    BORRADOR = "draft"  # Draft - not yet applied
    APLICADO = "applied"  # Applied - transferred to accumulated table


class TipoTransaccionPrestacion(StrEnum):
    """Transaction types for accumulated benefits."""

    SALDO_INICIAL = "initial_balance"  # Initial balance
    ADICION = "addition"  # Addition (increase)
    DISMINUCION = "decrease"  # Decrease (reduction)
    AJUSTE = "adjustment"  # Adjustment (can be positive or negative)


# ============================================================================
# Vacation Module Enums
# ============================================================================


class AccrualMethod(StrEnum):
    """Methods for vacation accrual calculation."""

    PERIODIC = "periodic"  # Fixed amount per period (monthly, annually, etc.)
    PROPORTIONAL = "proportional"  # Based on worked days/hours
    SENIORITY = "seniority"  # Tiered by years of service


class AccrualFrequency(StrEnum):
    """Frequency of vacation accrual."""

    MONTHLY = "monthly"  # Monthly accrual
    BIWEEKLY = "biweekly"  # Every two weeks
    ANNUAL = "annual"  # Once per year


class AccrualBasis(StrEnum):
    """Basis for proportional accrual calculation."""

    DAYS_WORKED = "days_worked"  # Based on days actually worked
    HOURS_WORKED = "hours_worked"  # Based on hours worked


class VacationLedgerType(StrEnum):
    """Types of vacation ledger entries."""

    ACCRUAL = "accrual"  # Earned vacation time
    USAGE = "usage"  # Vacation time taken
    ADJUSTMENT = "adjustment"  # Manual adjustment (+ or -)
    EXPIRATION = "expiration"  # Expired vacation time
    PAYOUT = "payout"  # Paid out vacation (e.g., on termination)


class VacationUnitType(StrEnum):
    """Unit types for vacation balances."""

    DAYS = "days"  # Calendar or working days
    HOURS = "hours"  # Hours


class ExpirationRule(StrEnum):
    """Rules for vacation expiration."""

    NEVER = "never"  # Vacation never expires
    FISCAL_YEAR_END = "fiscal_year_end"  # Expires at fiscal year end
    ANNIVERSARY = "anniversary"  # Expires on employment anniversary
    CUSTOM_DATE = "custom_date"  # Custom expiration date


# ============================================================================
# Reports Module Enums
# ============================================================================


class ReportType(StrEnum):
    """Types of reports in the system.

    System reports are pre-defined, optimized reports built into the core.
    Custom reports are user-defined reports created through the UI.

    """

    SYSTEM = "system"  # System-defined report
    CUSTOM = "custom"  # User-defined custom report


class ReportStatus(StrEnum):
    """Administrative status of a report.

    Controls whether a report is available for execution.

    """

    ENABLED = "enabled"  # Report is available for execution
    DISABLED = "disabled"  # Report is not available


class ReportExecutionStatus(StrEnum):
    """Status of a report execution.

    Tracks the lifecycle of a report execution from queued to completed.

    """

    QUEUED = "queued"  # Report execution is queued
    RUNNING = "running"  # Report is currently executing
    COMPLETED = "completed"  # Report execution completed successfully
    FAILED = "failed"  # Report execution failed
    CANCELLED = "cancelled"  # Report execution was cancelled
