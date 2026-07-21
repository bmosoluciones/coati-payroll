# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for NominaComparisonService KPI helpers."""

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from coati_payroll.enums import NominaEstado
from coati_payroll.vistas.planilla.services.nomina_comparison_service import NominaComparisonService


def _nomina_empleado(
    empleado_id: str,
    area: str,
    tipo_contrato: str,
    neto: str,
    bruto: str = "0",
    codigo: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        empleado_id=empleado_id,
        salario_neto=Decimal(neto),
        salario_bruto=Decimal(bruto),
        sueldo_base_historico=Decimal("0"),
        empleado=SimpleNamespace(
            area=area,
            tipo_contrato=tipo_contrato,
            codigo_empleado=codigo or f"EMP-{empleado_id}",
            primer_nombre="Ada",
            segundo_nombre="",
            primer_apellido="Lovelace",
            segundo_apellido="",
        ),
    )


def test_build_bucket_variacion_neto_classifies_expected_ranges() -> None:
    variaciones = [
        {"delta_neto": Decimal("-50"), "delta_pct": Decimal("-12")},
        {"delta_neto": Decimal("-10"), "delta_pct": Decimal("-5")},
        {"delta_neto": Decimal("0"), "delta_pct": Decimal("0")},
        {"delta_neto": Decimal("20"), "delta_pct": Decimal("7")},
        {"delta_neto": Decimal("100"), "delta_pct": Decimal("15")},
    ]

    buckets = NominaComparisonService._build_bucket_variacion_neto(variaciones)
    resultado = {item["rango"]: item["cantidad"] for item in buckets}

    assert resultado["<=-10%"] == 1
    assert resultado["-10% a 0%"] == 1
    assert resultado["0%"] == 1
    assert resultado["0% a 10%"] == 1
    assert resultado[">10%"] == 1


def test_build_bucket_variacion_neto_handles_none_delta_pct_using_delta_neto() -> None:
    variaciones = [
        {"delta_neto": Decimal("10"), "delta_pct": None},
        {"delta_neto": Decimal("-1"), "delta_pct": None},
        {"delta_neto": Decimal("0"), "delta_pct": None},
    ]

    buckets = NominaComparisonService._build_bucket_variacion_neto(variaciones)
    resultado = {item["rango"]: item["cantidad"] for item in buckets}

    assert resultado[">10%"] == 1
    assert resultado["<=-10%"] == 1
    assert resultado["0%"] == 1


def test_build_impacto_empleados_returns_expected_percentages() -> None:
    variaciones = [
        {"delta_neto": Decimal("100")},
        {"delta_neto": Decimal("-30")},
        {"delta_neto": Decimal("0")},
        {"delta_neto": Decimal("10")},
    ]

    impacto = NominaComparisonService._build_impacto_empleados(
        total_comunes=4,
        variaciones_neto_detalle=variaciones,
        empleados_variacion_positiva=2,
        empleados_variacion_negativa=1,
    )

    assert impacto["empleados_con_variacion"] == 3
    assert impacto["porcentaje_con_variacion"] == 75.0
    assert impacto["porcentaje_con_variacion_positiva"] == 50.0
    assert impacto["porcentaje_con_variacion_negativa"] == 25.0


def test_build_concentracion_impacto_calculates_top_contributors() -> None:
    variaciones = [
        {"delta_neto_abs": Decimal("100")},
        {"delta_neto_abs": Decimal("50")},
        {"delta_neto_abs": Decimal("25")},
    ]
    conceptos = {
        "por_tipo": {
            "ingresos": [
                {"variacion": Decimal("60")},
                {"variacion": Decimal("20")},
            ],
            "deducciones": [{"variacion": Decimal("20")}],
        }
    }

    concentracion = NominaComparisonService._build_concentracion_impacto(variaciones, conceptos)

    assert concentracion["top_5_empleados_pct"] == 100.0
    assert concentracion["top_10_empleados_pct"] == 100.0
    assert concentracion["top_5_conceptos_pct"] == 100.0
    assert concentracion["top_10_conceptos_pct"] == 100.0


