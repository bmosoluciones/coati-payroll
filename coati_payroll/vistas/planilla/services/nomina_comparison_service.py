# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Intelligent comparison service between two payroll runs."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from coati_payroll.enums import NominaEstado
from coati_payroll.model import (
    Deduccion,
    Nomina,
    NominaComparacion,
    NominaDetalle,
    NominaEmpleado,
    NominaNovedad,
    Percepcion,
    Planilla,
    PlanillaDeduccion,
    PlanillaIngreso,
    PlanillaPrestacion,
    PlanillaReglaCalculo,
    Prestacion,
    ReglaCalculo,
    db,
    utc_now,
)


class NominaComparisonService:
    """Build and cache comparison KPIs between payroll runs."""

    OUTLIER_DELTA_ABS = Decimal("100.00")
    OUTLIER_DELTA_PCT = Decimal("5.00")
    ESTABILIDAD_PESO_AFECTACION = Decimal("0.35")
    ESTABILIDAD_PESO_SEVERIDAD = Decimal("0.25")
    ESTABILIDAD_PESO_CONCENTRACION = Decimal("0.25")
    ESTABILIDAD_PESO_CAMBIOS_ESTRUCTURALES = Decimal("0.15")

    @staticmethod
    def get_nominas_disponibles(planilla_id: str, excluir_nomina_id: str | None = None) -> list[Nomina]:
        query = db.select(Nomina).filter(Nomina.planilla_id == planilla_id).order_by(Nomina.periodo_fin.desc())
        if excluir_nomina_id:
            query = query.filter(Nomina.id != excluir_nomina_id)
        return list(db.session.execute(query).scalars().all())

    @staticmethod
    def get_nomina_base_default(nomina_actual: Nomina) -> Nomina | None:
        return db.session.execute(
            db.select(Nomina)
            .filter(Nomina.planilla_id == nomina_actual.planilla_id, Nomina.periodo_fin < nomina_actual.periodo_fin)
            .order_by(Nomina.periodo_fin.desc())
        ).scalar_one_or_none()

    @classmethod
    def compare_or_cached(cls, planilla: Planilla, nomina_base: Nomina, nomina_actual: Nomina) -> dict[str, Any]:
        base_version = cls._nomina_version(nomina_base)
        actual_version = cls._nomina_version(nomina_actual)

        cached = cls._get_cached(planilla.id, nomina_base.id, nomina_actual.id)
        if cached and cached.base_modificado_en == base_version and cached.actual_modificado_en == actual_version:
            payload = dict(cached.resumen_json or {})
            payload["cache_generado_en"] = cls._iso_utc(cached.generado_en)
            payload["es_calculo_actual"] = bool(cached.es_calculo_actual)
            payload["planilla_actual_aprobada"] = cls._planilla_actual_aprobada(nomina_actual)
            payload["flujo_aprobacion"] = cls._flujo_aprobacion(nomina_actual)
            payload["is_cached"] = True
            return payload

        payload = cls.build_comparison(planilla=planilla, nomina_base=nomina_base, nomina_actual=nomina_actual)
        now = utc_now()

        if cached:
            cached.resumen_json = payload
            cached.base_modificado_en = base_version
            cached.actual_modificado_en = actual_version
            cached.es_calculo_actual = True
            cached.planilla_actual_aprobada = cls._planilla_actual_aprobada(nomina_actual)
            cached.generado_en = now
        else:
            db.session.add(
                NominaComparacion(
                    planilla_id=planilla.id,
                    nomina_base_id=nomina_base.id,
                    nomina_actual_id=nomina_actual.id,
                    resumen_json=payload,
                    base_modificado_en=base_version,
                    actual_modificado_en=actual_version,
                    es_calculo_actual=True,
                    planilla_actual_aprobada=cls._planilla_actual_aprobada(nomina_actual),
                    generado_en=now,
                )
            )

        try:
            db.session.commit()
        except IntegrityError:
            # Concurrent requests can race to insert the same pair and hit unique constraints.
            db.session.rollback()
            cached = cls._get_cached(planilla.id, nomina_base.id, nomina_actual.id)
            if cached:
                payload = dict(cached.resumen_json or payload)
                payload["cache_generado_en"] = cls._iso_utc(cached.generado_en)
                payload["es_calculo_actual"] = bool(cached.es_calculo_actual)
                payload["planilla_actual_aprobada"] = cls._planilla_actual_aprobada(nomina_actual)
                payload["flujo_aprobacion"] = cls._flujo_aprobacion(nomina_actual)
                payload["is_cached"] = True
                return payload
            raise

        payload["is_cached"] = False
        payload["cache_generado_en"] = cls._iso_utc(now)
        payload["es_calculo_actual"] = True
        payload["planilla_actual_aprobada"] = cls._planilla_actual_aprobada(nomina_actual)
        payload["flujo_aprobacion"] = cls._flujo_aprobacion(nomina_actual)
        return payload

    @staticmethod
    def _get_cached(planilla_id: str, nomina_base_id: str, nomina_actual_id: str) -> NominaComparacion | None:
        return db.session.execute(
            db.select(NominaComparacion).filter_by(
                planilla_id=planilla_id,
                nomina_base_id=nomina_base_id,
                nomina_actual_id=nomina_actual_id,
            )
        ).scalar_one_or_none()

    @classmethod
    def refresh_after_recalculo(cls, planilla_id: str, nomina_original_id: str, nomina_nueva_id: str) -> None:
        """Re-point comparison cache rows when a payroll is recalculated into a new id."""
        comparaciones = (
            db.session.execute(
                db.select(NominaComparacion).filter(
                    NominaComparacion.planilla_id == planilla_id,
                    (NominaComparacion.nomina_base_id == nomina_original_id)
                    | (NominaComparacion.nomina_actual_id == nomina_original_id),
                )
            )
            .scalars()
            .all()
        )

        if not comparaciones:
            return

        for comparacion in comparaciones:
            nuevo_base_id = (
                nomina_nueva_id if comparacion.nomina_base_id == nomina_original_id else comparacion.nomina_base_id
            )
            nuevo_actual_id = (
                nomina_nueva_id if comparacion.nomina_actual_id == nomina_original_id else comparacion.nomina_actual_id
            )

            if nuevo_base_id == nuevo_actual_id:
                db.session.delete(comparacion)
                continue

            duplicada = db.session.execute(
                db.select(NominaComparacion).filter(
                    NominaComparacion.planilla_id == planilla_id,
                    NominaComparacion.nomina_base_id == nuevo_base_id,
                    NominaComparacion.nomina_actual_id == nuevo_actual_id,
                    NominaComparacion.id != comparacion.id,
                )
            ).scalar_one_or_none()
            if duplicada:
                db.session.delete(comparacion)
                continue

            comparacion.nomina_base_id = nuevo_base_id
            comparacion.nomina_actual_id = nuevo_actual_id
            comparacion.es_calculo_actual = False
            resumen = dict(comparacion.resumen_json or {})
            resumen["es_calculo_actual"] = False
            resumen["mensaje_calculo_actual"] = "La planilla base/actual de este cálculo ha cambiado"
            comparacion.resumen_json = resumen

    @classmethod
    def build_comparison(cls, planilla: Planilla, nomina_base: Nomina, nomina_actual: Nomina) -> dict[str, Any]:
        empleados_base = cls._load_nomina_empleados(nomina_base.id)
        empleados_actual = cls._load_nomina_empleados(nomina_actual.id)
        conceptos = cls._comparar_conceptos(nomina_base.id, nomina_actual.id)

        base_by_emp = {item.empleado_id: item for item in empleados_base}
        actual_by_emp = {item.empleado_id: item for item in empleados_actual}
        ids_base = set(base_by_emp.keys())
        ids_actual = set(actual_by_emp.keys())

        solo_base = sorted(ids_base - ids_actual)
        solo_actual = sorted(ids_actual - ids_base)
        comunes = sorted(ids_base & ids_actual)

        salarios_cambiados = []
        saldo_neto_cero = []
        saldo_neto_negativo = []
        sin_cambios = []
        outliers_neto = []
        variaciones_neto_abs: list[Decimal] = []
        variaciones_neto_pct: list[Decimal | None] = []
        variaciones_neto_detalle: list[dict[str, Any]] = []
        empleados_variacion_positiva = 0
        empleados_variacion_negativa = 0

        for empleado_id in comunes:
            base_item = base_by_emp[empleado_id]
            actual_item = actual_by_emp[empleado_id]
            base_sueldo = cls._to_decimal(base_item.sueldo_base_historico)
            actual_sueldo = cls._to_decimal(actual_item.sueldo_base_historico)
            if base_sueldo != actual_sueldo:
                salarios_cambiados.append(
                    {
                        "empleado_id": empleado_id,
                        "empleado_codigo": actual_item.empleado.codigo_empleado,
                        "nombre": cls._employee_name(actual_item),
                        "sueldo_base_anterior": cls._money(base_sueldo),
                        "sueldo_base_actual": cls._money(actual_sueldo),
                        "variacion": cls._money(actual_sueldo - base_sueldo),
                        "variacion_pct": cls._percent(cls._pct_delta(actual_sueldo, base_sueldo)),
                    }
                )

            base_bruto = cls._to_decimal(base_item.salario_bruto)
            actual_bruto = cls._to_decimal(actual_item.salario_bruto)
            base_neto = cls._to_decimal(base_item.salario_neto)
            actual_neto = cls._to_decimal(actual_item.salario_neto)

            if base_bruto == actual_bruto and base_neto == actual_neto:
                sin_cambios.append(
                    {
                        "empleado_id": empleado_id,
                        "empleado_codigo": actual_item.empleado.codigo_empleado,
                        "nombre": cls._employee_name(actual_item),
                    }
                )

            delta_neto = actual_neto - base_neto
            delta_pct = cls._pct_delta(actual_neto, base_neto)
            variaciones_neto_abs.append(abs(delta_neto))
            variaciones_neto_pct.append(delta_pct)
            variaciones_neto_detalle.append(
                {
                    "empleado_id": empleado_id,
                    "delta_neto": delta_neto,
                    "delta_neto_abs": abs(delta_neto),
                    "delta_pct": delta_pct,
                }
            )
            if delta_neto > Decimal("0"):
                empleados_variacion_positiva += 1
            elif delta_neto < Decimal("0"):
                empleados_variacion_negativa += 1

            pct_supera = delta_pct is not None and abs(delta_pct) >= cls.OUTLIER_DELTA_PCT
            if abs(delta_neto) >= cls.OUTLIER_DELTA_ABS or pct_supera:
                outliers_neto.append(
                    {
                        "empleado_id": empleado_id,
                        "empleado_codigo": actual_item.empleado.codigo_empleado,
                        "nombre": cls._employee_name(actual_item),
                        "neto_base": cls._money(base_neto),
                        "neto_actual": cls._money(actual_neto),
                        "variacion_neto": cls._money(delta_neto),
                        "variacion_neto_pct": cls._percent(delta_pct),
                        "driver": cls._driver_principal(empleado_id, conceptos["drivers_empleado"]),
                        "severidad": "alta" if abs(delta_neto) >= (cls.OUTLIER_DELTA_ABS * 2) else "media",
                    }
                )

        for item in empleados_actual:
            salario_neto = cls._to_decimal(item.salario_neto)
            if salario_neto == Decimal("0"):
                saldo_neto_cero.append(
                    {
                        "empleado_id": item.empleado_id,
                        "empleado_codigo": item.empleado.codigo_empleado,
                        "nombre": cls._employee_name(item),
                    }
                )
            if salario_neto < Decimal("0"):
                saldo_neto_negativo.append(
                    {
                        "empleado_id": item.empleado_id,
                        "empleado_codigo": item.empleado.codigo_empleado,
                        "nombre": cls._employee_name(item),
                        "neto": cls._money(salario_neto),
                    }
                )

        resumen_totales = cls._resumen_totales(
            nomina_base, nomina_actual, empleados_base, empleados_actual, ids_base, ids_actual
        )

        outliers_neto.sort(key=lambda item: abs(item["variacion_neto"]), reverse=True)
        salarios_cambiados.sort(key=lambda item: abs(item["variacion"]), reverse=True)

        alertas = {
            "rojas": {
                "neto_negativo": len(saldo_neto_negativo),
                "neto_cero": len(saldo_neto_cero),
            },
            "amarillas": {
                "outliers_neto": len(outliers_neto),
                "salario_base_cambiado": len(salarios_cambiados),
            },
            "total_rojas": len(saldo_neto_negativo) + len(saldo_neto_cero),
            "total_amarillas": len(outliers_neto) + len(salarios_cambiados),
        }

        impacto_empleados = cls._build_impacto_empleados(
            total_comunes=len(comunes),
            variaciones_neto_detalle=variaciones_neto_detalle,
            empleados_variacion_positiva=empleados_variacion_positiva,
            empleados_variacion_negativa=empleados_variacion_negativa,
        )
        concentracion_impacto = cls._build_concentracion_impacto(
            variaciones_neto_detalle=variaciones_neto_detalle,
            conceptos=conceptos,
        )
        bucket_variacion_neto = cls._build_bucket_variacion_neto(variaciones_neto_detalle)
        segmentacion = cls._build_segmentacion(base_by_emp=base_by_emp, actual_by_emp=actual_by_emp, comunes=comunes)
        ratios = cls._build_ratios(nomina_base=nomina_base, nomina_actual=nomina_actual)
        flujo_caja = {
            "variacion_total_neto": resumen_totales["variacion_total_neto"],
            "variacion_total_deducciones": resumen_totales["variacion_total_deducciones"],
            "variacion_total_bruto": resumen_totales["variacion_total_bruto"],
        }
        calidad = cls._build_calidad(
            nomina_base_id=nomina_base.id, nomina_actual_id=nomina_actual.id, empleados_actual_total=len(ids_actual)
        )
        cambios_estructurales = cls._build_cambios_estructurales(nomina_base=nomina_base, nomina_actual=nomina_actual)
        indice_estabilidad = cls._build_indice_estabilidad(
            impacto_empleados=impacto_empleados,
            outliers_neto=outliers_neto,
            concentracion_impacto=concentracion_impacto,
            cambios_estructurales=cambios_estructurales,
        )

        return {
            "nomina_base": cls._nomina_meta(nomina_base),
            "nomina_actual": cls._nomina_meta(nomina_actual),
            "resumen": resumen_totales,
            "alertas": alertas,
            "impacto_empleados": impacto_empleados,
            "concentracion_impacto": concentracion_impacto,
            "bucket_variacion_neto": bucket_variacion_neto,
            "segmentacion": segmentacion,
            "ratios": ratios,
            "flujo_caja": flujo_caja,
            "calidad": calidad,
            "cambios_estructurales": cambios_estructurales,
            "indice_estabilidad": indice_estabilidad,
            "componentes_planilla": cls._comparar_componentes_planilla(planilla.id),
            "empleados": {
                "solo_en_base": cls._employee_list(solo_base, base_by_emp),
                "solo_en_actual": cls._employee_list(solo_actual, actual_by_emp),
                "salarios_base_cambiados": salarios_cambiados,
                "saldo_neto_cero_actual": saldo_neto_cero,
                "saldo_neto_negativo_actual": saldo_neto_negativo,
                "sin_cambios": sin_cambios,
                "outliers_neto": outliers_neto,
            },
            "conceptos": conceptos,
            "vacaciones": cls._comparar_reglas_vacaciones(nomina_base.id, nomina_actual.id),
            "parametros": {
                "outlier_delta_abs": cls._money(cls.OUTLIER_DELTA_ABS),
                "outlier_delta_pct": cls._percent(cls.OUTLIER_DELTA_PCT),
            },
            "es_calculo_actual": True,
            "planilla_actual_aprobada": cls._planilla_actual_aprobada(nomina_actual),
            "flujo_aprobacion": cls._flujo_aprobacion(nomina_actual),
            "generado_en": cls._iso_utc(utc_now()),
        }

    @classmethod
    def _resumen_totales(
        cls,
        nomina_base: Nomina,
        nomina_actual: Nomina,
        empleados_base: list[NominaEmpleado],
        empleados_actual: list[NominaEmpleado],
        ids_base: set[str],
        ids_actual: set[str],
    ) -> dict[str, Any]:
        bruto_base = cls._to_decimal(nomina_base.total_bruto)
        bruto_actual = cls._to_decimal(nomina_actual.total_bruto)
        ded_base = cls._to_decimal(nomina_base.total_deducciones)
        ded_actual = cls._to_decimal(nomina_actual.total_deducciones)
        neto_base = cls._to_decimal(nomina_base.total_neto)
        neto_actual = cls._to_decimal(nomina_actual.total_neto)

        netos_base = [cls._to_decimal(item.salario_neto) for item in empleados_base]
        netos_actual = [cls._to_decimal(item.salario_neto) for item in empleados_actual]
        brutos_base = [cls._to_decimal(item.salario_bruto) for item in empleados_base]
        brutos_actual = [cls._to_decimal(item.salario_bruto) for item in empleados_actual]
        dias_calculo_base = cls._dias_periodo(nomina_base)
        dias_calculo_actual = cls._dias_periodo(nomina_actual)
        variacion_dias_calculo = (
            (dias_calculo_actual - dias_calculo_base)
            if dias_calculo_base is not None and dias_calculo_actual is not None
            else None
        )

        return {
            "empleados_base": len(ids_base),
            "empleados_actual": len(ids_actual),
            "variacion_empleados": len(ids_actual) - len(ids_base),
            "total_bruto_base": cls._money(bruto_base),
            "total_bruto_actual": cls._money(bruto_actual),
            "variacion_total_bruto": cls._money(bruto_actual - bruto_base),
            "variacion_total_bruto_pct": cls._percent(cls._pct_delta(bruto_actual, bruto_base)),
            "total_neto_base": cls._money(neto_base),
            "total_neto_actual": cls._money(neto_actual),
            "variacion_total_neto": cls._money(neto_actual - neto_base),
            "variacion_total_neto_pct": cls._percent(cls._pct_delta(neto_actual, neto_base)),
            "total_deducciones_base": cls._money(ded_base),
            "total_deducciones_actual": cls._money(ded_actual),
            "variacion_total_deducciones": cls._money(ded_actual - ded_base),
            "variacion_total_deducciones_pct": cls._percent(cls._pct_delta(ded_actual, ded_base)),
            "promedio_bruto_base": cls._money(cls._avg(brutos_base)),
            "promedio_bruto_actual": cls._money(cls._avg(brutos_actual)),
            "promedio_neto_base": cls._money(cls._avg(netos_base)),
            "promedio_neto_actual": cls._money(cls._avg(netos_actual)),
            "dias_calculo_base": dias_calculo_base,
            "dias_calculo_actual": dias_calculo_actual,
            "variacion_dias_calculo": variacion_dias_calculo,
            "mediana_bruto_base": cls._money(cls._median(brutos_base)),
            "mediana_bruto_actual": cls._money(cls._median(brutos_actual)),
            "mediana_neto_base": cls._money(cls._median(netos_base)),
            "mediana_neto_actual": cls._money(cls._median(netos_actual)),
            "dispersion_neto_base": cls._money(cls._percentile(netos_base, 95) - cls._percentile(netos_base, 5)),
            "dispersion_neto_actual": cls._money(cls._percentile(netos_actual, 95) - cls._percentile(netos_actual, 5)),
            "distribucion": {
                "std_neto_base": cls._money(cls._std_dev(netos_base)),
                "std_neto_actual": cls._money(cls._std_dev(netos_actual)),
                "iqr_neto_base": cls._money(cls._iqr(netos_base)),
                "iqr_neto_actual": cls._money(cls._iqr(netos_actual)),
            },
        }

    @staticmethod
    def _dias_periodo(nomina: Nomina) -> int | None:
        if not nomina.periodo_inicio or not nomina.periodo_fin:
            return None
        return (nomina.periodo_fin - nomina.periodo_inicio).days + 1

    @staticmethod
    def _load_nomina_empleados(nomina_id: str) -> list[NominaEmpleado]:
        return list(
            db.session.execute(
                db.select(NominaEmpleado)
                .filter(NominaEmpleado.nomina_id == nomina_id)
                .options(selectinload(NominaEmpleado.empleado))  # type: ignore[arg-type]
            )
            .scalars()
            .all()
        )

    @staticmethod
    def _comparar_componentes_planilla(planilla_id: str) -> dict[str, list[str]]:
        percepciones = (
            db.session.execute(
                db.select(Percepcion.codigo)
                .select_from(PlanillaIngreso)
                .join(Percepcion, Percepcion.id == PlanillaIngreso.percepcion_id)
                .filter(PlanillaIngreso.planilla_id == planilla_id)
            )
            .scalars()
            .all()
        )
        deducciones = (
            db.session.execute(
                db.select(Deduccion.codigo)
                .select_from(PlanillaDeduccion)
                .join(Deduccion, Deduccion.id == PlanillaDeduccion.deduccion_id)
                .filter(PlanillaDeduccion.planilla_id == planilla_id)
            )
            .scalars()
            .all()
        )
        prestaciones = (
            db.session.execute(
                db.select(Prestacion.codigo)
                .select_from(PlanillaPrestacion)
                .join(Prestacion, Prestacion.id == PlanillaPrestacion.prestacion_id)
                .filter(PlanillaPrestacion.planilla_id == planilla_id)
            )
            .scalars()
            .all()
        )
        reglas = (
            db.session.execute(
                db.select(ReglaCalculo.codigo)
                .select_from(PlanillaReglaCalculo)
                .join(ReglaCalculo, ReglaCalculo.id == PlanillaReglaCalculo.regla_calculo_id)
                .filter(PlanillaReglaCalculo.planilla_id == planilla_id)
            )
            .scalars()
            .all()
        )
        return {
            "percepciones": sorted(set(percepciones)),
            "deducciones": sorted(set(deducciones)),
            "prestaciones": sorted(set(prestaciones)),
            "reglas_calculo": sorted(set(reglas)),
        }

    @classmethod
    def _comparar_conceptos(cls, nomina_base_id: str, nomina_actual_id: str) -> dict[str, Any]:
        def aggregate(
            nomina_id: str,
        ) -> tuple[
            dict[str, dict[str, Decimal]], dict[str, dict[str, set[str]]], dict[str, dict[str, dict[str, Decimal]]]
        ]:
            rows = db.session.execute(
                db.select(NominaDetalle.tipo, NominaDetalle.codigo, NominaDetalle.monto, NominaEmpleado.empleado_id)
                .join(NominaEmpleado, NominaEmpleado.id == NominaDetalle.nomina_empleado_id)
                .filter(NominaEmpleado.nomina_id == nomina_id)
            ).all()
            grouped: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
            affected: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
            by_employee: dict[str, dict[str, dict[str, Decimal]]] = defaultdict(
                lambda: defaultdict(lambda: defaultdict(lambda: Decimal("0")))
            )
            for tipo, codigo, monto, empleado_id in rows:
                monto_decimal = cls._to_decimal(monto)
                grouped[tipo][codigo] += monto_decimal
                affected[tipo][codigo].add(empleado_id)
                by_employee[empleado_id][tipo][codigo] += monto_decimal
            return grouped, affected, by_employee

        base, base_affected, base_employee = aggregate(nomina_base_id)
        actual, actual_affected, actual_employee = aggregate(nomina_actual_id)

        result: dict[str, list[dict[str, Any]]] = {}
        radar: list[dict[str, Any]] = []
        for tipo in ["income", "deduction", "benefit"]:
            codigos = sorted(set(base.get(tipo, {}).keys()) | set(actual.get(tipo, {}).keys()))
            result[tipo] = []
            for codigo in codigos:
                base_monto = base.get(tipo, {}).get(codigo, Decimal("0"))
                actual_monto = actual.get(tipo, {}).get(codigo, Decimal("0"))
                empleados_base = len(base_affected.get(tipo, {}).get(codigo, set()))
                empleados_actual = len(actual_affected.get(tipo, {}).get(codigo, set()))
                item = {
                    "codigo": codigo,
                    "monto_base": cls._money(base_monto),
                    "monto_actual": cls._money(actual_monto),
                    "variacion": cls._money(actual_monto - base_monto),
                    "variacion_pct": cls._percent(cls._pct_delta(actual_monto, base_monto)),
                    "empleados_base": empleados_base,
                    "empleados_actual": empleados_actual,
                    "promedio_base": cls._money(base_monto / Decimal(empleados_base)) if empleados_base else 0.0,
                    "promedio_actual": (
                        cls._money(actual_monto / Decimal(empleados_actual)) if empleados_actual else 0.0
                    ),
                    "nuevo_en_actual": empleados_base == 0 and empleados_actual > 0,
                    "eliminado_en_actual": empleados_base > 0 and empleados_actual == 0,
                    "tipo": tipo,
                }
                result[tipo].append(item)
                radar.append(item)

        radar.sort(key=lambda item: abs(item["variacion"]), reverse=True)

        drivers_empleado = cls._build_employee_drivers(base_employee, actual_employee)
        return {
            "por_tipo": result,
            "radar_top": radar[:10],
            "drivers_empleado": drivers_empleado,
        }

    @classmethod
    def _build_employee_drivers(
        cls,
        base_employee: dict[str, dict[str, dict[str, Decimal]]],
        actual_employee: dict[str, dict[str, dict[str, Decimal]]],
    ) -> dict[str, list[dict[str, Any]]]:
        all_emp_ids = set(base_employee.keys()) | set(actual_employee.keys())
        drivers: dict[str, list[dict[str, Any]]] = {}
        for empleado_id in all_emp_ids:
            base_tipos = base_employee.get(empleado_id, {})
            actual_tipos = actual_employee.get(empleado_id, {})
            items: list[dict[str, Any]] = []
            for tipo in ["income", "deduction", "benefit"]:
                codigos = set(base_tipos.get(tipo, {}).keys()) | set(actual_tipos.get(tipo, {}).keys())
                for codigo in codigos:
                    base_val = base_tipos.get(tipo, {}).get(codigo, Decimal("0"))
                    actual_val = actual_tipos.get(tipo, {}).get(codigo, Decimal("0"))
                    delta = actual_val - base_val
                    if delta != Decimal("0"):
                        items.append(
                            {
                                "tipo": tipo,
                                "codigo": codigo,
                                "variacion": cls._money(delta),
                            }
                        )
            items.sort(key=lambda item: abs(item["variacion"]), reverse=True)
            drivers[empleado_id] = items[:3]
        return drivers

    @classmethod
    def _comparar_reglas_vacaciones(cls, nomina_base_id: str, nomina_actual_id: str) -> dict[str, Any]:
        def aggregate(nomina_id: str) -> dict[str, Decimal]:
            rows = db.session.execute(
                db.select(NominaNovedad.codigo_concepto, NominaNovedad.valor_cantidad).filter(
                    NominaNovedad.nomina_id == nomina_id, NominaNovedad.es_descanso_vacaciones.is_(True)
                )
            ).all()
            grouped: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            for codigo_concepto, cantidad in rows:
                grouped[codigo_concepto or "SIN_CODIGO"] += cls._to_decimal(cantidad)
            return grouped

        base = aggregate(nomina_base_id)
        actual = aggregate(nomina_actual_id)
        reglas = sorted(set(base.keys()) | set(actual.keys()))
        return {
            "total_reglas": len(reglas),
            "reglas": [
                {
                    "codigo_concepto": regla,
                    "cantidad_base": cls._money(base.get(regla, Decimal("0"))),
                    "cantidad_actual": cls._money(actual.get(regla, Decimal("0"))),
                    "variacion": cls._money(actual.get(regla, Decimal("0")) - base.get(regla, Decimal("0"))),
                }
                for regla in reglas
            ],
        }

    @classmethod
    def _build_impacto_empleados(
        cls,
        total_comunes: int,
        variaciones_neto_detalle: list[dict[str, Any]],
        empleados_variacion_positiva: int,
        empleados_variacion_negativa: int,
    ) -> dict[str, Any]:
        empleados_con_variacion = sum(1 for item in variaciones_neto_detalle if item["delta_neto"] != Decimal("0"))
        total = Decimal(total_comunes or 1)
        return {
            "total_comunes": total_comunes,
            "empleados_con_variacion": empleados_con_variacion,
            "porcentaje_con_variacion": cls._percent((Decimal(empleados_con_variacion) / total) * Decimal("100")),
            "porcentaje_con_variacion_positiva": cls._percent(
                (Decimal(empleados_variacion_positiva) / total) * Decimal("100")
            ),
            "porcentaje_con_variacion_negativa": cls._percent(
                (Decimal(empleados_variacion_negativa) / total) * Decimal("100")
            ),
        }

    @classmethod
    def _build_concentracion_impacto(
        cls, variaciones_neto_detalle: list[dict[str, Any]], conceptos: dict[str, Any]
    ) -> dict[str, Any]:
        total_delta_abs = sum((item["delta_neto_abs"] for item in variaciones_neto_detalle), Decimal("0"))
        top_emp = sorted((item["delta_neto_abs"] for item in variaciones_neto_detalle), reverse=True)

        concept_items = []
        for tipo_items in conceptos.get("por_tipo", {}).values():
            for item in tipo_items:
                concept_items.append(abs(cls._to_decimal(item.get("variacion", 0))))
        concept_items.sort(reverse=True)
        total_concept_delta = sum(concept_items, Decimal("0"))

        return {
            "top_5_empleados_pct": cls._percent(cls._safe_pct(sum(top_emp[:5], Decimal("0")), total_delta_abs)),
            "top_10_empleados_pct": cls._percent(cls._safe_pct(sum(top_emp[:10], Decimal("0")), total_delta_abs)),
            "top_5_conceptos_pct": cls._percent(
                cls._safe_pct(sum(concept_items[:5], Decimal("0")), total_concept_delta)
            ),
            "top_10_conceptos_pct": cls._percent(
                cls._safe_pct(sum(concept_items[:10], Decimal("0")), total_concept_delta)
            ),
        }

    @classmethod
    def _build_bucket_variacion_neto(cls, variaciones_neto_detalle: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets = {
            "<=-10%": 0,
            "-10% a 0%": 0,
            "0%": 0,
            "0% a 10%": 0,
            ">10%": 0,
        }
        for item in variaciones_neto_detalle:
            delta_pct = item.get("delta_pct")
            if delta_pct is None:
                delta_neto = item.get("delta_neto", Decimal("0"))
                if delta_neto > 0:
                    buckets[">10%"] += 1
                elif delta_neto < 0:
                    buckets["<=-10%"] += 1
                else:
                    buckets["0%"] += 1
                continue
            if delta_pct <= Decimal("-10"):
                buckets["<=-10%"] += 1
            elif delta_pct < Decimal("0"):
                buckets["-10% a 0%"] += 1
            elif delta_pct == Decimal("0"):
                buckets["0%"] += 1
            elif delta_pct <= Decimal("10"):
                buckets["0% a 10%"] += 1
            else:
                buckets[">10%"] += 1
        return [{"rango": key, "cantidad": value} for key, value in buckets.items()]

    @classmethod
    def _build_segmentacion(
        cls,
        base_by_emp: dict[str, NominaEmpleado],
        actual_by_emp: dict[str, NominaEmpleado],
        comunes: list[str],
    ) -> dict[str, Any]:
        dept_data: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {"empleados": 0, "base": Decimal("0"), "actual": Decimal("0")}
        )
        contrato_data: dict[str, dict[str, Decimal | int]] = defaultdict(
            lambda: {"empleados": 0, "base": Decimal("0"), "actual": Decimal("0")}
        )

        for empleado_id in comunes:
            base_item = base_by_emp[empleado_id]
            actual_item = actual_by_emp[empleado_id]
            departamento = (actual_item.empleado.area or base_item.empleado.area or "Sin departamento").strip()
            tipo_contrato = (
                actual_item.empleado.tipo_contrato or base_item.empleado.tipo_contrato or "Sin tipo"
            ).strip()

            base_neto = cls._to_decimal(base_item.salario_neto)
            actual_neto = cls._to_decimal(actual_item.salario_neto)

            dept_data[departamento]["empleados"] = int(dept_data[departamento]["empleados"]) + 1
            dept_data[departamento]["base"] = cls._to_decimal(dept_data[departamento]["base"]) + base_neto
            dept_data[departamento]["actual"] = cls._to_decimal(dept_data[departamento]["actual"]) + actual_neto

            contrato_data[tipo_contrato]["empleados"] = int(contrato_data[tipo_contrato]["empleados"]) + 1
            contrato_data[tipo_contrato]["base"] = cls._to_decimal(contrato_data[tipo_contrato]["base"]) + base_neto
            contrato_data[tipo_contrato]["actual"] = (
                cls._to_decimal(contrato_data[tipo_contrato]["actual"]) + actual_neto
            )

        def serialize(data: dict[str, dict[str, Decimal | int]], key_name: str) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            for key, values in data.items():
                base = cls._to_decimal(values["base"])
                actual = cls._to_decimal(values["actual"])
                rows.append(
                    {
                        key_name: key,
                        "empleados": int(values["empleados"]),
                        "variacion_total_neto": cls._money(actual - base),
                        "variacion_pct": cls._percent(cls._pct_delta(actual, base)),
                    }
                )
            rows.sort(key=lambda item: abs(item["variacion_total_neto"]), reverse=True)
            return rows

        return {
            "departamentos": serialize(dept_data, "departamento"),
            "tipo_contrato": serialize(contrato_data, "tipo"),
        }

    @classmethod
    def _build_ratios(cls, nomina_base: Nomina, nomina_actual: Nomina) -> dict[str, Any]:
        bruto_base = cls._to_decimal(nomina_base.total_bruto)
        bruto_actual = cls._to_decimal(nomina_actual.total_bruto)
        ded_base = cls._to_decimal(nomina_base.total_deducciones)
        ded_actual = cls._to_decimal(nomina_actual.total_deducciones)

        ratio_base = cls._safe_div(ded_base, bruto_base)
        ratio_actual = cls._safe_div(ded_actual, bruto_actual)

        return {
            "ratio_deducciones_bruto_base": cls._percent(ratio_base * Decimal("100")),
            "ratio_deducciones_bruto_actual": cls._percent(ratio_actual * Decimal("100")),
            "variacion_ratio": cls._percent((ratio_actual - ratio_base) * Decimal("100")),
        }

    @classmethod
    def _build_calidad(cls, nomina_base_id: str, nomina_actual_id: str, empleados_actual_total: int) -> dict[str, Any]:
        empleados_base = set(
            db.session.execute(db.select(NominaNovedad.empleado_id).filter(NominaNovedad.nomina_id == nomina_base_id))
            .scalars()
            .all()
        )
        empleados_actual = set(
            db.session.execute(db.select(NominaNovedad.empleado_id).filter(NominaNovedad.nomina_id == nomina_actual_id))
            .scalars()
            .all()
        )
        total = Decimal(empleados_actual_total or 1)
        return {
            "empleados_con_novedades_base": len(empleados_base),
            "empleados_con_novedades_actual": len(empleados_actual),
            "porcentaje_actual": cls._percent((Decimal(len(empleados_actual)) / total) * Decimal("100")),
        }

    @classmethod
    def _build_cambios_estructurales(cls, nomina_base: Nomina, nomina_actual: Nomina) -> dict[str, bool]:
        return {
            "reglas_cambiadas": (nomina_base.configuracion_snapshot or {})
            != (nomina_actual.configuracion_snapshot or {}),
            "catalogos_cambiados": (nomina_base.catalogos_snapshot or {}) != (nomina_actual.catalogos_snapshot or {}),
            "tipos_cambio_modificados": (nomina_base.tipos_cambio_snapshot or {})
            != (nomina_actual.tipos_cambio_snapshot or {}),
        }

    @classmethod
    def _build_indice_estabilidad(
        cls,
        impacto_empleados: dict[str, Any],
        outliers_neto: list[dict[str, Any]],
        concentracion_impacto: dict[str, Any],
        cambios_estructurales: dict[str, bool],
    ) -> dict[str, Any]:
        afectacion = cls._to_decimal(impacto_empleados.get("porcentaje_con_variacion") or 0)
        severidad = Decimal(len([i for i in outliers_neto if i.get("severidad") == "alta"]))
        outlier_ratio = cls._safe_pct(severidad, Decimal(len(outliers_neto) or 1))
        concentracion = cls._to_decimal(concentracion_impacto.get("top_10_empleados_pct") or 0)
        cambios_score = Decimal("100") if any(cambios_estructurales.values()) else Decimal("0")

        riesgo = (
            (afectacion * cls.ESTABILIDAD_PESO_AFECTACION)
            + (outlier_ratio * cls.ESTABILIDAD_PESO_SEVERIDAD)
            + (concentracion * cls.ESTABILIDAD_PESO_CONCENTRACION)
            + (cambios_score * cls.ESTABILIDAD_PESO_CAMBIOS_ESTRUCTURALES)
        )
        score = max(Decimal("0"), Decimal("100") - riesgo)
        if score >= Decimal("75"):
            nivel = "alto"
        elif score >= Decimal("50"):
            nivel = "medio"
        else:
            nivel = "bajo"

        return {
            "score": cls._percent(score),
            "nivel": nivel,
            "algoritmo": {
                "afectacion_pct": cls._percent(afectacion),
                "outlier_alto_pct": cls._percent(outlier_ratio),
                "concentracion_top10_pct": cls._percent(concentracion),
                "cambios_estructurales_pct": cls._percent(cambios_score),
                "pesos": {
                    "afectacion": cls._percent(cls.ESTABILIDAD_PESO_AFECTACION * Decimal("100")),
                    "severidad": cls._percent(cls.ESTABILIDAD_PESO_SEVERIDAD * Decimal("100")),
                    "concentracion": cls._percent(cls.ESTABILIDAD_PESO_CONCENTRACION * Decimal("100")),
                    "cambios_estructurales": cls._percent(cls.ESTABILIDAD_PESO_CAMBIOS_ESTRUCTURALES * Decimal("100")),
                },
            },
        }

    @staticmethod
    def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
        if denominator == Decimal("0"):
            return Decimal("0")
        return numerator / denominator

    @classmethod
    def _safe_pct(cls, numerator: Decimal, denominator: Decimal) -> Decimal:
        if denominator == Decimal("0"):
            return Decimal("0")
        return (numerator / denominator) * Decimal("100")

    @staticmethod
    def _std_dev(values: list[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        mean = sum(values) / Decimal(len(values))
        variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
        return variance.sqrt()

    @classmethod
    def _iqr(cls, values: list[Decimal]) -> Decimal:
        return cls._percentile(values, 75) - cls._percentile(values, 25)

    @staticmethod
    def _employee_list(ids: list[str], source: dict[str, NominaEmpleado]) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for empleado_id in ids:
            empleado = source[empleado_id]
            items.append(
                {
                    "empleado_id": empleado_id,
                    "empleado_codigo": empleado.empleado.codigo_empleado,
                    "nombre": NominaComparisonService._employee_name(empleado),
                }
            )
        return items

    @staticmethod
    def _employee_name(item: NominaEmpleado) -> str:
        return " ".join(
            filter(
                None,
                [
                    item.empleado.primer_nombre,
                    item.empleado.segundo_nombre,
                    item.empleado.primer_apellido,
                    item.empleado.segundo_apellido,
                ],
            )
        )

    @staticmethod
    def _nomina_meta(nomina: Nomina) -> dict[str, Any]:
        return {
            "id": nomina.id,
            "periodo_inicio": nomina.periodo_inicio.isoformat() if nomina.periodo_inicio else None,
            "periodo_fin": nomina.periodo_fin.isoformat() if nomina.periodo_fin else None,
            "estado": nomina.estado,
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _avg(values: list[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        return sum(values) / Decimal(len(values))

    @staticmethod
    def _median(values: list[Decimal]) -> Decimal:
        if not values:
            return Decimal("0")
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2 == 0:
            return (ordered[middle - 1] + ordered[middle]) / Decimal("2")
        return ordered[middle]

    @staticmethod
    def _percentile(values: list[Decimal], percentile: int) -> Decimal:
        if not values:
            return Decimal("0")
        ordered = sorted(values)
        index = int((len(ordered) - 1) * (percentile / 100))
        return ordered[index]

    @classmethod
    def _pct_delta(cls, current: Decimal, previous: Decimal) -> Decimal | None:
        if previous == Decimal("0"):
            return Decimal("0") if current == Decimal("0") else None
        return ((current - previous) / abs(previous)) * Decimal("100")

    @staticmethod
    def _money(value: Decimal) -> float:
        return float(value.quantize(Decimal("0.01")))

    @staticmethod
    def _percent(value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value.quantize(Decimal("0.01")))

    @staticmethod
    def _iso_utc(value: Any) -> str | None:
        if not value:
            return None
        text = value.isoformat()
        if text.endswith("+00:00"):
            return text
        if text.endswith("Z"):
            return text[:-1] + "+00:00"
        if "T" in text and ("+" not in text[10:] and "-" not in text[10:]):
            return f"{text}+00:00"
        return text

    @staticmethod
    def _nomina_version(nomina: Nomina):
        return nomina.modificado or nomina.fecha_generacion

    @staticmethod
    def _driver_principal(empleado_id: str, drivers: dict[str, list[dict[str, Any]]]) -> str:
        items = drivers.get(empleado_id, [])
        if not items:
            return "Sin variación de conceptos"
        top = items[0]
        return f"{top['tipo']}:{top['codigo']} ({top['variacion']:+,.2f})"

    @staticmethod
    def _planilla_actual_aprobada(nomina_actual: Nomina) -> bool:
        return nomina_actual.estado in (NominaEstado.APLICADO, NominaEstado.PAGADO)

    @classmethod
    def _flujo_aprobacion(cls, nomina_actual: Nomina) -> dict[str, Any]:
        return {
            "creado_por": nomina_actual.generado_por,
            "validado_por": nomina_actual.aprobado_por,
            "aplicado_por": nomina_actual.aplicado_por,
            "creado_en": cls._iso_utc(nomina_actual.fecha_generacion),
            "validado_en": cls._iso_utc(nomina_actual.aprobado_en),
            "aplicado_en": cls._iso_utc(nomina_actual.aplicado_en),
        }
