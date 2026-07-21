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

        tasa_dia = (salario_mensual / Decimal(str(factor_dias))).quantize(Decimal("0.01"))
        monto_dias = (tasa_dia * Decimal(str(liquidacion.dias_por_pagar))).quantize(Decimal("0.01"))

        if liquidacion.dias_por_pagar > 0 and monto_dias > 0:
            liquidacion.detalles.append(
                LiquidacionDetalle(
                    tipo="income",
                    codigo="DIAS_POR_PAGAR",
                    descripcion="Días por pagar",
                    monto=monto_dias,
                    orden=1,
                )
            )

        # Apply pending loans/advances as deductions
        saldo_disponible = monto_dias
        loan_processor = LoanProcessor(
            nomina=None,
            fecha_calculo=self.fecha_calculo,
            periodo_inicio=ultimo_dia_pagado,
            periodo_fin=self.fecha_calculo,
            liquidacion=liquidacion,
            calcular_interes=False,
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

        orden = 1
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

        total_bruto = monto_dias
        total_neto = (total_bruto - total_deducciones).quantize(Decimal("0.01"))
        liquidacion.total_bruto = total_bruto
        liquidacion.total_deducciones = total_deducciones
        liquidacion.total_neto = total_neto

        liquidacion.errores_calculo = {"errors": self.errors} if self.errors else {}
        liquidacion.advertencias_calculo = list(self.warnings)

        return liquidacion


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