def test_build_segmentacion_groups_and_sorts_by_impact() -> None:
    base_by_emp = {
        "1": _nomina_empleado("1", "Ventas", "Tiempo completo", "100"),
        "2": _nomina_empleado("2", "Operaciones", "Tiempo completo", "100"),
    }
    actual_by_emp = {
        "1": _nomina_empleado("1", "Ventas", "Tiempo completo", "150"),
        "2": _nomina_empleado("2", "Operaciones", "Tiempo completo", "80"),
    }

    segmentacion = NominaComparisonService._build_segmentacion(base_by_emp, actual_by_emp, ["1", "2"])

    assert segmentacion["departamentos"][0]["departamento"] == "Ventas"
    assert segmentacion["departamentos"][0]["variacion_total_neto"] == 50.0
    assert segmentacion["departamentos"][1]["departamento"] == "Operaciones"
    assert segmentacion["departamentos"][1]["variacion_total_neto"] == -20.0
    assert segmentacion["tipo_contrato"][0]["empleados"] == 2


def test_build_indice_estabilidad_reports_low_for_high_risk() -> None:
    impacto_empleados = {"porcentaje_con_variacion": 90.0}
    outliers_neto = [{"severidad": "alta"}, {"severidad": "alta"}, {"severidad": "media"}]
    concentracion_impacto = {"top_10_empleados_pct": 95.0}
    cambios_estructurales = {
        "reglas_cambiadas": True,
        "catalogos_cambiados": False,
        "tipos_cambio_modificados": False,
    }

    indice = NominaComparisonService._build_indice_estabilidad(
        impacto_empleados=impacto_empleados,
        outliers_neto=outliers_neto,
        concentracion_impacto=concentracion_impacto,
        cambios_estructurales=cambios_estructurales,
    )

    assert indice["nivel"] == "bajo"
    assert 0 <= indice["score"] <= 100
    assert "algoritmo" in indice


def test_pct_delta_and_percent_helpers_handle_zero_base_case() -> None:
    assert NominaComparisonService._pct_delta(Decimal("100"), Decimal("0")) is None
    assert NominaComparisonService._pct_delta(Decimal("0"), Decimal("0")) == Decimal("0")
    assert NominaComparisonService._percent(None) is None


def test_statistical_helpers_return_expected_values() -> None:
    values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]

    assert NominaComparisonService._avg(values) == Decimal("2.5")
    assert NominaComparisonService._median(values) == Decimal("2.5")
    assert NominaComparisonService._percentile(values, 75) == Decimal("3")
    assert NominaComparisonService._iqr(values) == Decimal("2")
    assert NominaComparisonService._std_dev(values).quantize(Decimal("0.0001")) == Decimal("1.1180")


def test_resumen_totales_includes_period_days_variation() -> None:
    nomina_base = SimpleNamespace(
        total_bruto=Decimal("1000"),
        total_deducciones=Decimal("100"),
        total_neto=Decimal("900"),
        periodo_inicio=date(2026, 2, 1),
        periodo_fin=date(2026, 2, 28),
    )
    nomina_actual = SimpleNamespace(
        total_bruto=Decimal("50"),
        total_deducciones=Decimal("5"),
        total_neto=Decimal("45"),
        periodo_inicio=date(2026, 1, 1),
        periodo_fin=date(2026, 1, 1),
    )
    empleados_base = [SimpleNamespace(salario_neto=Decimal("900"), salario_bruto=Decimal("1000"))]
    empleados_actual = [SimpleNamespace(salario_neto=Decimal("45"), salario_bruto=Decimal("50"))]

    resumen = NominaComparisonService._resumen_totales(
        nomina_base=nomina_base,
        nomina_actual=nomina_actual,
        empleados_base=empleados_base,
        empleados_actual=empleados_actual,
        ids_base={"E1"},
        ids_actual={"E1"},
    )

    assert resumen["dias_calculo_base"] == 28
    assert resumen["dias_calculo_actual"] == 1
    assert resumen["variacion_dias_calculo"] == -27


