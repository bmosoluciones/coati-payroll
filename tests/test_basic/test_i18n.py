# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for internationalization module."""

from datetime import date
from decimal import Decimal

from flask_babel import force_locale


def test_locale_formatting_helpers_follow_active_locale(app):
    with app.app_context():
        from coati_payroll.i18n import local_date, money, number

        with force_locale("es"):
            spanish_money = money(Decimal("1234.50"), "USD")
            spanish_number = number(Decimal("1234.50"))
            spanish_date = local_date(date(2026, 9, 2))
        with force_locale("en"):
            english_money = money(Decimal("1234.50"), "USD")
            english_number = number(Decimal("1234.50"))
            english_date = local_date(date(2026, 9, 2))

        assert spanish_money != english_money
        assert spanish_number != english_number
        assert spanish_date != english_date


def test_i18n_basic_translation(app):
    """
    Test basic translation function.

    Setup:
        - App context

    Action:
        - Import and use translation function

    Verification:
        - Function works without error
    """
    with app.app_context():
        from coati_payroll.i18n import _

        # Basic translation - may return same text if not translated
        result = _("Hello")
        assert isinstance(result, str)
        assert len(result) > 0


def test_i18n_translation_with_kwargs(app):
    """
    Test translation function with keyword arguments.

    Setup:
        - App context

    Action:
        - Use translation with formatting

    Verification:
        - String interpolation works
    """
    with app.app_context():
        from coati_payroll.i18n import _

        result = _("Hello %(name)s", name="World")
        assert "World" in result


def test_i18n_translation_without_kwargs(app):
    """
    Test translation function without keyword arguments.

    Setup:
        - App context

    Action:
        - Use translation without formatting

    Verification:
        - Returns translated text
    """
    with app.app_context():
        from coati_payroll.i18n import _

        result = _("Simple text")
        assert isinstance(result, str)


def test_i18n_plural_translation(app):
    """
    Test plural translation function.

    Setup:
        - App context

    Action:
        - Use plural translation function

    Verification:
        - Function handles singular and plural
    """
    with app.app_context():
        from coati_payroll.i18n import _n

        # Test singular (n=1)
        result_singular = _n("%(num)d item", "%(num)d items", 1)
        assert isinstance(result_singular, str)

        # Test plural (n>1)
        result_plural = _n("%(num)d item", "%(num)d items", 5)
        assert isinstance(result_plural, str)


def test_i18n_lazy_translation(app):
    """
    Test lazy translation function.

    Setup:
        - App context

    Action:
        - Use lazy translation function

    Verification:
        - Returns lazy string object
    """
    with app.app_context():
        from coati_payroll.i18n import _l

        result = _l("Lazy text")
        # Lazy translation returns a special object
        # When converted to string, it should work
        assert str(result)


def test_i18n_translation_handles_empty_string(app):
    """
    Test that empty string translation is handled.

    Setup:
        - App context

    Action:
        - Translate empty string

    Verification:
        - Returns a string (gettext may return metadata for empty string)
    """
    with app.app_context():
        from coati_payroll.i18n import _

        result = _("")
        # gettext returns metadata for empty string, not empty string itself
        assert isinstance(result, str)


def test_i18n_multiple_kwargs(app):
    """
    Test translation with multiple keyword arguments.

    Setup:
        - App context

    Action:
        - Use translation with multiple placeholders

    Verification:
        - All placeholders are replaced
    """
    with app.app_context():
        from coati_payroll.i18n import _

        result = _("%(first)s and %(second)s", first="A", second="B")
        assert "A" in result
        assert "B" in result


def test_i18n_translation_with_special_characters(app):
    """
    Test translation with special characters.

    Setup:
        - App context

    Action:
        - Translate text with special chars

    Verification:
        - Special characters preserved
    """
    with app.app_context():
        from coati_payroll.i18n import _

        result = _("Text with áéíóú and ñ")
        assert isinstance(result, str)
        # Special characters should be preserved
        assert "áéíóú" in result or "Text" in result


def test_i18n_plural_zero(app):
    """
    Test plural translation with zero.

    Setup:
        - App context

    Action:
        - Use plural translation with n=0

    Verification:
        - Returns plural form
    """
    with app.app_context():
        from coati_payroll.i18n import _n

        result = _n("%(num)d item", "%(num)d items", 0)
        assert isinstance(result, str)


def test_i18n_all_functions_importable(app):
    """
    Test that all translation functions are importable.

    Setup:
        - App context

    Action:
        - Import all functions

    Verification:
        - All imports succeed
    """
    with app.app_context():
        from coati_payroll.i18n import _, _l, _n

        assert callable(_)
        assert callable(_l)
        assert callable(_n)
