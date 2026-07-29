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


def test_build_calidad_includes_floating_novelties(monkeypatch) -> None:
    # Arrange
    nomina_base = SimpleNamespace(id="NOM-BASE", periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 15))
    nomina_actual = SimpleNamespace(id="NOM-ACT", periodo_inicio=date(2026, 1, 16), periodo_fin=date(2026, 1, 31))

    executed_stmts = []

    class FakeScalars:
        def __init__(self, items) -> None:
            self.items = items
        def all(self):
            return self.items

    class FakeResult:
        def __init__(self, items) -> None:
            self.items = items
        def scalars(self):
            return FakeScalars(self.items)

    class FakeSession:
        def execute(self, stmt):
            executed_stmts.append(stmt)
            if "NOM-BASE" in str(stmt.compile(compile_kwargs={"literal_binds": True})):
                return FakeResult(["EMP-1", "EMP-2"])
            else:
                return FakeResult(["EMP-2", "EMP-3", "EMP-4"])

    from coati_payroll.vistas.planilla.services import nomina_comparison_service as module
    monkeypatch.setattr(module.db, 'session', FakeSession())

    # Act
    res = NominaComparisonService._build_calidad(nomina_base, nomina_actual, 10)

    # Assert
    assert res["empleados_con_novedades_base"] == 2
    assert res["empleados_con_novedades_actual"] == 3
    assert res["porcentaje_actual"] == 30.0  # 3 / 10 * 100
    assert len(executed_stmts) == 2

    # Verify the query conditions compiled correctly
    sql0 = str(executed_stmts[0].compile(compile_kwargs={"literal_binds": True}))
    assert "nomina_novedad.nomina_id = 'NOM-BASE'" in sql0
    assert "nomina_novedad.nomina_id IS NULL" in sql0
    assert "nomina_novedad.fecha_novedad >= '2026-01-01'" in sql0
    assert "nomina_novedad.fecha_novedad <= '2026-01-15'" in sql0


