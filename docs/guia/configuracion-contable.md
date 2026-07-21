# Configuración Contable para Nóminas

## Introducción

La generación correcta de comprobantes contables es una funcionalidad **CRÍTICA** del sistema de nómina. Un comprobante contable mal configurado puede resultar en:

- Registros contables desbalanceados (débitos ≠ créditos)
- Información contable incorrecta en los estados financieros
- Problemas en auditorías y declaraciones fiscales
- Incumplimiento de normativas contables

Este documento describe cómo configurar correctamente todos los componentes necesarios para generar comprobantes contables balanceados y precisos.

## Principio Fundamental: Balance Contable

**TODO comprobante contable DEBE estar balanceado:**

```
∑ Débitos = ∑ Créditos
Balance = 0.00
```

El sistema valida automáticamente este principio y generará advertencias si detecta configuraciones incompletas.

## Componentes de la Configuración Contable

### 1. Centro de Costos del Empleado

**REQUERIMIENTO**: Cada empleado DEBE tener definido su centro de costos.

#### ¿Por qué es importante?

El centro de costos permite:
- Distribución correcta de gastos por departamento/área
- Análisis de rentabilidad por centro de costos
- Trazabilidad de costos laborales

#### Configuración

Al crear o editar un empleado, complete el campo:

```
Centro de Costos: CC-VENTAS
```

**Ejemplo de valores comunes:**
- `CC-ADMIN`: Administración
- `CC-VENTAS`: Departamento de Ventas
- `CC-PROD`: Producción
- `CC-LOGIST`: Logística

#### Impacto en el Comprobante

Cada asiento contable incluirá el centro de costos del empleado:

```json
{
    "codigo_cuenta": "6101-001",
    "descripcion": "Gastos de Salario",
    "centro_costos": "CC-VENTAS",
    "debito": 15000.00,
    "credito": 0.00
}
```

### 2. Configuración Contable del Salario Base (Empresa/Planilla)

**REQUERIMIENTO**: El salario base DEBE tener configuradas cuentas de débito y crédito.

Desde la versión **1.7.4**, la fuente principal para salario base es la **Empresa** asociada a la planilla.

#### Orden de resolución (fuente de verdad)

1. **Empresa de la planilla** (prioridad alta)
2. **Planilla** (fallback para compatibilidad)

Esto permite estandarizar la contabilización del salario base cuando una empresa tiene múltiples planillas.

#### Campos Requeridos

1. **Cuenta Débito (Gasto) del Salario Base**
   - `código_cuenta_debe_salario`: Ej. `6101-001`
   - `descripcion_cuenta_debe_salario`: Ej. "Gastos de Salario Base"

2. **Cuenta Crédito (Pasivo) del Salario Base**
   - `codigo_cuenta_haber_salario`: Ej. `2101-001`
   - `descripcion_cuenta_haber_salario`: Ej. "Salarios por Pagar"

#### Lógica Contable del Salario Base

```
DÉBITO:  6101-001 - Gastos de Salario Base     $15,000.00
CRÉDITO: 2101-001 - Salarios por Pagar         $15,000.00
```

Esta configuración registra:
- El **gasto** laboral de la empresa (debe ir a cuentas 6xxx)
- El **pasivo** (obligación de pago) con el empleado (debe ir a cuentas 2xxx)

### 3. Matriz robusta de configuración contable para comprobante resumido

Para emitir un comprobante resumido sin advertencias, configure cuentas por tipo de movimiento así:

| Movimiento | ¿Dónde se define la cuenta? | Campos clave |
|-----------|------------------------------|--------------|
| **Salario básico** | **Empresa** (primario) / Planilla (fallback) | `codigo_cuenta_debe_salario`, `codigo_cuenta_haber_salario` |
| **Percepciones** | En cada percepción contabilizable | `codigo_cuenta_debe`, `codigo_cuenta_haber` |
| **Deducciones** | En cada deducción contabilizable | `codigo_cuenta_debe`, `codigo_cuenta_haber` |
| **Prestaciones** | En cada prestación contabilizable | `codigo_cuenta_debe`, `codigo_cuenta_haber` |
| **Devengo de vacaciones pagadas** | En la política de vacaciones (`VacationPolicy`) | `cuenta_debito_vacaciones_pagadas`, `cuenta_credito_vacaciones_pagadas` |

!!! info "Devengo de vacaciones"
    El devengo/consumo de vacaciones pagadas no se toma de percepción/deducción/prestación, sino de la **política de vacaciones** asociada por alcance (planilla/empresa/global) y se contabiliza como líneas de `vacation_liability`.

### 4. Configuración Contable de Percepciones

