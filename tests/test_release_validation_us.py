# SPDX-License-Identifier: Apache-2.0
"""United States 2026 FICA release validation through the payroll service."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from coati_payroll.model import (
    AcumuladoAnual,
    ConfiguracionCalculos, Deduccion, Empleado, Empresa, Moneda, Planilla,
    PlanillaDeduccion, PlanillaEmpleado, ReglaCalculo, TipoPlanilla, db,
)
from coati_payroll.nomina_engine.services.payroll_execution_service import PayrollExecutionService


pytestmark = pytest.mark.release_validation
PROFILE = json.loads((Path(__file__).parents[1] / "coati_payroll/jurisdictions/us_2026.json").read_text(encoding="utf-8"))


def test_us_2026_fica_monthly_payroll_from_json_profile(app, db_session):
    case = PROFILE["cases"][0]
    start, end = date.fromisoformat(case["period_start"]), date.fromisoformat(case["period_end"])

    with app.app_context():
        currency = Moneda(codigo=PROFILE["currency"], nombre="US Dollar", simbolo="$", activo=True)
        company = Empresa(codigo=PROFILE["company"]["code"], razon_social=PROFILE["company"]["legal_name"], ruc=PROFILE["company"]["tax_id"], primer_mes_nomina=1, primer_anio_nomina=start.year)
        payroll_type = TipoPlanilla(codigo=PROFILE["payroll"]["code"], descripcion=PROFILE["name"], periodicidad="monthly", dias=PROFILE["payroll"]["days_per_month"], periodos_por_anio=PROFILE["payroll"]["periods_per_year"], mes_inicio_fiscal=1, dia_inicio_fiscal=1)
        db_session.add_all([currency, company, payroll_type])
        db_session.flush()
        payroll = Planilla(nombre=PROFILE["payroll"]["code"], tipo_planilla=payroll_type, empresa=company, moneda=currency, mes_inicio_fiscal=1, activo=True)
        db_session.add(payroll)
        db_session.add(ConfiguracionCalculos(empresa_id=company.id, pais_id=PROFILE["country"], dias_mes_nomina=PROFILE["payroll"]["days_per_month"], dias_anio_nomina=PROFILE["payroll"]["days_per_year"], horas_jornada_diaria=Decimal(PROFILE["payroll"]["daily_hours"],), dias_mes_vacaciones=PROFILE["payroll"]["days_per_month"], dias_anio_vacaciones=PROFILE["payroll"]["days_per_year"], dias_anio_financiero=PROFILE["payroll"]["days_per_year"], meses_anio_financiero=PROFILE["payroll"]["periods_per_year"], dias_quincena=PROFILE["payroll"]["days_per_half_month"], dias_mes_antiguedad=PROFILE["payroll"]["days_per_month"], dias_anio_antiguedad=PROFILE["payroll"]["days_per_year"]))
        db_session.flush()
        employee = Empleado(codigo_empleado="US-EMP-0001", primer_nombre="Release", primer_apellido="Validation", identificacion_personal="US-RELEASE-0001", fecha_alta=start, salario_base=Decimal(case["salary"]), moneda_id=currency.id, empresa_id=company.id, activo=True)
        db_session.add(employee)
        db_session.flush()
        db_session.add(PlanillaEmpleado(planilla_id=payroll.id, empleado_id=employee.id, activo=True))

        deductions = []
        for priority, rule in enumerate(PROFILE["rules"].values(), start=1):
            deduction = Deduccion(codigo=rule["code"], nombre=rule["code"], formula_tipo="regla_calculo", es_impuesto=False, antes_impuesto=rule["before_tax"], activo=True)
            db_session.add(deduction)
            db_session.flush()
            db_session.add(ReglaCalculo(codigo=rule["code"], nombre=rule["code"], tipo_regla=rule["type"], esquema_json=rule["formula"], vigente_desde=start, activo=True, deduccion_id=deduction.id))
            db_session.add(PlanillaDeduccion(planilla_id=payroll.id, deduccion_id=deduction.id, prioridad=priority, es_obligatoria=True))
            deductions.append(deduction)
        db_session.commit()
        db_session.refresh(payroll)

        expected = case["expected"]
        for period_start, period_end in ((start, end), (date(2026, 2, 1), date(2026, 2, 28))):
            nomina, employees, errors, warnings = PayrollExecutionService(db_session).execute_payroll(planilla=payroll, periodo_inicio=period_start, periodo_fin=period_end, fecha_calculo=period_end, usuario="release-validation")
            assert errors == []
            assert nomina is not None and len(employees) == 1
            assert employees[0].salario_bruto == Decimal(expected["gross"])
            assert {item.codigo: item.monto for item in employees[0].deducciones} == {rule["code"]: Decimal(expected[key]) for rule, key in zip(PROFILE["rules"].values(), ("social_security", "medicare"))}
            assert employees[0].salario_neto == Decimal(expected["net"])

        accumulated = db_session.execute(db.select(AcumuladoAnual).filter_by(empleado_id=employee.id, empresa_id=company.id)).scalar_one()
        assert accumulated.salario_bruto_acumulado == Decimal("20000.00")
        assert accumulated.impuesto_retenido_acumulado == Decimal("0.00")
        assert accumulated.periodos_procesados == 2
