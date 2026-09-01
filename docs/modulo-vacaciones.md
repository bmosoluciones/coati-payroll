# Módulo de Vacaciones - Documentación Técnica

## Descripción General

El **Módulo de Vacaciones** de Coati Payroll es un subsistema robusto, auditable y agnóstico al país, diseñado para gestionar el control completo de vacaciones de empleados. Este módulo está basado en principios de sistemas enterprise HRIS/Payroll y puede adaptarse a las regulaciones de cualquier país de América (LATAM, USA y Canadá).

## Principios de Diseño

El módulo se basa en los siguientes principios fundamentales:

1. **Vacaciones no son días, son un balance**: Las vacaciones se gestionan como un balance contable que aumenta (acumulación) y disminuye (uso).

2. **El balance se modifica solo por eventos**: Todas las modificaciones al balance se realizan mediante eventos registrados en el libro mayor (ledger).

3. **Las reglas no viven en código, viven en configuración**: Las políticas de vacaciones son configurables y no requieren cambios en el código para adaptarse a diferentes legislaciones.

4. **El sistema no decide legalidad, solo ejecuta políticas**: El sistema ejecuta políticas configuradas; la interpretación legal es responsabilidad del usuario.

5. **El motor debe ser determinista y reproducible**: Dado el mismo conjunto de eventos, el sistema siempre produce el mismo balance.

6. **Toda mutación debe dejar trazabilidad**: Cada cambio en el balance deja un registro inmutable en el ledger.

## Arquitectura del Sistema

```
Employee
  └── VacationAccount (per policy)
         ├── current_balance
         ├── policy_id
         └── VacationLedger[] (immutable audit trail)
                ├── ACCRUAL (earned)
                ├── USAGE (taken)
                ├── ADJUSTMENT (manual)
                ├── EXPIRATION (expired)
                └── PAYOUT (paid out)
```

## Entidades del Modelo

### 1. VacationPolicy (Política de Vacaciones)

Define cómo se acumulan, usan y vencen las vacaciones. Es completamente configurable por planilla (nómina) o empresa.

**IMPORTANTE**: Las políticas se asocian principalmente a **Planillas (nóminas)**, no solo a empresas. Esto permite que una instalación tenga múltiples planillas con distintas reglas de vacaciones, incluso para distintos países en consolidados de empresas.

**Campos Principales:**

#### Identificación
- `codigo`: Código único de la política
- `nombre`: Nombre descriptivo
- `descripcion`: Descripción detallada
- `planilla_id`: Planilla asociada (recomendado, permite políticas específicas por nómina/país)
- `empresa_id`: Empresa asociada (opcional, para políticas globales que aplican a toda la empresa)

#### Configuración de Acumulación
- `accrual_method`: Método de acumulación
  - `periodic`: Cantidad fija por período
  - `proportional`: Basado en días/horas trabajadas
  - `seniority`: Escalonado por antigüedad
- `accrual_rate`: Tasa de acumulación (cantidad por período)
- `accrual_frequency`: Frecuencia de acumulación
  - `monthly`: Mensual
  - `biweekly`: Quincenal
  - `annual`: Anual
- `prorate_by_period_days`: Prorratear por días reales del período
  - `true`: prorratea la tasa cuando el período tiene menos días (ej: febrero)
  - `false`: aplica la tasa completa del ciclo aunque el período tenga menos días
- `accrual_basis`: Base para cálculo proporcional
  - `days_worked`: Días trabajados
  - `hours_worked`: Horas trabajadas
- `min_service_days`: Días mínimos de servicio antes de acumular
- `seniority_tiers`: Niveles por antigüedad (JSON)

#### Límites de Balance
- `max_balance`: Balance máximo permitido
- `allow_negative`: Permitir balance negativo (vacaciones adelantadas)

> El traspaso y vencimiento automáticos aún no están disponibles. Sus
> columnas se conservan para compatibilidad de datos, pero no se exponen en
> la configuración ni se aplican durante la acumulación.

#### Configuración de Uso
- `unit_type`: Tipo de unidad
  - `days`: Días
  - `hours`: Horas
