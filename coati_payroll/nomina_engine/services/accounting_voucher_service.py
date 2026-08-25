# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Service for generating accounting vouchers from payroll calculations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from collections import defaultdict
from datetime import date

from coati_payroll.model import (
    db,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    Planilla,
    Percepcion,
    Deduccion,
    Prestacion,
    Adelanto,
    ComprobanteContable,
    ComprobanteContableLinea,
    VacationLedger,
    VacationPolicy,
    ConfiguracionCalculos,
    NominaNovedad,
)
from ..utils.rounding import round_money
from ..constants import (
    CONCEPTO_SALARIO_BASE,
    CONCEPTO_SALARIO_BASE_DESC,
    CONCEPTO_VACACIONES_PAGADAS,
    CONCEPTO_VACACIONES_PAGADAS_DESC,
    CONCEPTO_PRESTAMO_ADELANTO,
)


class AccountingVoucherService:
    """Service for generating accounting vouchers from payroll calculations."""

    def __init__(self, session):
        self.session = session

    def validate_accounting_configuration(self, planilla: Planilla) -> tuple[bool, list[str]]:
        """Validate that all accounting configuration is complete.

        Args:
            planilla: The planilla to validate

        Returns:
            Tuple of (is_valid, list of warnings)
        """
        warnings = []

        # Check base salary accounts
        if not planilla.codigo_cuenta_debe_salario:
            warnings.append("Falta configurar la cuenta de débito para salario básico en la planilla")
        if not planilla.codigo_cuenta_haber_salario:
            warnings.append("Falta configurar la cuenta de crédito para salario básico en la planilla")

        # Check percepciones
        percepciones = (
            self.session.execute(
                db.select(Percepcion)
                .join(Percepcion.planillas)
                .filter(db.text("planilla_ingreso.planilla_id = :planilla_id"))
                .params(planilla_id=planilla.id)
            )
            .scalars()
            .all()
        )

        for percepcion in percepciones:
            if percepcion.contabilizable:
                if not percepcion.codigo_cuenta_debe:
                    warnings.append(
                        f"Percepción '{percepcion.nombre}' ({percepcion.codigo}) no tiene cuenta de débito configurada"
                    )
                if not percepcion.codigo_cuenta_haber:
                    warnings.append(
                        f"Percepción '{percepcion.nombre}' ({percepcion.codigo}) no tiene cuenta de crédito configurada"
                    )

        # Check deducciones
        deducciones = (
            self.session.execute(
                db.select(Deduccion)
                .join(Deduccion.planillas)
                .filter(db.text("planilla_deduccion.planilla_id = :planilla_id"))
                .params(planilla_id=planilla.id)
            )
            .scalars()
            .all()
        )

        for deduccion in deducciones:
            if deduccion.contabilizable:
                if not deduccion.codigo_cuenta_debe:
                    warnings.append(
                        f"Deducción '{deduccion.nombre}' ({deduccion.codigo}) no tiene cuenta de débito configurada"
                    )
                if not deduccion.codigo_cuenta_haber:
                    warnings.append(
                        f"Deducción '{deduccion.nombre}' ({deduccion.codigo}) no tiene cuenta de crédito configurada"
                    )

        # Check prestaciones
        prestaciones = (
            self.session.execute(
                db.select(Prestacion)
                .join(Prestacion.planillas)
                .filter(db.text("planilla_prestacion.planilla_id = :planilla_id"))
                .params(planilla_id=planilla.id)
            )
            .scalars()
            .all()
        )

        for prestacion in prestaciones:
            if prestacion.contabilizable:
                if not prestacion.codigo_cuenta_debe:
                    warnings.append(
                        f"Prestación '{prestacion.nombre}' ({prestacion.codigo}) no tiene cuenta de débito configurada"
                    )
                if not prestacion.codigo_cuenta_haber:
                    warnings.append(
                        f"Prestación '{prestacion.nombre}' ({prestacion.codigo}) no tiene cuenta de crédito configurada"
                    )

        paid_policies = (
            self.session.execute(
                db.select(VacationPolicy).filter(
                    VacationPolicy.activo.is_(True),
                    VacationPolicy.son_vacaciones_pagadas.is_(True),
                    db.or_(VacationPolicy.planilla_id == planilla.id, VacationPolicy.planilla_id.is_(None)),
                )
            )
            .scalars()
            .all()
        )
        for policy in paid_policies:
            if not policy.cuenta_debito_vacaciones_pagadas:
                warnings.append(
                    f"Política de vacaciones '{policy.nombre}' ({policy.codigo}) "
                    f"no tiene cuenta débito de vacaciones pagadas"
                )
            if not policy.cuenta_credito_vacaciones_pagadas:
                warnings.append(
                    f"Política de vacaciones '{policy.nombre}' ({policy.codigo}) "
                    f"no tiene cuenta crédito de vacaciones pagadas"
                )

        is_valid = len(warnings) == 0
        return is_valid, warnings

    def _get_vacation_days_base(self, empresa_id: str | None) -> Decimal:
        if not empresa_id:
            return Decimal("30")
        config = (
            self.session.execute(
                db.select(ConfiguracionCalculos)
                .filter(ConfiguracionCalculos.empresa_id == empresa_id, ConfiguracionCalculos.activo.is_(True))
                .order_by(ConfiguracionCalculos.creado.desc())
            )
            .scalars()
            .first()
        )
        if not config or not config.dias_mes_vacaciones:
            return Decimal("30")
        return Decimal(str(config.dias_mes_vacaciones))

    def _create_line(
        self,
        comprobante_id: str,
        ne: NominaEmpleado,
        empleado,
        empleado_nombre_completo: str,
        centro_costos: str | None,
        codigo_cuenta: str | None,
        descripcion_cuenta: str | None,
        tipo_debito_credito: str,
        monto: Decimal,
        concepto: str,
        tipo_concepto: str,
        concepto_codigo: str,
        orden: int,
    ) -> ComprobanteContableLinea:
        """Create a single accounting voucher line."""
        return ComprobanteContableLinea(
            comprobante_id=comprobante_id,
            nomina_empleado_id=ne.id,
            empleado_id=empleado.id,
            empleado_codigo=empleado.codigo_empleado,
            empleado_nombre=empleado_nombre_completo,
            codigo_cuenta=codigo_cuenta,
            descripcion_cuenta=descripcion_cuenta,
            centro_costos=centro_costos,
            tipo_debito_credito=tipo_debito_credito,
            debito=monto if tipo_debito_credito == "debito" else Decimal("0.00"),
            credito=monto if tipo_debito_credito == "credito" else Decimal("0.00"),
            monto_calculado=monto,
            concepto=concepto,
            tipo_concepto=tipo_concepto,
            concepto_codigo=concepto_codigo,
            orden=orden,
        )

    def _resolve_contabilizable_accounts(self, entity, invertir: bool = False):
        """Resolve debit/credit account codes and descriptions for a contabilizable entity.

        Returns (debe_codigo, haber_codigo, debe_desc, haber_desc).
        """
        if invertir:
            debe_codigo = entity.codigo_cuenta_haber
            haber_codigo = entity.codigo_cuenta_debe
            debe_desc = entity.descripcion_cuenta_haber or entity.nombre
            haber_desc = entity.descripcion_cuenta_debe or entity.nombre
        else:
            debe_codigo = entity.codigo_cuenta_debe
            haber_codigo = entity.codigo_cuenta_haber
            debe_desc = entity.descripcion_cuenta_debe or entity.nombre
            haber_desc = entity.descripcion_cuenta_haber or entity.nombre
        return debe_codigo, haber_codigo, debe_desc, haber_desc

    def _check_is_loan_advance(self, detalle, empleado) -> tuple[bool, str | None]:
        """Check if a detail line represents a loan/advance deduction."""
        if detalle.deduccion_id:
            deduccion = self.session.get(Deduccion, detalle.deduccion_id)
            if not deduccion:
                return False, None
            adelantos = (
                self.session.execute(db.select(Adelanto).filter_by(empleado_id=empleado.id, deduccion_id=deduccion.id))
                .scalars()
                .all()
            )
        elif detalle.codigo and detalle.codigo.startswith("ADELANTO_"):
            adelantos = (
                self.session.execute(
                    db.select(Adelanto).filter(
                        Adelanto.empleado_id == empleado.id,
                        Adelanto.deduccion_id.is_(None),
                    )
                )
                .scalars()
                .all()
            )
        else:
            return False, None

        if not adelantos:
            return False, None
        cuenta_control_prestamo = None
        for adelanto in adelantos:
            if adelanto.estado in ("approved", "applied"):
                cuenta_control_prestamo = adelanto.cuenta_haber
                break
        return True, cuenta_control_prestamo

    def _build_loan_advance_lines(
        self,
        comprobante,
        ne,
        empleado,
        empleado_nombre,
        centro_costos,
        detalle,
        cuenta_control_prestamo,
        salary_accounts,
        orden,
        null_account_count,
        total_debitos,
        total_creditos,
    ):
        """Build debit/credit lines for a loan/advance detail."""
        detalle_monto = round_money(detalle.monto)

        # Debit: Salary Payable
        orden += 1
        salary_payable_account = salary_accounts["codigo_cuenta_haber_salario"]
        if salary_payable_account is None:
            null_account_count += 1
        linea_debe = self._create_line(
            comprobante.id,
            ne,
            empleado,
            empleado_nombre,
            centro_costos,
            salary_payable_account,
            (
                (salary_accounts["descripcion_cuenta_haber_salario"] or "Salario por Pagar")
                if salary_payable_account
                else None
            ),
            "debito",
            detalle_monto,
            detalle.descripcion or CONCEPTO_PRESTAMO_ADELANTO,
            "loan",
            detalle.codigo,
            orden,
        )
        self.session.add(linea_debe)
        total_debitos += detalle_monto

        # Credit: Loan Control Account
        orden += 1
        if cuenta_control_prestamo is None:
            null_account_count += 1
        linea_haber = self._create_line(
            comprobante.id,
            ne,
            empleado,
            empleado_nombre,
            centro_costos,
            cuenta_control_prestamo,
            "Cuenta de Control Préstamos/Adelantos" if cuenta_control_prestamo else None,
            "credito",
            detalle_monto,
            detalle.descripcion or CONCEPTO_PRESTAMO_ADELANTO,
            "loan",
            detalle.codigo,
            orden,
        )
        self.session.add(linea_haber)
        total_creditos += detalle_monto

        return orden, null_account_count, total_debitos, total_creditos

    @staticmethod
    def _salary_accounting_snapshot(nomina: Nomina, planilla: Planilla) -> dict[str, str | None]:
        """Resolve frozen base-salary accounts, with a legacy live fallback."""
        context = (nomina.catalogos_snapshot or {}).get("contexto_planilla", {})
        stored = context.get("cuentas_salario") if isinstance(context, dict) else None
        if isinstance(stored, dict):
            return {
                "codigo_cuenta_debe_salario": stored.get("codigo_cuenta_debe_salario"),
                "descripcion_cuenta_debe_salario": stored.get("descripcion_cuenta_debe_salario"),
                "codigo_cuenta_haber_salario": stored.get("codigo_cuenta_haber_salario"),
                "descripcion_cuenta_haber_salario": stored.get("descripcion_cuenta_haber_salario"),
            }
        return {
            "codigo_cuenta_debe_salario": planilla.codigo_cuenta_debe_salario,
            "descripcion_cuenta_debe_salario": planilla.descripcion_cuenta_debe_salario,
            "codigo_cuenta_haber_salario": planilla.codigo_cuenta_haber_salario,
            "descripcion_cuenta_haber_salario": planilla.descripcion_cuenta_haber_salario,
        }

    def _build_concept_lines(
        self,
        comprobante,
        nomina,
        ne,
        empleado,
        empleado_nombre,
        centro_costos,
        detalle,
        orden,
        null_account_count,
        total_debitos,
        total_creditos,
    ):
        """Build debit/credit lines for income, deduction, or benefit details."""
        entity = None
        tipo_concepto = None
        invertir = False

        snapshot_entry = self._accounting_snapshot_for_detail(nomina, detalle)

        if detalle.tipo == "income" and detalle.percepcion_id:
            entity = self.session.get(Percepcion, detalle.percepcion_id)
            tipo_concepto = "percepcion"
            invertir = (
                snapshot_entry.get("invertir_asiento_contable", getattr(entity, "invertir_asiento_contable", False))
                if snapshot_entry
                else getattr(entity, "invertir_asiento_contable", False)
            )
        elif detalle.tipo == "deduction" and detalle.deduccion_id:
            entity = self.session.get(Deduccion, detalle.deduccion_id)
            tipo_concepto = "deduction"
            invertir = getattr(entity, "invertir_asiento_contable", False) if entity else False
        elif detalle.tipo == "benefit" and detalle.prestacion_id:
            entity = self.session.get(Prestacion, detalle.prestacion_id)
            tipo_concepto = "benefit"

        if not entity and not snapshot_entry:
            return orden, null_account_count, total_debitos, total_creditos

        contabilizable = (
            snapshot_entry.get("contabilizable", getattr(entity, "contabilizable", False))
            if snapshot_entry
            else entity.contabilizable
        )
        if not contabilizable:
            return orden, null_account_count, total_debitos, total_creditos

        nombre = snapshot_entry.get("nombre", getattr(entity, "nombre", "")) if snapshot_entry else entity.nombre
        codigo = snapshot_entry.get("codigo", getattr(entity, "codigo", detalle.codigo)) if snapshot_entry else entity.codigo
        if tipo_concepto == "benefit":
            debe_codigo = snapshot_entry.get("codigo_cuenta_debe", getattr(entity, "codigo_cuenta_debe", None)) if snapshot_entry else entity.codigo_cuenta_debe
            haber_codigo = snapshot_entry.get("codigo_cuenta_haber", getattr(entity, "codigo_cuenta_haber", None)) if snapshot_entry else entity.codigo_cuenta_haber
            debe_desc = (snapshot_entry.get("descripcion_cuenta_debe") or nombre) if debe_codigo and snapshot_entry else (entity.descripcion_cuenta_debe or entity.nombre if entity.codigo_cuenta_debe else None)
            haber_desc = (snapshot_entry.get("descripcion_cuenta_haber") or nombre) if haber_codigo and snapshot_entry else (entity.descripcion_cuenta_haber or entity.nombre if entity.codigo_cuenta_haber else None)
        else:
            if snapshot_entry:
                if invertir:
                    debe_codigo = snapshot_entry.get("codigo_cuenta_haber")
                    haber_codigo = snapshot_entry.get("codigo_cuenta_debe")
                    debe_desc = snapshot_entry.get("descripcion_cuenta_haber") or nombre
                    haber_desc = snapshot_entry.get("descripcion_cuenta_debe") or nombre
                else:
                    debe_codigo = snapshot_entry.get("codigo_cuenta_debe")
                    haber_codigo = snapshot_entry.get("codigo_cuenta_haber")
                    debe_desc = snapshot_entry.get("descripcion_cuenta_debe") or nombre
                    haber_desc = snapshot_entry.get("descripcion_cuenta_haber") or nombre
            else:
                debe_codigo, haber_codigo, debe_desc, haber_desc = self._resolve_contabilizable_accounts(entity, invertir)

        detalle_monto = round_money(detalle.monto)

        # Debit line
        orden += 1
        if debe_codigo is None:
            null_account_count += 1
        linea_debe = self._create_line(
            comprobante.id,
            ne,
            empleado,
            empleado_nombre,
            centro_costos,
            debe_codigo,
            debe_desc if debe_codigo else None,
            "debito",
            detalle_monto,
            detalle.descripcion or nombre,
            tipo_concepto,
            codigo,
            orden,
        )
        self.session.add(linea_debe)
        total_debitos += detalle_monto

        # Credit line
        orden += 1
        if haber_codigo is None:
            null_account_count += 1
        linea_haber = self._create_line(
            comprobante.id,
            ne,
            empleado,
            empleado_nombre,
            centro_costos,
            haber_codigo,
            haber_desc if haber_codigo else None,
            "credito",
            detalle_monto,
            detalle.descripcion or nombre,
            tipo_concepto,
            codigo,
            orden,
        )
        self.session.add(linea_haber)
        total_creditos += detalle_monto

        return orden, null_account_count, total_debitos, total_creditos

    @staticmethod
    def _accounting_snapshot_for_detail(nomina: Nomina, detalle: NominaDetalle) -> dict[str, Any] | None:
        """Return frozen accounting metadata for one historical concept detail."""
        catalogos = nomina.catalogos_snapshot or {}
        detail_types = {
            "income": ("percepciones", detalle.percepcion_id),
            "deduction": ("deducciones", detalle.deduccion_id),
            "benefit": ("prestaciones", detalle.prestacion_id),
        }
        category, concept_id = detail_types.get(detalle.tipo, (None, None))
        if not category or not concept_id:
            return None
        for entry in catalogos.get(category, []):
            if entry.get("id") == concept_id:
                return entry
        return None

    def _build_paid_vacation_liability_lines(
        self,
        comprobante: ComprobanteContable,
        nomina: Nomina,
        planilla: Planilla,
        nomina_empleados: list[NominaEmpleado],
        orden: int,
        null_account_count: int,
    ) -> tuple[Decimal, Decimal, int, int]:
        """Build accounting lines for paid vacation liability movements tied to this payroll."""
        total_debitos = Decimal("0.00")
        total_creditos = Decimal("0.00")

        nomina_empleado_ids = [ne.id for ne in nomina_empleados if ne.id]
        if not nomina_empleado_ids:
            return total_debitos, total_creditos, orden, null_account_count

        # ACCRUAL entries are linked by reference_type=nomina_empleado.
        accrual_entries = (
            self.session.execute(
                db.select(VacationLedger).filter(
                    VacationLedger.reference_type == "nomina_empleado",
                    VacationLedger.reference_id.in_(nomina_empleado_ids),
                )
            )
            .scalars()
            .all()
        )

        # USAGE entries created during payroll use reference_type=vacation_novelty.
        usage_entries = (
            self.session.execute(
                db.select(VacationLedger)
                .join(
                    NominaNovedad,
                    db.and_(
                        NominaNovedad.vacation_novelty_id == VacationLedger.reference_id,
                        VacationLedger.reference_type == "vacation_novelty",
                    ),
                )
                .filter(
                    NominaNovedad.nomina_id == nomina.id,
                    NominaNovedad.es_descanso_vacaciones.is_(True),
                )
            )
            .scalars()
            .all()
        )

        ledger_entries = [*accrual_entries, *usage_entries]

        nomina_empleado_by_id = {ne.id: ne for ne in nomina_empleados}
        nomina_empleado_by_empleado_id = {ne.empleado_id: ne for ne in nomina_empleados if ne.empleado_id}
        dias_base = self._get_vacation_days_base(planilla.empresa_id)
        if dias_base <= 0:
            dias_base = Decimal("30")

        for entry in ledger_entries:
            ne = None
            if entry.reference_type == "nomina_empleado":
                ne = nomina_empleado_by_id.get(entry.reference_id)
            elif entry.reference_type == "vacation_novelty":
                ne = nomina_empleado_by_empleado_id.get(entry.empleado_id)

            policy = entry.account.policy if entry.account and entry.account.policy else None
            policy_snapshot = self._vacation_policy_snapshot(nomina, policy.id if policy else None)
            is_paid_vacation = (
                policy_snapshot.get("son_vacaciones_pagadas", getattr(policy, "son_vacaciones_pagadas", False))
                if policy_snapshot
                else getattr(policy, "son_vacaciones_pagadas", False)
            )
            if not ne or not ne.empleado or not policy or not is_paid_vacation:
                continue

            empleado = ne.empleado
            centro_costos = ne.centro_costos_snapshot or empleado.centro_costos
            empleado_nombre_completo = f"{empleado.primer_nombre} {empleado.primer_apellido}"

            units = Decimal(str(abs(entry.quantity)))
            # Use employee's monthly salary and apply currency conversion from payroll
            # ne.sueldo_base_historico stores period salary, but vacation liability must use monthly salary
            salario_mensual = Decimal(str(empleado.salario_base or Decimal("0.00")))
            tipo_cambio = Decimal(str(ne.tipo_cambio_aplicado or Decimal("1.00")))
            salario_base = salario_mensual * tipo_cambio
            porcentaje_pago = Decimal(
                str(
                    policy_snapshot.get(
                        "porcentaje_pago_vacaciones",
                        policy.porcentaje_pago_vacaciones or Decimal("100.00"),
                    )
                    if policy_snapshot
                    else policy.porcentaje_pago_vacaciones or Decimal("100.00")
                )
            ) / Decimal("100")
            monto = round_money((salario_base / dias_base) * units * porcentaje_pago)
            if monto <= 0:
                continue

            cuenta_debito = (
                policy_snapshot.get("cuenta_debito_vacaciones_pagadas", policy.cuenta_debito_vacaciones_pagadas)
                if policy_snapshot
                else policy.cuenta_debito_vacaciones_pagadas
            )
            cuenta_credito = (
                policy_snapshot.get("cuenta_credito_vacaciones_pagadas", policy.cuenta_credito_vacaciones_pagadas)
                if policy_snapshot
                else policy.cuenta_credito_vacaciones_pagadas
            )
            desc_debito = (
                policy_snapshot.get(
                    "descripcion_cuenta_debito_vacaciones_pagadas",
                    policy.descripcion_cuenta_debito_vacaciones_pagadas,
                )
                if policy_snapshot
                else policy.descripcion_cuenta_debito_vacaciones_pagadas
            ) or "Gasto por vacaciones pagadas"
            desc_credito = (
                policy_snapshot.get(
                    "descripcion_cuenta_credito_vacaciones_pagadas",
                    policy.descripcion_cuenta_credito_vacaciones_pagadas,
                )
                if policy_snapshot
                else policy.descripcion_cuenta_credito_vacaciones_pagadas
            ) or "Pasivo laboral vacaciones"

            if entry.entry_type == "usage":
                cuenta_debito, cuenta_credito = cuenta_credito, cuenta_debito
                desc_debito, desc_credito = desc_credito, desc_debito

            orden += 1
            if cuenta_debito is None:
                null_account_count += 1
            linea_debe = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id=ne.id,
                empleado_id=empleado.id,
                empleado_codigo=empleado.codigo_empleado,
                empleado_nombre=empleado_nombre_completo,
                codigo_cuenta=cuenta_debito,
                descripcion_cuenta=(desc_debito if cuenta_debito else None),
                centro_costos=centro_costos,
                tipo_debito_credito="debito",
                debito=monto,
                credito=Decimal("0.00"),
                monto_calculado=monto,
                concepto=CONCEPTO_VACACIONES_PAGADAS_DESC,
                tipo_concepto="vacation_liability",
                concepto_codigo=CONCEPTO_VACACIONES_PAGADAS,
                orden=orden,
            )
            self.session.add(linea_debe)
            total_debitos += monto

            orden += 1
            if cuenta_credito is None:
                null_account_count += 1
            linea_haber = ComprobanteContableLinea(
                comprobante_id=comprobante.id,
                nomina_empleado_id=ne.id,
                empleado_id=empleado.id,
                empleado_codigo=empleado.codigo_empleado,
                empleado_nombre=empleado_nombre_completo,
                codigo_cuenta=cuenta_credito,
                descripcion_cuenta=(desc_credito if cuenta_credito else None),
                centro_costos=centro_costos,
                tipo_debito_credito="credito",
                debito=Decimal("0.00"),
                credito=monto,
                monto_calculado=monto,
                concepto=CONCEPTO_VACACIONES_PAGADAS_DESC,
                tipo_concepto="vacation_liability",
                concepto_codigo=CONCEPTO_VACACIONES_PAGADAS,
                orden=orden,
            )
            self.session.add(linea_haber)
            total_creditos += monto

        return total_debitos, total_creditos, orden, null_account_count

    @staticmethod
    def _vacation_policy_snapshot(nomina: Nomina, policy_id: str | None) -> dict[str, Any] | None:
        """Return the frozen paid-vacation policy configuration for a voucher."""
        if not policy_id:
            return None
        vacation_data = (nomina.catalogos_snapshot or {}).get("vacaciones", {})
        if not isinstance(vacation_data, dict):
            return None
        for policy in vacation_data.get("vacation_policies", []):
            if policy.get("id") == policy_id:
                return policy
        return None

    def generate_accounting_voucher(
        self, nomina: Nomina, planilla: Planilla, fecha_calculo: date | None = None, usuario: str | None = None
    ) -> ComprobanteContable:
        """Backward-compatible alias for audit voucher generation."""
        return self.generate_audit_voucher(nomina, planilla, fecha_calculo, usuario)

    def generate_audit_voucher(
        self, nomina: Nomina, planilla: Planilla, fecha_calculo: date | None = None, usuario: str | None = None
    ) -> ComprobanteContable:
        """Generate accounting voucher for a nomina with individual lines per employee.

        Args:
            nomina: The nomina to generate voucher for
            planilla: The planilla configuration
            fecha_calculo: Calculation date (defaults to nomina periodo_fin)
            usuario: User generating/regenerating the voucher

        Returns:
            ComprobanteContable with generated line entries
        """
        from datetime import datetime, timezone

        # Validate configuration
        _, warnings = self.validate_accounting_configuration(planilla)

        # Use nomina's calculation date or periodo_fin
        if fecha_calculo is None:
            fecha_calculo = nomina.fecha_calculo_original or nomina.periodo_fin
        # Generate voucher concept
        concepto = (
            f"Nómina {planilla.nombre}"
            + f" - Período {nomina.periodo_inicio.strftime('%d/%m/%Y')} al "
            + f"{nomina.periodo_fin.strftime('%d/%m/%Y')}"
        )

        # Get or create comprobante
        comprobante = self.session.execute(
            db.select(ComprobanteContable).filter_by(nomina_id=nomina.id)
        ).scalar_one_or_none()

        if comprobante:
            # Regenerating - update modification audit trail
            self.session.execute(
                db.delete(ComprobanteContableLinea).where(ComprobanteContableLinea.comprobante_id == comprobante.id)
            )
            self.session.flush()
            # Update header information
            comprobante.fecha_calculo = fecha_calculo
            comprobante.concepto = concepto
            comprobante.moneda_id = planilla.moneda_id
            comprobante.advertencias = warnings
            # Update modification tracking
            comprobante.modificado_por = usuario or nomina.generado_por
            comprobante.fecha_modificacion = datetime.now(timezone.utc)
            comprobante.veces_modificado += 1
        else:
            # Creating new - set initial audit trail
            # Check if nomina is already applied to set aplicado_por
            from coati_payroll.enums import NominaEstado

            aplicado_por = None
            fecha_aplicacion = None
            if nomina.estado in (NominaEstado.APLICADO, NominaEstado.PAGADO):
                aplicado_por = nomina.aplicado_por or usuario or nomina.generado_por
                fecha_aplicacion = nomina.aplicado_en or datetime.now(timezone.utc)

            comprobante = ComprobanteContable(
                nomina_id=nomina.id,
                fecha_calculo=fecha_calculo,
                concepto=concepto,
                moneda_id=planilla.moneda_id,
                total_debitos=Decimal("0.00"),
                total_creditos=Decimal("0.00"),
                balance=Decimal("0.00"),
                advertencias=warnings,
                aplicado_por=aplicado_por,
                fecha_aplicacion=fecha_aplicacion,
                veces_modificado=0,
            )
            self.session.add(comprobante)
            self.session.flush()

        # Get all nomina employees with their details
        nomina_empleados = (
            self.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=nomina.id)).scalars().all()
        )

        # Accumulate totals
        total_debitos = Decimal("0.00")
        total_creditos = Decimal("0.00")
        orden = 0
        null_account_count = 0
        salary_accounts = self._salary_accounting_snapshot(nomina, planilla)

        # Process each employee
        for ne in nomina_empleados:
            empleado = ne.empleado
            centro_costos = ne.centro_costos_snapshot or empleado.centro_costos
            empleado_nombre_completo = f"{empleado.primer_nombre} {empleado.primer_apellido}"

            # 1. Base Salary Accounting
            salario_base = round_money(ne.sueldo_base_historico)

            # Debit: Salary Expense
            orden += 1
            if salary_accounts["codigo_cuenta_debe_salario"] is None:
                null_account_count += 1
            linea_debe = self._create_line(
                comprobante.id,
                ne,
                empleado,
                empleado_nombre_completo,
                centro_costos,
                salary_accounts["codigo_cuenta_debe_salario"],
                (
                    salary_accounts["descripcion_cuenta_debe_salario"]
                    or ("Gasto por Salario" if salary_accounts["codigo_cuenta_debe_salario"] else None)
                ),
                "debito",
                salario_base,
                CONCEPTO_SALARIO_BASE_DESC,
                "salario_base",
                CONCEPTO_SALARIO_BASE,
                orden,
            )
            self.session.add(linea_debe)
            total_debitos += salario_base

            # Credit: Salary Payable
            orden += 1
            if salary_accounts["codigo_cuenta_haber_salario"] is None:
                null_account_count += 1
            linea_haber = self._create_line(
                comprobante.id,
                ne,
                empleado,
                empleado_nombre_completo,
                centro_costos,
                salary_accounts["codigo_cuenta_haber_salario"],
                (
                    salary_accounts["descripcion_cuenta_haber_salario"]
                    or ("Salario por Pagar" if salary_accounts["codigo_cuenta_haber_salario"] else None)
                ),
                "credito",
                salario_base,
                CONCEPTO_SALARIO_BASE_DESC,
                "salario_base",
                CONCEPTO_SALARIO_BASE,
                orden,
            )
            self.session.add(linea_haber)
            total_creditos += salario_base

            # 2. Process Loans and Advances (special treatment)
            detalles = (
                self.session.execute(
                    db.select(NominaDetalle).filter_by(nomina_empleado_id=ne.id).order_by(NominaDetalle.orden)
                )
                .scalars()
                .all()
            )

            for detalle in detalles:
                is_loan_advance, cuenta_control_prestamo = self._check_is_loan_advance(detalle, empleado)

                if is_loan_advance:
                    orden, null_account_count, total_debitos, total_creditos = self._build_loan_advance_lines(
                        comprobante,
                        ne,
                        empleado,
                        empleado_nombre_completo,
                        centro_costos,
                        detalle,
                        cuenta_control_prestamo,
                        salary_accounts,
                        orden,
                        null_account_count,
                        total_debitos,
                        total_creditos,
                    )
                else:
                    orden, null_account_count, total_debitos, total_creditos = self._build_concept_lines(
                        comprobante,
                        nomina,
                        ne,
                        empleado,
                        empleado_nombre_completo,
                        centro_costos,
                        detalle,
                        orden,
                        null_account_count,
                        total_debitos,
                        total_creditos,
                    )

        vac_debitos, vac_creditos, orden, null_account_count = self._build_paid_vacation_liability_lines(
            comprobante,
            nomina,
            planilla,
            nomina_empleados,
            orden,
            null_account_count,
        )
        total_debitos += vac_debitos
        total_creditos += vac_creditos

        # Calculate balance (should be 0 for balanced voucher)
        total_debitos = round_money(total_debitos)
        total_creditos = round_money(total_creditos)
        balance = round_money(total_debitos - total_creditos)

        # Validate balance
        if balance != Decimal("0.00"):
            balance_warning = (
                f"ADVERTENCIA: El comprobante no está balanceado. "
                f"Débitos: {total_debitos}, Créditos: {total_creditos}, "
                f"Diferencia: {abs(balance)}"
            )
            if balance_warning not in warnings:
                warnings.append(balance_warning)

        if null_account_count:
            warning_message = (
                "ADVERTENCIA: La configuración contable está incompleta. "
                f"Se detectaron {null_account_count} líneas con cuenta contable NULL."
            )
            if warning_message not in warnings:
                warnings.append(warning_message)

        # Update comprobante totals
        comprobante.total_debitos = total_debitos
        comprobante.total_creditos = total_creditos
        comprobante.balance = balance
        comprobante.advertencias = warnings

        return comprobante

    def validate_line_integrity(self, comprobante: ComprobanteContable) -> None:
        """Validate integrity rules for voucher lines."""
        lineas = (
            self.session.execute(db.select(ComprobanteContableLinea).filter_by(comprobante_id=comprobante.id))
            .scalars()
            .all()
        )
        errores = []
        for linea in lineas:
            debito = round_money(linea.debito)
            credito = round_money(linea.credito)
            monto_calculado = round_money(linea.monto_calculado)
            tiene_debito = debito > 0
            tiene_credito = credito > 0

            if tiene_debito == tiene_credito:
                errores.append(
                    f"Línea {linea.id}: debe contener solo débito o crédito (debito={debito}, credito={credito})."
                )

            if monto_calculado != round_money(debito + credito):
                errores.append(
                    "Línea "
                    f"{linea.id}: monto_calculado inconsistente "
                    f"(monto_calculado={monto_calculado}, debito+credito={debito + credito})."
                )

            if linea.tipo_debito_credito == "debito" and not (tiene_debito and not tiene_credito):
                errores.append(f"Línea {linea.id}: tipo_debito_credito=debito no coincide con montos.")
            elif linea.tipo_debito_credito == "credito" and not (tiene_credito and not tiene_debito):
                errores.append(f"Línea {linea.id}: tipo_debito_credito=credito no coincide con montos.")
            elif linea.tipo_debito_credito not in ("debito", "credito"):
                errores.append(f"Línea {linea.id}: tipo_debito_credito inválido ({linea.tipo_debito_credito}).")

        if errores:
            raise ValueError("Integridad de líneas inválida: " + " | ".join(errores))

    def summarize_voucher(self, comprobante: ComprobanteContable) -> list[dict[str, Any]]:
        """Summarize voucher lines by account and cost center with netting.

        Groups lines by (codigo_cuenta, centro_costos) and nets debits/credits.
        If same account+cost center has both debits and credits, they are netted
        and only one line with the net amount is shown.

        Lines with NULL accounts are skipped from summarization as they indicate
        incomplete accounting configuration.

        Args:
            comprobante: The comprobante to summarize

        Returns:
            List of summarized entries sorted by account code

        Raises:
            ValueError: If comprobante has NULL accounts (incomplete configuration)
        """
        self.validate_line_integrity(comprobante)
        # Dictionary to accumulate by (account, cost_center)
        summary_dict: dict[tuple[str, str | None], dict[str, Any]] = defaultdict(
            lambda: {"debito": Decimal("0.00"), "credito": Decimal("0.00"), "descripcion": ""}
        )

        # Get all lines
        lineas = (
            self.session.execute(
                db.select(ComprobanteContableLinea)
                .filter_by(comprobante_id=comprobante.id)
                .order_by(ComprobanteContableLinea.orden)
            )
            .scalars()
            .all()
        )

        # Check for NULL accounts and raise error if found
        null_account_lines = [linea for linea in lineas if linea.codigo_cuenta is None]
        if null_account_lines:
            raise ValueError(
                "No se puede generar comprobante sumarizado: existen líneas con cuentas contables sin configurar. "
                "Por favor configure todas las cuentas contables o utilice el comprobante de auditoría."
            )

        # Accumulate by account + cost center (only lines with valid accounts)
        for linea in lineas:
            if linea.codigo_cuenta is None:
                continue  # Skip NULL accounts

            key = (linea.codigo_cuenta, linea.centro_costos)
            summary_dict[key]["debito"] += round_money(linea.debito)
            summary_dict[key]["credito"] += round_money(linea.credito)
            # Use first description found for this account
            if not summary_dict[key]["descripcion"]:
                summary_dict[key]["descripcion"] = linea.descripcion_cuenta or ""

        # Create summarized entries with netting
        summarized_entries = []
        for (codigo_cuenta, centro_costos), amounts in summary_dict.items():
            debito = amounts["debito"]
            credito = amounts["credito"]

            # Net debits and credits
            if debito > credito:
                monto_neto = round_money(debito - credito)
                summarized_entries.append(
                    {
                        "codigo_cuenta": codigo_cuenta,
                        "descripcion": amounts["descripcion"],
                        "centro_costos": centro_costos,
                        "debito": monto_neto,
                        "credito": Decimal("0.00"),
                    }
                )
            elif credito > debito:
                monto_neto = round_money(credito - debito)
                summarized_entries.append(
                    {
                        "codigo_cuenta": codigo_cuenta,
                        "descripcion": amounts["descripcion"],
                        "centro_costos": centro_costos,
                        "debito": Decimal("0.00"),
                        "credito": monto_neto,
                    }
                )
            # If debito == credito, they cancel out completely, so line is excluded from summary
            # This is intentional: zero-balance entries don't need to appear in the summarized voucher

        # Sort by account code and cost center
        summarized_entries.sort(key=lambda x: (x["codigo_cuenta"], x["centro_costos"] or ""))

        return summarized_entries

    def get_detailed_voucher_by_employee(self, comprobante: ComprobanteContable) -> list[dict[str, Any]]:
        """Get detailed voucher lines grouped by employee for audit purposes.

        Args:
            comprobante: The comprobante to get details for

        Returns:
            List of entries grouped by employee with all their accounting lines
        """
        detailed_entries = []

        # Get all lines grouped by employee using the denormalized employee info
        lineas = (
            self.session.execute(
                db.select(ComprobanteContableLinea)
                .filter_by(comprobante_id=comprobante.id)
                .order_by(ComprobanteContableLinea.empleado_codigo, ComprobanteContableLinea.orden)
            )
            .scalars()
            .all()
        )

        # Group by employee
        current_empleado_codigo = None
        current_entry = None

        for linea in lineas:
            if linea.empleado_codigo != current_empleado_codigo:
                # New employee, save previous and start new
                if current_entry:
                    detailed_entries.append(current_entry)

                current_empleado_codigo = linea.empleado_codigo
                current_entry = {
                    "empleado_codigo": linea.empleado_codigo,
                    "empleado_nombre": linea.empleado_nombre,
                    "centro_costos": linea.centro_costos,
                    "lineas": [],
                }

            if current_entry is None:
                continue

            # Add line to current employee
            current_entry["lineas"].append(
                {
                    "concepto": linea.concepto,
                    "tipo_concepto": linea.tipo_concepto,
                    "codigo_cuenta": linea.codigo_cuenta,
                    "descripcion_cuenta": linea.descripcion_cuenta,
                    "debito": linea.debito,
                    "credito": linea.credito,
                }
            )

        # Don't forget the last employee
        if current_entry:
            detailed_entries.append(current_entry)

        return detailed_entries
