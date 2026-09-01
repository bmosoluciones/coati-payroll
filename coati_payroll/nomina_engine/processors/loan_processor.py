# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Loan processor for automatic loan and advance deductions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from coati_payroll.model import db, Adelanto, AdelantoAbono, Nomina, Liquidacion, TipoCambio
from coati_payroll.enums import AdelantoEstado, TipoInteres
from coati_payroll.i18n import _
from ..domain.calculation_items import DeduccionItem
from ..utils.rounding import round_money


class LoanProcessor:
    """Processor for automatic loan and advance deductions."""

    def __init__(
        self,
        nomina: Nomina | None,
        fecha_calculo: date,
        periodo_inicio: date,
        periodo_fin: date,
        liquidacion: Liquidacion | None = None,
        calcular_interes: bool = True,
        apply_side_effects: bool = True,
    ):
        self.nomina = nomina
        self.liquidacion = liquidacion
        self.fecha_calculo = fecha_calculo
        self.periodo_inicio = periodo_inicio
        self.periodo_fin = periodo_fin
        self.calcular_interes = calcular_interes
        self.apply_side_effects = apply_side_effects
        self._pending_actions: list[tuple[Adelanto, Decimal, Decimal, bool]] = []

    def process_loans(
        self, empleado_id: str, saldo_disponible: Decimal, aplicar_prestamos: bool, prioridad_prestamos: int
    ) -> list[DeduccionItem]:
        """Process loans for an employee."""
        deductions: list[DeduccionItem] = []

        if not aplicar_prestamos:
            return deductions

        # Get active loans
        from sqlalchemy import select

        prestamos = list(
            db.session.execute(
                select(Adelanto)
                .filter(
                    Adelanto.empleado_id == empleado_id,
                    Adelanto.estado == AdelantoEstado.APROBADO,
                    Adelanto.saldo_pendiente > 0,
                    Adelanto.deduccion_id.isnot(None),  # Only loans, not advances
                )
                .order_by(
                    Adelanto.fecha_aprobacion.is_(None),
                    Adelanto.fecha_aprobacion,
                    Adelanto.creado,
                    Adelanto.id,
                )
            )
            .scalars()
            .all()
        )

        for prestamo in prestamos:
            if saldo_disponible <= 0:
                break

            self._calculate_interest_if_needed(prestamo)

            monto_cuota = Decimal(str(prestamo.monto_por_cuota or 0))
            if monto_cuota <= 0:
                continue

            saldo_pendiente = Decimal(str(prestamo.saldo_pendiente or 0))
            monto_prestamo, monto_aplicar = self._payment_amount(
                prestamo, monto_cuota, saldo_pendiente, saldo_disponible
            )
            if monto_aplicar <= 0 or monto_prestamo <= 0:
                continue

            item = DeduccionItem(
                codigo=f"PRESTAMO_{prestamo.id[:8]}",
                nombre=f"Cuota préstamo - {prestamo.motivo or 'N/A'}",
                monto=monto_aplicar,
                prioridad=prioridad_prestamos,
                es_obligatoria=False,
                deduccion_id=prestamo.deduccion_id,
                tipo="loan",
            )
            deductions.append(item)
            saldo_disponible -= monto_aplicar

            self._record_or_queue_payment(prestamo, monto_prestamo, monto_aplicar)

        return deductions

    def _calculate_interest_if_needed(self, prestamo: Adelanto) -> None:
        """Calculate interest only when processing real side effects."""
        if self.calcular_interes and self.apply_side_effects:
            self._calculate_interest(prestamo)

    def _payment_amount(
        self, adelanto: Adelanto, installment: Decimal, balance: Decimal, available: Decimal
    ) -> tuple[Decimal, Decimal]:
        """Return the loan and payroll amounts that can be collected safely.

        Loan balances are stored in the loan's currency while payroll deductions
        are expressed in the planilla currency.  Both values must therefore be
        calculated independently before either the net pay or the loan balance
        is mutated.
        """
        target_loan_amount = min(balance, available) if self.liquidacion is not None else min(installment, balance)
        rate = self._loan_to_planilla_rate(adelanto)
        desired_planilla_amount = round_money(target_loan_amount * rate)
        payroll_amount = min(desired_planilla_amount, available)
        loan_amount = min(balance, round_money(payroll_amount / rate))
        payroll_amount = round_money(loan_amount * rate)
        return loan_amount, payroll_amount

    def _record_or_queue_payment(self, prestamo: Adelanto, loan_amount: Decimal, payroll_amount: Decimal) -> None:
        """Persist a payment or defer it until side effects are enabled."""
        if self.apply_side_effects:
            self._record_payment(prestamo, loan_amount, payroll_amount)
        else:
            self._pending_actions.append((prestamo, loan_amount, payroll_amount, True))

    def process_advances(
        self, empleado_id: str, saldo_disponible: Decimal, aplicar_adelantos: bool, prioridad_adelantos: int
    ) -> list[DeduccionItem]:
        """Process salary advances for an employee."""
        deductions: list[DeduccionItem] = []

        if not aplicar_adelantos:
            return deductions

        from sqlalchemy import select

        adelantos = list(
            db.session.execute(
                select(Adelanto)
                .filter(
                    Adelanto.empleado_id == empleado_id,
                    Adelanto.estado == AdelantoEstado.APROBADO,
                    Adelanto.saldo_pendiente > 0,
                    Adelanto.deduccion_id.is_(None),  # Only advances, not loans
                )
                .order_by(
                    Adelanto.fecha_aprobacion.is_(None),
                    Adelanto.fecha_aprobacion,
                    Adelanto.creado,
                    Adelanto.id,
                )
            )
            .scalars()
            .all()
        )

        for adelanto in adelantos:
            if saldo_disponible <= 0:
                break

            saldo_pendiente = Decimal(str(adelanto.saldo_pendiente or 0))
            if self.liquidacion is not None:
                # Termination settlement: the full outstanding balance is due.
                monto_prestamo, monto_aplicar = self._payment_amount(
                    adelanto, saldo_pendiente, saldo_pendiente, saldo_disponible
                )
            else:
                monto_cuota = Decimal(str(adelanto.monto_por_cuota or adelanto.saldo_pendiente))
                monto_prestamo, monto_aplicar = self._payment_amount(
                    adelanto, monto_cuota, saldo_pendiente, saldo_disponible
                )
            if monto_aplicar <= 0 or monto_prestamo <= 0:
                continue

            item = DeduccionItem(
                codigo=f"ADELANTO_{adelanto.id[:8]}",
                nombre=f"Adelanto salarial - {adelanto.motivo or 'N/A'}",
                monto=monto_aplicar,
                prioridad=prioridad_adelantos,
                es_obligatoria=False,
                tipo="advance",
            )
            deductions.append(item)
            saldo_disponible -= monto_aplicar

            # Record the payment
            if self.apply_side_effects:
                self._record_payment(adelanto, monto_prestamo, monto_aplicar)
            else:
                self._pending_actions.append((adelanto, monto_prestamo, monto_aplicar, False))

        return deductions

    def _calculate_interest(self, prestamo: Adelanto) -> None:
        """Calculate and apply interest for a loan."""
        from coati_payroll.interes_engine import calcular_interes_periodo
        from coati_payroll.model import InteresAdelanto

        if not self.nomina:
            return

        existing = db.session.execute(
            db.select(InteresAdelanto).filter_by(adelanto_id=prestamo.id, nomina_id=self.nomina.id)
        ).scalar_one_or_none()
        if existing:
            return

        tasa_interes = prestamo.tasa_interes or Decimal("0.0000")
        if tasa_interes <= 0:
            return

        if prestamo.saldo_pendiente <= 0:
            return

        fecha_desde = prestamo.fecha_ultimo_calculo_interes
        if not fecha_desde:
            fecha_desde = prestamo.fecha_desembolso or prestamo.fecha_aprobacion

        if not fecha_desde:
            return

        fecha_hasta = self.fecha_calculo

        if fecha_desde >= fecha_hasta:
            return

        tipo_interes = cast(TipoInteres, prestamo.tipo_interes or TipoInteres.SIMPLE)
        interes_calculado, dias = calcular_interes_periodo(
            saldo=prestamo.saldo_pendiente,
            tasa_anual=tasa_interes,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            tipo_interes=tipo_interes,
            empresa_id=getattr(getattr(prestamo, "empleado", None), "empresa_id", None),
        )

        if interes_calculado <= 0:
            return

        # Record interest in journal
        interes_entrada = InteresAdelanto(
            adelanto_id=prestamo.id,
            nomina_id=self.nomina.id if self.nomina else None,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            dias_transcurridos=dias,
            saldo_base=prestamo.saldo_pendiente,
            tasa_aplicada=tasa_interes,
            interes_calculado=interes_calculado,
            saldo_anterior=prestamo.saldo_pendiente,
            saldo_posterior=prestamo.saldo_pendiente + interes_calculado,
            observaciones=_("Interés calculado por nómina del {inicio} al {fin}").format(
                inicio=self.periodo_inicio, fin=self.periodo_fin
            ),
        )
        db.session.add(interes_entrada)

        # Update loan with interest
        prestamo.saldo_pendiente += interes_calculado
        prestamo.interes_acumulado = (prestamo.interes_acumulado or Decimal("0.00")) + interes_calculado
        prestamo.fecha_ultimo_calculo_interes = fecha_hasta

    def _loan_to_planilla_rate(self, adelanto: Adelanto) -> Decimal:
        """Get the loan-to-payroll currency rate for this payment."""
        planilla = self.nomina.planilla if self.nomina else None
        if not planilla or not adelanto.moneda_id or adelanto.moneda_id == planilla.moneda_id:
            return Decimal("1.00")

        rate = db.session.execute(
            db.select(TipoCambio.tasa)
            .where(
                TipoCambio.moneda_origen_id == adelanto.moneda_id,
                TipoCambio.moneda_destino_id == planilla.moneda_id,
                TipoCambio.fecha <= self.fecha_calculo,
            )
            .order_by(TipoCambio.fecha.desc())
            .limit(1)
        ).scalar_one_or_none()
        if rate is None or Decimal(str(rate)) <= 0:
            from ..validators import CalculationError

            raise CalculationError(
                "No se encontró un tipo de cambio válido para aplicar el préstamo en la moneda de la planilla."
            )
        return Decimal(str(rate))

    def _record_payment(self, adelanto: Adelanto, monto_prestamo: Decimal, monto_planilla: Decimal) -> None:
        """Record a payment towards a loan/advance."""
        if self.nomina:
            existing = db.session.execute(
                db.select(AdelantoAbono).filter_by(adelanto_id=adelanto.id, nomina_id=self.nomina.id)
            ).scalar_one_or_none()
            if existing:
                return

        saldo_anterior = Decimal(str(adelanto.saldo_pendiente))
        saldo_posterior = saldo_anterior - monto_prestamo

        abono = AdelantoAbono(
            adelanto_id=adelanto.id,
            nomina_id=self.nomina.id if self.nomina else None,
            liquidacion_id=self.liquidacion.id if self.liquidacion else None,
            fecha_abono=self.fecha_calculo,
            monto_abonado=monto_prestamo,
            saldo_anterior=saldo_anterior,
            saldo_posterior=max(saldo_posterior, Decimal("0.00")),
            tipo_abono="liquidacion" if self.liquidacion else "nomina",
        )
        db.session.add(abono)

        # Update adelanto balance
        adelanto.saldo_pendiente = max(saldo_posterior, Decimal("0.00"))
        adelanto.monto_deducido_moneda_planilla = (
            Decimal(str(adelanto.monto_deducido_moneda_planilla or 0)) + monto_planilla
        )
        adelanto.monto_aplicado_moneda_prestamo = (
            Decimal(str(adelanto.monto_aplicado_moneda_prestamo or 0)) + monto_prestamo
        )
        if adelanto.saldo_pendiente <= 0:
            adelanto.estado = AdelantoEstado.PAGADO

    def apply_pending_effects(self) -> None:
        """Apply deferred loan/advance side effects after successful payroll."""
        if self.apply_side_effects or not self._pending_actions:
            return

        from coati_payroll.log import log

        for adelanto, monto_prestamo, monto_planilla, requires_interest in self._pending_actions:
            try:
                if requires_interest and self.calcular_interes:
                    self._calculate_interest(adelanto)
                self._record_payment(adelanto, monto_prestamo, monto_planilla)
            except Exception as e:
                log.error(
                    "Error aplicando efecto pendiente para adelanto %s: %s",
                    adelanto.id,
                    str(e),
                    exc_info=True,
                )
                raise