- `count_weekends`: Incluir fines de semana en el cálculo
- `count_holidays`: Incluir feriados en el cálculo
- `partial_units_allowed`: Permitir fracciones de días/horas
- `rounding_rule`: Regla de redondeo (`nearest`, `up`, `down`)
- `accrue_during_leave`: Continuar acumulando durante vacaciones
- `payout_on_termination`: Pagar vacaciones al terminar relación laboral

#### Configuración Contable (Vacaciones Pagadas)
- `son_vacaciones_pagadas`: Indica si las vacaciones generan contabilización de pasivo laboral
  - `True`: Se generan asientos contables por acumulación y consumo de vacaciones
  - `False` (default): No se genera contabilización automática
- `porcentaje_pago_vacaciones`: Porcentaje del salario diario a pagar por día de vacaciones (default: 100.00)
  - `100.00`: 1 día de vacaciones = 100% del salario diario (caso estándar)
  - `50.00`: 1 día de vacaciones = 50% del salario diario
  - `120.00`: 1 día de vacaciones = 120% del salario diario (incluye bonificación)
- `cuenta_debito_vacaciones_pagadas`: Cuenta contable de gasto (débito) para vacaciones pagadas
- `descripcion_cuenta_debito_vacaciones_pagadas`: Descripción de la cuenta de débito
- `cuenta_credito_vacaciones_pagadas`: Cuenta contable de pasivo (crédito) para vacaciones pagadas
- `descripcion_cuenta_credito_vacaciones_pagadas`: Descripción de la cuenta de crédito

**Nota sobre Contabilización:**
Cuando `son_vacaciones_pagadas=True`, el sistema genera automáticamente asientos contables durante la ejecución de nómina:
- **Acumulación**: Débito a gasto, Crédito a pasivo laboral (por vacaciones ganadas)
- **Consumo**: Débito a pasivo laboral, Crédito a gasto (reverso al tomar vacaciones)

El monto se calcula como: `(salario_base / dias_base) * unidades * (porcentaje_pago_vacaciones / 100)`

**Ejemplo de Configuración - Nicaragua:**
```python
policy_nicaragua = VacationPolicy(
    codigo="NIC-STANDARD",
    nombre="Política Nicaragua Estándar",
    accrual_method="periodic",
    accrual_rate=1.25,  # 15 días al año / 12 meses
    accrual_frequency="monthly",
    unit_type="days",
    count_weekends=True,
    count_holidays=True,
    payout_on_termination=True
)
```

**Ejemplo de Configuración - USA:**
```python
policy_usa = VacationPolicy(
    codigo="USA-HOURLY",
    nombre="USA Hourly Accrual",
    accrual_method="proportional",
    accrual_basis="hours_worked",
    accrual_rate=0.025,  # 1 hora por cada 40 horas trabajadas
    accrual_frequency="monthly",
    unit_type="hours",
    count_weekends=False,
    count_holidays=False,
    partial_units_allowed=True,
    allow_negative=False,
    payout_on_termination=True
)
```

**Ejemplo de Configuración - Antigüedad:**
```python
policy_seniority = VacationPolicy(
    codigo="LAT-SENIORITY",
    nombre="Política por Antigüedad LATAM",
    accrual_method="seniority",
    accrual_frequency="annual",
    unit_type="days",
    seniority_tiers=[
        {"years": 0, "rate": 10},   # 0-1 años: 10 días
        {"years": 2, "rate": 15},   # 2-5 años: 15 días
        {"years": 6, "rate": 20}    # 6+ años: 20 días
    ],
    payout_on_termination=True
)
```

**Ejemplo de Configuración - Vacaciones Pagadas con Contabilización:**
```python
policy_paid_vacation = VacationPolicy(
    codigo="NIC-PAID-VAC",
    nombre="Vacaciones Pagadas Nicaragua",
    accrual_method="periodic",
    accrual_rate=1.25,  # 15 días al año / 12 meses
    accrual_frequency="monthly",
    unit_type="days",
    # Configuración contable
    son_vacaciones_pagadas=True,
    porcentaje_pago_vacaciones=Decimal("100.00"),  # 100% del salario diario
    cuenta_debito_vacaciones_pagadas="5201",
    descripcion_cuenta_debito_vacaciones_pagadas="Gasto por Vacaciones Pagadas",
    cuenta_credito_vacaciones_pagadas="2205",
    descripcion_cuenta_credito_vacaciones_pagadas="Pasivo Laboral - Vacaciones",
    payout_on_termination=True
)
```

