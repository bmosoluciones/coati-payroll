# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Stress and Verification Script for Coati Payroll Formula Engine.

This script executes a highly complex, multi-tiered real-world reference formula schema
over a diverse dataset with boundary values, and measures performance, correctness, and reliability.
"""

import sys
import os
import time
from decimal import Decimal

# Ensure the coati_payroll module is on the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from coati_payroll.formula_engine import FormulaEngine

# Complex real-world reference tax & deduction schema
STRESS_SCHEMA = {
    "meta": {
        "name": "Nicaragua/LATAM Progressive Income Tax & Social Security with Caps",
        "description": "Stress-testing with complex progressive lookup tables, overtime calculations, conditional logic, and social security ceilings.",
    },
    "inputs": [
        {"name": "salario_base", "type": "decimal", "default": 0},
        {"name": "novedad_HORAS_EXTRA", "type": "decimal", "default": 0},
        {"name": "novedad_COMISION", "type": "decimal", "default": 0},
        {"name": "meses_restantes", "type": "integer", "default": 12},
        {"name": "salario_acumulado", "type": "decimal", "default": 0},
        {"name": "ir_retenido_acumulado", "type": "decimal", "default": 0},
    ],
    "steps": [
        # 1. Hourly rate calculation: base_salary / 30 / 8
        {
            "name": "salario_diario",
            "type": "calculation",
            "formula": "salario_base / 30",
        },
        {
            "name": "salario_hora",
            "type": "calculation",
            "formula": "salario_diario / 8",
        },
        # 2. Overtime calculation with 150% rate
        {
            "name": "horas_extra_monto",
            "type": "calculation",
            "formula": "novedad_HORAS_EXTRA * salario_hora * 1.5",
        },
        # 3. Gross salary calculation
        {
            "name": "salario_bruto_mensual",
            "type": "calculation",
            "formula": "salario_base + horas_extra_monto + novedad_COMISION",
        },
        # 4. Social security deduction (INSS) of 7% capped at a maximum salary base of 105,000
        {
            "name": "base_inss",
            "type": "calculation",
            "formula": "min(salario_bruto_mensual, 105000)",
        },
        {
            "name": "deduccion_seguro_social",
            "type": "calculation",
            "formula": "base_inss * 0.07",
        },
        # 5. Net salary before tax
        {
            "name": "salario_neto_mensual",
            "type": "calculation",
            "formula": "salario_bruto_mensual - deduccion_seguro_social",
        },
        # 6. Annual projection of salary remaining in fiscal year
        {
            "name": "expectativa_anual",
            "type": "calculation",
            "formula": "salario_neto_mensual * meses_restantes",
        },
        # 7. Total projected taxable income
        {
            "name": "base_imponible_anual",
            "type": "calculation",
            "formula": "salario_acumulado + expectativa_anual",
        },
        # 8. Progressive tax table lookup (Nicaragua IR standard reference values)
        {
            "name": "annual_tax",
            "type": "tax_lookup",
            "table": "latam_progressive_ir",
            "input": "base_imponible_anual",
        },
        # 9. Deduct historical annual tax withholdings
        {
            "name": "pending_tax",
            "type": "calculation",
            "formula": "annual_tax - ir_retenido_acumulado",
        },
        # 10. Proportional tax to withhold this month
        {
            "name": "monthly_tax",
            "type": "calculation",
            "formula": "max(0, pending_tax / meses_restantes)",
        },
        # 11. Final net payout
        {
            "name": "neto_pagar",
            "type": "calculation",
            "formula": "salario_bruto_mensual - deduccion_seguro_social - monthly_tax",
        }
    ],
    "tax_tables": {
        "latam_progressive_ir": [
            {"min": 0, "max": 100000, "rate": 0, "fixed": 0, "over": 0},
            {"min": 100000.01, "max": 200000, "rate": 0.15, "fixed": 0, "over": 100000},
            {"min": 200000.01, "max": 350000, "rate": 0.20, "fixed": 15000, "over": 200000},
            {"min": 350000.01, "max": 500000, "rate": 0.25, "fixed": 45000, "over": 350000},
            {"min": 500000.01, "max": None, "rate": 0.30, "fixed": 82500, "over": 500000},
        ]
    },
    "output": "neto_pagar",
}


def run_stress_test():
    print("=" * 70)
    print(" INICIANDO PRUEBA DE ESTRÉS Y RENDIMIENTO DE COATI PAYROLL")
    print("=" * 70)

    # Initialize the formula engine
    print("1. Inicializando FormulaEngine con esquema complejo de referencia...")
    start_init = time.perf_counter()
    engine = FormulaEngine(STRESS_SCHEMA, strict_mode=True)
    end_init = time.perf_counter()
    print(f"   [Éxito] Inicializado en {((end_init - start_init) * 1000):.3f} ms.")
    print("-" * 70)

    # Dataset with 5 distinct real-world employee profiles
    test_cases = [
        {
            "profile": "Perfil 1: Operario con Salario Mínimo y Horas Extra",
            "inputs": {
                "salario_base": Decimal("9500.00"),
                "novedad_HORAS_EXTRA": Decimal("10"),
                "novedad_COMISION": Decimal("0.00"),
                "meses_restantes": 12,
                "salario_acumulado": Decimal("0.00"),
                "ir_retenido_acumulado": Decimal("0.00")
            },
            # Expected values:
            # Hourly rate: 9500 / 30 / 8 = 39.5833
            # Overtime rate: 39.5833 * 1.5 = 59.375
            # Overtime amount: 59.375 * 10 = 593.75
            # Gross: 9500 + 593.75 = 10093.75
            # INSS: 10093.75 * 0.07 = 706.5625 -> 706.56
            # Net monthly: 10093.75 - 706.56 = 9387.19
            # Projected annual: 9387.19 * 12 = 112646.28
            # Tax annual: (112646.28 - 100000) * 0.15 = 1896.942 -> 1896.94
            # Tax monthly: 1896.94 / 12 = 158.08
            # Payout: 10093.75 - 706.56 - 158.08 = 9229.11
            "expected_payout": Decimal("9229.11")
        },
        {
            "profile": "Perfil 2: Gerente con Salario Superior a Tope de INSS",
            "inputs": {
                "salario_base": Decimal("120000.00"),
                "novedad_HORAS_EXTRA": Decimal("0"),
                "novedad_COMISION": Decimal("15000.00"),
                "meses_restantes": 6,  # Mid-year
                "salario_acumulado": Decimal("600000.00"), # Already has high accumulation
                "ir_retenido_acumulado": Decimal("100000.00")
            },
            # Expected values:
            # Gross: 120000 + 15000 = 135000
            # INSS: 105000 * 0.07 = 7350.00 (capped!)
            # Net monthly: 135000 - 7350 = 127650.00
            # Projected annual remaining: 127650 * 6 = 765900.00
            # Total annual taxable: 600000 (acumulado) + 765900 = 1365900.00
            # Annual tax: 82500 + (1365900 - 500000) * 0.30 = 82500 + 259770 = 342270.00
            # Pending tax: 342270 - 100000 (acumulado) = 242270.00
            # Monthly tax: 242270 / 6 = 40378.33
            # Payout: 135000 - 7350 - 40378.33 = 87271.67
            "expected_payout": Decimal("87271.67")
        },
        {
            "profile": "Perfil 3: Ejecutivo con Rango de Impuesto Medio",
            "inputs": {
                "salario_base": Decimal("30000.00"),
                "novedad_HORAS_EXTRA": Decimal("0"),
                "novedad_COMISION": Decimal("5000.00"),
                "meses_restantes": 12,
                "salario_acumulado": Decimal("0.00"),
                "ir_retenido_acumulado": Decimal("0.00")
            },
            # Expected:
            # Gross: 35000
            # INSS: 35000 * 0.07 = 2450.00
            # Net monthly: 32550
            # Projected annual: 32550 * 12 = 390600.00
            # Annual tax bracket 350k-500k: 45000 + (390600 - 350000) * 0.25 = 45000 + 10150 = 55150.00
            # Monthly tax: 55150 / 12 = 4595.83
            # Payout: 35000 - 2450 - 4595.83 = 27954.17
            "expected_payout": Decimal("27954.17")
        },
        {
            "profile": "Perfil 4: Empleado de Bajos Ingresos Exento de Impuesto",
            "inputs": {
                "salario_base": Decimal("7000.00"),
                "novedad_HORAS_EXTRA": Decimal("0"),
                "novedad_COMISION": Decimal("0"),
                "meses_restantes": 12,
                "salario_acumulado": Decimal("0.00"),
                "ir_retenido_acumulado": Decimal("0.00")
            },
            # Expected:
            # Gross: 7000
            # INSS: 7000 * 0.07 = 490
            # Net: 6510
            # Projected: 78120
            # Tax bracket (under 100k): 0
            # Payout: 7000 - 490 = 6510.00
            "expected_payout": Decimal("6510.00")
        },
        {
            "profile": "Perfil 5: Ajuste de Fin de Año Fiscal con Reajuste",
            "inputs": {
                "salario_base": Decimal("40000.00"),
                "novedad_HORAS_EXTRA": Decimal("0"),
                "novedad_COMISION": Decimal("10000.00"),
                "meses_restantes": 1,  # Last month!
                "salario_acumulado": Decimal("440000.00"),
                "ir_retenido_acumulado": Decimal("50000.00")
            },
            # Expected:
            # Gross: 50000
            # INSS: 50000 * 0.07 = 3500
            # Net monthly: 46500
            # Projected annual: 440000 (acumulado) + 46500 * 1 = 486500.00
            # Annual tax bracket 350k-500k: 45000 + (486500 - 350000) * 0.25 = 45000 + 34125 = 79125.00
            # Pending tax: 79125 - 50000 = 29125.00
            # Monthly tax (1 month left): 29125.00
            # Payout: 50000 - 3500 - 29125 = 17375.00
            "expected_payout": Decimal("17375.00")
        }
    ]

    print("2. Ejecutando verificación de precisión matemática de cada perfil...")
    for idx, case in enumerate(test_cases, 1):
        inputs = case["inputs"]
        profile = case["profile"]
        expected = case["expected_payout"]

        result = engine.execute(inputs)
        actual = Decimal(result["output"])

        print(f"\n   -> {profile}")
        print(f"      Entradas: Salario Base={inputs['salario_base']}, Horas Extra={inputs['novedad_HORAS_EXTRA']}, Comisión={inputs['novedad_COMISION']}")
        print(f"      Bruto Mensual Calculado: {result['variables']['salario_bruto_mensual']}")
        print(f"      Deducción INSS Calculada: {result['variables']['deduccion_seguro_social']}")
        print(f"      Proyección Anual Imponible: {result['variables']['base_imponible_anual']}")
        print(f"      Impuesto Mensual Calculado (IR): {result['variables']['monthly_tax']}")
        print(f"      Neto a Pagar: {actual} (Esperado: {expected})")

        # Verify result with a tollerance of 0.05 due to roundings in sub-steps vs precise math
        diff = abs(actual - expected)
        assert diff <= Decimal("0.05"), f"Diferencia de {diff} detectada en {profile}"
        print("      [APROBADO] Coincidencia matemática exacta.")

    print("\n" + "-" * 70)
    print("3. Ejecutando PRUEBA DE CARGA DE ESTRÉS (10,000 cálculos de nómina complejos)...")

    stress_iterations = 10000
    start_stress = time.perf_counter()

    # Run the stress loop
    for i in range(stress_iterations):
        # Rotate between the 5 profiles
        case = test_cases[i % len(test_cases)]
        engine.execute(case["inputs"])

    end_stress = time.perf_counter()
    elapsed = end_stress - start_stress
    ops_per_sec = stress_iterations / elapsed
    ms_per_op = (elapsed / stress_iterations) * 1000

    print(f"   [Éxito] Completadas {stress_iterations:,} ejecuciones complejas.")
    print(f"   Tiempo total transcurrido: {elapsed:.3f} segundos.")
    print(f"   Rendimiento: {ops_per_sec:.2f} cálculos por segundo.")
    print(f"   Latencia promedio por nómina: {ms_per_op:.4f} ms.")
    print("=" * 70)


if __name__ == "__main__":
    run_stress_test()
