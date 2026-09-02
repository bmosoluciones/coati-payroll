# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for absence default utilities."""

from types import SimpleNamespace

from coati_payroll.absence_defaults import (
    resolve_absence_flags,
    resolve_absence_flags_from_concept,
    resolve_explicit_flag_from_form,
)


def _field(value):
    return SimpleNamespace(data=value)


def test_resolve_explicit_flag_returns_none_when_field_is_missing():
    """If form has no field, no explicit override should be detected."""
    form = SimpleNamespace()
    result = resolve_explicit_flag_from_form(
        form,
        "es_inasistencia",
        has_request_context=False,
        request_form=None,
    )
    assert result is None


def test_resolve_explicit_flag_returns_none_when_payload_omits_field():
    """With request context, omitted payload field must map to None."""
    form = SimpleNamespace(es_inasistencia=_field(True))
    result = resolve_explicit_flag_from_form(
        form,
        "es_inasistencia",
        has_request_context=True,
        request_form={"codigo_concepto": "TEST"},
    )
    assert result is None


def test_resolve_explicit_flag_reads_bool_when_payload_includes_field():
    """With request context, included field must be treated as explicit value."""
    form = SimpleNamespace(es_inasistencia=_field(False))
    result = resolve_explicit_flag_from_form(
        form,
        "es_inasistencia",
        has_request_context=True,
        request_form={"es_inasistencia": ""},
    )
    assert result is False


def test_resolve_absence_flags_from_concept_uses_defaults():
    """Defaults should come from concept when no explicit values are provided."""
    concept = SimpleNamespace(es_inasistencia=True, descontar_pago_inasistencia=False)
    es_inasistencia, descontar_pago = resolve_absence_flags_from_concept(concept)
    assert es_inasistencia is True
    assert descontar_pago is False


def test_resolve_absence_flags_from_concept_explicit_overrides_defaults():
    """Explicit values should override concept defaults."""
    concept = SimpleNamespace(es_inasistencia=True, descontar_pago_inasistencia=True)
    es_inasistencia, descontar_pago = resolve_absence_flags_from_concept(
        concept,
        explicit_es_inasistencia=False,
        explicit_descontar_pago_inasistencia=False,
    )
    assert es_inasistencia is False
    assert descontar_pago is False


def test_resolve_absence_flags_looks_up_percepcion():
    """Percepcion lookup should be used when percepcion_id is provided."""
    concept = SimpleNamespace(es_inasistencia=True, descontar_pago_inasistencia=True)
    es_inasistencia, descontar_pago = resolve_absence_flags(
        percepcion_id="percepcion-id",
        deduccion_id=None,
        get_percepcion=lambda _concept_id: concept,
        get_deduccion=lambda _concept_id: None,
    )
    assert es_inasistencia is True
    assert descontar_pago is True


def test_resolve_absence_flags_looks_up_deduccion():
    """Deduccion lookup should be used when deduccion_id is provided."""
    concept = SimpleNamespace(es_inasistencia=False, descontar_pago_inasistencia=True)
    es_inasistencia, descontar_pago = resolve_absence_flags(
        percepcion_id=None,
        deduccion_id="deduccion-id",
        get_percepcion=lambda _concept_id: None,
        get_deduccion=lambda _concept_id: concept,
    )
    assert es_inasistencia is False
    assert descontar_pago is True
