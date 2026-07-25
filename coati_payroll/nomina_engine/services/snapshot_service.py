"""Snapshot Service for Payroll Recalculation Consistency.

This service captures immutable snapshots of all configuration data needed
to ensure payroll calculations can be recalculated consistently.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from coati_payroll.model import (
    ConfiguracionCalculos,
    Deduccion,
    NominaNovedad,
    Percepcion,
    Planilla,
    PlanillaEmpleado,
    Prestacion,
    TipoCambio,
    VacationNovelty,
    VacationPolicy,
    db,
)


class SnapshotService:
    """Service for capturing configuration snapshots for payroll consistency."""

    def __init__(self, session):
        self.session = session

    def capture_configuration_snapshot(self, empresa_id: str) -> dict[str, Any]:
        """Capture complete company configuration snapshot.

        Args:
            empresa_id: Company ID

        Returns:
            Dictionary with all configuration values
        """
        config = self.session.execute(
            db.select(ConfiguracionCalculos).filter(
                ConfiguracionCalculos.empresa_id == empresa_id,
                ConfiguracionCalculos.activo.is_(True),
            )
        ).scalar_one_or_none()

        if not config:
            return {}

        return {
            "empresa_id": config.empresa_id,
            "pais_id": config.pais_id,
            "dias_mes_nomina": config.dias_mes_nomina,
            "dias_anio_nomina": config.dias_anio_nomina,
            "horas_jornada_diaria": str(config.horas_jornada_diaria),
            "dias_mes_vacaciones": config.dias_mes_vacaciones,
            "dias_anio_vacaciones": config.dias_anio_vacaciones,
            "considerar_bisiesto_vacaciones": config.considerar_bisiesto_vacaciones,
            "dias_anio_financiero": config.dias_anio_financiero,
            "meses_anio_financiero": config.meses_anio_financiero,
            "dias_quincena": config.dias_quincena,
            "liquidacion_modo_dias": config.liquidacion_modo_dias,
            "liquidacion_factor_calendario": config.liquidacion_factor_calendario,
            "liquidacion_factor_laboral": config.liquidacion_factor_laboral,
            "dias_mes_antiguedad": config.dias_mes_antiguedad,
            "dias_anio_antiguedad": config.dias_anio_antiguedad,
            "activo": config.activo,
        }

    def capture_exchange_rates_snapshot(self, planilla: Planilla, fecha_calculo: date) -> dict[str, Any]:
        """Capture exchange rates snapshot for all currencies used.

        Args:
            planilla: Planilla being processed
            fecha_calculo: Calculation date

        Returns:
            Dictionary with exchange rates by currency
        """
        rates = {}

        # Get all unique currencies from employees in this planilla
        from coati_payroll.model import Empleado

        empleados = (
            self.session.execute(
                db.select(Empleado)
                .join(PlanillaEmpleado)
                .filter(
                    PlanillaEmpleado.planilla_id == planilla.id,
                    PlanillaEmpleado.activo.is_(True),
                    Empleado.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )

        monedas_usadas = {emp.moneda_id for emp in empleados if emp.moneda_id}
        monedas_usadas.add(planilla.moneda_id)

        # Get exchange rates for each currency
        for moneda_id in monedas_usadas:
            if moneda_id == planilla.moneda_id:
                rates[moneda_id] = {"tasa": "1.00", "fecha": fecha_calculo.isoformat()}
            else:
                tipo_cambio = (
                    self.session.execute(
                        db.select(TipoCambio)
                        .filter(
                            TipoCambio.moneda_origen_id == moneda_id,
                            TipoCambio.moneda_destino_id == planilla.moneda_id,
                            TipoCambio.fecha <= fecha_calculo,
                        )
                        .order_by(TipoCambio.fecha.desc())
                    )
                    .scalars()
                    .first()
                )

                if tipo_cambio:
                    rates[moneda_id] = {
                        "tasa": str(tipo_cambio.tasa),
                        "fecha": tipo_cambio.fecha.isoformat(),
                        "moneda_destino_id": tipo_cambio.moneda_destino_id,
                    }

        return rates

    def capture_catalogs_snapshot(self, planilla: Planilla) -> dict[str, Any]:
        """Capture complete catalogs snapshot (percepciones, deducciones, prestaciones).

        Args:
            planilla: Planilla being processed

        Returns:
            Dictionary with all catalog items and their formulas
        """
        snapshot: dict[str, list[Any]] = {
            "percepciones": [],
            "deducciones": [],
            "prestaciones": [],
        }

        # Capture Percepciones linked to this planilla
        from coati_payroll.model import PlanillaIngreso

        percepciones_ids = (
            self.session.execute(
                db.select(PlanillaIngreso.percepcion_id).filter(
                    PlanillaIngreso.planilla_id == planilla.id,
                    PlanillaIngreso.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )

        if percepciones_ids:
            percepciones = (
                self.session.execute(
                    db.select(Percepcion).filter(
                        Percepcion.id.in_(percepciones_ids),
                        Percepcion.activo.is_(True),
                    )
                )
                .scalars()
                .all()
            )
        else:
            percepciones = []

        for p in percepciones:
            snapshot["percepciones"].append(
                {
                    "id": p.id,
                    "codigo": p.codigo,
                    "nombre": p.nombre,
                    "descripcion": p.descripcion,
                    "formula_tipo": p.formula_tipo,
                    "formula": p.formula,
                    "monto_default": str(p.monto_default) if p.monto_default else None,
                    "porcentaje": str(p.porcentaje) if p.porcentaje else None,
                    "gravable": p.gravable,
                    "base_calculo": p.base_calculo,
                    "estado_aprobacion": p.estado_aprobacion,
                }
            )

        # Capture Deducciones linked to this planilla
        from coati_payroll.model import PlanillaDeduccion

        deducciones_ids = (
            self.session.execute(
                db.select(PlanillaDeduccion.deduccion_id).filter(
                    PlanillaDeduccion.planilla_id == planilla.id,
                    PlanillaDeduccion.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )

        if deducciones_ids:
            deducciones = (
                self.session.execute(
                    db.select(Deduccion).filter(
                        Deduccion.id.in_(deducciones_ids),
                        Deduccion.activo.is_(True),
                    )
                )
                .scalars()
                .all()
            )
        else:
            deducciones = []

        # Also capture linked ReglaCalculo for reproducibility
        from coati_payroll.model import ReglaCalculo

        reglas_by_deduccion = {}
        if deducciones_ids:
            reglas = (
                self.session.execute(
                    db.select(ReglaCalculo).filter(
                        ReglaCalculo.deduccion_id.in_(deducciones_ids),
                        ReglaCalculo.activo.is_(True),
                    )
                )
                .scalars()
                .all()
            )
            for regla in reglas:
                if regla.deduccion_id:
                    reglas_by_deduccion[regla.deduccion_id] = {
                        "id": regla.id,
                        "codigo": regla.codigo,
                        "nombre": regla.nombre,
                        "esquema_json": regla.esquema_json,
                        "vigente_desde": regla.vigente_desde.isoformat() if regla.vigente_desde else None,
                        "vigente_hasta": regla.vigente_hasta.isoformat() if regla.vigente_hasta else None,
                    }

        for d in deducciones:
            deduccion_data = {
                "id": d.id,
                "codigo": d.codigo,
                "nombre": d.nombre,
                "descripcion": d.descripcion,
                "formula_tipo": d.formula_tipo,
                "formula": d.formula,
                "monto_default": str(d.monto_default) if d.monto_default else None,
                "porcentaje": str(d.porcentaje) if d.porcentaje else None,
                "es_impuesto": d.es_impuesto,
                "antes_impuesto": d.antes_impuesto,
                "base_calculo": d.base_calculo,
                "estado_aprobacion": d.estado_aprobacion,
            }
            # Include ReglaCalculo if linked
            if d.id in reglas_by_deduccion:
                deduccion_data["regla_calculo"] = reglas_by_deduccion[d.id]
            snapshot["deducciones"].append(deduccion_data)

        # Capture Prestaciones linked to this planilla
        from coati_payroll.model import PlanillaPrestacion

        prestaciones_ids = (
            self.session.execute(
                db.select(PlanillaPrestacion.prestacion_id).filter(
                    PlanillaPrestacion.planilla_id == planilla.id,
                    PlanillaPrestacion.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )

        if prestaciones_ids:
            prestaciones = (
                self.session.execute(
                    db.select(Prestacion).filter(
                        Prestacion.id.in_(prestaciones_ids),
                        Prestacion.activo.is_(True),
                    )
                )
                .scalars()
                .all()
            )
        else:
            prestaciones = []

        for pr in prestaciones:
            snapshot["prestaciones"].append(
                {
                    "id": pr.id,
                    "codigo": pr.codigo,
                    "nombre": pr.nombre,
                    "descripcion": pr.descripcion,
                    "formula_tipo": pr.formula_tipo,
                    "formula": pr.formula,
                    "monto_default": str(pr.monto_default) if pr.monto_default else None,
                    "porcentaje": str(pr.porcentaje) if pr.porcentaje else None,
                    "base_calculo": pr.base_calculo,
                    "tipo_acumulacion": pr.tipo_acumulacion,
                    "estado_aprobacion": pr.estado_aprobacion,
                }
            )

        return snapshot

    def capture_vacation_snapshot(
        self,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        excluded_nomina_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture vacation-specific snapshot data for reproducible processing."""
        snapshot: dict[str, Any] = {"vacation_policies": [], "vacation_novelty_ids": []}

        policies = (
            self.session.execute(
                db.select(VacationPolicy).filter(
                    VacationPolicy.activo.is_(True),
                    db.or_(
                        VacationPolicy.planilla_id == planilla.id,
                        VacationPolicy.empresa_id == planilla.empresa_id,
                        db.and_(
                            VacationPolicy.planilla_id.is_(None),
                            VacationPolicy.empresa_id.is_(None),
                        ),
                    ),
                )
            )
            .scalars()
            .all()
        )
        snapshot["vacation_policies"] = [
            {
                "id": policy.id,
                "codigo": policy.codigo,
                "planilla_id": policy.planilla_id,
                "empresa_id": policy.empresa_id,
                "unit_type": policy.unit_type,
                "accrual_method": policy.accrual_method,
                "accrual_rate": str(policy.accrual_rate),
                "prorate_by_period_days": policy.prorate_by_period_days,
                "accrual_frequency": policy.accrual_frequency,
                "min_service_days": policy.min_service_days,
                "max_balance": str(policy.max_balance) if policy.max_balance is not None else None,
                "allow_negative": policy.allow_negative,
                "partial_units_allowed": policy.partial_units_allowed,
                "rounding_rule": policy.rounding_rule,
                "accrue_during_leave": policy.accrue_during_leave,
            }
            for policy in policies
        ]

        condition = NominaNovedad.nomina_id.is_(None)
        if excluded_nomina_id:
            condition = db.or_(
                NominaNovedad.nomina_id.is_(None),
                NominaNovedad.nomina_id == excluded_nomina_id,
            )

        novelties = (
            self.session.execute(
                db.select(VacationNovelty.id)
                .join(NominaNovedad, NominaNovedad.vacation_novelty_id == VacationNovelty.id)
                .join(PlanillaEmpleado, PlanillaEmpleado.empleado_id == NominaNovedad.empleado_id)
                .filter(
                    PlanillaEmpleado.planilla_id == planilla.id,
                    PlanillaEmpleado.activo.is_(True),
                    NominaNovedad.es_descanso_vacaciones.is_(True),
                    NominaNovedad.fecha_novedad >= periodo_inicio,
                    NominaNovedad.fecha_novedad <= periodo_fin,
                    condition,
                )
            )
            .scalars()
            .all()
        )
        snapshot["vacation_novelty_ids"] = novelties
        return snapshot

    def capture_complete_snapshot(
        self,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        fecha_calculo: date,
        excluded_nomina_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture complete snapshot of all configuration data.

        Args:
            planilla: Planilla being processed
            periodo_inicio: Payroll period start
            periodo_fin: Payroll period end
            fecha_calculo: Calculation date
            excluded_nomina_id: Optional Nomina ID to ignore in snapshot generation

        Returns:
            Complete snapshot dictionary
        """
        catalogos = self.capture_catalogs_snapshot(planilla)
        vacaciones = self.capture_vacation_snapshot(
            planilla, periodo_inicio, periodo_fin, excluded_nomina_id=excluded_nomina_id
        )
        catalogos["vacaciones"] = vacaciones

        return {
            "configuracion": self.capture_configuration_snapshot(planilla.empresa_id),
            "tipos_cambio": self.capture_exchange_rates_snapshot(planilla, fecha_calculo),
            "catalogos": catalogos,
            "vacaciones": vacaciones,
            "fecha_captura": fecha_calculo.isoformat(),
        }
