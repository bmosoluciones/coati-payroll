# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Available data sources for formula engine calculations.

This module defines all available data sources that can be accessed
when creating calculation rules in the formula engine.
"""

# ................................ CONTANTES ................................ #
AVAILABLE_DATA_SOURCES = {
    "empleado": {
        "label": "Empleado",
        "description": "Datos del registro de empleado",
        "fields": {
            # Identificación
            "primer_nombre": {
                "type": "string",
                "label": "Primer Nombre",
                "description": "Primer nombre del empleado",
            },
            "segundo_nombre": {
                "type": "string",
                "label": "Segundo Nombre",
                "description": "Segundo nombre del empleado",
            },
            "primer_apellido": {
                "type": "string",
                "label": "Primer Apellido",
                "description": "Primer apellido del empleado",
            },
            "segundo_apellido": {
                "type": "string",
                "label": "Segundo Apellido",
                "description": "Segundo apellido del empleado",
            },
            "identificacion_personal": {
                "type": "string",
                "label": "Identificación Personal",
                "description": "Número de cédula o documento de identidad",
            },
            "id_seguridad_social": {
                "type": "string",
                "label": "ID Seguridad Social",
                "description": "Número de seguro social (INSS)",
            },
            "id_fiscal": {
                "type": "string",
                "label": "ID Fiscal",
                "description": "Número de identificación fiscal (RUC/NIT)",
            },
            "genero": {
                "type": "string",
                "label": "Género",
                "description": "Género del empleado",
            },
            "nacionalidad": {
                "type": "string",
                "label": "Nacionalidad",
                "description": "Nacionalidad del empleado",
            },
            "estado_civil": {
                "type": "string",
                "label": "Estado Civil",
                "description": "Estado civil del empleado",
            },
            # Fechas
            "fecha_nacimiento": {
                "type": "date",
                "label": "Fecha de Nacimiento",
                "description": "Fecha de nacimiento del empleado",
            },
            "fecha_alta": {
                "type": "date",
                "label": "Fecha de Ingreso",
                "description": "Fecha de inicio de labores del empleado",
            },
            "fecha_baja": {
                "type": "date",
                "label": "Fecha de Baja",
                "description": "Fecha de terminación de labores",
            },
            "fecha_ultimo_aumento": {
                "type": "date",
                "label": "Fecha Último Aumento",
                "description": "Fecha del último aumento de salario",
            },
            # Información laboral
            "cargo": {
                "type": "string",
                "label": "Cargo",
                "description": "Cargo o puesto del empleado",
            },
            "area": {
                "type": "string",
                "label": "Área",
                "description": "Área o departamento del empleado",
            },
            "centro_costos": {
                "type": "string",
                "label": "Centro de Costos",
                "description": "Centro de costos asignado al empleado",
            },
            "tipo_contrato": {
                "type": "string",
                "label": "Tipo de Contrato",
                "description": "Tipo de contrato (indefinido, temporal, etc.)",
            },
            "activo": {
                "type": "boolean",
                "label": "Empleado Activo",
                "description": "Indica si el empleado está activo",
            },
            # Salario y compensación
            "salario_base": {
                "type": "decimal",
                "label": "Salario Base",
                "description": "Salario mensual base del empleado",
            },
            # Datos bancarios
            "banco": {
                "type": "string",
                "label": "Banco",
                "description": "Nombre del banco para depósito",
            },
            "numero_cuenta_bancaria": {
                "type": "string",
                "label": "Número de Cuenta Bancaria",
                "description": "Número de cuenta para depósito de nómina",
            },
            # Implementation initial fields - for when system starts mid-fiscal-year
            "salario_acumulado": {
                "type": "decimal",
                "label": "Salario Acumulado (Implementación)",
                "description": "Suma de salarios del año fiscal antes del sistema",
            },
            "impuesto_acumulado": {
                "type": "decimal",
                "label": "Impuesto Acumulado (Implementación)",
                "description": "Suma de impuestos pagados antes del sistema",
            },
            "ultimos_tres_salarios": {
                "type": "json",
                "label": "Últimos Tres Salarios",
                "description": "JSON con los últimos 3 salarios mensuales previos",
            },
            # Datos adicionales (campos personalizados)
            "datos_adicionales": {
                "type": "json",
                "label": "Datos Adicionales",
                "description": "Campos personalizados definidos para el empleado",
            },
        },
    },
    "nomina": {
        "label": "Nómina / Cálculo",
        "description": "Datos del período de nómina actual",
        "fields": {
            "fecha_calculo": {
                "type": "date",
                "label": "Fecha de Cálculo",
                "description": "Fecha en que se ejecuta/genera la nómina",
            },
            "periodo_inicio": {
                "type": "date",
                "label": "Inicio del Período",
                "description": "Fecha de inicio del período de nómina",
            },
            "periodo_fin": {
                "type": "date",
                "label": "Fin del Período",
                "description": "Fecha de fin del período de nómina",
            },
            "dias_periodo": {
                "type": "integer",
                "label": "Días del Período",
                "description": "Número de días del período de nómina",
            },
            "mes_nomina": {
                "type": "integer",
                "label": "Mes de Nómina",
                "description": "Mes del período de nómina (1-12)",
            },
            "anio_nomina": {
                "type": "integer",
                "label": "Año de Nómina",
                "description": "Año del período de nómina",
            },
            "numero_periodo": {
                "type": "integer",
                "label": "Número de Período",
                "description": "Número de período en el año fiscal (1, 2, 3...)",
            },
            "es_ultimo_periodo_anual": {
                "type": "boolean",
                "label": "Es Último Período del Año",
                "description": "Indica si es el último período del año fiscal",
            },
        },
    },
    "tipo_planilla": {
        "label": "Tipo de Planilla",
        "description": "Configuración del tipo de planilla",
        "fields": {
            "codigo": {
                "type": "string",
                "label": "Código",
                "description": "Código del tipo de planilla",
            },
            "periodicidad": {
                "type": "string",
                "label": "Periodicidad",
                "description": "Frecuencia de pago (mensual, quincenal, semanal)",
            },
            "dias": {
                "type": "integer",
                "label": "Días del Período",
                "description": "Días usados para prorrateos",
            },
            "periodos_por_anio": {
                "type": "integer",
                "label": "Períodos por Año",
                "description": "Número de períodos de pago por año fiscal",
            },
            "mes_inicio_fiscal": {
                "type": "integer",
                "label": "Mes Inicio Fiscal",
                "description": "Mes de inicio del período fiscal (1-12)",
            },
            "dia_inicio_fiscal": {
                "type": "integer",
                "label": "Día Inicio Fiscal",
                "description": "Día de inicio del período fiscal",
            },
            "acumula_anual": {
                "type": "boolean",
                "label": "Acumula Anual",
                "description": "Si acumula valores anuales para cálculos",
            },
        },
    },
    "planilla": {
        "label": "Planilla",
        "description": "Datos de la planilla actual",
        "fields": {
            "nombre": {
                "type": "string",
                "label": "Nombre de Planilla",
                "description": "Nombre de la planilla",
            },
            "periodo_fiscal_inicio": {
                "type": "date",
                "label": "Inicio Período Fiscal",
                "description": "Fecha de inicio del período fiscal de la planilla",
            },
            "periodo_fiscal_fin": {
                "type": "date",
                "label": "Fin Período Fiscal",
                "description": "Fecha de fin del período fiscal de la planilla",
            },
            "prioridad_prestamos": {
                "type": "integer",
                "label": "Prioridad Préstamos",
                "description": "Prioridad de deducción de préstamos",
            },
            "prioridad_adelantos": {
                "type": "integer",
                "label": "Prioridad Adelantos",
                "description": "Prioridad de deducción de adelantos",
            },
        },
    },
    "acumulado_anual": {
        "label": "Acumulados del Período Fiscal",
        "description": "Valores acumulados en el año fiscal actual",
        "fields": {
            "salario_bruto_acumulado": {
                "type": "decimal",
                "label": "Salario Bruto Acumulado",
                "description": "Total de salario bruto en el período fiscal",
            },
            "salario_gravable_acumulado": {
                "type": "decimal",
                "label": "Salario Gravable Acumulado",
                "description": "Total de salario gravable en el período fiscal",
            },
            "deducciones_antes_impuesto_acumulado": {
                "type": "decimal",
                "label": "Deducciones Pre-Impuesto Acumuladas",
                "description": "Total de deducciones antes de impuesto",
            },
            "impuesto_retenido_acumulado": {
                "type": "decimal",
                "label": "Impuesto Retenido Acumulado",
                "description": "Total de impuesto retenido en el período",
            },
            "periodos_procesados": {
                "type": "integer",
                "label": "Períodos Procesados",
                "description": "Número de nóminas procesadas en el período fiscal",
            },
            "total_percepciones_acumulado": {
                "type": "decimal",
                "label": "Total Percepciones Acumulado",
                "description": "Total de percepciones en el período fiscal",
            },
            "total_deducciones_acumulado": {
                "type": "decimal",
                "label": "Total Deducciones Acumulado",
                "description": "Total de deducciones en el período fiscal",
            },
            "total_neto_acumulado": {
                "type": "decimal",
                "label": "Total Neto Acumulado",
                "description": "Total neto pagado en el período fiscal",
            },
            "salario_acumulado_mes": {
                "type": "decimal",
                "label": "Salario Acumulado del Mes",
                "description": "Total de salario bruto acumulado en el mes calendario actual.",
            },
        },
    },
    "prestamos_adelantos": {
        "label": "Préstamos y Adelantos (Automático)",
        "description": "Valores calculados automáticamente desde la tabla Adelanto",
        "fields": {
            "total_cuotas_prestamos": {
                "type": "decimal",
                "label": "Total Cuotas de Préstamos",
                "description": "Suma de cuotas de préstamos activos a descontar",
            },
            "total_adelantos_pendientes": {
                "type": "decimal",
                "label": "Total Adelantos Pendientes",
                "description": "Suma de adelantos salariales pendientes",
            },
            "cantidad_prestamos_activos": {
                "type": "integer",
                "label": "Cantidad de Préstamos Activos",
                "description": "Número de préstamos activos del empleado",
            },
            "saldo_total_prestamos": {
                "type": "decimal",
                "label": "Saldo Total de Préstamos",
                "description": "Saldo pendiente total de todos los préstamos",
            },
        },
    },
    "vacaciones": {
        "label": "Vacaciones",
        "description": "Datos de vacaciones del empleado",
        "fields": {
            "dias_vacaciones_acumulados": {
                "type": "decimal",
                "label": "Días de Vacaciones Acumulados",
                "description": "Días de vacaciones acumulados pendientes de disfrutar",
            },
            "dias_vacaciones_tomados": {
                "type": "decimal",
                "label": "Días de Vacaciones Tomados",
                "description": "Días de vacaciones ya disfrutados",
            },
            "dias_vacaciones_disponibles": {
                "type": "decimal",
                "label": "Días de Vacaciones Disponibles",
                "description": "Días de vacaciones disponibles para disfrutar",
            },
            "provision_vacaciones": {
                "type": "decimal",
                "label": "Provisión de Vacaciones",
                "description": "Monto provisionado para vacaciones",
            },
        },
    },
    "novedad": {
        "label": "Novedades del Período",
        "description": "Valores de novedades registradas para el empleado en el período actual",
        "fields": {
            # A. Compensación Base y Directa
            "horas_extra": {
                "type": "decimal",
                "label": "Horas Extraordinarias",
                "description": "Horas trabajadas más allá de la jornada estándar",
                "codigo_concepto": "OVERTIME",
                "tipo_valor": "horas",
                "gravable": True,
            },
            "horas_extra_dobles": {
                "type": "decimal",
                "label": "Horas Extra Dobles/Festivas",
                "description": "Horas extra en feriados, domingos o nocturnas",
                "codigo_concepto": "HORAS_EXTRA_DOBLES",
                "tipo_valor": "horas",
                "gravable": True,
            },
            "comisiones": {
                "type": "decimal",
                "label": "Comisiones",
                "description": "Porcentaje sobre ventas o negocios concretados",
                "codigo_concepto": "COMISION",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "bono_objetivos": {
                "type": "decimal",
                "label": "Bono por Objetivos",
                "description": "Pago variable por cumplimiento de metas específicas",
                "codigo_concepto": "BONO_OBJETIVOS",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "bono_anual": {
                "type": "decimal",
                "label": "Bono Anual/Trimestral",
                "description": "Compensación discrecional o por resultados generales",
                "codigo_concepto": "BONO_ANUAL",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "plus_peligrosidad": {
                "type": "decimal",
                "label": "Plus por Peligrosidad/Toxicidad",
                "description": "Adicional por trabajar en entornos de riesgo",
                "codigo_concepto": "PLUS_PELIGROSIDAD",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "plus_nocturno": {
                "type": "decimal",
                "label": "Plus por Trabajo Nocturno",
                "description": "Adicional por laborar en horarios nocturnos",
                "codigo_concepto": "PLUS_NOCTURNO",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "plus_antiguedad": {
                "type": "decimal",
                "label": "Plus por Antigüedad",
                "description": "Compensación por años de servicio",
                "codigo_concepto": "PLUS_ANTIGUEDAD",
                "tipo_valor": "monto",
                "gravable": True,
            },
            # B. Compensaciones en Especie y Beneficios
            "uso_vehiculo": {
                "type": "decimal",
                "label": "Uso de Vehículo de Empresa",
                "description": "Valor del beneficio de vehículo para uso personal",
                "codigo_concepto": "USO_VEHICULO",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "seguro_salud": {
                "type": "decimal",
                "label": "Seguro de Salud Privado",
                "description": "Cobertura médica pagada por la empresa",
                "codigo_concepto": "SEGURO_SALUD",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "aporte_pension": {
                "type": "decimal",
                "label": "Aporte a Pensión/Retiro",
                "description": "Aportaciones de la empresa a fondo de pensión",
                "codigo_concepto": "APORTE_PENSION",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "stock_options": {
                "type": "decimal",
                "label": "Opciones de Acciones",
                "description": "Valor de opciones de compra de acciones",
                "codigo_concepto": "STOCK_OPTIONS",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "subsidio_alimentacion": {
                "type": "decimal",
                "label": "Subsidio de Alimentación",
                "description": "Vales, tarjetas o servicio de comedor",
                "codigo_concepto": "SUBSIDIO_ALIMENTACION",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "subsidio_transporte": {
                "type": "decimal",
                "label": "Subsidio de Transporte",
                "description": "Compensación por gastos de desplazamiento",
                "codigo_concepto": "SUBSIDIO_TRANSPORTE",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "subsidio_guarderia": {
                "type": "decimal",
                "label": "Subsidio de Guardería",
                "description": "Ayuda para costes de cuidado infantil",
                "codigo_concepto": "SUBSIDIO_GUARDERIA",
                "tipo_valor": "monto",
                "gravable": False,
            },
            # C. Compensaciones por Tiempo y Bienestar
            "vacaciones_dias": {
                "type": "decimal",
                "label": "Días de Vacaciones",
                "description": "Días de vacaciones pagadas en el período",
                "codigo_concepto": "VACATION",
                "tipo_valor": "dias",
                "gravable": True,
            },
            "pago_festivos": {
                "type": "decimal",
                "label": "Pago por Días Festivos",
                "description": "Compensación por trabajar en días de asueto",
                "codigo_concepto": "PAGO_FESTIVOS",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "aguinaldo": {
                "type": "decimal",
                "label": "Aguinaldo/Gratificación Anual",
                "description": "Pago extra en época específica del año",
                "codigo_concepto": "THIRTEENTH_SALARY",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "participacion_utilidades": {
                "type": "decimal",
                "label": "Participación en Utilidades",
                "description": "Porcentaje de beneficios anuales de la empresa",
                "codigo_concepto": "UTILIDADES",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "permiso_pagado_dias": {
                "type": "decimal",
                "label": "Permisos Pagados (días)",
                "description": "Días de permiso pagado (enfermedad, maternidad, etc.)",
                "codigo_concepto": "PERMISO_PAGADO",
                "tipo_valor": "dias",
                "gravable": True,
            },
            "fondo_ahorro_empresa": {
                "type": "decimal",
                "label": "Aporte Empresa a Fondo de Ahorro",
                "description": "Aporte de la empresa al fondo de ahorro del empleado",
                "codigo_concepto": "FONDO_AHORRO_EMPRESA",
                "tipo_valor": "monto",
                "gravable": False,
            },
            # D. Reembolsos y Dietas
            "viaticos": {
                "type": "decimal",
                "label": "Viáticos",
                "description": "Gastos de alojamiento, comida y transporte en viajes",
                "codigo_concepto": "VIATICO",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "gastos_representacion": {
                "type": "decimal",
                "label": "Gastos de Representación",
                "description": "Costes de entretenimiento y relaciones con clientes",
                "codigo_concepto": "GASTOS_REPRESENTACION",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "reembolso_formacion": {
                "type": "decimal",
                "label": "Reembolso de Formación",
                "description": "Cursos, certificaciones, maestrías, etc.",
                "codigo_concepto": "REEMBOLSO_FORMACION",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "reembolso_medico": {
                "type": "decimal",
                "label": "Reembolso de Gastos Médicos",
                "description": "Tratamientos o medicamentos no cubiertos",
                "codigo_concepto": "REEMBOLSO_MEDICO",
                "tipo_valor": "monto",
                "gravable": False,
            },
            # E. Pagos por Eventos Específicos
            "indemnizacion_despido": {
                "type": "decimal",
                "label": "Indemnización por Despido",
                "description": "Pago por terminación de relación laboral",
                "codigo_concepto": "INDEMNIZACION",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "compensacion_reubicacion": {
                "type": "decimal",
                "label": "Compensación por Reubicación",
                "description": "Ayuda para mudanza o cambio de residencia",
                "codigo_concepto": "COMPENSACION_REUBICACION",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "premio_puntualidad": {
                "type": "decimal",
                "label": "Premio por Puntualidad/Asistencia",
                "description": "Premio por asistencia perfecta o puntualidad",
                "codigo_concepto": "PREMIO_PUNTUALIDAD",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "premio_innovacion": {
                "type": "decimal",
                "label": "Premio por Ideas/Innovación",
                "description": "Reconocimiento por ideas innovadoras",
                "codigo_concepto": "PREMIO_INNOVACION",
                "tipo_valor": "monto",
                "gravable": True,
            },
            "ayuda_fallecimiento": {
                "type": "decimal",
                "label": "Ayuda por Fallecimiento",
                "description": "Apoyo económico en situaciones de luto",
                "codigo_concepto": "AYUDA_FALLECIMIENTO",
                "tipo_valor": "monto",
                "gravable": False,
            },
            # Deducciones comunes
            "dias_ausencia": {
                "type": "decimal",
                "label": "Días de Ausencia",
                "description": "Días de ausencia no justificada a descontar",
                "codigo_concepto": "ABSENCE",
                "tipo_valor": "dias",
                "gravable": False,
            },
            "dias_incapacidad": {
                "type": "decimal",
                "label": "Días de Incapacidad",
                "description": "Días de incapacidad médica",
                "codigo_concepto": "DISABILITY",
                "tipo_valor": "dias",
                "gravable": False,
            },
            "adelanto_salario": {
                "type": "decimal",
                "label": "Adelanto de Salario",
                "description": "Monto de adelanto de salario a descontar",
                "codigo_concepto": "ADVANCE",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "prestamo_cuota": {
                "type": "decimal",
                "label": "Cuota de Préstamo",
                "description": "Cuota de préstamo a descontar",
                "codigo_concepto": "LOAN",
                "tipo_valor": "monto",
                "gravable": False,
            },
            "fondo_ahorro_empleado": {
                "type": "decimal",
                "label": "Aporte Empleado a Fondo de Ahorro",
                "description": "Aporte del empleado al fondo de ahorro",
                "codigo_concepto": "FONDO_AHORRO_EMPLEADO",
                "tipo_valor": "monto",
                "gravable": False,
            },
        },
    },
    "calculado": {
        "label": "Valores Calculados",
        "fields": {
            "salario_neto_inasistencia": {
                "type": "decimal",
                "label": "Salario Neto por Inasistencia",
                "description": "Salario del período después de descontar inasistencias marcadas",
            },
            "meses_restantes_fiscal": {
                "type": "integer",
                "label": "Meses Restantes en Período Fiscal",
                "description": "Meses que faltan para terminar el período fiscal",
            },
            "periodos_restantes_fiscal": {
                "type": "integer",
                "label": "Períodos Restantes",
                "description": "Períodos de pago restantes en el año fiscal",
            },
            "dias_trabajados_periodo": {
                "type": "integer",
                "label": "Días Trabajados en Período",
                "description": "Días efectivamente trabajados en el período actual",
            },
            "es_primer_periodo_sistema": {
                "type": "boolean",
                "label": "Es Primer Período del Sistema",
                "description": "Indica si es el primer período procesado por el sistema",
            },
            "salario_diario": {
                "type": "decimal",
                "label": "Salario Diario",
                "description": "Salario base dividido entre días del período",
            },
            "salario_hora": {
                "type": "decimal",
                "label": "Salario por Hora",
                "description": "Salario base dividido entre horas laborales del período",
            },
            "antiguedad_dias": {
                "type": "integer",
                "label": "Antigüedad (Días)",
                "description": "Días transcurridos desde la fecha de ingreso",
            },
            "antiguedad_meses": {
                "type": "integer",
                "label": "Antigüedad (Meses)",
                "description": "Meses completos desde la fecha de ingreso",
            },
            "antiguedad_anios": {
                "type": "integer",
                "label": "Antigüedad (Años)",
                "description": "Años completos desde la fecha de ingreso",
            },
            "edad_anios": {
                "type": "integer",
                "label": "Edad (Años)",
                "description": "Edad del empleado en años cumplidos",
            },
            "es_nuevo_ingreso": {
                "type": "boolean",
                "label": "Es Nuevo Ingreso",
                "description": "Indica si el empleado ingresó durante el período actual",
            },
            "dias_proporcional": {
                "type": "integer",
                "label": "Días para Cálculo Proporcional",
                "description": "Días a considerar para prorrateo de nuevo ingreso/baja",
            },
        },
    },
}
