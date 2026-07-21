# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Service for Excel export operations."""

from io import BytesIO

from coati_payroll.enums import NominaEstado, TipoDetalle
from coati_payroll.model import (
    db,
    Planilla,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    Liquidacion,
    LiquidacionDetalle,
    ComprobanteContable,
)
from coati_payroll.vistas.planilla.helpers.excel_helpers import check_openpyxl_available
from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

# Constants
ERROR_OPENPYXL_NOT_AVAILABLE = "openpyxl no está disponible"


class ExportService:
    """Service for Excel export operations."""

    @staticmethod
    def _create_styles(openpyxl_classes):
        """Create common Excel styles from openpyxl classes."""
        Workbook, Font, Alignment, PatternFill, Border, Side = openpyxl_classes
        return {
            "header_font": Font(bold=True, size=14, color="FFFFFF"),
            "header_fill": PatternFill(start_color="366092", end_color="366092", fill_type="solid"),
            "subheader_font": Font(bold=True, size=11),
            "subheader_fill": PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid"),
            "total_font": Font(bold=True, size=11),
            "total_fill": PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid"),
            "border": Border(
                left=Side(style="thin"),
                right=Side(style="thin"),
                top=Side(style="thin"),
                bottom=Side(style="thin"),
            ),
        }

    @staticmethod
    def _write_title(ws, title: str, styles: dict, merge_range: str = "A1:F1"):
        """Write a styled title to the worksheet."""
        from openpyxl.styles import Alignment
        ws.merge_cells(merge_range)
        cell = ws["A1"]
        cell.value = title
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = Alignment(horizontal="center", vertical="center")

    @staticmethod
    def _write_info_block(ws, row: int, planilla, nomina=None, comprobante=None) -> int:
        """Write common metadata info block. Returns next available row."""
        if planilla.empresa_id and planilla.empresa:
            ws[f"A{row}"] = "Empresa:"
            ws[f"B{row}"] = planilla.empresa.razon_social
            row += 1
            if planilla.empresa.ruc:
                ws[f"A{row}"] = "RUC:"
                ws[f"B{row}"] = planilla.empresa.ruc
                row += 1

        if nomina:
            ws[f"A{row}"] = "Período:"
            ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"
            row += 1
            ws[f"A{row}"] = "Estado:"
            ws[f"B{row}"] = nomina.estado
            row += 1
            ws[f"A{row}"] = "Generado por:"
            ws[f"B{row}"] = nomina.generado_por or ""
            row += 1

        if comprobante:
            ws[f"A{row}"] = "Concepto:"
            ws[f"B{row}"] = comprobante.concepto or ""
            row += 1
            ws[f"A{row}"] = "Fecha de Cálculo:"
            ws[f"B{row}"] = comprobante.fecha_calculo.strftime("%d/%m/%Y")
            row += 1
            ws[f"A{row}"] = "ID Planilla:"
            ws[f"B{row}"] = planilla.id
            row += 1
            ws[f"A{row}"] = "Estatus Planilla:"
            ws[f"B{row}"] = nomina.estado
            row += 1
            if comprobante.moneda:
                ws[f"A{row}"] = "Moneda:"
                ws[f"B{row}"] = f"{comprobante.moneda.codigo} - {comprobante.moneda.nombre}"
                row += 1
            if comprobante.aplicado_por:
                ws[f"A{row}"] = "Aplicado por:"
                ws[f"B{row}"] = comprobante.aplicado_por
                row += 1
            if comprobante.fecha_aplicacion:
                ws[f"A{row}"] = "Fecha aplicación:"
                ws[f"B{row}"] = comprobante.fecha_aplicacion.strftime("%d/%m/%Y %H:%M")
                row += 1
            if comprobante.veces_modificado > 0:
                ws[f"A{row}"] = "Modificado:"
                ws[f"B{row}"] = f"{comprobante.veces_modificado} vez/veces"
                row += 1
                if comprobante.modificado_por:
                    ws[f"A{row}"] = "Última modificación por:"
                    ws[f"B{row}"] = comprobante.modificado_por
                    row += 1
                if comprobante.fecha_modificacion:
                    ws[f"A{row}"] = "Fecha última modificación:"
                    ws[f"B{row}"] = comprobante.fecha_modificacion.strftime("%d/%m/%Y %H:%M")
                    row += 1

        return row

    @staticmethod
    def _write_table_headers(ws, row: int, headers: list[str], styles: dict):
        """Write styled table headers."""
        from openpyxl.styles import Alignment
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = styles["subheader_font"]
            cell.fill = styles["subheader_fill"]
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = styles["border"]

    @staticmethod
    def _write_totals_row(ws, row: int, total_debitos, total_credito, styles: dict):
        """Write a totals row."""
        border = styles["border"]
        ws.cell(row=row, column=1, value="TOTALES").font = styles["total_font"]
        ws.cell(row=row, column=1).fill = styles["total_fill"]
        ws.cell(row=row, column=1).border = border
        ws.cell(row=row, column=2).border = border
        ws.cell(row=row, column=3).border = border

        cell_debito = ws.cell(row=row, column=4, value=float(total_debitos))
        cell_debito.font = styles["total_font"]
        cell_debito.fill = styles["total_fill"]
        cell_debito.border = border

        cell_credito = ws.cell(row=row, column=5, value=float(total_credito))
        cell_credito.font = styles["total_font"]
        cell_credito.fill = styles["total_fill"]
        cell_credito.border = border

    @staticmethod
    def _write_warnings(ws, row: int, warnings: list[str]):
        """Write warning messages."""
        from openpyxl.styles import Font
        if not warnings:
            return row
        ws[f"A{row}"] = "ADVERTENCIAS:"
        ws[f"A{row}"].font = Font(bold=True, color="FF0000")
        row += 1
        for warning in warnings:
            ws[f"A{row}"] = f"• {warning}"
            ws[f"A{row}"].font = Font(color="FF0000")
            row += 1
        return row + 1

    @staticmethod
    def _save_workbook(wb, planilla, nomina, prefix: str) -> tuple[BytesIO, str]:
        """Save workbook to BytesIO and return with filename."""
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"{prefix}_{planilla.nombre}_{nomina.periodo_inicio.strftime('%Y%m%d')}_{nomina.id[:8]}.xlsx"
        return output, filename

    @staticmethod
    def _add_traceability_section(ws, row: int, nomina: Nomina) -> int:
        """Add user traceability section and return next available row."""
        ws[f"A{row}"] = "TRAZABILIDAD DE USUARIO:"
        row += 1

        ws[f"A{row}"] = "Creado por:"
        ws[f"B{row}"] = nomina.generado_por or "N/A"
        row += 1

        ws[f"A{row}"] = "Aprobado por:"
        ws[f"B{row}"] = nomina.aprobado_por or "N/A"
        row += 1

        ws[f"A{row}"] = "Aplicado por:"
        ws[f"B{row}"] = nomina.aplicado_por or "N/A"
        return row + 1

    @staticmethod
    def exportar_nomina_excel(planilla: Planilla, nomina: Nomina) -> tuple[BytesIO, str]:
        """Export nomina to Excel with employee details and calculations.

        Args:
            planilla: The planilla
            nomina: The nomina to export

        Returns:
            Tuple of (BytesIO file object, filename)
        """
        openpyxl_classes = check_openpyxl_available()
        if not openpyxl_classes:
            raise ImportError(ERROR_OPENPYXL_NOT_AVAILABLE)

        Workbook, Font, Alignment, PatternFill, Border, Side = openpyxl_classes

        nomina_empleados = db.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=nomina.id)).scalars().all()

        wb = Workbook()
        ws = wb.active
        ws.title = "Nómina"

        styles = ExportService._create_styles(openpyxl_classes)
        ExportService._write_title(ws, f"NÓMINA - {planilla.nombre}", styles, "A1:P1")

        row = ExportService._write_info_block(ws, 3, planilla, nomina)
        row += 1

        headers = [
            "Cód. Empleado", "Identificación", "No. Seg. Social", "ID Fiscal",
            "Nombres", "Apellidos", "Cargo", "Salario Base",
            "Total Percepciones", "Total Deducciones", "Salario Neto",
        ]
        ExportService._write_table_headers(ws, row, headers, styles)

        for ne in nomina_empleados:
            row += 1
            emp = ne.empleado
            ws.cell(row=row, column=1, value=emp.codigo_empleado).border = styles["border"]
            ws.cell(row=row, column=2, value=emp.identificacion_personal).border = styles["border"]
            ws.cell(row=row, column=3, value=emp.id_seguridad_social or "").border = styles["border"]
            ws.cell(row=row, column=4, value=emp.id_fiscal or "").border = styles["border"]
            name = f"{emp.primer_nombre} {emp.segundo_nombre or ''}".strip()
            ws.cell(row=row, column=5, value=name).border = styles["border"]
            last_name = f"{emp.primer_apellido} {emp.segundo_apellido or ''}".strip()
            ws.cell(row=row, column=6, value=last_name).border = styles["border"]
            ws.cell(row=row, column=7, value=ne.cargo_snapshot or emp.cargo or "").border = styles["border"]
            ws.cell(row=row, column=8, value=float(ne.sueldo_base_historico)).border = styles["border"]
            ws.cell(row=row, column=9, value=float(ne.total_ingresos)).border = styles["border"]
            ws.cell(row=row, column=10, value=float(ne.total_deducciones)).border = styles["border"]
            ws.cell(row=row, column=11, value=float(ne.salario_neto)).border = styles["border"]

        for col in range(1, 12):
            ws.column_dimensions[chr(64 + col)].width = 15

        return ExportService._save_workbook(wb, planilla, nomina, "nomina")

    @staticmethod
    def exportar_prestaciones_excel(planilla: Planilla, nomina: Nomina) -> tuple[BytesIO, str]:
        """Export benefits (prestaciones) to Excel separately.

        Args:
            planilla: The planilla
            nomina: The nomina to export

        Returns:
            Tuple of (BytesIO file object, filename)
        """
        openpyxl_classes = check_openpyxl_available()
        if not openpyxl_classes:
            raise ImportError(ERROR_OPENPYXL_NOT_AVAILABLE)

        Workbook, Font, Alignment, PatternFill, Border, Side = openpyxl_classes

        # Get all nomina employees
        nomina_empleados = db.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=nomina.id)).scalars().all()

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Prestaciones"

        # Define styles
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        subheader_font = Font(bold=True, size=11)
        subheader_fill = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Title
        ws.merge_cells("A1:F1")
        title_cell = ws["A1"]
        title_cell.value = f"PRESTACIONES LABORALES - {planilla.nombre}"
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Nomina info
        row = 3
        if planilla.empresa_id and planilla.empresa:
            ws[f"A{row}"] = "Empresa:"
            ws[f"B{row}"] = planilla.empresa.razon_social
            row += 1
            if planilla.empresa.ruc:
                ws[f"A{row}"] = "RUC:"
                ws[f"B{row}"] = planilla.empresa.ruc
                row += 1
        ws[f"A{row}"] = "Período:"
        ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"
        row += 2

        # Table headers
        headers = ["Cód. Empleado", "Nombres", "Apellidos"]

        # Get all unique prestaciones
        prestaciones_set = set()
        for ne in nomina_empleados:
            detalles = (
                db.session.execute(
                    db.select(NominaDetalle).filter_by(nomina_empleado_id=ne.id, tipo=TipoDetalle.PRESTACION)
                )
                .scalars()
                .all()
            )
            for d in detalles:
                prestaciones_set.add((d.codigo, d.descripcion))

        prestaciones_list = sorted(prestaciones_set, key=lambda x: x[0])
        headers.extend([p[1] or p[0] for p in prestaciones_list])

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = subheader_font
            cell.fill = subheader_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        # Data rows
        for ne in nomina_empleados:
            row += 1
            emp = ne.empleado

            ws.cell(row=row, column=1, value=emp.codigo_empleado).border = border
            ws.cell(row=row, column=2, value=f"{emp.primer_nombre} {emp.segundo_nombre or ''}".strip()).border = border
            ws.cell(row=row, column=3, value=f"{emp.primer_apellido} {emp.segundo_apellido or ''}".strip()).border = (
                border
            )

            # Get prestaciones for this employee
            detalles = (
                db.session.execute(
                    db.select(NominaDetalle)
                    .filter_by(nomina_empleado_id=ne.id, tipo=TipoDetalle.PRESTACION)
                    .order_by(NominaDetalle.orden)
                )
                .scalars()
                .all()
            )

            prestaciones_dict = {d.codigo: float(d.monto) for d in detalles}

            # Fill prestacion amounts
            for col_idx, (codigo, _nombre) in enumerate(prestaciones_list, start=4):
                cell = ws.cell(row=row, column=col_idx, value=prestaciones_dict.get(codigo, 0.0))
                cell.border = border

        # Auto-adjust column widths
        for col in range(1, min(len(headers) + 1, 27)):
            ws.column_dimensions[chr(64 + col)].width = 15

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"prestaciones_{planilla.nombre}_{nomina.periodo_inicio.strftime('%Y%m%d')}_{nomina.id[:8]}.xlsx"
        return output, filename

    @staticmethod
    def exportar_liquidacion_excel(liquidacion: Liquidacion) -> tuple[BytesIO, str]:
        openpyxl_classes = check_openpyxl_available()
        if not openpyxl_classes:
            raise ImportError(ERROR_OPENPYXL_NOT_AVAILABLE)

        Workbook, Font, Alignment, PatternFill, Border, Side = openpyxl_classes

        liquidacion = db.session.merge(liquidacion)
        empleado = liquidacion.empleado

        detalles = (
            db.session.execute(
                db.select(LiquidacionDetalle)
                .filter_by(liquidacion_id=liquidacion.id)
                .order_by(LiquidacionDetalle.orden)
            )
            .scalars()
            .all()
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Liquidación"

        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        subheader_font = Font(bold=True, size=11)
        subheader_fill = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        ws.merge_cells("A1:F1")
        title_cell = ws["A1"]
        title_cell.value = "LIQUIDACIÓN"
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        row = 3
        ws[f"A{row}"] = "Empleado:"
        ws[f"B{row}"] = (
            f"{empleado.codigo_empleado} - {empleado.primer_nombre} {empleado.primer_apellido}" if empleado else ""
        )
        row += 1
        ws[f"A{row}"] = "Fecha cálculo:"
        ws[f"B{row}"] = str(liquidacion.fecha_calculo)
        row += 1
        ws[f"A{row}"] = "Último día pagado:"
        ws[f"B{row}"] = str(liquidacion.ultimo_dia_pagado or "")
        row += 1
        ws[f"A{row}"] = "Días por pagar:"
        ws[f"B{row}"] = liquidacion.dias_por_pagar
        row += 1
        ws[f"A{row}"] = "Estado:"
        ws[f"B{row}"] = liquidacion.estado
        row += 2

        headers = ["Tipo", "Código", "Descripción", "Monto"]
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = subheader_font
            cell.fill = subheader_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        for d in detalles:
            row += 1
            ws.cell(row=row, column=1, value=d.tipo).border = border
            ws.cell(row=row, column=2, value=d.codigo).border = border
            ws.cell(row=row, column=3, value=d.descripcion or "").border = border
            ws.cell(row=row, column=4, value=float(d.monto)).border = border

        row += 2
        ws[f"A{row}"] = "Total bruto:"
        ws[f"B{row}"] = float(liquidacion.total_bruto or 0)
        row += 1
        ws[f"A{row}"] = "Total deducciones:"
        ws[f"B{row}"] = float(liquidacion.total_deducciones or 0)
        row += 1
        ws[f"A{row}"] = "Total neto:"
        ws[f"B{row}"] = float(liquidacion.total_neto or 0)

        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 45
        ws.column_dimensions["D"].width = 15

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        emp_code = empleado.codigo_empleado if empleado else "empleado"
        filename = f"liquidacion_{emp_code}_{liquidacion.fecha_calculo.strftime('%Y%m%d')}_{liquidacion.id[:8]}.xlsx"
        return output, filename

    @staticmethod
    def exportar_comprobante_excel(planilla: Planilla, nomina: Nomina) -> tuple[BytesIO, str]:
        """Export summarized accounting voucher (comprobante contable) to Excel.

        Exports the accounting voucher grouped by account and cost center with netted amounts.

        Raises ValueError if accounting configuration is incomplete.

        Args:
            planilla: The planilla
            nomina: The nomina to export

        Returns:
            Tuple of (BytesIO file object, filename)

        Raises:
            ValueError: If comprobante doesn't exist or has incomplete accounting configuration
        """
        openpyxl_classes = check_openpyxl_available()
        if not openpyxl_classes:
            raise ImportError(ERROR_OPENPYXL_NOT_AVAILABLE)

        Workbook, Font, Alignment, PatternFill, Border, Side = openpyxl_classes

        if nomina.estado == NominaEstado.GENERADO_CON_ERRORES:
            raise ValueError("Nómina calculada con errores: corrija empleados fallidos y recalcule antes de exportar.")

        # Get comprobante
        comprobante = db.session.execute(
            db.select(ComprobanteContable).filter_by(nomina_id=nomina.id)
        ).scalar_one_or_none()

        if not comprobante:
            raise ValueError("No existe comprobante contable para esta nómina")

        balance = comprobante.balance
        if balance is None:
            total_debitos = comprobante.total_debitos or 0
            total_creditos = comprobante.total_creditos or 0
            balance = total_debitos - total_creditos

        if balance != 0:
            raise ValueError(
                "El comprobante no esta balanceado. "
                f"Debitos: {comprobante.total_debitos}, Creditos: {comprobante.total_creditos}."
            )

        # Get summarized entries - will raise ValueError if accounts are NULL
        accounting_service = AccountingVoucherService(db.session)
        accounting_service.validate_line_integrity(comprobante)
        try:
            summarized_entries = accounting_service.summarize_voucher(comprobante)
        except ValueError as e:
            # Re-raise with clear message about incomplete configuration
            raise ValueError(
                f"No se puede exportar comprobante sumarizado: {str(e)} "
                "Utilice la exportación detallada para auditoría."
            ) from e

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Comprobante Contable"

        # Define styles
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        subheader_font = Font(bold=True, size=11)
        subheader_fill = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
        total_font = Font(bold=True, size=11)
        total_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Title
        ws.merge_cells("A1:F1")
        title_cell = ws["A1"]
        title_cell.value = f"COMPROBANTE CONTABLE - {planilla.nombre}"
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Comprobante info
        row = 3
        if planilla.empresa_id and planilla.empresa:
            ws[f"A{row}"] = "Empresa:"
            ws[f"B{row}"] = planilla.empresa.razon_social
            row += 1

        ws[f"A{row}"] = "Concepto:"
        ws[f"B{row}"] = comprobante.concepto or ""
        row += 1

        ws[f"A{row}"] = "Fecha de Cálculo:"
        ws[f"B{row}"] = comprobante.fecha_calculo.strftime("%d/%m/%Y")
        row += 1

        ws[f"A{row}"] = "Período:"
        ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"
        row += 1

        ws[f"A{row}"] = "ID Planilla:"
        ws[f"B{row}"] = planilla.id
        row += 1

        ws[f"A{row}"] = "Estatus Planilla:"
        ws[f"B{row}"] = nomina.estado
        row += 1

        if comprobante.moneda:
            ws[f"A{row}"] = "Moneda:"
            ws[f"B{row}"] = f"{comprobante.moneda.codigo} - {comprobante.moneda.nombre}"
            row += 1

        # Audit trail information
        if comprobante.aplicado_por:
            ws[f"A{row}"] = "Aplicado por:"
            ws[f"B{row}"] = comprobante.aplicado_por
            row += 1

        if comprobante.fecha_aplicacion:
            ws[f"A{row}"] = "Fecha aplicación:"
            ws[f"B{row}"] = comprobante.fecha_aplicacion.strftime("%d/%m/%Y %H:%M")
            row += 1

        if comprobante.veces_modificado > 0:
            ws[f"A{row}"] = "Modificado:"
            ws[f"B{row}"] = f"{comprobante.veces_modificado} vez/veces"
            row += 1

            if comprobante.modificado_por:
                ws[f"A{row}"] = "Última modificación por:"
                ws[f"B{row}"] = comprobante.modificado_por
                row += 1

            if comprobante.fecha_modificacion:
                ws[f"A{row}"] = "Fecha última modificación:"
                ws[f"B{row}"] = comprobante.fecha_modificacion.strftime("%d/%m/%Y %H:%M")
                row += 1

        row += 1

        # Warnings if any
        if comprobante.advertencias:
            ws[f"A{row}"] = "ADVERTENCIAS:"
            ws[f"A{row}"].font = Font(bold=True, color="FF0000")
            row += 1
            for warning in comprobante.advertencias:
                ws[f"A{row}"] = f"• {warning}"
                ws[f"A{row}"].font = Font(color="FF0000")
                row += 1
            row += 1

        # Table headers
        headers = ["Código Cuenta", "Descripción", "Centro de Costos", "Débito", "Crédito"]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = subheader_font
            cell.fill = subheader_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        # Data rows
        for entry in summarized_entries:
            row += 1
            ws.cell(row=row, column=1, value=entry["codigo_cuenta"]).border = border
            ws.cell(row=row, column=2, value=entry["descripcion"]).border = border
            ws.cell(row=row, column=3, value=entry["centro_costos"] or "").border = border
            ws.cell(row=row, column=4, value=float(entry["debito"])).border = border
            ws.cell(row=row, column=5, value=float(entry["credito"])).border = border

        # Totals row
        row += 1
        ws.cell(row=row, column=1, value="TOTALES").font = total_font
        ws.cell(row=row, column=1).fill = total_fill
        ws.cell(row=row, column=1).border = border
        ws.cell(row=row, column=2).border = border
        ws.cell(row=row, column=3).border = border

        cell_debito = ws.cell(row=row, column=4, value=float(comprobante.total_debitos))
        cell_debito.font = total_font
        cell_debito.fill = total_fill
        cell_debito.border = border

        cell_credito = ws.cell(row=row, column=5, value=float(comprobante.total_creditos))
        cell_credito.font = total_font
        cell_credito.fill = total_fill
        cell_credito.border = border

        # Balance check
        row += 2
        ws[f"A{row}"] = "Balance (debe ser 0):"
        ws[f"B{row}"] = float(comprobante.balance)
        if comprobante.balance != 0:
            ws[f"B{row}"].font = Font(bold=True, color="FF0000")

        row += 2
        row = ExportService._add_traceability_section(ws, row, nomina)

        # Auto-adjust column widths
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 40
        ws.column_dimensions["C"].width = 20
        ws.column_dimensions["D"].width = 15
        ws.column_dimensions["E"].width = 15

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"comprobante_{planilla.nombre}_{nomina.periodo_inicio.strftime('%Y%m%d')}_{nomina.id[:8]}.xlsx"
        return output, filename

    @staticmethod
    def exportar_comprobante_detallado_excel(planilla: Planilla, nomina: Nomina) -> tuple[BytesIO, str]:
        """Export detailed accounting voucher per employee to Excel.

        Exports the full accounting voucher with all lines per employee for audit purposes.
        This export works even with incomplete accounting configuration, showing NULL for
        missing account fields.

        Args:
            planilla: The planilla
            nomina: The nomina to export

        Returns:
            Tuple of (BytesIO file object, filename)
        """
        openpyxl_classes = check_openpyxl_available()
        if not openpyxl_classes:
            raise ImportError(ERROR_OPENPYXL_NOT_AVAILABLE)

        Workbook, Font, Alignment, PatternFill, Border, Side = openpyxl_classes

        # Get comprobante
        comprobante = db.session.execute(
            db.select(ComprobanteContable).filter_by(nomina_id=nomina.id)
        ).scalar_one_or_none()

        if not comprobante:
            raise ValueError("No existe comprobante contable para esta nómina")

        # Get detailed entries
        accounting_service = AccountingVoucherService(db.session)
        detailed_entries = accounting_service.get_detailed_voucher_by_employee(comprobante)

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Comprobante Detallado"

        # Define styles
        header_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        subheader_font = Font(bold=True, size=11)
        subheader_fill = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Title
        ws.merge_cells("A1:G1")
        title_cell = ws["A1"]
        title_cell.value = f"COMPROBANTE CONTABLE DETALLADO - {planilla.nombre}"
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Comprobante info
        row = 3
        if planilla.empresa_id and planilla.empresa:
            ws[f"A{row}"] = "Empresa:"
            ws[f"B{row}"] = planilla.empresa.razon_social
            row += 1

        ws[f"A{row}"] = "Concepto:"
        ws[f"B{row}"] = comprobante.concepto or ""
        row += 1

        ws[f"A{row}"] = "Fecha de Cálculo:"
        ws[f"B{row}"] = comprobante.fecha_calculo.strftime("%d/%m/%Y")
        row += 1

        ws[f"A{row}"] = "Período:"
        ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"
        row += 1

        ws[f"A{row}"] = "ID Planilla:"
        ws[f"B{row}"] = planilla.id
        row += 1

        ws[f"A{row}"] = "Estatus Planilla:"
        ws[f"B{row}"] = nomina.estado
        row += 2

        # Table headers
        headers = ["Código Empleado", "Empleado", "Concepto", "Código Cuenta", "Descripción", "Débito", "Crédito"]

        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = subheader_font
            cell.fill = subheader_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        # Data rows - per employee
        for employee_entry in detailed_entries:
            for linea in employee_entry["lineas"]:
                row += 1
                ws.cell(row=row, column=1, value=employee_entry["empleado_codigo"]).border = border
                ws.cell(row=row, column=2, value=employee_entry["empleado_nombre"]).border = border
                ws.cell(row=row, column=3, value=linea["concepto"]).border = border
                ws.cell(row=row, column=4, value=linea["codigo_cuenta"]).border = border
                ws.cell(row=row, column=5, value=linea["descripcion_cuenta"]).border = border
                ws.cell(row=row, column=6, value=float(linea["debito"])).border = border
                ws.cell(row=row, column=7, value=float(linea["credito"])).border = border

        row += 2
        row = ExportService._add_traceability_section(ws, row, nomina)

        # Auto-adjust column widths
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 30
        ws.column_dimensions["C"].width = 30
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 35
        ws.column_dimensions["F"].width = 15
        ws.column_dimensions["G"].width = 15

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = (
            f"comprobante_detallado_{planilla.nombre}_{nomina.periodo_inicio.strftime('%Y%m%d')}_{nomina.id[:8]}.xlsx"
        )
        return output, filename
