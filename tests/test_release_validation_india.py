# SPDX-License-Identifier: Apache-2.0
"""India AY 2026-27 release validation through the complete payroll flow."""

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
PROFILE = json.loads(
    (Path(__file__).parents[1] / "coati_payroll" / "jurisdictions" / "india_2026_27.json").read_text(
        encoding="utf-8"
    )
)


def _rule(profile_rule: dict, *, deduction_id: str, effective_from: date) -> ReglaCalculo:
    return ReglaCalculo(
        codigo=profile_rule["code"],
        nombre=profile_rule["code"],
        tipo_regla=profile_rule["type"],
        esquema_json=profile_rule["formula"],
        vigente_desde=effective_from,
        activo=True,
        deduccion_id=deduction_id,
    )


def test_india_ay_2026_27_complete_multi_employee_payroll_from_json_profile(app, db_session):
    """Stress the full India flow with employees, benefits, vacations and accumulators."""
    case = PROFILE["cases"][0]
    start = date.fromisoformat(case["period_start"])
    stress = PROFILE["stress_case"]

    with app.app_context():
        currency = Moneda(codigo=PROFILE["currency"], nombre="Indian Rupee", simbolo="₹", activo=True)
        company = Empresa(
            codigo=PROFILE["company"]["code"],
            razon_social=PROFILE["company"]["legal_name"],
            ruc=PROFILE["company"]["tax_id"],
            primer_mes_nomina=PROFILE["payroll"]["fiscal_start_month"],
            primer_anio_nomina=start.year,
        )
        payroll_type = TipoPlanilla(
            codigo=PROFILE["payroll"]["code"],
            descripcion=PROFILE["name"],
            periodicidad=PROFILE["payroll"]["frequency"],
            dias=PROFILE["payroll"]["days_per_month"],
            periodos_por_anio=PROFILE["payroll"]["periods_per_year"],
            mes_inicio_fiscal=PROFILE["payroll"]["fiscal_start_month"],
            dia_inicio_fiscal=PROFILE["payroll"]["fiscal_start_day"],
        )
        db_session.add_all([currency, company, payroll_type])
        db_session.flush()

        payroll = Planilla(
            nombre=PROFILE["payroll"]["code"],
            tipo_planilla=payroll_type,
            empresa=company,
            moneda=currency,
            mes_inicio_fiscal=PROFILE["payroll"]["fiscal_start_month"],
            activo=True,
        )
        config = ConfiguracionCalculos(
            empresa_id=company.id,
            pais_id=PROFILE["country"],
            dias_mes_nomina=PROFILE["payroll"]["days_per_month"],
            dias_anio_nomina=PROFILE["payroll"]["days_per_year"],
            horas_jornada_diaria=Decimal(PROFILE["payroll"]["daily_hours"]),
            dias_mes_vacaciones=PROFILE["payroll"]["days_per_month"],
            dias_anio_vacaciones=PROFILE["payroll"]["days_per_year"],
            dias_anio_financiero=PROFILE["payroll"]["days_per_year"],
            meses_anio_financiero=PROFILE["payroll"]["periods_per_year"],
            dias_quincena=PROFILE["payroll"]["days_per_half_month"],
            dias_mes_antiguedad=PROFILE["payroll"]["days_per_month"],
            dias_anio_antiguedad=PROFILE["payroll"]["days_per_year"],
        )
        db_session.add_all([payroll, config])
        db_session.flush()

        employees = []
        for index in range(stress["employee_count"]):
            employee = Empleado(
                codigo_empleado=f"IN-EMP-{index + 1:04d}",
                primer_nombre="Release",
                primer_apellido=f"Validation {index + 1}",
                identificacion_personal=f"IN-RELEASE-{index + 1:04d}",
                fecha_alta=start,
                salario_base=Decimal(stress["salary"]),
                moneda_id=currency.id,
                empresa_id=company.id,
                activo=True,
            )
            employees.append(employee)
        db_session.add_all(employees)
        db_session.flush()
        db_session.add_all(
            PlanillaEmpleado(planilla_id=payroll.id, empleado_id=employee.id, activo=True)
            for employee in employees
        )

        vacation_config = stress["vacation"]
        vacation_policy = VacationPolicy(
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
        db_session.add(vacation_policy)
        db_session.flush()
        payroll.vacation_policy_id = vacation_policy.id
        vacation_accounts = [
            VacationAccount(empleado_id=employee.id, policy_id=vacation_policy.id, activo=True)
            for employee in employees
        ]
        db_session.add_all(vacation_accounts)
        db_session.flush()

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

        epf = Deduccion(
            codigo=PROFILE["rules"]["epf_employee"]["code"],
            nombre="Employee EPF",
            formula_tipo="regla_calculo",
            es_impuesto=False,
            antes_impuesto=True,
            activo=True,
        )
        tds = Deduccion(
            codigo=PROFILE["rules"]["income_tax"]["code"],
            nombre="Salary TDS under section 115BAC(1A)",
            formula_tipo="regla_calculo",
            es_impuesto=True,
            antes_impuesto=False,
            activo=True,
        )
        db_session.add_all([epf, tds])
        db_session.flush()
        db_session.add_all([
            _rule(PROFILE["rules"]["epf_employee"], deduction_id=epf.id, effective_from=start),
            _rule(PROFILE["rules"]["income_tax"], deduction_id=tds.id, effective_from=start),
            PlanillaDeduccion(planilla_id=payroll.id, deduccion_id=epf.id, prioridad=1, es_obligatoria=True),
            PlanillaDeduccion(planilla_id=payroll.id, deduccion_id=tds.id, prioridad=2, es_obligatoria=True),
        ])
        db_session.commit()
        db_session.refresh(payroll)

        runs = [(date.fromisoformat(item[0]), date.fromisoformat(item[1])) for item in stress["periods"]]
        vacation_employee = employees[vacation_config["usage_employee_index"]]
        vacation_novelty = VacationNovelty(
            empleado_id=vacation_employee.id,
            account_id=vacation_accounts[vacation_config["usage_employee_index"]].id,
            start_date=runs[vacation_config["usage_period_index"]][0],
            end_date=runs[vacation_config["usage_period_index"]][0],
            units=Decimal(vacation_config["usage_days"]),
            estado="approved",
            fecha_aprobacion=runs[vacation_config["usage_period_index"]][0],
            aprobado_por="release-validation",
        )
        db_session.add(vacation_novelty)
        db_session.flush()
        db_session.add(
            NominaNovedad(
                empleado_id=vacation_employee.id,
                tipo_valor="dias",
                codigo_concepto=vacation_policy.codigo,
                valor_cantidad=Decimal(vacation_config["usage_days"]),
                fecha_novedad=runs[vacation_config["usage_period_index"]][0],
                es_descanso_vacaciones=True,
                fecha_inicio_descanso=runs[vacation_config["usage_period_index"]][0],
                fecha_fin_descanso=runs[vacation_config["usage_period_index"]][0],
                vacation_novelty_id=vacation_novelty.id,
            )
        )
        db_session.commit()

        expected = case["expected"]
        expected_benefits = {
            item["code"]: (
                Decimal(stress["salary"]) * Decimal(item["percentage"]) / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for item in stress["benefits"].values()
        }
        executed = []
        for period_start, period_end in runs:
            nomina, employee_results, errors, warnings = PayrollExecutionService(db_session).execute_payroll(
                planilla=payroll,
                periodo_inicio=period_start,
                periodo_fin=period_end,
                fecha_calculo=period_end,
                usuario="release-validation",
            )
            assert errors == []
            assert len(employee_results) == stress["employee_count"]
            assert nomina is not None
            for employee_result in employee_results:
                assert employee_result.total_percepciones == Decimal("0.00")
                assert employee_result.salario_bruto == Decimal(expected["gross"])
                assert {item.codigo: item.monto for item in employee_result.deducciones} == {
                    PROFILE["rules"]["epf_employee"]["code"]: Decimal(expected["epf_employee"]),
                    PROFILE["rules"]["income_tax"]["code"]: Decimal(expected["tds"]),
                }
                assert employee_result.salario_neto == Decimal(expected["net"])
                assert {item.codigo: item.monto for item in employee_result.prestaciones} == expected_benefits
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
            assert accumulated.salario_bruto_acumulado == Decimal(stress["salary"]) * len(runs)
            assert accumulated.salario_gravable_acumulado == Decimal(stress["salary"]) * len(runs)
            assert accumulated.deducciones_antes_impuesto_acumulado == Decimal(expected["epf_employee"]) * len(runs)
            assert accumulated.impuesto_retenido_acumulado == Decimal(expected["tds"]) * len(runs)
            assert accumulated.periodos_procesados == len(runs)

        benefit_transactions = db_session.execute(
            db.select(PrestacionAcumulada).filter(PrestacionAcumulada.nomina_id.in_([item.id for item in executed]))
        ).scalars().all()
        assert len(benefit_transactions) == stress["employee_count"] * len(stress["benefits"]) * len(runs)

        vacation_entries = db_session.execute(
            db.select(VacationLedger).join(VacationAccount).filter(
                VacationAccount.empleado_id.in_([item.id for item in employees])
            )
        ).scalars().all()
        assert len(vacation_entries) == stress["employee_count"] * len(runs) + 1
        assert sum(item.quantity for item in vacation_entries if item.entry_type == "usage") == -Decimal(
            vacation_config["usage_days"]
        )
        assert sum(item.quantity for item in vacation_entries if item.entry_type == "accrual") == Decimal(
            vacation_config["accrual_rate_days"]
        ) * stress["employee_count"] * len(runs)
