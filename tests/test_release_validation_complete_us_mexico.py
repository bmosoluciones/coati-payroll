# SPDX-License-Identifier: Apache-2.0
"""Complete configurable payroll stress validations for US and Mexico."""

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from coati_payroll.model import (
    AcumuladoAnual,
    ConfiguracionCalculos,
    Deduccion,
    Empleado,
    Empresa,
    Moneda,
    NominaNovedad,
    Planilla,
    PlanillaDeduccion,
    PlanillaEmpleado,
    PlanillaPrestacion,
    Prestacion,
    PrestacionAcumulada,
    ReglaCalculo,
    TipoPlanilla,
    VacationAccount,
    VacationLedger,
    VacationNovelty,
    VacationPolicy,
    db,
)
from coati_payroll.nomina_engine.services.payroll_execution_service import PayrollExecutionService
from coati_payroll.vistas.planilla.nomina_routes import _aplicar_prestaciones_nomina, _aplicar_vacaciones_nomina

pytestmark = pytest.mark.release_validation
ROOT = Path(__file__).parents[1]


def _profile(country: str) -> dict:
    if country in {"GT", "HN", "SV", "NI", "CR", "PA", "BZ"}:
        profiles = json.loads(
            (ROOT / "coati_payroll" / "jurisdictions" / "central_america_2026.json").read_text(encoding="utf-8")
        )
        profile = profiles["countries"][country]
        profile["vacation_defaults"] = profiles["vacation_defaults"]
        profile["stress_defaults"] = profiles["stress_defaults"]
        return profile
    filename = {"US": "us_2026.json", "MX": "mexico_2026.json", "BR": "brazil_2026.json"}[country]
    return json.loads((ROOT / "coati_payroll" / "jurisdictions" / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "country",
    ["US", "MX", "BR", "GT", "HN", "SV", "NI", "CR", "PA", "BZ"],
    ids=[
        "us",
        "mexico",
        "brazil",
        "guatemala",
        "honduras",
        "el-salvador",
        "nicaragua",
        "costa-rica",
        "panama",
        "belize",
    ],
)
def test_complete_configurable_payroll_stress_for_major_jurisdictions(app, db_session, country):
    profile = _profile(country)
    case = profile["cases"][0]
    stress = {**profile["stress_case"], **profile.get("stress_defaults", {})}
    periods = [(date.fromisoformat(start), date.fromisoformat(end)) for start, end in stress["periods"]]
    expected = case["expected"]

    with app.app_context():
        currency = Moneda(
            codigo=profile["currency"], nombre=profile["currency"], simbolo=profile["currency"], activo=True
        )
        company = Empresa(
            codigo=profile["company"]["code"],
            razon_social=profile["company"]["legal_name"],
            ruc=profile["company"]["tax_id"],
            primer_mes_nomina=profile["payroll"]["fiscal_start_month"],
            primer_anio_nomina=periods[0][0].year,
        )
        payroll_type = TipoPlanilla(
            codigo=profile["payroll"]["code"],
            descripcion=profile["name"],
            periodicidad=profile["payroll"]["frequency"],
            dias=profile["payroll"]["days_per_month"],
            periodos_por_anio=profile["payroll"]["periods_per_year"],
            mes_inicio_fiscal=profile["payroll"]["fiscal_start_month"],
            dia_inicio_fiscal=profile["payroll"]["fiscal_start_day"],
        )
        db_session.add_all([currency, company, payroll_type])
        db_session.flush()
        payroll = Planilla(
            nombre=profile["payroll"]["code"],
            tipo_planilla=payroll_type,
            empresa=company,
            moneda=currency,
            mes_inicio_fiscal=profile["payroll"]["fiscal_start_month"],
            activo=True,
        )
        config = ConfiguracionCalculos(
            empresa_id=company.id,
            pais_id=profile["country"],
            dias_mes_nomina=profile["payroll"]["days_per_month"],
            dias_anio_nomina=profile["payroll"]["days_per_year"],
            horas_jornada_diaria=Decimal(profile["payroll"]["daily_hours"]),
            dias_mes_vacaciones=profile["payroll"]["days_per_month"],
            dias_anio_vacaciones=profile["payroll"]["days_per_year"],
            dias_anio_financiero=profile["payroll"]["days_per_year"],
            meses_anio_financiero=profile["payroll"]["periods_per_year"],
            dias_quincena=profile["payroll"]["days_per_half_month"],
            dias_mes_antiguedad=profile["payroll"]["days_per_month"],
            dias_anio_antiguedad=profile["payroll"]["days_per_year"],
        )
        db_session.add_all([payroll, config])
        db_session.flush()

        employees = [
            Empleado(
                codigo_empleado=f"{country}-EMP-{index + 1:04d}",
                primer_nombre="Release",
                primer_apellido=f"Validation {index + 1}",
                identificacion_personal=f"{country}-RELEASE-{index + 1:04d}",
                fecha_alta=periods[0][0],
                salario_base=Decimal(stress["salary"]),
                moneda_id=currency.id,
                empresa_id=company.id,
                activo=True,
            )
            for index in range(stress["employee_count"])
        ]
        db_session.add_all(employees)
        db_session.flush()
        db_session.add_all(
            PlanillaEmpleado(planilla_id=payroll.id, empleado_id=employee.id, activo=True) for employee in employees
        )

        vacation_config = {**profile.get("vacation_defaults", {}), **stress["vacation"]}
        policy = VacationPolicy(
            codigo=vacation_config["code"],
            nombre=vacation_config["code"],
            planilla_id=payroll.id,
            empresa_id=company.id,
            accrual_rate=Decimal(vacation_config["accrual_rate_days"]),
            accrual_frequency=vacation_config["frequency"],
            prorate_by_period_days=vacation_config["prorate_by_period_days"],
            unit_type=vacation_config["unit_type"],
            partial_units_allowed=vacation_config["partial_units_allowed"],
            accrue_during_leave=vacation_config["accrue_during_leave"],
        )
        db_session.add(policy)
        db_session.flush()
        payroll.vacation_policy_id = policy.id
        accounts = [
            VacationAccount(empleado_id=employee.id, policy_id=policy.id, activo=True) for employee in employees
        ]
        db_session.add_all(accounts)

        benefits = []
        for benefit_config in stress["benefits"].values():
            benefit = Prestacion(
                codigo=benefit_config["code"],
                nombre=benefit_config["code"],
                tipo="employer",
                formula_tipo="salary_percentage",
                porcentaje=Decimal(benefit_config["percentage"]),
                base_calculo="salario_base",
                tipo_acumulacion=benefit_config["accumulation"],
                recurrente=True,
                activo=True,
            )
            benefits.append(benefit)
        db_session.add_all(benefits)
        db_session.flush()
        db_session.add_all(
            PlanillaPrestacion(planilla_id=payroll.id, prestacion_id=benefit.id, orden=index + 1, activo=True)
            for index, benefit in enumerate(benefits)
        )

        active_rules = [rule for rule in profile["rules"].values() if rule.get("enabled", True)]
        for priority, rule in enumerate(active_rules, start=1):
            deduction = Deduccion(
                codigo=rule["code"],
                nombre=rule["code"],
                formula_tipo="regla_calculo",
                es_impuesto=rule["type"] == "tax",
                antes_impuesto=rule["before_tax"],
                activo=True,
            )
            db_session.add(deduction)
            db_session.flush()
            db_session.add(
                ReglaCalculo(
                    codigo=rule["code"],
                    nombre=rule["code"],
                    tipo_regla=rule["type"],
                    esquema_json=rule["formula"],
                    vigente_desde=periods[0][0],
                    activo=True,
                    deduccion_id=deduction.id,
                )
            )
            db_session.add(
                PlanillaDeduccion(
                    planilla_id=payroll.id, deduccion_id=deduction.id, prioridad=priority, es_obligatoria=True
                )
            )
        db_session.flush()

        usage_index = vacation_config["usage_employee_index"]
        usage_period = periods[vacation_config["usage_period_index"]]
        vacation_novelty = VacationNovelty(
            empleado_id=employees[usage_index].id,
            account_id=accounts[usage_index].id,
            start_date=usage_period[0],
            end_date=usage_period[0],
            units=Decimal(vacation_config["usage_days"]),
            estado="approved",
            fecha_aprobacion=usage_period[0],
            aprobado_por="release-validation",
        )
        db_session.add(vacation_novelty)
        db_session.flush()
        db_session.add(
            NominaNovedad(
                empleado_id=employees[usage_index].id,
                tipo_valor="dias",
                codigo_concepto=policy.codigo,
                valor_cantidad=Decimal(vacation_config["usage_days"]),
                fecha_novedad=usage_period[0],
                es_descanso_vacaciones=True,
                fecha_inicio_descanso=usage_period[0],
                fecha_fin_descanso=usage_period[0],
                vacation_novelty_id=vacation_novelty.id,
            )
        )
        db_session.commit()
        db_session.refresh(payroll)

        executed = []
        for period_start, period_end in periods:
            nomina, results, errors, warnings = PayrollExecutionService(db_session).execute_payroll(
                planilla=payroll,
                periodo_inicio=period_start,
                periodo_fin=period_end,
                fecha_calculo=period_end,
                usuario="release-validation",
            )
            assert errors == []
            assert len(results) == stress["employee_count"]
            expected_deductions = {
                rule["code"]: Decimal(expected[key])
                for rule, key in zip(active_rules, case["deduction_keys"])
                if Decimal(expected[key]) != Decimal("0.00")
            }
            expected_benefits = {
                benefit["code"]: (Decimal(stress["salary"]) * Decimal(benefit["percentage"]) / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                for benefit in stress["benefits"].values()
            }
            for result in results:
                assert result.salario_bruto == Decimal(expected["gross"])
                assert {item.codigo: item.monto for item in result.deducciones} == expected_deductions
                assert result.salario_neto == Decimal(expected["net"])
                assert {item.codigo: item.monto for item in result.prestaciones} == expected_benefits
            nomina.estado = "approved"
            db_session.flush()
            _aplicar_prestaciones_nomina(nomina, payroll, "release-validation")
            _aplicar_vacaciones_nomina(nomina, payroll, "release-validation")
            nomina.estado = "applied"
            db_session.commit()
            executed.append(nomina)

        for employee in employees:
            accumulated = db_session.execute(
                db.select(AcumuladoAnual).filter_by(empleado_id=employee.id, empresa_id=company.id)
            ).scalar_one()
            assert accumulated.salario_bruto_acumulado == Decimal(stress["salary"]) * len(periods)
            assert accumulated.periodos_procesados == len(periods)
        benefit_transactions = (
            db_session.execute(
                db.select(PrestacionAcumulada).filter(
                    PrestacionAcumulada.nomina_id.in_([nomina.id for nomina in executed])
                )
            )
            .scalars()
            .all()
        )
        assert len(benefit_transactions) == stress["employee_count"] * len(stress["benefits"]) * len(periods)
        vacation_entries = (
            db_session.execute(
                db.select(VacationLedger)
                .join(VacationAccount)
                .filter(VacationAccount.empleado_id.in_([employee.id for employee in employees]))
            )
            .scalars()
            .all()
        )
        assert len(vacation_entries) == stress["employee_count"] * len(periods) + 1
        assert sum(entry.quantity for entry in vacation_entries if entry.entry_type == "usage") == -Decimal(
            vacation_config["usage_days"]
        )