### 2. VacationAccount (Cuenta de Vacaciones)

Representa el balance de vacaciones de un empleado bajo una política específica.

**Campos Principales:**
- `empleado_id`: ID del empleado
- `policy_id`: ID de la política aplicable
- `current_balance`: Balance actual (calculado desde el ledger)
- `last_accrual_date`: Fecha de la última acumulación
- `activo`: Estado de la cuenta

**Regla de Oro:** Nunca actualizar `current_balance` directamente sin registrar una entrada en `VacationLedger`.

### 3. VacationLedger (Libro Mayor de Vacaciones)

Registro inmutable de todos los movimientos de vacaciones. Es la fuente de verdad del sistema.

**Campos Principales:**
- `account_id`: ID de la cuenta
- `empleado_id`: ID del empleado (para consultas rápidas)
- `fecha`: Fecha del movimiento
- `entry_type`: Tipo de entrada
  - `accrual`: Vacaciones ganadas
  - `usage`: Vacaciones tomadas
  - `adjustment`: Ajuste manual
  - `expiration`: Vacaciones vencidas
  - `payout`: Vacaciones pagadas (al terminar)
- `quantity`: Cantidad (positiva para adiciones, negativa para deducciones)
- `source`: Origen del movimiento (`system`, `novelty`, `termination`, `manual`)
- `reference_id`: ID de referencia (ej: ID de novedad)
- `reference_type`: Tipo de referencia
- `observaciones`: Notas adicionales
- `balance_after`: Balance después de este movimiento

**Características:**
- **Inmutable**: Una vez creado, nunca se modifica o elimina
- **Auditable**: Rastrea quién, cuándo y por qué se modificó el balance
- **Determinista**: `balance = SUM(ledger.quantity)`

### 4. VacationNovelty (Novedad/Solicitud de Vacaciones)

Representa una solicitud de vacaciones que afecta el balance cuando es aprobada.

**Campos Principales:**
- `empleado_id`: ID del empleado
- `account_id`: ID de la cuenta de vacaciones
- `start_date`: Fecha de inicio
- `end_date`: Fecha de fin
- `units`: Unidades solicitadas (días/horas)
- `estado`: Estado de la solicitud
  - `pendiente`: Pendiente de aprobación
  - `aprobado`: Aprobada
  - `rechazado`: Rechazada
  - `disfrutado`: Disfrutada/completada
- `fecha_aprobacion`: Fecha de aprobación
- `aprobado_por`: Usuario que aprobó
- `ledger_entry_id`: ID de la entrada en el ledger (cuando es aprobada)
- `observaciones`: Notas
- `motivo_rechazo`: Motivo del rechazo (si aplica)

## Flujos de Trabajo

### Flujo 1: Acumulación de Vacaciones

```
1. Job programado ejecuta motor de acumulación
2. Motor evalúa política de cada cuenta activa
3. Calcula cantidad a acumular según método
4. Genera entrada en VacationLedger (type=ACCRUAL)
5. Actualiza current_balance en VacationAccount
6. Actualiza last_accrual_date
```

### Flujo 2: Solicitud y Aprobación de Vacaciones

```
1. Usuario crea VacationNovelty (estado=pendiente)
2. Sistema valida:
   - Empleado tiene cuenta activa
   - Balance suficiente (o policy.allow_negative=true)
3. Administrador revisa solicitud
4. Si aprueba:
   a. Cambia estado a 'aprobado'
   b. Registra fecha_aprobacion y aprobado_por
   c. **NOTA**: El descuento del balance se difiere a la ejecución de nómina
   d. Durante la ejecución de nómina:
      - Se convierte a NominaNovedad
      - Se genera VacationLedger (type=USAGE, quantity=-N)
      - Se actualiza current_balance
      - Se genera contabilización si son_vacaciones_pagadas=True
5. Si rechaza:
   a. Cambia estado a 'rechazado'
   b. Registra motivo_rechazo
```