**REQUERIMIENTO**: Cada percepción que debe contabilizarse DEBE tener sus cuentas configuradas.

#### Campos de Configuración

Para cada percepción (bonos, comisiones, horas extras, etc.):

1. **Contabilizable**: Marcar como `SÍ` si debe aparecer en el comprobante
2. **Cuenta Débito**: Cuenta de gasto (ej. `6102-001` para Bonos)
3. **Descripción Débito**: Descripción del gasto
4. **Cuenta Crédito**: Cuenta de pasivo (ej. `2101-001` para Salarios por Pagar)
5. **Descripción Crédito**: Descripción del pasivo

#### Ejemplo: Configuración de Bono

```
Código: BONO-DESEMPEÑO
Nombre: Bono por Desempeño
Contabilizable: SÍ
Cuenta Débito: 6102-001 (Gastos de Bonos)
Cuenta Crédito: 2101-001 (Salarios por Pagar)
```

#### Lógica Contable

```
DÉBITO:  6102-001 - Gastos de Bonos            $2,000.00
CRÉDITO: 2101-001 - Salarios por Pagar         $2,000.00
```

### 5. Configuración Contable de Deducciones

**REQUERIMIENTO**: Cada deducción contabilizable DEBE tener configuradas sus cuentas.

#### Campos de Configuración

Para cada deducción (INSS, IR, préstamos, etc.):

1. **Contabilizable**: Marcar como `SÍ`
2. **Cuenta Débito**: Cuenta de pasivo donde se registra lo retenido (ej. `2102-001` para INSS por Pagar)
3. **Descripción Débito**: Descripción
4. **Cuenta Crédito**: Cuenta de salarios por pagar (ej. `2101-001`)
5. **Descripción Crédito**: Descripción

#### Ejemplo: INSS Laboral

```
Código: INSS-LABORAL
Nombre: INSS Laboral (6.25%)
Contabilizable: SÍ
Cuenta Débito: 2102-001 (INSS por Pagar)
Cuenta Crédito: 2101-001 (Salarios por Pagar)
```

#### Lógica Contable

```
DÉBITO:  2102-001 - INSS por Pagar             $1,062.50
CRÉDITO: 2101-001 - Salarios por Pagar         $1,062.50
```

**Nota**: La deducción REDUCE el salario por pagar al empleado, por eso se debita la cuenta de salarios por pagar y se acredita una cuenta de pasivo con el instituto (INSS).

### 6. Configuración Contable de Prestaciones

**REQUERIMIENTO**: Cada prestación patronal contabilizable DEBE tener configuradas sus cuentas.

#### Campos de Configuración

Para cada prestación (INSS patronal, INATEC, aguinaldo, etc.):

1. **Contabilizable**: Marcar como `SÍ`
2. **Cuenta Débito**: Cuenta de gasto patronal (ej. `6103-001` para INSS Patronal)
3. **Descripción Débito**: Descripción del gasto
4. **Cuenta Crédito**: Cuenta de pasivo patronal (ej. `2102-002` para INSS Patronal por Pagar)
5. **Descripción Crédito**: Descripción del pasivo

#### Ejemplo: INSS Patronal

```
Código: INSS-PATRONAL
Nombre: INSS Patronal (19%)
Contabilizable: SÍ
Cuenta Débito: 6103-001 (Gastos de INSS Patronal)
Cuenta Crédito: 2102-002 (INSS Patronal por Pagar)
```

#### Lógica Contable

```
DÉBITO:  6103-001 - Gastos de INSS Patronal    $3,230.00
CRÉDITO: 2102-002 - INSS Patronal por Pagar    $3,230.00
```

**Nota**: Las prestaciones son costos del empleador que NO afectan el salario neto del empleado.

## Ejemplo Completo de Comprobante Balanceado

### Configuración del Escenario

**Empleado:**
- Salario base: $15,000.00
- Centro de costos: CC-VENTAS

**Percepciones:**
- Bono por desempeño: $2,000.00

**Deducciones:**
- INSS Laboral (6.25% del bruto): $1,062.50

**Prestaciones:**
- INSS Patronal (19% del bruto): $3,230.00

### Cálculo de Nómina

```
Salario Base:       $15,000.00
+ Bono:              $2,000.00
= Salario Bruto:    $17,000.00

- INSS Laboral:      $1,062.50
= Salario Neto:     $15,937.50

Prestaciones (INSS Patronal): $3,230.00
```

### Comprobante Contable Generado

