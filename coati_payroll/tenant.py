# SPDX-License-Identifier: Apache-2.0
"""Tenant/company access helpers.

Company access is deliberately kept in one module so every view applies the
same rules. Administrators may work across all companies; other users may
only work in companies explicitly assigned to their account.
"""

from __future__ import annotations

from typing import Any

from flask import abort, redirect, request, session, url_for
from flask_login import current_user
from sqlalchemy import or_

from coati_payroll.enums import TipoUsuario
from coati_payroll.model import Empresa, db

ACTIVE_COMPANY_SESSION_KEY = "active_empresa_id"


def is_tenant_admin() -> bool:
    """Return whether the authenticated user has unrestricted company access."""
    return bool(current_user.is_authenticated and current_user.tipo == TipoUsuario.ADMIN.value)


def accessible_empresa_ids() -> set[str] | None:
    """Return permitted company IDs, or ``None`` for an administrator."""
    if not current_user.is_authenticated:
        return set()
    if is_tenant_admin():
        return None
    return {empresa.id for empresa in current_user.empresas if empresa.activo}


def report_empresa_ids() -> set[str] | None:
    """Return the company scope that report execution must apply.

    Unlike the general query helper, a multi-company user without an active
    selection receives an empty scope.  Reports must never silently aggregate
    all assigned companies when the UI is scoped to one selected company.
    """
    permitted = accessible_empresa_ids()
    if permitted is None:
        return None
    selected = active_empresa_id()
    if selected:
        return {selected}
    if len(permitted) == 1:
        return permitted
    return set()


def accessible_empresas(*, active_only: bool = True) -> list[Empresa]:
    """Return companies visible to the current user."""
    query = db.select(Empresa).order_by(Empresa.razon_social)
    if active_only:
        query = query.filter(Empresa.activo.is_(True))
    ids = accessible_empresa_ids()
    if ids is not None:
        if not ids:
            return []
        query = query.filter(Empresa.id.in_(ids))
    return list(db.session.execute(query).scalars().all())


def active_empresa_id() -> str | None:
    """Return the validated company selected for the current session.

    A user with exactly one assigned company is automatically scoped to it.
    A multi-company user must explicitly select one, preventing accidental
    cross-company views when a session has not yet been configured.
    """
    if not current_user.is_authenticated:
        return None

    permitted = accessible_empresa_ids()
    selected = session.get(ACTIVE_COMPANY_SESSION_KEY)
    if selected:
        company = db.session.get(Empresa, selected)
        if company is not None and company.activo and (permitted is None or selected in permitted):
            return selected
        session.pop(ACTIVE_COMPANY_SESSION_KEY, None)

    if permitted is not None and len(permitted) == 1:
        selected = next(iter(permitted))
        session[ACTIVE_COMPANY_SESSION_KEY] = selected
        return selected
    return None


def set_active_empresa(empresa_id: str) -> bool:
    """Select a company only when the current user is allowed to use it."""
    company = db.session.get(Empresa, empresa_id)
    permitted = accessible_empresa_ids()
    if company is None or not company.activo or (permitted is not None and empresa_id not in permitted):
        return False
    session[ACTIVE_COMPANY_SESSION_KEY] = empresa_id
    session.modified = True
    return True


def clear_active_empresa() -> None:
    """Clear the current company selection."""
    session.pop(ACTIVE_COMPANY_SESSION_KEY, None)
    session.modified = True


def scope_company_query(query: Any, company_column: Any) -> Any:
    """Apply the current tenant scope to a query with a company FK column."""
    selected = active_empresa_id()
    permitted = accessible_empresa_ids()
    if selected:
        return query.filter(company_column == selected)
    if permitted is None:
        return query
    if not permitted or len(permitted) > 1:
        return query.filter(db.false())
    return query.filter(company_column.in_(permitted))


def company_is_accessible(empresa_id: str | None) -> bool:
    """Check access to a company ID, including the active-session scope."""
    if not empresa_id:
        # Keep legacy, unassigned records operable for unrestricted admins.
        # Non-admin users can never use an unassigned tenant-owned record.
        return is_tenant_admin() and active_empresa_id() is None
    permitted = accessible_empresa_ids()
    if permitted is not None and empresa_id not in permitted:
        return False
    selected = active_empresa_id()
    return selected is None or selected == empresa_id


def require_company_access(empresa_id: str | None) -> None:
    """Abort with 404 for objects outside the current tenant scope."""
    if not company_is_accessible(empresa_id):
        abort(404)


def scoped_or_404(model: Any, object_id: str, company_column: Any) -> Any:
    """Load a company-owned object without exposing cross-tenant existence."""
    query = scope_company_query(db.select(model), company_column).filter(model.id == object_id)
    obj = db.session.execute(query).scalar_one_or_none()
    if obj is None:
        abort(404)
    return obj


def scoped_employee_owned_or_none(model: Any, object_id: str, employee_id_column: Any) -> Any:
    """Load an employee-owned object without revealing another tenant."""
    from coati_payroll.model import Empleado

    query = db.select(model).join(Empleado, employee_id_column == Empleado.id)
    query = scope_company_query(query, Empleado.empresa_id).filter(model.id == object_id)
    return db.session.execute(query).scalar_one_or_none()


def scoped_employee_owned_or_404(model: Any, object_id: str, employee_id_column: Any) -> Any:
    """Load an employee-owned object or return an indistinguishable 404."""
    obj = scoped_employee_owned_or_none(model, object_id, employee_id_column)
    if obj is None:
        abort(404)
    return obj


def concept_scope_query(query: Any, association_table: Any, concept_id_column: Any) -> Any:
    """Limit a global concept query to global concepts or the active company."""
    selected = active_empresa_id()
    permitted = accessible_empresa_ids()
    if permitted is None and selected is None:
        return query
    company_ids = {selected} if selected else permitted
    return (
        query.outerjoin(association_table, concept_id_column == association_table.c.concept_id)
        .filter(or_(association_table.c.empresa_id.is_(None), association_table.c.empresa_id.in_(company_ids or set())))
        .distinct()
    )


def concept_scope_for_company(query: Any, association_table: Any, concept_id_column: Any, empresa_id: str) -> Any:
    """Limit concepts to global definitions or definitions allowed for a company."""
    return (
        query.outerjoin(association_table, concept_id_column == association_table.c.concept_id)
        .filter(or_(association_table.c.empresa_id.is_(None), association_table.c.empresa_id == empresa_id))
        .distinct()
    )


def policy_scope_query(query: Any) -> Any:
    """Scope vacation policies by their company or associated planilla."""
    from coati_payroll.model import Planilla, VacationPolicy

    selected = active_empresa_id()
    permitted = accessible_empresa_ids()
    if permitted is None and selected is None:
        return query
    company_ids = {selected} if selected else permitted
    return (
        query.outerjoin(Planilla, VacationPolicy.planilla_id == Planilla.id)
        .filter(
            or_(
                db.and_(VacationPolicy.empresa_id.is_(None), VacationPolicy.planilla_id.is_(None)),
                VacationPolicy.empresa_id.in_(company_ids or set()),
                db.and_(VacationPolicy.empresa_id.is_(None), Planilla.empresa_id.in_(company_ids or set())),
            )
        )
        .distinct()
    )


def same_origin_redirect(default_endpoint: str):
    """Redirect back to a local referrer after a company switch."""
    target = request.referrer
    if not target or not target.startswith(request.host_url):
        target = url_for(default_endpoint)
    return redirect(target)