**Separación de Concerns:**
- **Aprobación**: Solo valida y cambia estado (no modifica balance)
- **Ejecución de Nómina**: Descuenta balance vía VacationLedger y genera contabilidad
- **Beneficio**: Trazabilidad completa y reproducibilidad en cálculos de nómina

### Flujo 3: Ajuste Manual

```
1. Administrador crea ajuste manual
2. Sistema genera VacationLedger (type=ADJUSTMENT)
3. Actualiza current_balance
4. Registra observaciones y usuario
```

### Flujo 4: Pago al Terminar Relación Laboral

```
1. Empleado es dado de baja
2. Si policy.payout_on_termination=true:
   a. Genera VacationLedger (type=PAYOUT, quantity=-balance)
   b. Balance queda en 0
   c. Se integra con nómina para pago
```

### Consideraciones de recálculo y aplicación

Para mantener consistencia contable y evitar dobles acumulaciones, el sistema opera así:

- La **acumulación de vacaciones** se calcula durante la generación/revisión de nómina, pero el movimiento definitivo en `VacationLedger` se materializa al **aplicar/pagar** la nómina.
- Al recalcular una nómina no aplicada, se limpian referencias heredadas del recálculo previo para impedir duplicados en el ledger.
- Los montos de acumulación se redondean a **2 decimales** para mantener balances estables entre recálculos y exportaciones.
- En políticas periódicas, `prorate_by_period_days` permite elegir entre:
  - aplicar la tasa completa mensual (valor recomendado por defecto en configuración estándar Nicaragua), o
  - prorratear por días reales del período (útil para periodos parciales).

Este diseño permite recalcular borradores sin contaminar saldos históricos y dejar la mutación contable para el cierre operativo de la nómina.

## Casos de Uso Cubiertos

### ✅ LATAM (Ejemplo: Nicaragua)
- Acumulación: 15 días calendario al año
- Frecuencia: Mensual (1.25 días/mes)
- Unidad: Días calendario
- Vencimiento: 12 meses después del aniversario
- Pago al terminar: Sí

### ✅ USA
- Acumulación: Por horas trabajadas
- Frecuencia: Mensual (basado en horas del mes)
- Unidad: Horas
- Vencimiento: Fin de año fiscal
- Fracciones: Permitidas

### ✅ Canadá
- Acumulación: Porcentaje del salario
- Frecuencia: Quincenal o mensual
- Unidad: Días u horas
- Pago al terminar: Sí

### ✅ Part-Time / Empleados por Horas
- Acumulación proporcional basada en horas trabajadas
- Configuración específica por tipo de empleado

### ✅ Vacaciones Adelantadas
- Configurar `allow_negative=true` en la política
- El balance puede ser negativo
- Se descuenta en futuras acumulaciones

### ✅ Ajustes Manuales Auditables
- Todos los ajustes quedan registrados en el ledger
- Se registra usuario, fecha y motivo

## Integración con Nómina

El módulo de vacaciones **NO calcula dinero**, solo gestiona **unidades** (días/horas).

La integración con nómina se realiza mediante:

1. **Vacaciones Tomadas**: Se registran como novedades que pueden afectar el cálculo de la nómina
2. **Pago de Vacaciones al Terminar**: El evento `PAYOUT` genera una novedad que se procesa en la nómina final
3. **Provisión de Vacaciones**: Se puede configurar como prestación patronal basada en el balance acumulado

### Puente Vacaciones-Nómina (Vacation-to-Payroll Bridge)

**Funcionalidad introducida en v1.1.0**

El sistema incluye un puente automatizado que permite aplicar vacaciones aprobadas directamente a las nóminas en curso. Este mecanismo conecta el módulo de vacaciones con el cálculo de nómina de manera transparente y auditable.

#### ¿Cómo Funciona?

Cuando se aprueba una solicitud de vacaciones (`LeaveRequest`):

1. **Validación de Balance**: El sistema verifica que el empleado tenga balance suficiente en su `VacationAccount`