| Cuenta | Descripción | Centro Costos | Débito | Crédito |
|--------|-------------|---------------|--------|---------|
| 6101-001 | Gastos de Salario Base | CC-VENTAS | $15,000.00 | |
| 2101-001 | Salarios por Pagar | CC-VENTAS | | $15,000.00 |
| 6102-001 | Gastos de Bonos | CC-VENTAS | $2,000.00 | |
| 2101-001 | Salarios por Pagar | CC-VENTAS | | $2,000.00 |
| 2102-001 | INSS por Pagar | CC-VENTAS | $1,062.50 | |
| 2101-001 | Salarios por Pagar | CC-VENTAS | | $1,062.50 |
| 6103-001 | Gastos INSS Patronal | CC-VENTAS | $3,230.00 | |
| 2102-002 | INSS Patronal por Pagar | CC-VENTAS | | $3,230.00 |
| **TOTALES** | | | **$21,292.50** | **$21,292.50** |

**Balance: $0.00 ✓**

### Agrupación por Cuenta

El sistema agrupa los asientos por (código_cuenta, centro_costos):

| Cuenta | Centro Costos | Débito | Crédito |
|--------|---------------|--------|---------|
| 2101-001 | CC-VENTAS | | $15,937.50 |
| 2102-001 | CC-VENTAS | $1,062.50 | |
| 2102-002 | CC-VENTAS | | $3,230.00 |
| 6101-001 | CC-VENTAS | $15,000.00 | |
| 6102-001 | CC-VENTAS | $2,000.00 | |
| 6103-001 | CC-VENTAS | $3,230.00 | |

## Validación del Comprobante

### Verificación en la Base de Datos

El sistema almacena cada comprobante en la tabla `comprobante_contable`:

```sql
SELECT 
    c.id,
    c.nomina_id,
    c.total_debitos,
    c.total_creditos,
    c.balance,
    c.advertencias
FROM comprobante_contable c
WHERE c.nomina_id = 'NOMINA_ID';
```

**Verificación Crítica:**
- `total_debitos` = `total_creditos`
- `balance` = 0.00
- `advertencias` = [] (lista vacía)

### Exportación a Excel

El comprobante se puede exportar a Excel para revisión y análisis:

1. Navegar a la nómina generada
2. Hacer clic en **"Exportar Comprobante Contable a Excel"**
3. El archivo descargado incluirá:
   - Información de la planilla y período
   - Identificadores de trazabilidad de la ejecución (`ID planilla` y `estado de nómina`)
   - Detalle de todos los asientos contables
   - Totales de débitos y créditos
   - Indicador visual de balance

Además, al pie del archivo se incluye una sección de **Trazabilidad de Usuario** con:

- `Creado por`
- `Aprobado por`
- `Aplicado por`

Esta sección facilita conciliación operativa y auditorías internas cuando un mismo comprobante atraviesa varias etapas del flujo de nómina.

## Guía de Depuración

### Problema: "Comprobante Desbalanceado"

**Síntoma**: Los débitos no igualan los créditos.

**Causas Comunes:**

1. **Configuración Incompleta de Cuentas**
   - **Solución**: Verificar que TODOS los conceptos contabilizables tengan configuradas AMBAS cuentas (débito Y crédito)
   
2. **Centro de Costos No Definido**
   - **Solución**: Asignar centro de costos a todos los empleados
   
3. **Concepto Marcado como Contabilizable sin Cuentas**
   - **Solución**: Configurar las cuentas o desmarcar "Contabilizable"

### Problema: "Advertencias en el Comprobante"

**Síntoma**: El campo `advertencias` contiene mensajes.

**Ejemplos de Advertencias:**

```
"Planilla: Falta configurar cuenta débito para salario base"
"Percepción 'BONO-001': Falta configurar cuenta crédito"
"Deducción 'INSS': Falta configurar cuenta débito"
```

**Solución**: Revisar cada advertencia y completar la configuración faltante.

### Problema: "Comprobante No Se Genera"

**Causas Posibles:**

1. **Planilla sin Configuración Contable**
   - Verificar que la planilla tenga configuradas las cuentas de salario base
   
2. **Ningún Concepto Contabilizable**
   - Verificar que al menos algún concepto esté marcado como "Contabilizable"
   
3. **Error en Ejecución de Nómina**
   - Revisar los logs de la nómina para identificar errores previos

### Herramientas de Depuración

#### 1. Revisión de Logs

Los logs del sistema registran:
- Advertencias de configuración contable
- Errores en cálculos
- Información de balances

```python
# Verificar logs de una nómina
nomina = db.session.get(Nomina, nomina_id)
print(nomina.log_procesamiento)
```

#### 2. Consulta SQL de Verificación

