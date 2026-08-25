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

        # Get exchange rates for all non-planilla currencies in a single query
        monedas_a_consultar = [m for m in monedas_usadas if m != planilla.moneda_id]
        if monedas_a_consultar:
            tipo_cambios = (
                self.session.execute(
                    db.select(TipoCambio)
                    .filter(
                        TipoCambio.moneda_origen_id.in_(monedas_a_consultar),
                        TipoCambio.moneda_destino_id == planilla.moneda_id,
                        TipoCambio.fecha <= fecha_calculo,
                    )
                    .order_by(TipoCambio.moneda_origen_id, TipoCambio.fecha.desc())
                )
                .scalars()
                .all()
            )
            # Keep only the latest rate per origin currency
            seen: set[str] = set()
            for tc in tipo_cambios:
                if tc.moneda_origen_id not in seen:
                    seen.add(tc.moneda_origen_id)
                    rates[tc.moneda_origen_id] = {
                        "tasa": str(tc.tasa),
                        "fecha": tc.fecha.isoformat(),
                        "moneda_destino_id": tc.moneda_destino_id,
                    }

        # Add planilla's own currency at 1.00
        rates[planilla.moneda_id] = {"tasa": "1.00", "fecha": fecha_calculo.isoformat()}

        return rates

    def capture_catalogs_snapshot(self, planilla: Planilla) -> dict[str, Any]:
        """Capture complete catalogs snapshot (percepciones, deducciones, prestaciones).

        Args:
            planilla: Planilla being processed

        Returns:
            Dictionary with all catalog items and their formulas
        """
        snapshot: dict[str, Any] = {
            "percepciones": [],
            "deducciones": [],
            "prestaciones": [],
            "empleados": [],
            "contexto_planilla": {},
        }

        # Employee compensation is a calculation input, not merely display
        # metadata. Freeze it with the payroll so a later salary/currency
        # change cannot rewrite a historical recalculation.
        employees = (
            self.session.execute(
                db.select(PlanillaEmpleado)
                .filter(PlanillaEmpleado.planilla_id == planilla.id, PlanillaEmpleado.activo.is_(True))
            )
            .scalars()
            .all()
        )
        snapshot["empleados"] = [
            {
                "id": association.empleado_id,
                "salario_base": str(association.empleado.salario_base or 0),
                "moneda_id": association.empleado.moneda_id,
            }
            for association in employees
            if association.empleado_id and association.empleado
        ]

        # Capture Percepciones linked to this planilla
        from coati_payroll.model import PlanillaIngreso

        percepcion_associations = (
            self.session.execute(
                db.select(PlanillaIngreso).filter(
                    PlanillaIngreso.planilla_id == planilla.id,
                    PlanillaIngreso.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )
        percepciones_ids = [association.percepcion_id for association in percepcion_associations]
        percepcion_association_by_id = {
            association.percepcion_id: association for association in percepcion_associations
        }

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
                    "monto_default": str(p.monto_default) if p.monto_default is not None else None,
                    "porcentaje": str(p.porcentaje) if p.porcentaje is not None else None,
                    "gravable": p.gravable,
                    "base_calculo": p.base_calculo,
                    "unidad_calculo": p.unidad_calculo,
                    "contabilizable": p.contabilizable,
                    "invertir_asiento_contable": p.invertir_asiento_contable,
                    "codigo_cuenta_debe": p.codigo_cuenta_debe,
                    "descripcion_cuenta_debe": p.descripcion_cuenta_debe,
                    "codigo_cuenta_haber": p.codigo_cuenta_haber,
                    "descripcion_cuenta_haber": p.descripcion_cuenta_haber,
                    "estado_aprobacion": p.estado_aprobacion,
                    "vigente_desde": p.vigente_desde.isoformat() if p.vigente_desde else None,
                    "valido_hasta": p.valido_hasta.isoformat() if p.valido_hasta else None,
                    "asociacion": self._serialize_association(
                        percepcion_association_by_id.get(p.id),
                        ("orden", "editable", "monto_predeterminado", "porcentaje", "activo"),
                    ),
                }
            )

        # Capture Deducciones linked to this planilla
        from coati_payroll.model import PlanillaDeduccion

        deduccion_associations = (
            self.session.execute(
                db.select(PlanillaDeduccion).filter(
                    PlanillaDeduccion.planilla_id == planilla.id,
                    PlanillaDeduccion.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )
        deducciones_ids = [association.deduccion_id for association in deduccion_associations]
        deduccion_association_by_id = {association.deduccion_id: association for association in deduccion_associations}

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

        # Capture Prestaciones linked to this planilla
        from coati_payroll.model import PlanillaPrestacion

        prestacion_associations = (
            self.session.execute(
                db.select(PlanillaPrestacion).filter(
                    PlanillaPrestacion.planilla_id == planilla.id,
                    PlanillaPrestacion.activo.is_(True),
                )
            )
            .scalars()
            .all()
        )
        prestaciones_ids = [association.prestacion_id for association in prestacion_associations]
        prestacion_association_by_id = {
            association.prestacion_id: association for association in prestacion_associations
        }
        snapshot["contexto_planilla"] = {
            "moneda_id": planilla.moneda_id,
            "percepciones": [
                self._serialize_association(
                    association,
                    ("orden", "editable", "monto_predeterminado", "porcentaje", "activo"),
                )
                for association in percepcion_associations
            ],
            "deducciones": [
                self._serialize_association(
                    association,
                    (
                        "prioridad",
                        "orden",
                        "editable",
                        "monto_predeterminado",
                        "porcentaje",
                        "activo",
                        "es_obligatoria",
                        "detener_si_insuficiente",
                    ),
                )
                for association in deduccion_associations
            ],
            "prestaciones": [
                self._serialize_association(
                    association,
                    ("orden", "editable", "monto_predeterminado", "porcentaje", "activo"),
                )
                for association in prestacion_associations
            ],
            "cuentas_salario": {
                "codigo_cuenta_debe_salario": planilla.codigo_cuenta_debe_salario,
                "descripcion_cuenta_debe_salario": planilla.descripcion_cuenta_debe_salario,
                "codigo_cuenta_haber_salario": planilla.codigo_cuenta_haber_salario,
                "descripcion_cuenta_haber_salario": planilla.descripcion_cuenta_haber_salario,
            },
        }

        # Capture linked ReglaCalculo for every concept type. A historical
        # recalculation must never fall back to a mutable live rule.
        from coati_payroll.model import ReglaCalculo
        from sqlalchemy import or_

        reglas_by_concept = {}
        concept_ids = [*deducciones_ids, *percepciones_ids, *prestaciones_ids]
        if concept_ids:
            reglas = (
                self.session.execute(
                    db.select(ReglaCalculo).filter(
                        or_(
                            ReglaCalculo.deduccion_id.in_(deducciones_ids or ["__none__"]),
                            ReglaCalculo.percepcion_id.in_(percepciones_ids or ["__none__"]),
                            ReglaCalculo.prestacion_id.in_(prestaciones_ids or ["__none__"]),
                        ),
                        ReglaCalculo.activo.is_(True),
                    )
                )
                .scalars()
                .all()
            )
            for regla in reglas:
                for concept_id in (regla.deduccion_id, regla.percepcion_id, regla.prestacion_id):
                    if not concept_id:
                        continue
                    reglas_by_concept[concept_id] = {
                        "id": regla.id,
                        "codigo": regla.codigo,
                        "nombre": regla.nombre,
                        "esquema_json": regla.esquema_json,
                        "vigente_desde": regla.vigente_desde.isoformat() if regla.vigente_desde else None,
                        "vigente_hasta": regla.vigente_hasta.isoformat() if regla.vigente_hasta else None,
                    }

        for percepcion_data in snapshot["percepciones"]:
            if percepcion_data["id"] in reglas_by_concept:
                percepcion_data["regla_calculo"] = reglas_by_concept[percepcion_data["id"]]

        for d in deducciones:
            deduccion_data = {
                "id": d.id,
                "codigo": d.codigo,
                "nombre": d.nombre,
                "descripcion": d.descripcion,
                "formula_tipo": d.formula_tipo,
                "formula": d.formula,
                "monto_default": str(d.monto_default) if d.monto_default is not None else None,
                "porcentaje": str(d.porcentaje) if d.porcentaje is not None else None,
                "es_impuesto": d.es_impuesto,
                "antes_impuesto": d.antes_impuesto,
                "base_calculo": d.base_calculo,
                "unidad_calculo": d.unidad_calculo,
                "contabilizable": d.contabilizable,
                "invertir_asiento_contable": d.invertir_asiento_contable,
                "codigo_cuenta_debe": d.codigo_cuenta_debe,
                "descripcion_cuenta_debe": d.descripcion_cuenta_debe,
                "codigo_cuenta_haber": d.codigo_cuenta_haber,
                "descripcion_cuenta_haber": d.descripcion_cuenta_haber,
                "estado_aprobacion": d.estado_aprobacion,
                "vigente_desde": d.vigente_desde.isoformat() if d.vigente_desde else None,
                "valido_hasta": d.valido_hasta.isoformat() if d.valido_hasta else None,
                "regla_calculo": reglas_by_concept.get(d.id),
                "asociacion": self._serialize_association(
                    deduccion_association_by_id.get(d.id),
                    (
                        "prioridad",
                        "orden",
                        "editable",
                        "monto_predeterminado",
                        "porcentaje",
                        "activo",
                        "es_obligatoria",
                        "detener_si_insuficiente",
                    ),
                ),
            }
            snapshot["deducciones"].append(deduccion_data)

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
                    "monto_default": str(pr.monto_default) if pr.monto_default is not None else None,
                    "porcentaje": str(pr.porcentaje) if pr.porcentaje is not None else None,
                    "base_calculo": pr.base_calculo,
                    "unidad_calculo": pr.unidad_calculo,
                    "contabilizable": pr.contabilizable,
                    "codigo_cuenta_debe": pr.codigo_cuenta_debe,
                    "descripcion_cuenta_debe": pr.descripcion_cuenta_debe,
                    "codigo_cuenta_haber": pr.codigo_cuenta_haber,
                    "descripcion_cuenta_haber": pr.descripcion_cuenta_haber,
                    "tipo_acumulacion": pr.tipo_acumulacion,
                    "estado_aprobacion": pr.estado_aprobacion,
                    "vigente_desde": pr.vigente_desde.isoformat() if pr.vigente_desde else None,
                    "valido_hasta": pr.valido_hasta.isoformat() if pr.valido_hasta else None,
                    "tope_aplicacion": str(pr.tope_aplicacion) if pr.tope_aplicacion is not None else None,
                    "regla_calculo": reglas_by_concept.get(pr.id),
                    "asociacion": self._serialize_association(
                        prestacion_association_by_id.get(pr.id),
                        ("orden", "editable", "monto_predeterminado", "porcentaje", "activo"),
                    ),
                }
            )

        return snapshot

    @staticmethod
    def _serialize_association(association, fields: tuple[str, ...]) -> dict[str, Any] | None:
        """Serialize planilla-association inputs that affect a payroll result."""
        if association is None:
            return None
        result: dict[str, Any] = {"id": association.id}
        for field in fields:
            value = getattr(association, field, None)
            result[field] = (
                str(value)
                if value is not None and field in {"monto_predeterminado", "porcentaje"}
                else value
            )
        return result

    def validate_planilla_snapshot(self, planilla: Planilla, catalogos: dict[str, Any]) -> list[str]:
        """Reject recalculation when the live planilla context differs from its snapshot.

        Legacy payrolls without association metadata are intentionally skipped;
        they cannot be proven reproducible and retain their historical fallback.
        New snapshots fail closed instead of silently calculating a different
        payroll after an association, override, or active concept changes.
        """
        from coati_payroll.model import (
            PlanillaDeduccion,
            PlanillaIngreso,
            PlanillaPrestacion,
        )

        definitions = (
            (
                "percepciones",
                PlanillaIngreso,
                Percepcion,
                ("orden", "editable", "monto_predeterminado", "porcentaje", "activo"),
            ),
            (
                "deducciones",
                PlanillaDeduccion,
                Deduccion,
                (
                    "prioridad",
                    "orden",
                    "editable",
                    "monto_predeterminado",
                    "porcentaje",
                    "activo",
                    "es_obligatoria",
                    "detener_si_insuficiente",
                ),
            ),
            (
                "prestaciones",
                PlanillaPrestacion,
                Prestacion,
                ("orden", "editable", "monto_predeterminado", "porcentaje", "activo"),
            ),
        )
        errors: list[str] = []
        snapshot_context = catalogos.get("contexto_planilla")
        for key, association_model, concept_model, fields in definitions:
            entries = [entry for entry in catalogos.get(key, []) if entry.get("asociacion")]
            expected_associations = (
                snapshot_context.get(key) if isinstance(snapshot_context, dict) and key in snapshot_context else None
            )
            if expected_associations is None:
                expected_associations = [entry["asociacion"] for entry in entries]
            if snapshot_context is None and not expected_associations:
                continue

            current_associations = (
                self.session.execute(
                    db.select(association_model).filter(
                        association_model.planilla_id == planilla.id,
                        association_model.activo.is_(True),
                    )
                )
                .scalars()
                .all()
            )
            expected_ids = {association["id"] for association in expected_associations}
            current_ids = {association.id for association in current_associations}
            if expected_ids != current_ids:
                errors.append(
                    f"El contexto snapshot de {key} no coincide con las asociaciones activas actuales; "
                    "se requiere una nueva nómina en lugar de un recálculo histórico."
                )
                continue

            current_by_id = {association.id: association for association in current_associations}
            for snapshot_association in expected_associations:
                current = current_by_id.get(snapshot_association["id"])
                if not current:
                    continue
                for field in fields:
                    expected = snapshot_association.get(field)
                    actual = getattr(current, field, None)
                    actual = (
                        str(actual)
                        if actual is not None and field in {"monto_predeterminado", "porcentaje"}
                        else actual
                    )
                    if expected != actual:
                        errors.append(
                            f"Cambió el campo {field} de la asociación {snapshot_association['id']} "
                            f"para {key}; el recálculo histórico fue bloqueado."
                        )
                        break

            for entry in entries:
                concept_id = entry.get("id")
                concept = self.session.get(concept_model, concept_id)
                if not concept or not concept.activo:
                    errors.append(
                        f"El concepto {concept_id} de {key} ya no está activo o no existe; "
                        "el recálculo histórico fue bloqueado."
                    )
        self._validate_vacation_snapshot(catalogos.get("vacaciones"), errors)
        return errors

    def _validate_vacation_snapshot(self, vacation_snapshot: Any, errors: list[str]) -> None:
        """Reject a recalculation that would apply a changed vacation policy."""
        if not isinstance(vacation_snapshot, dict):
            return
        policies = vacation_snapshot.get("vacation_policies")
        if not isinstance(policies, list):
            return

        fields = (
            "planilla_id",
            "empresa_id",
            "unit_type",
            "accrual_method",
            "accrual_rate",
            "prorate_by_period_days",
            "accrual_frequency",
            "accrual_basis",
            "min_service_days",
            "seniority_tiers",
            "max_balance",
            "allow_negative",
            "partial_units_allowed",
            "rounding_rule",
            "accrue_during_leave",
        )
        for expected_policy in policies:
            if not isinstance(expected_policy, dict) or not expected_policy.get("id"):
                continue
            policy = self.session.get(VacationPolicy, expected_policy["id"])
            if not policy or not policy.activo:
                errors.append(
                    f"La política de vacaciones {expected_policy.get('id')} ya no está activa o no existe; "
                    "el recálculo histórico fue bloqueado."
                )
                continue
            for field in fields:
                expected = expected_policy.get(field)
                actual = getattr(policy, field, None)
                if field in {"accrual_rate", "max_balance"} and actual is not None:
                    actual = str(actual)
                if expected != actual:
                    errors.append(
                        f"Cambió el campo {field} de la política de vacaciones {policy.id}; "
                        "el recálculo histórico fue bloqueado."
                    )
                    break

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
                "accrual_basis": policy.accrual_basis,
                "min_service_days": policy.min_service_days,
                "seniority_tiers": policy.seniority_tiers,
                "max_balance": str(policy.max_balance) if policy.max_balance is not None else None,
                "allow_negative": policy.allow_negative,
                "partial_units_allowed": policy.partial_units_allowed,
                "rounding_rule": policy.rounding_rule,
                "accrue_during_leave": policy.accrue_during_leave,
                "son_vacaciones_pagadas": policy.son_vacaciones_pagadas,
                "porcentaje_pago_vacaciones": str(policy.porcentaje_pago_vacaciones),
                "cuenta_debito_vacaciones_pagadas": policy.cuenta_debito_vacaciones_pagadas,
                "descripcion_cuenta_debito_vacaciones_pagadas": policy.descripcion_cuenta_debito_vacaciones_pagadas,
                "cuenta_credito_vacaciones_pagadas": policy.cuenta_credito_vacaciones_pagadas,
                "descripcion_cuenta_credito_vacaciones_pagadas": policy.descripcion_cuenta_credito_vacaciones_pagadas,
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
            "fecha_captura": fecha_calculo.isoformat(),
        }