2. **Deducción Automática**: Se deduce el balance inmediatamente de la cuenta de vacaciones

3. **Registro en Ledger**: Se crea un registro `VacationLedger` con:
   - `entry_type = "USAGE"`
   - `quantity = cantidad negativa` (días/horas tomadas)
   - `reference_type = "LeaveRequest"`
   - `reference_id = ID de la solicitud`
   - `source = "leave_request_approval"`

4. **Creación de Novedad para Nómina**: Se genera automáticamente un `VacationNovelty` que:
   - Vincula la solicitud aprobada con la nómina correspondiente
   - Contiene información sobre el período de ausencia
   - Marca la ausencia como pagada (configuración predeterminada)

5. **Aplicación a Nómina**: Cuando se ejecuta la nómina, el sistema:
   - Detecta las novedades de vacaciones (`VacationNovelty`)
   - Las convierte en `NominaNovedad` con los flags apropiados
   - Aplica las reglas configuradas (descuento o no descuento según tipo)

#### Flujo Completo con Ejemplo

```python
# 1. Empleado solicita vacaciones
leave_request = LeaveRequest(
    empleado_id=empleado.id,
    account_id=vacation_account.id,
    start_date=date(2025, 2, 10),
    end_date=date(2025, 2, 14),
    days_requested=Decimal("5.00"),
    status="PENDING"
)
db.session.add(leave_request)

# 2. Supervisor aprueba la solicitud (vía UI o API)
# El sistema automáticamente:
# a) Valida balance suficiente
if vacation_account.current_balance < leave_request.days_requested:
    raise ValueError("Balance insuficiente")

# b) Deduce del balance
ledger_entry = VacationLedger(
    account_id=vacation_account.id,
    empleado_id=empleado.id,
    entry_type="USAGE",
    reference_type="LeaveRequest",
    reference_id=leave_request.id,
    quantity=-leave_request.days_requested,  # Negativo para deducción
    balance_after=vacation_account.current_balance - leave_request.days_requested,
    source="leave_request_approval"
)
vacation_account.current_balance -= leave_request.days_requested
leave_request.status = "APPROVED"

# c) Crea VacationNovelty para la nómina
vacation_novelty = VacationNovelty(
    leave_request_id=leave_request.id,
    empleado_id=empleado.id,
    start_date=leave_request.start_date,
    end_date=leave_request.end_date,
    days_count=leave_request.days_requested,
    applied_to_payroll=False  # Pendiente de aplicar a nómina
)

# 3. Al ejecutar la nómina, se convierte en NominaNovedad
nomina_novedad = NominaNovedad(
    nomina_id=nomina.id,
    empleado_id=empleado.id,
    codigo_concepto="VACACIONES",  # Concepto configurado para vacaciones
    valor_cantidad=vacation_novelty.days_count,
    tipo_valor="dias",
    fecha_novedad=vacation_novelty.start_date,
    es_inasistencia=True,           # Es una ausencia
    descontar_pago_inasistencia=False,  # NO se descuenta (vacaciones pagadas)
)
vacation_novelty.applied_to_payroll = True
```

#### Configuración del Concepto de Vacaciones

Para que el puente funcione correctamente, debe configurarse un concepto de percepción o deducción con código `VACACIONES` (o el que use su organización):

**Opción 1: Como Percepción (Vacaciones que se pagan adicionalmente)**
```yaml
Código: VACACIONES
Nombre: Vacaciones Pagadas
Tipo: Percepción
Es Inasistencia: Sí
Descontar Pago por Inasistencia: No  # Vacaciones son pagadas
```

**Opción 2: Como Deducción (Vacaciones que no se descuentan)**
```yaml
Código: VACACIONES
Nombre: Ausencia por Vacaciones
Tipo: Deducción
Es Inasistencia: Sí
Descontar Pago por Inasistencia: No  # NO se descuenta porque son pagadas
```

#### Flujo en la Interfaz de Usuario

1. **Empleado/HR crea solicitud de vacaciones** → `LeaveRequest` en estado `PENDING`

2. **Supervisor aprueba en el módulo de vacaciones** → Automáticamente:
   - Balance se deduce
   - Ledger se actualiza
   - VacationNovelty se crea

