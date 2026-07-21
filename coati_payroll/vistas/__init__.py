# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Vistas module for the payroll application."""

from coati_payroll.vistas.user import user_bp
from coati_payroll.vistas.currency import currency_bp
from coati_payroll.vistas.exchange_rate import exchange_rate_bp
from coati_payroll.vistas.employee import employee_bp
from coati_payroll.vistas.custom_field import custom_field_bp
from coati_payroll.vistas.calculation_rule import calculation_rule_bp
from coati_payroll.vistas.payroll_concepts import (
    percepcion_bp,
    deduccion_bp,
    prestacion_bp,
)
from coati_payroll.vistas.planilla import planilla_bp
from coati_payroll.vistas.nomina import nomina_bp
from coati_payroll.vistas.tipo_planilla import tipo_planilla_bp
from coati_payroll.vistas.prestamo import prestamo_bp
from coati_payroll.vistas.empresa import empresa_bp
from coati_payroll.vistas.configuracion import configuracion_bp
from coati_payroll.vistas.carga_inicial_prestacion import carga_inicial_prestacion_bp
from coati_payroll.vistas.vacation import vacation_bp
from coati_payroll.vistas.prestacion import prestacion_management_bp
from coati_payroll.vistas.report import report_bp
from coati_payroll.vistas.settings import settings_bp
from coati_payroll.vistas.implementation import implementation_bp
from coati_payroll.vistas.config_calculos import config_calculos_bp
from coati_payroll.vistas.liquidacion import liquidacion_bp
from coati_payroll.vistas.plugins import plugins_bp

__all__ = [
    "user_bp",
    "currency_bp",
    "exchange_rate_bp",
    "employee_bp",
    "custom_field_bp",
    "calculation_rule_bp",
    "percepcion_bp",
    "deduccion_bp",
    "prestacion_bp",
    "planilla_bp",
    "nomina_bp",
    "tipo_planilla_bp",
    "prestamo_bp",
    "empresa_bp",
    "configuracion_bp",
    "carga_inicial_prestacion_bp",
    "vacation_bp",
    "prestacion_management_bp",
    "report_bp",
    "settings_bp",
    "implementation_bp",
    "plugins_bp",
    "config_calculos_bp",
    "liquidacion_bp",
]
