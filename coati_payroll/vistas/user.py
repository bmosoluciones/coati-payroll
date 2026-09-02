# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""User CRUD routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coati_payroll.auth import proteger_passwd, validar_acceso
from coati_payroll.enums import TipoUsuario
from coati_payroll.forms import UserForm, ProfileForm
from coati_payroll.i18n import _
from coati_payroll.model import Empresa, Usuario, db
from coati_payroll.rbac import require_role
from coati_payroll.tenant import accessible_empresas
from coati_payroll.vistas.constants import PER_PAGE

user_bp = Blueprint("user", __name__, url_prefix="/user")
USER_INDEX_ENDPOINT = "user.index"
USER_FORM_TEMPLATE = "modules/user/form.html"


def _populate_company_choices(form: UserForm) -> None:
    """Populate company memberships using only companies the admin can see."""
    form.empresa_ids.choices = [(empresa.id, f"{empresa.codigo} - {empresa.razon_social}") for empresa in accessible_empresas()]


@user_bp.route("/", methods=["GET"])
@require_role(TipoUsuario.ADMIN)
def index():
    """List all users with pagination. Only administrators can manage users."""
    page = request.args.get("page", 1, type=int)
    pagination = db.paginate(
        db.select(Usuario).order_by(Usuario.usuario),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template("modules/user/index.html", users=pagination.items, pagination=pagination)


@user_bp.route("/new", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def new():
    """Create a new user. Only administrators can create users."""
    form = UserForm()
    _populate_company_choices(form)

    if form.validate_on_submit():
        user = Usuario()
        user.usuario = form.usuario.data
        if form.password.data:
            user.acceso = proteger_passwd(form.password.data)
        else:
            flash(_("La contraseña es requerida para nuevos usuarios."), "error")
            return render_template(USER_FORM_TEMPLATE, form=form, title=_("Nuevo Usuario"))

        user.nombre = form.nombre.data
        user.apellido = form.apellido.data
        user.correo_electronico = form.correo_electronico.data
        user.tipo = form.tipo.data
        user.activo = form.activo.data
        user.empresas = list(
            db.session.execute(db.select(Empresa).where(Empresa.id.in_(form.empresa_ids.data or []))).scalars().all()
        )
        user.creado_por = current_user.usuario

        db.session.add(user)
        db.session.commit()
        flash(_("Usuario creado exitosamente."), "success")
        return redirect(url_for(USER_INDEX_ENDPOINT))

    return render_template(USER_FORM_TEMPLATE, form=form, title=_("Nuevo Usuario"))


@user_bp.route("/edit/<string:id_>", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def edit(id_: str):
    """Edit an existing user. Only administrators can edit users."""
    user = db.session.get(Usuario, id_)
    if not user:
        flash(_("Usuario no encontrado."), "error")
        return redirect(url_for(USER_INDEX_ENDPOINT))

    form = UserForm(obj=user)
    _populate_company_choices(form)
    if request.method == "GET":
        form.empresa_ids.data = [empresa.id for empresa in user.empresas]

    if form.validate_on_submit():
        user.usuario = form.usuario.data
        if form.password.data:
            user.acceso = proteger_passwd(form.password.data)
        user.nombre = form.nombre.data
        user.apellido = form.apellido.data
        user.correo_electronico = form.correo_electronico.data
        user.tipo = form.tipo.data
        user.activo = form.activo.data
        user.empresas = list(
            db.session.execute(db.select(Empresa).where(Empresa.id.in_(form.empresa_ids.data or []))).scalars().all()
        )
        user.modificado_por = current_user.usuario

        db.session.commit()
        flash(_("Usuario actualizado exitosamente."), "success")
        return redirect(url_for(USER_INDEX_ENDPOINT))

    # Don't show password in form
    form.password.data = ""
    return render_template(USER_FORM_TEMPLATE, form=form, title=_("Editar Usuario"), user=user)


@user_bp.route("/delete/<string:id_>", methods=["POST"])
@require_role(TipoUsuario.ADMIN)
def delete(id_: str):
    """Delete a user. Only administrators can delete users."""
    user = db.session.get(Usuario, id_)
    if not user:
        flash(_("Usuario no encontrado."), "error")
        return redirect(url_for(USER_INDEX_ENDPOINT))

    if user.id == current_user.id:
        flash(_("No puedes eliminar tu propio usuario."), "error")
        return redirect(url_for(USER_INDEX_ENDPOINT))

    db.session.delete(user)
    db.session.commit()
    flash(_("Usuario eliminado exitosamente."), "success")
    return redirect(url_for(USER_INDEX_ENDPOINT))


@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Edit current user's profile and password."""
    form = ProfileForm(obj=current_user)

    if form.validate_on_submit():
        # Update basic profile information
        current_user.nombre = form.nombre.data
        current_user.apellido = form.apellido.data
        current_user.correo_electronico = form.correo_electronico.data

        # Handle password change if any password field has data
        password_change_attempted = form.current_password.data or form.new_password.data or form.confirm_password.data

        if password_change_attempted:
            # Validate password change
            error_message = None

            if not form.current_password.data:
                error_message = _("Debe ingresar la contraseña actual.")
            elif not validar_acceso(current_user.usuario, form.current_password.data):
                error_message = _("La contraseña actual es incorrecta.")
            elif not form.new_password.data:
                error_message = _("Debe ingresar una nueva contraseña.")
            elif form.new_password.data != form.confirm_password.data:
                error_message = _("Las contraseñas no coinciden.")

            if error_message:
                flash(error_message, "error")
                return render_template("modules/user/profile.html", form=form)

            # Update password
            current_user.acceso = proteger_passwd(form.new_password.data)
            flash(_("Contraseña actualizada exitosamente."), "success")

        current_user.modificado_por = current_user.usuario
        db.session.commit()
        flash(_("Perfil actualizado exitosamente."), "success")
        return redirect(url_for("user.profile"))

    # Clear password fields
    form.current_password.data = ""
    form.new_password.data = ""
    form.confirm_password.data = ""

    return render_template("modules/user/profile.html", form=form)
