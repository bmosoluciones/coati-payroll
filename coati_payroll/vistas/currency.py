# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Currency CRUD routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import false, true

from coati_payroll.forms import CurrencyForm
from coati_payroll.i18n import _
from coati_payroll.rbac import require_read_access, require_write_access
from coati_payroll.model import Moneda, db
from coati_payroll.vistas.constants import PER_PAGE

currency_bp = Blueprint("currency", __name__, url_prefix="/currency")


@currency_bp.route("/", methods=["GET"])
@require_read_access()
def index():
    """List all currencies with pagination and filters."""
    page = request.args.get("page", 1, type=int)

    # Get filter parameters
    buscar = request.args.get("buscar", type=str)
    estado = request.args.get("estado", type=str)

    # Build query with filters
    query = db.select(Moneda)

    if buscar:
        search_term = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Moneda.codigo.ilike(search_term),
                Moneda.nombre.ilike(search_term),
            )
        )

    if estado == "activo":
        query = query.filter(Moneda.activo.is_(true()))
    elif estado == "inactivo":
        query = query.filter(Moneda.activo.is_(false()))

    query = query.order_by(Moneda.codigo)

    pagination = db.paginate(
        query,
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )

    return render_template(
        "modules/currency/index.html",
        currencies=pagination.items,
        pagination=pagination,
        buscar=buscar,
        estado=estado,
    )


@currency_bp.route("/new", methods=["GET", "POST"])
@require_write_access()
def new():
    """Create a new currency."""
    form = CurrencyForm()

    if form.validate_on_submit():
        currency = Moneda()
        currency.codigo = form.codigo.data
        currency.nombre = form.nombre.data
        currency.simbolo = form.simbolo.data
        currency.activo = form.activo.data
        currency.creado_por = current_user.usuario

        db.session.add(currency)
        db.session.commit()
        flash(_("Moneda creada exitosamente."), "success")
        return redirect(url_for("currency.index"))

    return render_template("modules/currency/form.html", form=form, title=_("Nueva Moneda"))


@currency_bp.route("/edit/<string:id_>", methods=["GET", "POST"])
@require_write_access()
def edit(id_: str):
    """Edit an existing currency."""
    currency = db.session.get(Moneda, id_)
    if not currency:
        flash(_("Moneda no encontrada."), "error")
        return redirect(url_for("currency.index"))

    form = CurrencyForm(obj=currency)

    if form.validate_on_submit():
        currency.codigo = form.codigo.data
        currency.nombre = form.nombre.data
        currency.simbolo = form.simbolo.data
        currency.activo = form.activo.data
        currency.modificado_por = current_user.usuario

        db.session.commit()
        flash(_("Moneda actualizada exitosamente."), "success")
        return redirect(url_for("currency.index"))

    return render_template(
        "modules/currency/form.html",
        form=form,
        title=_("Editar Moneda"),
        currency=currency,
    )


@currency_bp.route("/delete/<string:id_>", methods=["POST"])
@require_write_access()
def delete(id_: str):
    """Delete a currency."""
    currency = db.session.get(Moneda, id_)
    if not currency:
        flash(_("Moneda no encontrada."), "error")
        return redirect(url_for("currency.index"))

    db.session.delete(currency)
    db.session.commit()
    flash(_("Moneda eliminada exitosamente."), "success")
    return redirect(url_for("currency.index"))
