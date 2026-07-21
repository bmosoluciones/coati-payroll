from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for

from coati_payroll.i18n import _
from coati_payroll.model import PluginRegistry, db
from coati_payroll.rbac import require_write_access

plugins_bp = Blueprint("plugins", __name__, url_prefix="/plugins")

# Constants
ROUTE_PLUGINS_INDEX = "plugins.index"


@plugins_bp.route("/", methods=["GET"])
@require_write_access()
def index():
    plugins = db.session.execute(db.select(PluginRegistry).order_by(PluginRegistry.distribution_name)).scalars().all()
    return render_template("modules/plugins/index.html", plugins=plugins)


@plugins_bp.route("/toggle/<string:plugin_id>", methods=["POST"])
@require_write_access()
def toggle(plugin_id: str):
    plugin = db.session.get(PluginRegistry, plugin_id)
    if not plugin:
        flash(_("Plugin no encontrado."), "error")
        return redirect(url_for(ROUTE_PLUGINS_INDEX))

    if not plugin.installed and plugin.active:
        plugin.active = False
        db.session.commit()
        flash(_("Plugin marcado como inactivo."), "success")
        return redirect(url_for(ROUTE_PLUGINS_INDEX))

    plugin.active = not plugin.active
    db.session.commit()

    if plugin.active:
        flash(_("Plugin activado. Reinicie la aplicación para cargar sus blueprints."), "success")
    else:
        flash(_("Plugin desactivado."), "success")

    return redirect(url_for(ROUTE_PLUGINS_INDEX))