3. **Al generar nómina para el período** → Sistema:
   - Detecta VacationNovelty pendientes de aplicar
   - Convierte a NominaNovedad con concepto `VACACIONES`
   - Marca `applied_to_payroll = True`

4. **Cálculo de nómina procesa la novedad** → Según configuración:
   - Si `descontar_pago_inasistencia = False`: Empleado recibe salario completo
   - Registro queda en la nómina para auditoría

#### Ventajas del Puente Automatizado

✅ **Trazabilidad completa**: Conexión clara entre solicitud → aprobación → deducción de balance → novedad → nómina
✅ **Prevención de errores**: No es necesario crear novedades manualmente
✅ **Auditoría robusta**: Cada paso queda registrado con timestamp y usuario
✅ **Sincronización**: Balance de vacaciones y nómina siempre están alineados
✅ **Reversibilidad**: Si se revierte la aprobación, se puede ajustar el balance y eliminar la novedad

#### Consultas Útiles

**Ver vacaciones aplicadas a nómina:**
```sql
SELECT
    n.numero_nomina,
    e.codigo_empleado,
    lr.start_date,
    lr.end_date,
    vn.days_count,
    vn.applied_to_payroll
FROM vacation_novelty vn
JOIN leave_request lr ON vn.leave_request_id = lr.id
JOIN empleado e ON vn.empleado_id = e.id
JOIN nomina_novedad nn ON nn.empleado_id = e.id AND nn.codigo_concepto = 'VACACIONES'
JOIN nomina n ON nn.nomina_id = n.id
WHERE vn.applied_to_payroll = TRUE
ORDER BY n.numero_nomina, e.codigo_empleado;
```

**Ver vacaciones aprobadas pendientes de aplicar:**
```sql
SELECT
    e.codigo_empleado,
    lr.start_date,
    lr.end_date,
    vn.days_count
FROM vacation_novelty vn
JOIN leave_request lr ON vn.leave_request_id = lr.id
JOIN empleado e ON vn.empleado_id = e.id
WHERE vn.applied_to_payroll = FALSE
  AND lr.status = 'APPROVED'
ORDER BY lr.start_date;
```

## Reportes y Consultas

### Balance por Empleado
```sql
SELECT current_balance FROM vacation_account WHERE empleado_id = ?
```

### Historial Completo
```sql
SELECT * FROM vacation_ledger
WHERE empleado_id = ?
ORDER BY fecha DESC
```

### Cálculo Verificable del Balance
```sql
SELECT SUM(quantity) FROM vacation_ledger WHERE account_id = ?
-- Debe ser igual a vacation_account.current_balance
```

## Seguridad y Permisos

- **Crear/Editar Políticas**: Solo administradores
- **Ver Cuentas**: Usuarios con permisos de lectura
- **Aprobar Solicitudes**: Administradores y RRHH
- **Crear Solicitudes**: Usuarios con permisos de escritura
- **Ajustes Manuales**: Solo administradores

## Ventajas del Diseño

✅ **100% agnóstico al país**: Se adapta a cualquier legislación mediante configuración
✅ **Auditable**: Cada cambio queda registrado
✅ **Reversible**: Ajustes se registran, no se borran
✅ **Extensible**: Nuevas reglas se agregan sin cambiar código
✅ **Compatible con plugins**: Sistema de eventos permite extensiones
✅ **No rompe nómina**: Integración limpia con el módulo de nómina

## Riesgos Evitados

❌ Hardcodear días legales
❌ Mezclar vacaciones con nómina
❌ Actualizar balances directamente
❌ No tener ledger (libro mayor)
❌ No modelar eventos

## Próximas Mejoras

- Motor de acumulación automático (scheduled job)
- Notificaciones de vacaciones por vencer
- Integración con calendario empresarial
- Reportes avanzados y dashboards
- API REST para integraciones externas
- Importación masiva de balances iniciales

## Conclusión

El Módulo de Vacaciones de Coati Payroll implementa un sistema robusto basado en **políticas + eventos + ledger + motor de reglas**, apto para cumplir con legislaciones de cualquier país de América sin necesidad de reescribir código.