def test_iso_utc_normalizes_naive_and_aware_datetimes() -> None:
    naive = datetime(2026, 2, 22, 10, 30, 0)
    aware = datetime(2026, 2, 22, 10, 30, 0, tzinfo=timezone.utc)

    assert NominaComparisonService._iso_utc(naive).endswith("+00:00")
    assert NominaComparisonService._iso_utc(aware).endswith("+00:00")



def test_planilla_actual_aprobada_true_only_for_aplicado_o_pagado() -> None:
    nomina_aplicada = SimpleNamespace(estado=NominaEstado.APLICADO)
    nomina_pagada = SimpleNamespace(estado=NominaEstado.PAGADO)
    nomina_generada = SimpleNamespace(estado=NominaEstado.GENERADO)

    assert NominaComparisonService._planilla_actual_aprobada(nomina_aplicada) is True
    assert NominaComparisonService._planilla_actual_aprobada(nomina_pagada) is True
    assert NominaComparisonService._planilla_actual_aprobada(nomina_generada) is False


def test_flujo_aprobacion_includes_expected_users_and_timestamps() -> None:
    nomina = SimpleNamespace(
        generado_por="alice",
        aprobado_por="bob",
        aplicado_por="carol",
        fecha_generacion=datetime(2026, 2, 22, 9, 0, 0),
        aprobado_en=datetime(2026, 2, 22, 10, 0, 0),
        aplicado_en=datetime(2026, 2, 22, 11, 0, 0),
    )

    flujo = NominaComparisonService._flujo_aprobacion(nomina)

    assert flujo["creado_por"] == "alice"
    assert flujo["validado_por"] == "bob"
    assert flujo["aplicado_por"] == "carol"
    assert flujo["creado_en"].endswith("+00:00")
    assert flujo["validado_en"].endswith("+00:00")
    assert flujo["aplicado_en"].endswith("+00:00")


def test_compare_or_cached_handles_integrity_error_on_concurrent_insert(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.rollback_called = False
            self.add_called = False

        def add(self, _obj) -> None:
            self.add_called = True

        def commit(self) -> None:
            raise IntegrityError('insert', {}, Exception('duplicate'))

        def rollback(self) -> None:
            self.rollback_called = True

    fake_session = FakeSession()

    cached_row = SimpleNamespace(
        resumen_json={"from": "cache"},
        generado_en=datetime(2026, 2, 22, 12, 0, 0),
        es_calculo_actual=True,
    )

    cache_reads = iter([None, cached_row])
    monkeypatch.setattr(NominaComparisonService, '_get_cached', staticmethod(lambda *_args: next(cache_reads)))
    monkeypatch.setattr(NominaComparisonService, 'build_comparison', classmethod(lambda cls, **_kwargs: {"fresh": True}))
    monkeypatch.setattr(NominaComparisonService, '_nomina_version', staticmethod(lambda _nomina: datetime(2026, 2, 22, 11, 0, 0)))
    monkeypatch.setattr(NominaComparisonService, '_planilla_actual_aprobada', staticmethod(lambda _nomina: False))
    monkeypatch.setattr(NominaComparisonService, '_flujo_aprobacion', staticmethod(lambda _nomina: {}))

    from coati_payroll.vistas.planilla.services import nomina_comparison_service as module

    monkeypatch.setattr(module.db, 'session', fake_session)

    payload = NominaComparisonService.compare_or_cached(
        planilla=SimpleNamespace(id='PLA-1'),
        nomina_base=SimpleNamespace(id='NOM-BASE', modificado_en=None, actualizado_en=None, fecha_generacion=None),
        nomina_actual=SimpleNamespace(id='NOM-ACT', modificado_en=None, actualizado_en=None, fecha_generacion=None),
    )

    assert fake_session.add_called is True
    assert fake_session.rollback_called is True
    assert payload['is_cached'] is True
    assert payload['from'] == 'cache'
