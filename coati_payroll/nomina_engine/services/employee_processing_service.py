# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Employee processing service for building calculation variables."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from coati_payroll.i18n import _
from coati_payroll.formula_engine.data_sources import AVAILABLE_DATA_SOURCES, get_formula_variable_name
from coati_payroll.model import AcumuladoAnual, Adelanto, Empleado, Planilla, VacationAccount, db
from ..domain.employee_calculation import EmpleadoCalculo
from ..repositories.acumulado_repository import AcumuladoRepository
from ..repositories.config_repository import ConfigRepository
from ..results.warning_collector import WarningCollectorProtocol
from ..utils.fiscal import fiscal_start_date


class EmployeeProcessingService:
    """Service for processing employee calculations and building variables."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        acumulado_repository: AcumuladoRepository,
    ):
        self.config_repo = config_repository
        self.acumulado_repo = acumulado_repository

    def build_calculation_variables(
        self,
        emp_calculo: EmpleadoCalculo,
        planilla: Planilla,
        periodo_inicio: date,
        periodo_fin: date,
        fecha_calculo: date,
        configuracion_snapshot: dict[str, Any] | None = None,
        bootstrap_context: dict[str, Any] | None = None,
        warnings: WarningCollectorProtocol | None = None,
    ) -> dict[str, Any]:
        """Build the calculation variables for an employee."""
        empleado = emp_calculo.empleado
        tipo_planilla = planilla.tipo_planilla
        empresa = planilla.empresa

        config = self._resolve_config(planilla.empresa_id, configuracion_snapshot)

        # Calculate days in period
        dias_periodo = (periodo_fin - periodo_inicio).days + 1

        # Calculate seniority using configuration
        fecha_alta = empleado.fecha_alta or date.today()
        antiguedad_dias = (fecha_calculo - fecha_alta).days
        antiguedad_meses = antiguedad_dias // config.dias_mes_antiguedad
        antiguedad_anios = antiguedad_dias // config.dias_anio_antiguedad

        # Calendar/personal flags are exposed as numeric values so they can be
        # consumed by the formula engine's Decimal comparisons.  This keeps
        # event-driven concepts (birthday and Mother's Day bonuses) configurable
        # as ordinary perceptions instead of embedding amounts in the engine.
        fecha_nacimiento = getattr(empleado, "fecha_nacimiento", None)
        es_cumpleanos = bool(
            fecha_nacimiento
            and fecha_nacimiento.month == fecha_calculo.month
            and fecha_nacimiento.day == fecha_calculo.day
        )
        datos_adicionales = getattr(empleado, "datos_adicionales", None) or {}
        es_madre = bool(datos_adicionales.get("es_madre", False))
        # Nicaragua's statutory Mother's Day is May 30.  The date is isolated
        # as a variable so deployments with another local rule can override it
        # in their calculation formula/configuration without changing payroll
        # arithmetic.
        es_dia_madre = fecha_calculo.month == 5 and fecha_calculo.day == 30

        # Calculate remaining months in fiscal year (source of truth: planilla.mes_inicio_fiscal)
        mes_inicio_fiscal = int(planilla.mes_inicio_fiscal or (tipo_planilla.mes_inicio_fiscal if tipo_planilla else 1))
        meses_anio_financiero = int(config.meses_anio_financiero)
        if meses_anio_financiero <= 0:
            from ..validators import ValidationError

            raise ValidationError("Configuración inválida: meses_anio_financiero debe ser mayor que cero.")

        if not 1 <= mes_inicio_fiscal <= meses_anio_financiero:
            from ..validators import ValidationError

            raise ValidationError(
                "Configuración inválida: mes_inicio_fiscal fuera del rango del año financiero configurado."
            )

        meses_transcurridos = (fecha_calculo.month - mes_inicio_fiscal) % meses_anio_financiero
        meses_restantes = meses_anio_financiero - meses_transcurridos
        if meses_restantes <= 0:
            from ..validators import ValidationError

            raise ValidationError("Configuración inválida: meses_restantes calculado es menor o igual a cero.")

        # Build variables dictionary
        variables = {
            # Employee base data
            "salario_base": emp_calculo.salario_base,
            "salario_mensual": emp_calculo.salario_mensual,
            "tipo_cambio": emp_calculo.tipo_cambio,
            "salario_neto_inasistencia": emp_calculo.salario_neto_inasistencia,
            "salario_gravable": emp_calculo.salario_gravable,
            "salario_gravable_periodo": emp_calculo.salario_gravable,
            # Period data
            "fecha_calculo": fecha_calculo,
            "periodo_inicio": periodo_inicio,
            "periodo_fin": periodo_fin,
            "dias_periodo": Decimal(str(dias_periodo)),
            # Seniority
            "fecha_alta": fecha_alta,
            "antiguedad_dias": Decimal(str(antiguedad_dias)),
            "antiguedad_meses": Decimal(str(antiguedad_meses)),
            "antiguedad_anios": Decimal(str(antiguedad_anios)),
            "es_cumpleanos": Decimal("1") if es_cumpleanos else Decimal("0"),
            "es_madre": Decimal("1") if es_madre else Decimal("0"),
            "es_dia_madre": Decimal("1") if es_dia_madre else Decimal("0"),
            # Fiscal calculations
            "meses_restantes": Decimal(str(meses_restantes)),
            "periodos_por_anio": Decimal(
                str(tipo_planilla.periodos_por_anio if tipo_planilla else meses_anio_financiero)
            ),
            # Accumulated values (will be populated from AcumuladoAnual)
            "salario_acumulado": Decimal("0.00"),
            "impuesto_acumulado": Decimal("0.00"),
            "ir_retenido_acumulado": Decimal("0.00"),
            "salario_acumulado_mes": Decimal("0.00"),
            # Absence tracking
            "inasistencia_dias": emp_calculo.inasistencia_dias,
            "inasistencia_horas": emp_calculo.inasistencia_horas,
            "inasistencia_descuento": emp_calculo.inasistencia_descuento,
        }

        # The formula editor publishes flat identifiers, so expose the
        # documented employee, payroll type and planilla fields directly in
        # the calculation context rather than advertising unusable dotted
        # paths.  ``getattr`` keeps old installations compatible with records
        # that predate optional fields.
        for field in (
            "primer_nombre",
            "segundo_nombre",
            "primer_apellido",
            "segundo_apellido",
            "identificacion_personal",
            "id_seguridad_social",
            "id_fiscal",
            "genero",
            "nacionalidad",
            "estado_civil",
            "fecha_nacimiento",
            "fecha_alta",
            "fecha_baja",
            "fecha_ultimo_aumento",
            "cargo",
            "area",
            "centro_costos",
            "tipo_contrato",
            "activo",
            "banco",
            "numero_cuenta_bancaria",
            "ultimos_tres_salarios",
            "datos_adicionales",
        ):
            variables[field] = getattr(empleado, field, None)
        for field in (
            "codigo",
            "periodicidad",
            "dias",
            "periodos_por_anio",
            "mes_inicio_fiscal",
            "dia_inicio_fiscal",
            "acumula_anual",
        ):
            variables[field] = getattr(tipo_planilla, field, None) if tipo_planilla else None
        for field in (
            "nombre",
            "periodo_fiscal_inicio",
            "periodo_fiscal_fin",
            "prioridad_prestamos",
            "prioridad_adelantos",
        ):
            variables[field] = getattr(planilla, field, None)

        dias_base = Decimal(str(config.dias_mes_nomina))
        horas_diarias = Decimal(str(config.horas_jornada_diaria))
        inicio_laborado = max(periodo_inicio, fecha_alta)
        fecha_baja = getattr(empleado, "fecha_baja", None)
        fin_laborado = min(periodo_fin, fecha_baja) if fecha_baja else periodo_fin
        dias_trabajados = max((fin_laborado - inicio_laborado).days + 1, 0)
        edad_anios = 0
        if fecha_nacimiento:
            edad_anios = (
                fecha_calculo.year
                - fecha_nacimiento.year
                - ((fecha_calculo.month, fecha_calculo.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
            )
        variables.update(
            {
                "salario_diario": emp_calculo.salario_mensual / dias_base,
                "salario_hora": emp_calculo.salario_mensual / dias_base / horas_diarias,
                "edad_anios": Decimal(str(max(edad_anios, 0))),
                "es_nuevo_ingreso": Decimal("1") if periodo_inicio <= fecha_alta <= periodo_fin else Decimal("0"),
                "dias_proporcional": Decimal(str(dias_trabajados)),
                "dias_trabajados_periodo": Decimal(str(dias_trabajados)),
                "mes_nomina": Decimal(str(periodo_fin.month)),
                "anio_nomina": Decimal(str(periodo_fin.year)),
                "meses_restantes_fiscal": Decimal(str(meses_restantes)),
                "periodos_restantes_fiscal": Decimal("0"),
                "es_primer_periodo_sistema": Decimal("0"),
            }
        )

        salario_base_acumulado = Decimal(str(empleado.salario_acumulado or 0))
        impuesto_base_acumulado = Decimal(str(empleado.impuesto_acumulado or 0))

        es_periodo_inicial = self._is_initial_company_period(empresa, periodo_inicio, bootstrap_context)
        if es_periodo_inicial:
            variables["salario_acumulado"] = salario_base_acumulado
            variables["impuesto_acumulado"] = impuesto_base_acumulado
            variables["ir_retenido_acumulado"] = impuesto_base_acumulado
            if warnings and salario_base_acumulado == Decimal("0") and impuesto_base_acumulado == Decimal("0"):
                warnings.append(
                    _(
                        "Empleado %(codigo)s no tiene salario_acumulado ni "
                        "impuesto_acumulado para el período inicial; se continúa con el cálculo.",
                    )
                    % {"codigo": empleado.codigo_empleado}
                )

        # Add novelties
        for codigo, valor in emp_calculo.novedades.items():
            variables[f"novedad_{codigo}"] = valor
        for field_name, field_info in AVAILABLE_DATA_SOURCES["novedad"]["fields"].items():
            variables.setdefault(get_formula_variable_name("novedad", field_name, field_info), Decimal("0.00"))

        # Only values denominated in the planilla currency are safe to combine
        # directly in a formula.  Cross-currency loan deductions are converted
        # when they are applied by LoanProcessor.
        employee_id = getattr(empleado, "id", None)
        if employee_id:
            loans_and_advances = (
                db.session.execute(
                    db.select(Adelanto).where(
                        Adelanto.empleado_id == employee_id,
                        Adelanto.estado == "approved",
                        Adelanto.saldo_pendiente > 0,
                        db.or_(Adelanto.moneda_id.is_(None), Adelanto.moneda_id == planilla.moneda_id),
                    )
                )
                .scalars()
                .all()
            )
            loans = [item for item in loans_and_advances if item.deduccion_id]
            advances = [item for item in loans_and_advances if not item.deduccion_id]
            variables.update(
                {
                    "total_cuotas_prestamos": sum(
                        (Decimal(str(item.monto_por_cuota or 0)) for item in loans), Decimal("0.00")
                    ),
                    "total_adelantos_pendientes": sum(
                        (Decimal(str(item.saldo_pendiente or 0)) for item in advances), Decimal("0.00")
                    ),
                    "cantidad_prestamos_activos": Decimal(str(len(loans))),
                    "saldo_total_prestamos": sum(
                        (Decimal(str(item.saldo_pendiente or 0)) for item in loans), Decimal("0.00")
                    ),
                }
            )
            accounts_query = db.select(VacationAccount).where(
                VacationAccount.empleado_id == employee_id,
                VacationAccount.activo.is_(True),
            )
            if planilla.vacation_policy_id:
                accounts_query = accounts_query.where(VacationAccount.policy_id == planilla.vacation_policy_id)
            vacation_accounts = db.session.execute(accounts_query).scalars().all()
            variables.update(
                {
                    "dias_vacaciones_acumulados": sum(
                        (Decimal(str(account.accrued_days or 0)) for account in vacation_accounts), Decimal("0.00")
                    ),
                    "dias_vacaciones_tomados": sum(
                        (Decimal(str(account.used_days or 0)) for account in vacation_accounts), Decimal("0.00")
                    ),
                    "dias_vacaciones_disponibles": sum(
                        (Decimal(str(account.current_balance or 0)) for account in vacation_accounts), Decimal("0.00")
                    ),
                }
            )

        # Load accumulated annual values
        acumulado = self._get_acumulado_anual(empleado, planilla, periodo_inicio)
        if acumulado:
            variables["salario_acumulado"] = Decimal(str(acumulado.salario_bruto_acumulado or 0))
            variables["impuesto_acumulado"] = Decimal(str(acumulado.impuesto_retenido_acumulado or 0))
            variables["ir_retenido_acumulado"] = Decimal(str(acumulado.impuesto_retenido_acumulado or 0))
            variables["salario_acumulado_mes"] = Decimal(str(acumulado.salario_acumulado_mes or 0))
            accumulated_totals = acumulado.datos_adicionales or {}
            variables["total_percepciones_acumulado"] = Decimal(
                str(accumulated_totals.get("total_percepciones_acumulado", 0))
            )
            variables["total_deducciones_acumulado"] = Decimal(
                str(accumulated_totals.get("total_deducciones_acumulado", 0))
            )
            variables["total_neto_acumulado"] = Decimal(str(accumulated_totals.get("total_neto_acumulado", 0)))

            # Additional accumulated values for progressive tax calculations
            variables["salario_bruto_acumulado"] = Decimal(str(acumulado.salario_bruto_acumulado or 0))
            variables["salario_gravable_acumulado"] = Decimal(str(acumulado.salario_gravable_acumulado or 0))
            variables["deducciones_antes_impuesto_acumulado"] = Decimal(
                str(acumulado.deducciones_antes_impuesto_acumulado or 0)
            )
            variables["periodos_procesados"] = Decimal(str(acumulado.periodos_procesados or 0))
            variables["numero_periodo"] = Decimal(str(int(acumulado.periodos_procesados or 0) + 1))
            # For monthly payroll, months worked should follow the fiscal calendar
            # (e.g. Feb payroll corresponds to period 2), not only processed runs.
            if tipo_planilla and (tipo_planilla.periodicidad or "").lower() in ("mensual", "monthly"):
                meses_previos = self._calculate_elapsed_fiscal_months_before_period(
                    fecha_referencia=periodo_fin,
                    fecha_alta=fecha_alta,
                    mes_inicio_fiscal=mes_inicio_fiscal,
                    dia_inicio_fiscal=tipo_planilla.dia_inicio_fiscal,
                )
                variables["meses_trabajados"] = Decimal(str(meses_previos))
            else:
                variables["meses_trabajados"] = Decimal(str(acumulado.periodos_procesados or 0))

            # Calculate net accumulated salary
            variables["salario_neto_acumulado"] = Decimal(str(acumulado.salario_bruto_acumulado or 0)) - Decimal(
                str(acumulado.deducciones_antes_impuesto_acumulado or 0)
            )
        else:
            # Define default values for progressive tax calculations (when acumulado is None)
            salario_bruto_default = salario_base_acumulado if es_periodo_inicial else Decimal("0.00")
            deducciones_antes_impuesto_default = Decimal("0.00")

            variables["salario_bruto_acumulado"] = salario_bruto_default
            variables["salario_gravable_acumulado"] = salario_base_acumulado if es_periodo_inicial else Decimal("0.00")
            variables["deducciones_antes_impuesto_acumulado"] = deducciones_antes_impuesto_default
            variables["impuesto_retenido_acumulado"] = (
                impuesto_base_acumulado if es_periodo_inicial else Decimal("0.00")
            )
            variables["periodos_procesados"] = Decimal("0.00")
            variables["numero_periodo"] = Decimal("1")
            if tipo_planilla and (tipo_planilla.periodicidad or "").lower() in ("mensual", "monthly"):
                meses_previos = self._calculate_elapsed_fiscal_months_before_period(
                    fecha_referencia=periodo_fin,
                    fecha_alta=fecha_alta,
                    mes_inicio_fiscal=mes_inicio_fiscal,
                    dia_inicio_fiscal=tipo_planilla.dia_inicio_fiscal,
                )
                variables["meses_trabajados"] = Decimal(str(meses_previos))
            else:
                variables["meses_trabajados"] = Decimal("0.00")
            variables["salario_neto_acumulado"] = salario_bruto_default - deducciones_antes_impuesto_default

        for field_name in AVAILABLE_DATA_SOURCES["acumulado_anual"]["fields"]:
            variables.setdefault(field_name, Decimal("0.00"))
        for field_name in AVAILABLE_DATA_SOURCES["prestamos_adelantos"]["fields"]:
            variables.setdefault(field_name, Decimal("0.00"))
        for field_name in AVAILABLE_DATA_SOURCES["vacaciones"]["fields"]:
            variables.setdefault(field_name, Decimal("0.00"))

        numero_periodo = Decimal(str(variables["numero_periodo"]))
        periodos_por_anio = Decimal(str(tipo_planilla.periodos_por_anio if tipo_planilla else meses_anio_financiero))
        variables["periodos_restantes"] = max(periodos_por_anio - numero_periodo, Decimal("0"))
        variables["periodos_restantes_fiscal"] = variables["periodos_restantes"]
        variables["es_ultimo_periodo_anual"] = Decimal("1") if numero_periodo >= periodos_por_anio else Decimal("0")
        variables["es_periodo_inicial"] = Decimal("1") if es_periodo_inicial else Decimal("0")
        variables["es_primer_periodo_sistema"] = variables["es_periodo_inicial"]

        # Include initial accumulated values from employee
        variables["salario_inicial_acumulado"] = salario_base_acumulado
        variables["impuesto_inicial_acumulado"] = impuesto_base_acumulado

        return variables

    def _calculate_elapsed_fiscal_months_before_period(
        self,
        fecha_referencia: date,
        fecha_alta: date,
        mes_inicio_fiscal: int,
        dia_inicio_fiscal: int,
    ) -> int:
        """Return elapsed fiscal months before the current payroll period.

        Example:
        - Fiscal start Jan 1
        - Payroll period in Feb
        -> returns 1, so formulas can compute period 2 with +1.
        """
        fiscal_year = fecha_referencia.year
        if fecha_referencia.month < mes_inicio_fiscal:
            fiscal_year -= 1

        fiscal_start = fiscal_start_date(fiscal_year, mes_inicio_fiscal, dia_inicio_fiscal)
        employee_start_month = date(fecha_alta.year, fecha_alta.month, 1)
        effective_start = max(fiscal_start, employee_start_month)
        reference_month = date(fecha_referencia.year, fecha_referencia.month, 1)

        if reference_month < effective_start:
            return 0

        months = (reference_month.year - effective_start.year) * 12 + (reference_month.month - effective_start.month)
        return max(months, 0)

    def _resolve_config(self, empresa_id: str, configuracion_snapshot: dict[str, Any] | None) -> Any:
        if configuracion_snapshot:
            return SimpleNamespace(**configuracion_snapshot)

        return self.config_repo.get_for_empresa(empresa_id)

    def _get_acumulado_anual(
        self, empleado: Empleado, planilla: Planilla, periodo_inicio: date
    ) -> AcumuladoAnual | None:
        """Get accumulated annual values for employee."""
        if not planilla.tipo_planilla:
            return None

        tipo_planilla = planilla.tipo_planilla

        # Calculate fiscal period
        anio = periodo_inicio.year
        mes_inicio = int(planilla.mes_inicio_fiscal or tipo_planilla.mes_inicio_fiscal)
        dia_inicio = tipo_planilla.dia_inicio_fiscal

        # Honor the configured start *day* as well as the start month.  A
        # payroll before that day belongs to the fiscal year which began the
        # previous calendar year.
        if periodo_inicio < fiscal_start_date(anio, mes_inicio, dia_inicio):
            anio -= 1

        periodo_fiscal_inicio = fiscal_start_date(anio, mes_inicio, dia_inicio)

        # Look up existing accumulated record
        from sqlalchemy import select
        from coati_payroll.model import db

        acumulado = (
            db.session.execute(
                select(AcumuladoAnual).filter(
                    AcumuladoAnual.empleado_id == empleado.id,
                    AcumuladoAnual.tipo_planilla_id == tipo_planilla.id,
                    AcumuladoAnual.empresa_id == planilla.empresa_id,
                    AcumuladoAnual.periodo_fiscal_inicio == periodo_fiscal_inicio,
                )
            )
            .unique()
            .scalar_one_or_none()
        )

        return acumulado

    def _is_initial_company_period(
        self,
        empresa,
        periodo_inicio: date,
        bootstrap_context: dict[str, Any] | None = None,
    ) -> bool:
        """Return whether periodo_inicio matches the company's first payroll period."""
        if bootstrap_context is not None and "is_initial_period" in bootstrap_context:
            return bool(bootstrap_context["is_initial_period"])

        if not empresa:
            return False

        primer_mes = empresa.primer_mes_nomina
        primer_anio = empresa.primer_anio_nomina
        if primer_mes is None or primer_anio is None:
            return False

        return periodo_inicio.month == int(primer_mes) and periodo_inicio.year == int(primer_anio)
