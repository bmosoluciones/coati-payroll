# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Internationalization module."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from typing import Any

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from flask_babel import format_currency, format_date, format_decimal, gettext, lazy_gettext, ngettext

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #


# ---------------------------------------------------------------------------------------
# Translation functions
# ---------------------------------------------------------------------------------------
def _(text: str, **kwargs) -> str:
    """Mark text for translation.

    Supports keyword arguments for string formatting.
    Example: _("Hello %(name)s", name="World")
    """
    translated = gettext(text)
    if kwargs:
        return translated % kwargs
    return translated


def _n(singular: str, plural: str, n: int) -> str:
    """Mark text for plural translation."""
    return ngettext(singular, plural, n)


def _l(text: str) -> str | Any:
    """Mark text for lazy translation (useful in forms)."""
    return lazy_gettext(text)


def money(value: Any, currency: str = "USD") -> str:
    """Format a monetary value using the active user's regional locale."""
    return format_currency(value or 0, currency)


def local_date(value: Any, format: str = "medium") -> str:
    """Format a date according to the active locale."""
    return format_date(value, format=format)


def number(value: Any) -> str:
    """Format a number with locale-specific decimal and grouping marks."""
    return format_decimal(value or 0)
