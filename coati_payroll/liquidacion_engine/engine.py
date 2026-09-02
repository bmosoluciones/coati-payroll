# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

"""Liquidación engine orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select

from coati_payroll.enums import LiquidacionEstado, NominaEstado
from coati_payroll.formula_engine import FormulaEngine, FormulaEngineError
from coati_payroll.model import (
    ConfiguracionCalculos,
    Empleado,
    Liquidacion,
    LiquidacionDetalle,
    Nomina,
    NominaEmpleado,
    AdelantoAbono,
    Adelanto,
    db,
)
from coati_payroll.nomina_engine.repositories.config_repository import ConfigRepository
from coati_payroll.nomina_engine.processors.loan_processor import LoanProcessor


@dataclass(frozen=True)
class LiquidacionResult:
    liquidacion: Liquidacion | None
    errors: list[str]
    warnings: list[str]


class LiquidacionEngine:
    """Engine for calculating employee termination settlements (liquidaciones)."""

    def __init__(self, empleado: Empleado, fecha_calculo: date | None = None, usuario: str | None = None):
        self.empleado = empleado
        self.fecha_calculo = fecha_calculo or date.today()
        self.usuario = usuario
        self.errors: list[str] = []
        self.warnings: list[str] = []

        self._config_repo = ConfigRepository(cast(Any, db.session))

    def _get_config(self) -> ConfiguracionCalculos:
        return self._config_repo.get_for_empresa(self.empleado.empresa_id)

    def determinar_ultimo_dia_pagado(self) -> date:
        """Get the last day covered by the employee's last applied/paid payroll."""
        stmt = (
            select(Nomina.periodo_fin)
            .join(NominaEmpleado, NominaEmpleado.nomina_id == Nomina.id)
            .where(
                NominaEmpleado.empleado_id == self.empleado.id,
                Nomina.estado.in_([NominaEstado.APLICADO, NominaEstado.PAGADO]),
            )
            .order_by(Nomina.periodo_fin.desc())
            .limit(1)
        )

        ultimo = db.session.execute(stmt).scalar_one_or_none()
        if ultimo:
            return ultimo

        fecha_alta = self.empleado.fecha_alta
        if not fecha_alta:
            self.warnings.append("Empleado sin fecha de alta; usando fecha de cálculo como referencia.")
            return self.fecha_calculo

        return fecha_alta - timedelta(days=1)

    def _get_factor_dias(self, config: ConfiguracionCalculos) -> int:
        modo = (config.liquidacion_modo_dias or "calendar").strip().lower()
        if modo in {"calendario", "calendar"}:
            return int(config.liquidacion_factor_calendario)
        if modo in {"laboral", "working"}:
            return int(config.liquidacion_factor_laboral)
        self.warnings.append("Modo de días de liquidación no reconocido; se usará calendario.")
        return int(config.liquidacion_factor_calendario)

    def calcular(self, liquidacion: Liquidacion) -> Liquidacion | None:
        """Calculate a liquidacion record in-place."""
        config = self._get_config()

        liquidacion.total_bruto = Decimal("0.00")
        liquidacion.total_deducciones = Decimal("0.00")
        liquidacion.total_neto = Decimal("0.00")

        ultimo_dia_pagado = self.determinar_ultimo_dia_pagado()
        liquidacion.ultimo_dia_pagado = ultimo_dia_pagado
        liquidacion.fecha_calculo = self.fecha_calculo

        if self.fecha_calculo <= ultimo_dia_pagado:
            liquidacion.dias_por_pagar = 0
            self.warnings.append("La fecha de cálculo es menor o igual al último día pagado.")
        else:
            liquidacion.dias_por_pagar = (self.fecha_calculo - ultimo_dia_pagado).days

        # Clear previous details (support recalculation)
        liquidacion.detalles.clear()

        # Income for pending days
        factor_dias = self._get_factor_dias(config)
        salario_mensual = Decimal(str(self.empleado.salario_base or 0))
        if factor_dias <= 0:
            self.errors.append("Factor de días inválido en configuración.")
            return None

        # Keep the daily rate unrounded so the proration is exact; only the
        # final line amounts are quantized below.
        tasa_dia = salario_mensual / Decimal(str(factor_dias))
        monto_dias = (tasa_dia * Decimal(str(liquidacion.dias_por_pagar))).quantize(Decimal("0.01"))

        # Side effects (loan payments, vacation payout ledger entries, ...) are
        # deferred until the liquidacion leaves BORRADOR: calculating a draft
        # must never mutate real balances, otherwise abandoned drafts would
        # reduce the employee's outstanding debt without an applied settlement.
        apply_side_effects = liquidacion.estado != LiquidacionEstado.BORRADOR

        orden = 1
        total_bruto = Decimal("0.00")
        if liquidacion.dias_por_pagar > 0 and monto_dias > 0:
            liquidacion.detalles.append(
                LiquidacionDetalle(
                    tipo="income",
                    codigo="DIAS_POR_PAGAR",
                    descripcion="Días por pagar",
                    monto=monto_dias,
                    orden=orden,
                )
            )
            total_bruto += monto_dias
            orden += 1

        # Jurisdiction-specific severance, bonus and proportional-benefit
        # rules are supplied as the same safe formula schema used by payroll.
        # A missing schema intentionally means no extra statutory line.
        monto_configurado = self._calcular_concepto_configurado(liquidacion, tasa_dia, total_bruto)
        if monto_configurado > 0:
            concepto = liquidacion.concepto
            liquidacion.detalles.append(
                LiquidacionDetalle(
                    tipo="income",
                    codigo=concepto.codigo,
                    descripcion=concepto.nombre,
                    monto=monto_configurado,
                    orden=orden,
                )
            )
            total_bruto += monto_configurado
            orden += 1

        # Vacation payout on termination: the pending vacation balance is
        # valued at the daily salary and paid out when the policy allows it.
        monto_vacaciones = self._procesar_vacaciones_finiquito(
            liquidacion, tasa_dia, apply_side_effects=apply_side_effects, orden=orden
        )
        if monto_vacaciones > 0:
            total_bruto += monto_vacaciones
            orden += 1

        # Apply pending loans/advances as deductions.
        saldo_disponible = total_bruto
        loan_processor = LoanProcessor(
            nomina=None,
            fecha_calculo=self.fecha_calculo,
            periodo_inicio=ultimo_dia_pagado,
            periodo_fin=self.fecha_calculo,
            liquidacion=liquidacion,
            calcular_interes=False,
            apply_side_effects=apply_side_effects,
        )

        prioridad_prestamos = config.liquidacion_prioridad_prestamos
        prioridad_adelantos = config.liquidacion_prioridad_adelantos

        deducciones = []
        deducciones.extend(
            loan_processor.process_loans(
                empleado_id=self.empleado.id,
                saldo_disponible=saldo_disponible,
                aplicar_prestamos=True,
                prioridad_prestamos=prioridad_prestamos,
            )
        )
        for d in deducciones:
            saldo_disponible -= d.monto

        deducciones_adv = loan_processor.process_advances(
            empleado_id=self.empleado.id,
            saldo_disponible=saldo_disponible,
            aplicar_adelantos=True,
            prioridad_adelantos=prioridad_adelantos,
        )
        deducciones.extend(deducciones_adv)

        total_deducciones = Decimal("0.00")
        for item in deducciones:
            orden += 1
            total_deducciones += item.monto
            liquidacion.detalles.append(
                LiquidacionDetalle(
                    tipo="deduction",
                    codigo=item.codigo,
                    descripcion=item.nombre,
                    monto=item.monto,
                    orden=orden,
                )
            )

        total_neto = (total_bruto - total_deducciones).quantize(Decimal("0.01"))
        liquidacion.total_bruto = total_bruto
        liquidacion.total_deducciones = total_deducciones
        liquidacion.total_neto = total_neto

        liquidacion.errores_calculo = {"errors": self.errors} if self.errors else {}
        liquidacion.advertencias_calculo = list(self.warnings)

        return liquidacion

    def _calcular_concepto_configurado(
        self, liquidacion: Liquidacion, tasa_dia: Decimal, total_bruto: Decimal
    ) -> Decimal:
        """Evaluate the selected jurisdiction-specific liquidation rule."""
        concepto = liquidacion.concepto
        schema = concepto.esquema_json if concepto else None
        if not schema:
            return Decimal("0.00")
        fecha_alta = self.empleado.fecha_alta or self.fecha_calculo
        dias_servicio = max(0, (self.fecha_calculo - fecha_alta).days)
        inputs = {
            "salario_mensual": Decimal(str(self.empleado.salario_base or 0)),
            "salario_diario": tasa_dia,
            "dias_por_pagar": Decimal(str(liquidacion.dias_por_pagar)),
            "dias_servicio": Decimal(str(dias_servicio)),
            "anos_servicio": Decimal(str(dias_servicio)) / Decimal("365.25"),
            "total_bruto": total_bruto,
            "total_deducciones": Decimal("0.00"),
        }
        try:
            result = FormulaEngine(schema).execute(inputs)
            amount = Decimal(str(result.get("output", 0)))
            return max(Decimal("0.00"), amount).quantize(Decimal("0.01"))
        except (FormulaEngineError, ValueError, TypeError) as exc:
            self.errors.append(f"Concepto de liquidación {concepto.codigo}: {exc}")
            return Decimal("0.00")

    def _procesar_vacaciones_finiquito(
        self, liquidacion: Liquidacion, tasa_dia: Decimal, apply_side_effects: bool, orden: int
    ) -> Decimal:
        """Pay out pending vacation balance on termination.

        When the employee's active vacation policy has payout_on_termination
        enabled, the accumulated balance is valued at the daily salary and
        added as an income line. Once the liquidacion leaves BORRADOR a
        PAYOUT ledger entry is recorded to zero the account balance.

        Returns:
            The total vacation payout amount.
        """
        from coati_payroll.enums import VacationLedgerType
        from coati_payroll.model import VacationAccount, VacationLedger, VacationPolicy

        accounts = (
            db.session.execute(
                db.select(VacationAccount)
                .join(VacationPolicy, VacationPolicy.id == VacationAccount.policy_id)
                .where(
                    VacationAccount.empleado_id == self.empleado.id,
                    VacationAccount.activo.is_(True),
                    VacationPolicy.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )

        config = self._get_config()
        horas_jornada = Decimal(str(getattr(config, "horas_jornada_diaria", 8) or 8))

        monto_total = Decimal("0.00")
        for account in accounts:
            policy = cast(Any, account.policy)
            payout = self._calculate_vacation_payout(policy, account, horas_jornada, tasa_dia)
            if payout is None:
                continue
            balance, monto = payout

            liquidacion.detalles.append(
                LiquidacionDetalle(
                    tipo="income",
                    codigo="VACACIONES_PENDIENTES",
                    descripcion=f"Vacaciones pendientes ({policy.codigo})",
                    monto=monto,
                    orden=orden,
                )
            )
            monto_total += monto

            if not apply_side_effects:
                continue

            existing = (
                db.session.execute(
                    db.select(VacationLedger).filter(
                        VacationLedger.entry_type == VacationLedgerType.PAYOUT,
                        VacationLedger.source == "termination",
                        VacationLedger.reference_type == "liquidacion",
                        VacationLedger.reference_id == liquidacion.id,
                        VacationLedger.account_id == account.id,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                continue

            db.session.add(
                VacationLedger(
                    account_id=account.id,
                    empleado_id=self.empleado.id,
                    fecha=self.fecha_calculo,
                    entry_type=VacationLedgerType.PAYOUT,
                    quantity=-balance,
                    source="termination",
                    reference_id=liquidacion.id,
                    reference_type="liquidacion",
                    observaciones="Pago de vacaciones pendientes en liquidación",
                    balance_after=Decimal("0.00"),
                )
            )
            account.current_balance = Decimal("0.0000")

        return monto_total

    @staticmethod
    def _calculate_vacation_payout(
        policy: Any, account: Any, hours_per_day: Decimal, daily_rate: Decimal
    ) -> tuple[Decimal, Decimal] | None:
        """Calculate a positive vacation payout, or return ``None`` when ineligible."""
        if not policy.payout_on_termination:
            return None

        balance = Decimal(str(account.current_balance or 0))
        if balance <= 0:
            return None

        if policy.unit_type == "hours":
            amount = (balance / hours_per_day * daily_rate).quantize(Decimal("0.01"))
        else:
            amount = (balance * daily_rate).quantize(Decimal("0.01"))

        if amount <= 0:
            return None
        return balance, amount


def recalcular_liquidacion(liquidacion_id: str, fecha_calculo: date | None = None, usuario: str | None = None):
    """Recalculate an existing liquidacion.

    - Removes existing details
    - Reverts any AdelantoAbono records created by this liquidation
    - Re-runs calculation
    """
    liquidacion = db.session.get(Liquidacion, liquidacion_id)
    if not liquidacion:
        return None, ["Liquidación no encontrada."], []

    if liquidacion.estado not in {LiquidacionEstado.BORRADOR, LiquidacionEstado.CALCULADA}:
        return None, ["Solo se pueden recalcular liquidaciones en borrador o calculadas."], []

    empleado = db.session.get(Empleado, liquidacion.empleado_id)
    if not empleado:
        from coati_payroll.vistas.constants import MSG_EMPLEADO_NO_ENCONTRADO

        return None, [MSG_EMPLEADO_NO_ENCONTRADO], []

    # Revert loan/advance payments applied by this liquidation
    abonos = (
        db.session.execute(select(AdelantoAbono).where(AdelantoAbono.liquidacion_id == liquidacion.id)).scalars().all()
    )

    for abono in abonos:
        adelanto = db.session.get(Adelanto, abono.adelanto_id)
        if adelanto:
            # Undo the payment (add back to saldo)
            adelanto.saldo_pendiente = (
                Decimal(str(adelanto.saldo_pendiente)) + Decimal(str(abono.monto_abonado))
            ).quantize(Decimal("0.01"))
            if adelanto.saldo_pendiente > 0 and adelanto.estado == "paid":
                adelanto.estado = "approved"
        db.session.delete(abono)

    # Revert vacation payout ledger entries applied by this liquidation
    from coati_payroll.enums import VacationLedgerType
    from coati_payroll.model import VacationAccount, VacationLedger

    payouts = (
        db.session.execute(
            db.select(VacationLedger).filter(
                VacationLedger.entry_type == VacationLedgerType.PAYOUT,
                VacationLedger.source == "termination",
                VacationLedger.reference_type == "liquidacion",
                VacationLedger.reference_id == liquidacion.id,
            )
        )
        .scalars()
        .all()
    )
    for entry in payouts:
        account = db.session.get(VacationAccount, entry.account_id)
        if account:
            account.current_balance = (Decimal(str(account.current_balance)) + Decimal(str(-entry.quantity))).quantize(
                Decimal("0.0001")
            )
        db.session.delete(entry)

    # Remove existing details
    liquidacion.detalles.clear()

    engine = LiquidacionEngine(
        empleado=empleado, fecha_calculo=fecha_calculo or liquidacion.fecha_calculo, usuario=usuario
    )
    calculated = engine.calcular(liquidacion)
    if not calculated:
        db.session.rollback()
        return None, engine.errors, engine.warnings

    db.session.commit()
    return calculated, engine.errors, engine.warnings


def ejecutar_liquidacion(
    empleado_id: str,
    concepto_id: str | None,
    fecha_calculo: date | None = None,
    usuario: str | None = None,
) -> tuple[Liquidacion | None, list[str], list[str]]:
    """Convenience function to create and calculate a liquidacion."""
    empleado = db.session.get(Empleado, empleado_id)
    if not empleado:
        from coati_payroll.vistas.constants import MSG_EMPLEADO_NO_ENCONTRADO

        return None, [MSG_EMPLEADO_NO_ENCONTRADO], []

    liquidacion = Liquidacion(
        empleado_id=empleado.id,
        concepto_id=concepto_id,
        fecha_calculo=fecha_calculo or date.today(),
        estado=LiquidacionEstado.BORRADOR,
    )
    db.session.add(liquidacion)
    db.session.flush()

    engine = LiquidacionEngine(empleado=empleado, fecha_calculo=fecha_calculo, usuario=usuario)
    calculated = engine.calcular(liquidacion)

    if not calculated:
        db.session.rollback()
        return None, engine.errors, engine.warnings

    db.session.commit()
    return calculated, engine.errors, engine.warnings
