# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for loan interest calculation functionality."""

from datetime import date
from decimal import Decimal

from coati_payroll.enums import MetodoAmortizacion, TipoInteres
from coati_payroll.interes_engine import (
    calcular_cuota_frances,
    calcular_interes_compuesto,
    calcular_interes_periodo,
    calcular_interes_simple,
    generar_tabla_amortizacion,
)


class TestInteresSimple:
    """Tests for simple interest calculations."""

    def test_calcular_interes_simple_basico(self):
        """Test basic simple interest calculation."""
        # 1000 at 12% annual for 30 days
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        dias = 30

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        # Expected: 1000 * 0.12 * (30/365) = 9.86
        assert interes == Decimal("9.86")

    def test_calcular_interes_simple_un_anio(self):
        """Test simple interest for one full year."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("10.0")
        dias = 365

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        # Expected: 1000 * 0.10 * 1 = 100
        assert interes == Decimal("100.00")

    def test_calcular_interes_simple_tasa_cero(self):
        """Test simple interest with zero rate."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("0.0")
        dias = 30

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")

    def test_calcular_interes_simple_sin_dias(self):
        """Test simple interest with zero days."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        dias = 0

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")

    def test_calcular_interes_simple_principal_negativo(self):
        """Test simple interest with negative principal."""
        principal = Decimal("-1000.00")
        tasa_anual = Decimal("12.0")
        dias = 30

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")

    def test_calcular_interes_simple_tasa_negativa(self):
        """Test simple interest with negative rate."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("-12.0")
        dias = 30

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")

    def test_calcular_interes_simple_dias_negativos(self):
        """Test simple interest with negative days."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        dias = -30

        interes = calcular_interes_simple(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")


class TestInteresCompuesto:
    """Tests for compound interest calculations."""

    def test_calcular_interes_compuesto_basico(self):
        """Test basic compound interest calculation."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        dias = 30

        interes = calcular_interes_compuesto(principal, tasa_anual, dias)

        # Compound interest should be slightly higher than simple
        interes_simple = calcular_interes_simple(principal, tasa_anual, dias)
        assert interes > interes_simple

    def test_calcular_interes_compuesto_tasa_cero(self):
        """Test compound interest with zero rate."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("0.0")
        dias = 30

        interes = calcular_interes_compuesto(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")

    def test_calcular_interes_compuesto_principal_negativo(self):
        """Test compound interest with negative principal."""
        principal = Decimal("-1000.00")
        tasa_anual = Decimal("12.0")
        dias = 30

        interes = calcular_interes_compuesto(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")

    def test_calcular_interes_compuesto_sin_dias(self):
        """Test compound interest with zero days."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        dias = 0

        interes = calcular_interes_compuesto(principal, tasa_anual, dias)

        assert interes == Decimal("0.00")


