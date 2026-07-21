# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Prestacion (Benefits) module views.

This module provides views for managing benefits including a dashboard
and bulk loading capabilities similar to the vacation module.
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import distinct
from sqlalchemy.sql.functions import count

from coati_payroll.enums import TipoUsuario
from coati_payroll.i18n import _
from coati_payroll.model import (
    db,
    Prestacion,
    PrestacionAcumulada,
    CargaInicialPrestacion,
    Empleado,
    Moneda,
)
from coati_payroll.rbac import require_role

# Constants
MAX_DISPLAYED_ERRORS = 10  # Maximum number of errors to display in bulk upload results

prestacion_management_bp = Blueprint("prestacion_management", __name__, url_prefix="/prestacion-management")


# ============================================================================
# Prestacion Dashboard
# ============================================================================


@prestacion_management_bp.route("/", methods=["GET"])
@login_required
def dashboard():
    """Prestacion management dashboard."""
    # Statistics
    total_prestaciones = (
        db.session.execute(db.select(count(Prestacion.id)).filter(Prestacion.activo.is_(True))).scalar() or 0
    )

    # Count employees with benefit balances
    total_accounts = db.session.execute(db.select(count(distinct(PrestacionAcumulada.empleado_id)))).scalar() or 0

    # Count pending initial loads
    pending_loads = (
        db.session.execute(
            db.select(count(CargaInicialPrestacion.id)).filter(CargaInicialPrestacion.estado == "draft")
        ).scalar()
        or 0
    )

    # Recent activity - latest transactions
    recent_transactions = (
        db.session.execute(
            db.select(PrestacionAcumulada)
            .join(PrestacionAcumulada.empleado)
            .order_by(PrestacionAcumulada.fecha_transaccion.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    return render_template(
        "modules/prestacion_management/dashboard.html",
        total_prestaciones=total_prestaciones,
        total_accounts=total_accounts,
        pending_loads=pending_loads,
        recent_transactions=recent_transactions,
    )


# ============================================================================
# Initial Balance Loading (for System Implementation)
# ============================================================================


@prestacion_management_bp.route("/initial-balance/bulk", methods=["GET", "POST"])
@require_role(TipoUsuario.ADMIN)
def initial_balance_bulk():
    """Bulk load initial prestacion balances from Excel.

    Used during system implementation for companies with many employees.
    Allows uploading an Excel file with initial prestacion balances for multiple
    employees at once.

    Expected Excel format (without headers, data starts on row 1):
    - Column A: Código de Empleado
    - Column B: Código de Prestación
    - Column C: Año de Corte
    - Column D: Mes de Corte
    - Column E: Código de Moneda
    - Column F: Saldo Acumulado
    - Column G: Tipo de Cambio (opcional, default 1.0)
    - Column H: Observaciones (opcional)
    """
    if request.method == "POST":
        # Check if file was uploaded
        if "file" not in request.files:
            flash(_("No se seleccionó ningún archivo."), "warning")
            return redirect(url_for("prestacion_management.initial_balance_bulk"))

        file = request.files["file"]

        if file.filename == "":
            flash(_("No se seleccionó ningún archivo."), "warning")
            return redirect(url_for("prestacion_management.initial_balance_bulk"))

        if not file.filename.endswith((".xlsx", ".xls")):
            flash(_("Por favor, suba un archivo Excel (.xlsx o .xls)."), "warning")
            return redirect(url_for("prestacion_management.initial_balance_bulk"))

        try:
            import openpyxl

            # Load Excel file
            workbook = openpyxl.load_workbook(file, data_only=True)
            sheet = workbook.active

            success_count = 0
            error_count = 0
            errors = []

            # Process each row (data starts at row 1, no headers expected)
            for row_num, row in enumerate(sheet.iter_rows(min_row=1, values_only=True), start=1):
                codigo_empleado = row[0]
                codigo_prestacion = row[1]
                anio_corte = row[2]
                mes_corte = row[3]
                codigo_moneda = row[4]
                saldo_acumulado = row[5]
                tipo_cambio = row[6] if len(row) > 6 and row[6] is not None else Decimal("1.0")
                observaciones = row[7] if len(row) > 7 else "Carga masiva de saldo inicial"

                # Validate required fields
                if not all(
                    [
                        codigo_empleado,
                        codigo_prestacion,
                        anio_corte,
                        mes_corte,
                        codigo_moneda,
                        saldo_acumulado is not None,
                    ]
                ):
                    errors.append(f"Fila {row_num}: Faltan campos requeridos")
                    error_count += 1
                    continue

                # Find employee
                empleado = db.session.execute(
                    db.select(Empleado).filter(Empleado.codigo_empleado == codigo_empleado, Empleado.activo.is_(True))
                ).scalar_one_or_none()

                if not empleado:
                    errors.append(f"Fila {row_num}: Empleado {codigo_empleado} no encontrado")
                    error_count += 1
                    continue

                # Find prestacion
                prestacion = db.session.execute(
                    db.select(Prestacion).filter(Prestacion.codigo == codigo_prestacion, Prestacion.activo.is_(True))
                ).scalar_one_or_none()

                if not prestacion:
                    errors.append(f"Fila {row_num}: Prestación {codigo_prestacion} no encontrada")
                    error_count += 1
                    continue

                # Find moneda
                moneda = db.session.execute(
                    db.select(Moneda).filter(Moneda.codigo == codigo_moneda, Moneda.activo.is_(True))
                ).scalar_one_or_none()

                if not moneda:
                    errors.append(f"Fila {row_num}: Moneda {codigo_moneda} no encontrada")
                    error_count += 1
                    continue

                # Check for duplicate
                existing = db.session.execute(
                    db.select(CargaInicialPrestacion).filter(
                        CargaInicialPrestacion.empleado_id == empleado.id,
                        CargaInicialPrestacion.prestacion_id == prestacion.id,
                        CargaInicialPrestacion.anio_corte == anio_corte,
                        CargaInicialPrestacion.mes_corte == mes_corte,
                    )
                ).scalar_one_or_none()

                if existing:
                    errors.append(
                        f"Fila {row_num}: Duplicado {codigo_empleado}, {codigo_prestacion}, {mes_corte}/{anio_corte}"
                    )
                    error_count += 1
                    continue

                try:
                    # Calculate saldo_convertido
                    saldo_convertido = Decimal(str(saldo_acumulado)) * Decimal(str(tipo_cambio))

                    # Create CargaInicialPrestacion
                    carga = CargaInicialPrestacion(
                        empleado_id=empleado.id,
                        prestacion_id=prestacion.id,
                        anio_corte=anio_corte,
                        mes_corte=mes_corte,
                        moneda_id=moneda.id,
                        saldo_acumulado=Decimal(str(saldo_acumulado)),
                        tipo_cambio=Decimal(str(tipo_cambio)),
                        saldo_convertido=saldo_convertido,
                        observaciones=str(observaciones) if observaciones else "Carga masiva de saldo inicial",
                        estado="draft",
                        creado_por=current_user.usuario if current_user.is_authenticated else None,
                    )

                    db.session.add(carga)
                    success_count += 1

                except Exception as e:
                    errors.append(f"Fila {row_num}: Error al procesar {codigo_empleado}: {str(e)}")
                    error_count += 1
                    continue

            # Commit all changes
            try:
                db.session.commit()
                flash(
                    _("Carga completada: {} registros exitosos en estado borrador, {} errores.").format(
                        success_count, error_count
                    ),
                    "success" if error_count == 0 else "warning",
                )

                if errors:
                    error_details = "<br>".join(errors[:MAX_DISPLAYED_ERRORS])
                    if len(errors) > MAX_DISPLAYED_ERRORS:
                        error_details += f"<br>...y {len(errors) - MAX_DISPLAYED_ERRORS} errores más"
                    flash(error_details, "warning")

            except Exception as e:
                db.session.rollback()
                flash(_("Error al guardar los cambios: {}").format(str(e)), "danger")

        except ImportError:
            flash(_("Error: La librería openpyxl no está instalada. Contacte al administrador."), "danger")
        except Exception as e:
            flash(_("Error al procesar el archivo Excel: {}").format(str(e)), "danger")

        return redirect(url_for("prestacion_management.initial_balance_bulk"))

    return render_template("modules/prestacion_management/initial_balance_bulk.html")