def test_comparar_reglas_vacaciones_includes_floating_vacations(monkeypatch) -> None:
    # Arrange
    nomina_base = SimpleNamespace(id="NOM-BASE", periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 15))
    nomina_actual = SimpleNamespace(id="NOM-ACT", periodo_inicio=date(2026, 1, 16), periodo_fin=date(2026, 1, 31))

    executed_stmts = []

    class FakeResult:
        def __init__(self, items) -> None:
            self.items = items
        def all(self):
            return self.items

    class FakeSession:
        def execute(self, stmt):
            executed_stmts.append(stmt)
            sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            if "NOM-BASE" in sql:
                # Base rule: 10 days for VAC
                return FakeResult([("VAC", Decimal("10"))])
            else:
                # Actual rule: 15 days for VAC and 5 for EXTRA
                return FakeResult([("VAC", Decimal("15")), ("EXTRA", Decimal("5"))])

    from coati_payroll.vistas.planilla.services import nomina_comparison_service as module
    monkeypatch.setattr(module.db, 'session', FakeSession())

    # Act
    res = NominaComparisonService._comparar_reglas_vacaciones(nomina_base, nomina_actual)

    # Assert
    assert res["total_reglas"] == 2
    reglas_by_code = {r["codigo_concepto"]: r for r in res["reglas"]}
    assert reglas_by_code["VAC"]["cantidad_base"] == 10.0
    assert reglas_by_code["VAC"]["cantidad_actual"] == 15.0
    assert reglas_by_code["VAC"]["variacion"] == 5.0
    assert reglas_by_code["EXTRA"]["cantidad_base"] == 0.0
    assert reglas_by_code["EXTRA"]["cantidad_actual"] == 5.0
    assert reglas_by_code["EXTRA"]["variacion"] == 5.0

    # Verify compiling SQL
    sql0 = str(executed_stmts[0].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "nomina_novedad.nomina_id = 'nom-base'" in sql0
    assert "nomina_novedad.nomina_id is null" in sql0
    assert "es_descanso_vacaciones is true" in sql0 or "es_descanso_vacaciones = true" in sql0 or "es_descanso_vacaciones is" in sql0


# ============================================================================
# EXTENDED NOMINA COMPARISON SERVICE COVERAGE TESTS
# ============================================================================


def _create_planilla(db_session):
    from coati_payroll.model import Planilla, TipoPlanilla, Moneda, Empresa
    tipo = TipoPlanilla(codigo="MENSUAL", descripcion="Mensual", dias=30, periodicidad="mensual")
    moneda = Moneda(codigo="USD", nombre="Dólar")
    empresa = Empresa(codigo="EMP", razon_social="Test Corp", ruc="123")
    db_session.add_all([tipo, moneda, empresa])
    db_session.flush()

    planilla = Planilla(
        nombre="Test Planilla",
        tipo_planilla_id=tipo.id,
        moneda_id=moneda.id,
        empresa_id=empresa.id,
        periodo_fiscal_inicio=date(2024, 1, 1),
        periodo_fiscal_fin=date(2024, 12, 31),
        activo=True,
    )
    db_session.add(planilla)
    db_session.flush()
    return planilla


def test_transferir_comparativas_edge_cases(app, db_session):
    """Test transferir_comparativas with various duplicate or deleted conditions."""
    from coati_payroll.model import NominaComparacion, Nomina
    from coati_payroll.vistas.planilla.services.nomina_comparison_service import NominaComparisonService

    with app.app_context():
        planilla = _create_planilla(db_session)

        n_orig = Nomina(id="NOM_ORIGINAL", planilla_id=planilla.id, periodo_inicio=date(2025,1,1), periodo_fin=date(2025,1,15))
        n_new = Nomina(id="NOM_NUEVA", planilla_id=planilla.id, periodo_inicio=date(2025,1,1), periodo_fin=date(2025,1,15))
        n_other = Nomina(id="NOM_OTRA", planilla_id=planilla.id, periodo_inicio=date(2025,1,16), periodo_fin=date(2025,1,31))
        db_session.add_all([n_orig, n_new, n_other])
        db_session.flush()

        # Create primary comparison
        comp = NominaComparacion(
            planilla_id=planilla.id,
            nomina_base_id=n_orig.id,
            nomina_actual_id=n_other.id,
            resumen_json={"es_calculo_actual": True}
        )
        db_session.add(comp)
        db_session.commit()

        # Run transfer
        NominaComparisonService.refresh_after_recalculo(
            planilla_id=planilla.id,
            nomina_original_id=n_orig.id,
            nomina_nueva_id=n_new.id
        )

        assert comp.nomina_base_id == n_new.id
        assert comp.resumen_json["es_calculo_actual"] is False


def test_cargar_conceptos_catalogo(app, db_session):
    """Test _comparar_componentes_planilla correctly fetches lists of rules and concepts."""
    from coati_payroll.model import Percepcion, Deduccion, Prestacion, ReglaCalculo, PlanillaIngreso, PlanillaDeduccion, PlanillaPrestacion
    from coati_payroll.vistas.planilla.services.nomina_comparison_service import NominaComparisonService

    with app.app_context():
        planilla = _create_planilla(db_session)

        perc = Percepcion(codigo="P_TEST", nombre="Perc Test")
        ded = Deduccion(codigo="D_TEST", nombre="Ded Test")
        pres = Prestacion(codigo="PR_TEST", nombre="Pres Test")
        reg = ReglaCalculo(codigo="R_TEST", nombre="Rule Test", vigente_desde=date(2025,1,1))
        db_session.add_all([perc, ded, pres, reg])
        db_session.flush()

        db_session.add(PlanillaIngreso(planilla_id=planilla.id, percepcion_id=perc.id))
        db_session.add(PlanillaDeduccion(planilla_id=planilla.id, deduccion_id=ded.id))
        db_session.add(PlanillaPrestacion(planilla_id=planilla.id, prestacion_id=pres.id))
        from coati_payroll.model import PlanillaReglaCalculo
        db_session.add(PlanillaReglaCalculo(planilla_id=planilla.id, regla_calculo_id=reg.id, orden=1))
        db_session.commit()

        conceptos = NominaComparisonService._comparar_componentes_planilla(planilla.id)
        assert "P_TEST" in conceptos["percepciones"]
        assert "D_TEST" in conceptos["deducciones"]
        assert "PR_TEST" in conceptos["prestaciones"]
        assert "R_TEST" in conceptos["reglas_calculo"]


def test_get_nominas_disponibles_and_default(app, db_session):
    """Test get_nominas_disponibles and default base selection."""
    from coati_payroll.model import Nomina
    from coati_payroll.vistas.planilla.services.nomina_comparison_service import NominaComparisonService

    with app.app_context():
        planilla = _create_planilla(db_session)

        n1 = Nomina(id="NOM_1", planilla_id=planilla.id, estado="generado", periodo_inicio=date(2025,1,1), periodo_fin=date(2025,1,15))
        n2 = Nomina(id="NOM_2", planilla_id=planilla.id, estado="generado", periodo_inicio=date(2025,1,16), periodo_fin=date(2025,1,31))
        db_session.add_all([n1, n2])
        db_session.commit()

        disp = NominaComparisonService.get_nominas_disponibles(planilla.id, excluir_nomina_id="NOM_1")
        assert len(disp) == 1
        assert disp[0].id == "NOM_2"

        default_base = NominaComparisonService.get_nomina_base_default(n2)
        assert default_base is not None
