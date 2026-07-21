# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Settings page to consolidate administrative options."""

from __future__ import annotations

from flask import Blueprint, render_template

from coati_payroll.rbac import require_write_access

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET"])
@require_write_access()
def index():
    """Display settings page with links to all configuration options."""
    return render_template("modules/settings/index.html")