class TestCuotaFrances:
    """Tests for French method (constant payment) calculations."""

    def test_calcular_cuota_frances_sin_interes(self):
        """Test French method with no interest."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("0.0")
        num_cuotas = 12

        cuota = calcular_cuota_frances(principal, tasa_anual, num_cuotas)

        # Should be simple division: 12000 / 12 = 1000
        assert cuota == Decimal("1000.00")

    def test_calcular_cuota_frances_con_interes(self):
        """Test French method with interest."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("12.0")  # 12% annual = 1% monthly
        num_cuotas = 12

        cuota = calcular_cuota_frances(principal, tasa_anual, num_cuotas)

        # With 1% monthly rate, payment should be higher than 1000
        assert cuota > Decimal("1000.00")
        # But not too much higher (should be around 1066)
        assert cuota < Decimal("1100.00")

    def test_calcular_cuota_frances_una_cuota(self):
        """Test French method with single installment."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 1

        cuota = calcular_cuota_frances(principal, tasa_anual, num_cuotas)

        # Single payment should be principal plus one period of interest using
        # the same day-accurate basis as the accrual (dias_mes_nomina=30,
        # dias_anio_financiero=365): 1000 * (1 + 0.12 * 30/365) = 1009.86
        assert cuota == Decimal("1009.86")

    def test_calcular_cuota_frances_cubre_interes_devengado(self):
        """French payment must cover the exact-days interest accrued in a period.

        A nominal monthly rate (tasa/12) is smaller than the day-accurate
        interest (31/365 > 1/12), which would leave a residual balance that
        never amortizes. The constant payment must be at least the interest
        accrued on the opening balance for a 31-day month.
        """
        principal = Decimal("12000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 12

        cuota = calcular_cuota_frances(principal, tasa_anual, num_cuotas)
        interes_31_dias = calcular_interes_simple(principal, tasa_anual, 31)

        assert cuota > interes_31_dias

    def test_calcular_cuota_frances_principal_cero(self):
        """Test French method with zero principal."""
        principal = Decimal("0.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 12

        cuota = calcular_cuota_frances(principal, tasa_anual, num_cuotas)

        assert cuota == Decimal("0.00")

    def test_calcular_cuota_frances_cuotas_cero(self):
        """Test French method with zero installments."""
        principal = Decimal("1000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 0

        cuota = calcular_cuota_frances(principal, tasa_anual, num_cuotas)

        assert cuota == Decimal("0.00")


class TestIntersPeriodo:
    """Tests for interest calculation over a period."""

    def test_calcular_interes_periodo_30_dias(self):
        """Test interest calculation for 30-day period."""
        saldo = Decimal("10000.00")
        tasa_anual = Decimal("12.0")
        fecha_desde = date(2024, 1, 1)
        fecha_hasta = date(2024, 1, 31)

        interes, dias = calcular_interes_periodo(saldo, tasa_anual, fecha_desde, fecha_hasta, TipoInteres.SIMPLE)

        assert dias == 30
        # Should match simple interest calculation
        assert interes == calcular_interes_simple(saldo, tasa_anual, dias)

    def test_calcular_interes_periodo_compuesto(self):
        """Test compound interest for a period."""
        saldo = Decimal("10000.00")
        tasa_anual = Decimal("12.0")
        fecha_desde = date(2024, 1, 1)
        fecha_hasta = date(2024, 1, 31)

        interes, dias = calcular_interes_periodo(saldo, tasa_anual, fecha_desde, fecha_hasta, TipoInteres.COMPUESTO)

        assert dias == 30
        # Should match compound interest calculation
        assert interes == calcular_interes_compuesto(saldo, tasa_anual, dias)

    def test_calcular_interes_periodo_fechas_iguales(self):
        """Test interest calculation with same start and end date."""
        saldo = Decimal("10000.00")
        tasa_anual = Decimal("12.0")
        fecha_desde = date(2024, 1, 1)
        fecha_hasta = date(2024, 1, 1)

        interes, dias = calcular_interes_periodo(saldo, tasa_anual, fecha_desde, fecha_hasta)

        assert dias == 0
        assert interes == Decimal("0.00")

    def test_calcular_interes_periodo_saldo_cero(self):
        """Test interest calculation with zero balance."""
        saldo = Decimal("0.00")
        tasa_anual = Decimal("12.0")
        fecha_desde = date(2024, 1, 1)
        fecha_hasta = date(2024, 1, 31)

        interes, dias = calcular_interes_periodo(saldo, tasa_anual, fecha_desde, fecha_hasta)

        assert interes == Decimal("0.00")

    def test_calcular_interes_periodo_tasa_cero(self):
        """Test interest calculation with zero rate."""
        saldo = Decimal("10000.00")
        tasa_anual = Decimal("0.0")
        fecha_desde = date(2024, 1, 1)
        fecha_hasta = date(2024, 1, 31)

        interes, dias = calcular_interes_periodo(saldo, tasa_anual, fecha_desde, fecha_hasta)

        assert interes == Decimal("0.00")


class TestTablaAmortizacion:
    """Tests for amortization schedule generation."""

    def test_generar_tabla_frances_sin_interes(self):
        """Test French method amortization without interest."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("0.0")
        num_cuotas = 12
        fecha_inicio = date(2024, 1, 1)

        tabla = generar_tabla_amortizacion(
            principal, tasa_anual, num_cuotas, fecha_inicio, metodo=MetodoAmortizacion.FRANCES
        )

        assert len(tabla) == 12
        # All payments should be equal (1000 each)
        for cuota in tabla[:-1]:  # Except last one which may have rounding
            assert abs(cuota.cuota_total - Decimal("1000.00")) < Decimal("1.00")
            assert cuota.interes == Decimal("0.00")

        # Final balance should be zero
        assert tabla[-1].saldo == Decimal("0.00")

    def test_generar_tabla_frances_con_interes(self):
        """Test French method amortization with interest."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 12
        fecha_inicio = date(2024, 1, 1)

        tabla = generar_tabla_amortizacion(
            principal, tasa_anual, num_cuotas, fecha_inicio, metodo=MetodoAmortizacion.FRANCES
        )

        assert len(tabla) == 12

        # All payments should be roughly equal (French method)
        cuotas = [c.cuota_total for c in tabla[:-1]]
        avg_cuota = sum(cuotas) / len(cuotas)
        for cuota in cuotas:
            # Allow 5% variance
            assert abs(cuota - avg_cuota) < avg_cuota * Decimal("0.05")

        # Interest should decrease over time
        intereses = [c.interes for c in tabla]
        assert intereses[0] > intereses[-2]  # First > second to last

        # Final balance should be zero
        assert tabla[-1].saldo == Decimal("0.00")

    def test_generar_tabla_aleman_con_interes(self):
        """Test German method amortization with interest."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 12
        fecha_inicio = date(2024, 1, 1)

        tabla = generar_tabla_amortizacion(
            principal, tasa_anual, num_cuotas, fecha_inicio, metodo=MetodoAmortizacion.ALEMAN
        )

        assert len(tabla) == 12

        # Principal payments should be roughly equal (German method)
        capitales = [c.capital for c in tabla[:-1]]
        avg_capital = sum(capitales) / len(capitales)
        for capital in capitales:
            # Allow small variance due to rounding
            assert abs(capital - avg_capital) < Decimal("1.00")

        # Total payment should decrease over time (constant principal, decreasing interest)
        assert tabla[0].cuota_total > tabla[-2].cuota_total

        # Interest should decrease over time
        intereses = [c.interes for c in tabla]
        assert intereses[0] > intereses[-2]

        # Final balance should be zero
        assert tabla[-1].saldo == Decimal("0.00")

    def test_generar_tabla_fechas_consecutivas(self):
        """Test that payment dates are consecutive months."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 3
        fecha_inicio = date(2024, 1, 15)

        tabla = generar_tabla_amortizacion(principal, tasa_anual, num_cuotas, fecha_inicio)

        # Check dates are monthly intervals
        assert tabla[0].fecha_estimada == date(2024, 1, 15)
        assert tabla[1].fecha_estimada == date(2024, 2, 15)
        assert tabla[2].fecha_estimada == date(2024, 3, 15)

    def test_generar_tabla_principal_cero(self):
        """Test amortization table with zero principal."""
        principal = Decimal("0.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 12
        fecha_inicio = date(2024, 1, 1)

        tabla = generar_tabla_amortizacion(principal, tasa_anual, num_cuotas, fecha_inicio)

        assert len(tabla) == 0

    def test_generar_tabla_cuotas_cero(self):
        """Test amortization table with zero installments."""
        principal = Decimal("12000.00")
        tasa_anual = Decimal("12.0")
        num_cuotas = 0
        fecha_inicio = date(2024, 1, 1)

        tabla = generar_tabla_amortizacion(principal, tasa_anual, num_cuotas, fecha_inicio)

        assert len(tabla) == 0
