# Configuración de Cálculos

Esta sección documenta las opciones de configuración global que afectan los cálculos de nómina y liquidaciones.

## Acceder al Módulo

1. Navegue a **Configuración > Cálculos**

## Liquidaciones: Modo de Días

El campo **Modo de Días (Liquidación)** define el factor base usado para prorratear el salario en liquidaciones.

| Opción | Efecto en el cálculo |
|--------|----------------------|
| **Calendario** | Calcula la tasa diaria como `salario_mensual / factor_calendario` (por defecto 30). |
| **Laboral** | Calcula la tasa diaria como `salario_mensual / factor_laboral` (por defecto 28). |

### Factores disponibles

| Campo | Descripción | Valor típico |
|-------|-------------|--------------|
| **Factor Días Calendario** | Días base cuando el modo es Calendario | 30 |
| **Factor Días Laborales** | Días base cuando el modo es Laboral | 28 |

### Ejemplo práctico

Si el salario mensual es C$ 30,000:

- **Calendario (30)** → Tasa diaria = 30,000 / 30 = C$ 1,000.
- **Laboral (28)** → Tasa diaria = 30,000 / 28 = C$ 1,071.43.

El monto por días pendientes en la liquidación se calcula multiplicando la tasa diaria por los días por pagar.

## Casos límite

- Si el **modo** no coincide con un valor válido, el sistema usa **Calendario** como valor por defecto.
- Un factor de días inválido (0 o negativo) evita el cálculo de la liquidación y genera error.

## Nota sobre Implementacion Inicial de Nomina

Desde la version 1.7.3, el periodo inicial de implementacion no se configura en **Configuracion > Calculos**.

Ahora se define por empresa en **Empresas** mediante:

- `primer_mes_nomina`
- `primer_anio_nomina`
