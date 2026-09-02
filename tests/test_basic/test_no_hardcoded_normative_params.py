# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression guard: avoid hardcoded normative parameters outside config files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PARAM_PATTERNS = {
    "dias_mes_nomina": re.compile(r"\bdias_mes_nomina\s*=\s*\d+"),
    "dias_anio_nomina": re.compile(r"\bdias_anio_nomina\s*=\s*\d+"),
    "horas_jornada_diaria": re.compile(r"\bhoras_jornada_diaria\s*=\s*Decimal\([\"']\d+(?:\.\d+)?[\"']\)"),
    "dias_mes_vacaciones": re.compile(r"\bdias_mes_vacaciones\s*=\s*\d+"),
    "dias_anio_vacaciones": re.compile(r"\bdias_anio_vacaciones\s*=\s*\d+"),
    "dias_anio_financiero": re.compile(r"\bdias_anio_financiero\s*=\s*\d+"),
    "meses_anio_financiero": re.compile(r"\bmeses_anio_financiero\s*=\s*\d+"),
    "dias_quincena": re.compile(r"\bdias_quincena\s*=\s*\d+"),
    "dias_mes_antiguedad": re.compile(r"\bdias_mes_antiguedad\s*=\s*\d+"),
    "dias_anio_antiguedad": re.compile(r"\bdias_anio_antiguedad\s*=\s*\d+"),
}

ALLOWED_FILES = {
    "coati_payroll/model.py",
    "coati_payroll/nomina_engine/repositories/config_repository.py",
    "coati_payroll/interes_engine.py",
    "coati_payroll/vacation_service.py",
}


@dataclass
class Violation:
    file: str
    line: int
    parameter: str
    code: str


def _scan_for_hardcoded_normative_params(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for file_path in root.rglob("*.py"):
        rel = file_path.as_posix()

        if rel.startswith("tests/") or rel.startswith("dev/"):
            continue
        if rel in ALLOWED_FILES:
            continue

        for line_no, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
            for parameter, pattern in PARAM_PATTERNS.items():
                if pattern.search(line):
                    violations.append(
                        Violation(
                            file=rel,
                            line=line_no,
                            parameter=parameter,
                            code=line.strip(),
                        )
                    )

    return violations


def test_no_hardcoded_normative_params_outside_configuration() -> None:
    violations = _scan_for_hardcoded_normative_params(Path("coati_payroll"))
    assert not violations, (
        "Found hardcoded normative payroll parameters outside allowed configuration files. "
        f"Violations: {violations}"
    )