```sql
-- Verificar configuración de planilla
SELECT 
    p.nombre,
    p.codigo_cuenta_debe_salario,
    p.codigo_cuenta_haber_salario
FROM planilla p
WHERE p.id = 'PLANILLA_ID';

-- Verificar configuración de percepciones
SELECT 
    pe.codigo,
    pe.nombre,
    pe.contabilizable,
    pe.codigo_cuenta_debe,
    pe.codigo_cuenta_haber
FROM percepcion pe
WHERE pe.activo = true;

-- Verificar empleados sin centro de costos
SELECT 
    e.codigo_empleado,
    e.primer_nombre,
    e.primer_apellido,
    e.centro_costos
FROM empleado e
WHERE e.activo = true 
  AND (e.centro_costos IS NULL OR e.centro_costos = '');
```

#### 3. Test de Validación

El sistema incluye tests automatizados que validan:
- Balance de débitos y créditos
- Presencia de centro de costos
- Configuración completa de cuentas

```bash
pytest tests/test_accounting_voucher_e2e.py -v
```

## Lista de Verificación Pre-Ejecución

Antes de ejecutar una nómina, verificar:

- [ ] Todos los empleados tienen centro de costos definido
- [ ] La **empresa de la planilla** tiene configuradas las cuentas de salario base (débito y crédito)
- [ ] (Compatibilidad) Si no se usa empresa, la planilla tiene cuentas de salario base como fallback
- [ ] Todas las percepciones contabilizables tienen ambas cuentas configuradas
- [ ] Todas las deducciones contabilizables tienen ambas cuentas configuradas
- [ ] Todas las prestaciones contabilizables tienen ambas cuentas configuradas
- [ ] Si usa vacaciones pagadas, la política de vacaciones tiene cuentas de débito y crédito configuradas
- [ ] Las cuentas de gasto usan el rango correcto (6xxx)
- [ ] Las cuentas de pasivo usan el rango correcto (2xxx)
- [ ] Se ha probado con una nómina de prueba pequeña primero

## Plan de Cuentas Recomendado

### Cuentas de Gasto (6xxx)

| Cuenta | Descripción |
|--------|-------------|
| 6101-001 | Gastos de Salario Base |
| 6102-001 | Gastos de Bonos |
| 6102-002 | Gastos de Horas Extras |
| 6102-003 | Gastos de Comisiones |
| 6103-001 | Gastos de INSS Patronal |
| 6103-002 | Gastos de INATEC |
| 6104-001 | Provisión para Aguinaldo |
| 6104-002 | Provisión para Vacaciones |

### Cuentas de Pasivo (2xxx)

| Cuenta | Descripción |
|--------|-------------|
| 2101-001 | Salarios por Pagar |
| 2102-001 | INSS Laboral por Pagar |
| 2102-002 | INSS Patronal por Pagar |
| 2102-003 | INATEC por Pagar |
| 2103-001 | Impuesto sobre la Renta por Pagar |
| 2104-001 | Préstamos a Empleados (por descontar) |
| 2105-001 | Aguinaldo por Pagar |
| 2105-002 | Vacaciones por Pagar |

## Mejores Prácticas

1. **Realizar Pruebas Primero**: Siempre ejecutar una nómina de prueba con 1-2 empleados antes de procesar la nómina completa.

2. **Revisar el Balance**: Después de generar cada nómina, verificar que el balance sea exactamente 0.00.

3. **Documentar el Plan de Cuentas**: Mantener documentado el plan de cuentas específico de la empresa.

4. **Capacitar al Personal**: Asegurar que el personal encargado entienda los principios contables básicos.

5. **Auditorías Regulares**: Realizar auditorías periódicas de los comprobantes generados.

6. **Backup de Configuración**: Documentar toda la configuración contable para referencia futura.

7. **Coordinación con Contabilidad**: Trabajar estrechamente con el departamento de contabilidad para definir las cuentas correctas.

## Soporte y Ayuda

Si después de seguir esta guía aún tiene problemas:

1. Revise los tests automatizados en `tests/test_accounting_voucher_e2e.py`
2. Consulte los logs del sistema
3. Verifique que está usando la última versión del software
4. Contacte al soporte técnico con:
   - ID de la nómina problemática
   - Captura del comprobante generado
   - Lista de advertencias recibidas
   - Configuración de cuentas utilizada

## Referencias

- Documentación de Planillas: `docs/guia/planillas.md`
- Documentación de Percepciones: `docs/guia/percepciones.md`
- Documentación de Deducciones: `docs/guia/deducciones.md`
- Documentación de Prestaciones: `docs/guia/prestaciones.md`
- Documentación de Nóminas: `docs/guia/nomina.md`
