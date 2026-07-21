# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Service for Excel export operations."""

from io import BytesIO
from typing import cast

from coati_payroll.enums import NominaEstado, TipoDetalle
from coati_payroll.model import (
    db,
    Planilla,
    PlanillaIngreso,
    PlanillaDeduccion,
    PlanillaPrestacion,
    Nomina,
    NominaEmpleado,
    NominaDetalle,
    Liquidacion,
    LiquidacionDetalle,
    ComprobanteContable,
    ComprobanteContableLinea,
)
from coati_payroll.vistas.planilla.helpers.excel_helpers import check_openpyxl_available
from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService

# Constants
ERROR_OPENPYXL_NOT_AVAILABLE = "openpyxl no está disponible"
TITLE_MERGE_RANGE = "A1:F1"
LABEL_PLANILLA_ID = "ID Planilla:"
LABEL_PLANILLA_STATUS = "Status Planilla:"
LABEL_APPLIED_BY = "Aplicado por:"
LABEL_CONCEPT = "Concepto:"
LABEL_CALCULATION_DATE = "Fecha de Cálculo:"
DATE_FORMAT = "%d/%m/%Y"
DATETIME_FORMAT = "%d/%m/%Y %H:%M"


class ExportService:
    """Service for Excel export operations."""

    @staticmethod
    def _create_styles(openpyxl_classes):
        """Create common Excel styles from openpyxl classes."""
        _, font_class, _, pattern_fill_class, border_class, side_class = openpyxl_classes
        return {
            "header_font": font_class(bold=True, size=14, color="FFFFFF"),
            "header_fill": pattern_fill_class(start_color="366092", end_color="366092", fill_type="solid"),
            "subheader_font": font_class(bold=True, size=11),
            "subheader_fill": pattern_fill_class(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid"),
            "total_font": font_class(bold=True, size=11),
            "total_fill": pattern_fill_class(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid"),
            "border": border_class(
                left=side_class(style="thin"),
                right=side_class(style="thin"),
                top=side_class(style="thin"),
                bottom=side_class(style="thin"),
            ),
        }

    @staticmethod
    def _write_title(ws, title: str, styles: dict, merge_range: str = TITLE_MERGE_RANGE):
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
        row = ExportService._write_company_info(ws, row, planilla)
        if nomina:
            row = ExportService._write_nomina_info(ws, row, planilla, nomina)
        if comprobante:
            row = ExportService._write_comprobante_info(ws, row, planilla, comprobante)
        return row

    @staticmethod
    def _write_company_info(ws, row: int, planilla) -> int:
        """Write company metadata."""
        if planilla.empresa_id and planilla.empresa:
            ws[f"A{row}"] = "ID Empresa:"
            ws[f"B{row}"] = planilla.empresa_id
            row += 1
            ws[f"A{row}"] = "Empresa:"
            ws[f"B{row}"] = planilla.empresa.razon_social
            row += 1
            if planilla.empresa.ruc:
                ws[f"A{row}"] = "RUC:"
                ws[f"B{row}"] = planilla.empresa.ruc
                row += 1
        return row

    @staticmethod
    def _write_nomina_info(ws, row: int, planilla, nomina) -> int:
        """Write payroll metadata."""
        rows = (
            ("Período:", f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"),
            (LABEL_PLANILLA_ID, planilla.id),
            (LABEL_PLANILLA_STATUS, planilla.estado_aprobacion or ""),
            ("Estado Nomina:", nomina.estado),
            ("Creado por:", nomina.generado_por or ""),
        )
        for label, value in rows:
            ws[f"A{row}"] = label
            ws[f"B{row}"] = value
            row += 1
        for label, attribute in (("Aprobado por:", "aprobado_por"), (LABEL_APPLIED_BY, "aplicado_por")):
            value = getattr(nomina, attribute, None)
            if value:
                ws[f"A{row}"] = label
                ws[f"B{row}"] = value
                row += 1
        return row

    @staticmethod
    def _write_comprobante_info(ws, row: int, planilla, comprobante) -> int:
        """Write accounting voucher metadata."""
        rows = (
            (LABEL_CONCEPT, comprobante.concepto or ""),
            (LABEL_CALCULATION_DATE, comprobante.fecha_calculo.strftime(DATE_FORMAT)),
            (LABEL_PLANILLA_ID, planilla.id),
            (LABEL_PLANILLA_STATUS, planilla.estado_aprobacion or ""),
        )
        for label, value in rows:
            ws[f"A{row}"] = label
            ws[f"B{row}"] = value
            row += 1
        if comprobante.moneda:
            ws[f"A{row}"] = "Moneda:"
            ws[f"B{row}"] = f"{comprobante.moneda.codigo} - {comprobante.moneda.nombre}"
            row += 1
        optional_rows = (
            (LABEL_APPLIED_BY, comprobante.aplicado_por),
            (
                "Fecha aplicación:",
                comprobante.fecha_aplicacion.strftime(DATETIME_FORMAT) if comprobante.fecha_aplicacion else None,
            ),
        )
        for label, value in optional_rows:
            if value:
                ws[f"A{row}"] = label
                ws[f"B{row}"] = value
                row += 1
        if comprobante.veces_modificado > 0:
            ws[f"A{row}"] = "Modificado:"
            ws[f"B{row}"] = f"{comprobante.veces_modificado} vez/veces"
            row += 1
            for label, value in (
                ("Última modificación por:", comprobante.modificado_por),
                (
                    "Fecha última modificación:",
                    (
                        comprobante.fecha_modificacion.strftime(DATETIME_FORMAT)
                        if comprobante.fecha_modificacion
                        else None
                    ),
                ),
            ):
                if value:
                    ws[f"A{row}"] = label
                    ws[f"B{row}"] = value
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

        ws[f"A{row}"] = LABEL_APPLIED_BY
        ws[f"B{row}"] = nomina.aplicado_por or "N/A"
        return row + 1

    @staticmethod
    def _excel_col(col_num: int) -> str:
        label = ""
        while col_num > 0:
            col_num, remainder = divmod(col_num - 1, 26)
            label = chr(65 + remainder) + label
        return label

    @staticmethod
    def _unique_label(existing: set[str], preferred: str | None, fallback: str | None, base: str) -> str:
        raw = (preferred or fallback or base or "").strip()
        if not raw:
            raw = base
        candidate = raw
        idx = 2
        while candidate in existing:
            candidate = f"{raw} ({idx})"
            idx += 1
        existing.add(candidate)
        return candidate

    @staticmethod
    def exportar_nomina_excel(planilla: Planilla, nomina: Nomina) -> tuple[BytesIO, str]:
        """Export nomina to Excel in 5 dynamic sections."""
        openpyxl_classes = check_openpyxl_available()
        if not openpyxl_classes:
            raise ImportError(ERROR_OPENPYXL_NOT_AVAILABLE)

        workbook_class, font_class, alignment_class, pattern_fill_class, border_class, side_class = openpyxl_classes

        nomina_empleados = db.session.execute(db.select(NominaEmpleado).filter_by(nomina_id=nomina.id)).scalars().all()
        nomina_empleado_ids = [ne.id for ne in nomina_empleados if ne.id]

        detalles: list[NominaDetalle] = []
        if nomina_empleado_ids:
            detalles = list(
                db.session.execute(
                    db.select(NominaDetalle).where(NominaDetalle.nomina_empleado_id.in_(nomina_empleado_ids))
                )
                .scalars()
                .all()
            )

        ingresos_asociados = sorted(
            [
                assoc
                for assoc in cast(list[PlanillaIngreso], planilla.planilla_percepciones)
                if assoc.activo and assoc.percepcion
            ],
            key=lambda assoc: (assoc.orden or 0, assoc.percepcion.nombre or assoc.percepcion.codigo or ""),
        )
        deducciones_asociadas = sorted(
            [
                assoc
                for assoc in cast(list[PlanillaDeduccion], planilla.planilla_deducciones)
                if assoc.activo and assoc.deduccion
            ],
            key=lambda assoc: (
                assoc.prioridad or 0,
                assoc.orden or 0,
                assoc.deduccion.nombre or assoc.deduccion.codigo or "",
            ),
        )
        prestaciones_asociadas = sorted(
            [
                assoc
                for assoc in cast(list[PlanillaPrestacion], planilla.planilla_prestaciones)
                if assoc.activo and assoc.prestacion
            ],
            key=lambda assoc: (assoc.orden or 0, assoc.prestacion.nombre or assoc.prestacion.codigo or ""),
        )

        ingresos_config_ids = {assoc.percepcion_id for assoc in ingresos_asociados if assoc.percepcion_id}
        deducciones_config_ids = {assoc.deduccion_id for assoc in deducciones_asociadas if assoc.deduccion_id}
        prestaciones_config_ids = {assoc.prestacion_id for assoc in prestaciones_asociadas if assoc.prestacion_id}

        ingresos_catalogo_by_ne: dict[str, dict[str, float]] = {}
        deducciones_catalogo_by_ne: dict[str, dict[str, float]] = {}
        prestaciones_catalogo_by_ne: dict[str, dict[str, float]] = {}
        ingresos_extra_by_ne: dict[str, dict[str, float]] = {}
        deducciones_extra_by_ne: dict[str, dict[str, float]] = {}
        prestaciones_extra_by_ne: dict[str, dict[str, float]] = {}
        ingresos_extra_labels: dict[str, tuple[str, str]] = {}
        deducciones_extra_labels: dict[str, tuple[str, str]] = {}
        prestaciones_extra_labels: dict[str, tuple[str, str]] = {}

        for detalle in detalles:
            ne_id = detalle.nomina_empleado_id
            monto = float(detalle.monto or 0)

            if detalle.tipo == TipoDetalle.INGRESO:
                if detalle.percepcion_id and detalle.percepcion_id in ingresos_config_ids:
                    bucket = ingresos_catalogo_by_ne.setdefault(ne_id, {})
                    bucket[detalle.percepcion_id] = bucket.get(detalle.percepcion_id, 0.0) + monto
                else:
                    extra_key = (
                        f"income:{detalle.percepcion_id or ''}:" f"{detalle.codigo or ''}:{detalle.descripcion or ''}"
                    )
                    bucket = ingresos_extra_by_ne.setdefault(ne_id, {})
                    bucket[extra_key] = bucket.get(extra_key, 0.0) + monto
                    ingresos_extra_labels.setdefault(extra_key, (detalle.descripcion or "", detalle.codigo or ""))
            elif detalle.tipo == TipoDetalle.DEDUCCION:
                if detalle.deduccion_id and detalle.deduccion_id in deducciones_config_ids:
                    bucket = deducciones_catalogo_by_ne.setdefault(ne_id, {})
                    bucket[detalle.deduccion_id] = bucket.get(detalle.deduccion_id, 0.0) + monto
                else:
                    extra_key = (
                        f"deduction:{detalle.deduccion_id or ''}:" f"{detalle.codigo or ''}:{detalle.descripcion or ''}"
                    )
                    bucket = deducciones_extra_by_ne.setdefault(ne_id, {})
                    bucket[extra_key] = bucket.get(extra_key, 0.0) + monto
                    deducciones_extra_labels.setdefault(extra_key, (detalle.descripcion or "", detalle.codigo or ""))
            elif detalle.tipo == TipoDetalle.PRESTACION:
                if detalle.prestacion_id and detalle.prestacion_id in prestaciones_config_ids:
                    bucket = prestaciones_catalogo_by_ne.setdefault(ne_id, {})
                    bucket[detalle.prestacion_id] = bucket.get(detalle.prestacion_id, 0.0) + monto
                else:
                    extra_key = (
                        f"benefit:{detalle.prestacion_id or ''}:" f"{detalle.codigo or ''}:{detalle.descripcion or ''}"
                    )
                    bucket = prestaciones_extra_by_ne.setdefault(ne_id, {})
                    bucket[extra_key] = bucket.get(extra_key, 0.0) + monto
                    prestaciones_extra_labels.setdefault(extra_key, (detalle.descripcion or "", detalle.codigo or ""))

        ingresos_cols: list[dict[str, str]] = []
        deducciones_cols: list[dict[str, str]] = []
        prestaciones_cols: list[dict[str, str]] = []

        ingreso_headers_seen: set[str] = set()
        deduccion_headers_seen: set[str] = set()
        prestacion_headers_seen: set[str] = set()
        reclasificacion_ids: set[str] = set()

        for assoc in ingresos_asociados:
            concept = assoc.percepcion
            if not concept:
                continue
            label = ExportService._unique_label(ingreso_headers_seen, concept.nombre, concept.codigo, "Ingreso")
            ingresos_cols.append({"type": "income_catalog", "id": concept.id, "header": label})
            if not concept.mostrar_como_ingreso_reportes:
                reclasificacion_ids.add(concept.id)

        for key, (desc, code) in sorted(
            ingresos_extra_labels.items(),
            key=lambda item: ((item[1][0] or item[1][1] or ""), item[0]),
        ):
            label = ExportService._unique_label(ingreso_headers_seen, desc, code, "Ingreso Extra")
            ingresos_cols.append({"type": "income_extra", "id": key, "header": f"{label} (Extra)"})

        for assoc in deducciones_asociadas:
            concept = assoc.deduccion
            if not concept:
                continue
            label = ExportService._unique_label(deduccion_headers_seen, concept.nombre, concept.codigo, "Deduccion")
            deducciones_cols.append({"type": "deduction_catalog", "id": concept.id, "header": label})

        for key, (desc, code) in sorted(
            deducciones_extra_labels.items(),
            key=lambda item: ((item[1][0] or item[1][1] or ""), item[0]),
        ):
            label = ExportService._unique_label(deduccion_headers_seen, desc, code, "Deduccion Extra")
            deducciones_cols.append({"type": "deduction_extra", "id": key, "header": f"{label} (Extra)"})

        for assoc in prestaciones_asociadas:
            concept = assoc.prestacion
            if not concept:
                continue
            label = ExportService._unique_label(prestacion_headers_seen, concept.nombre, concept.codigo, "Prestacion")
            prestaciones_cols.append({"type": "benefit_catalog", "id": concept.id, "header": label})

        for key, (desc, code) in sorted(
            prestaciones_extra_labels.items(),
            key=lambda item: ((item[1][0] or item[1][1] or ""), item[0]),
        ):
            label = ExportService._unique_label(prestacion_headers_seen, desc, code, "Prestacion Extra")
            prestaciones_cols.append({"type": "benefit_extra", "id": key, "header": f"{label} (Extra)"})

        vacation_liability_by_ne: dict[str, float] = {}
        show_vacation_liability = bool(
            planilla.vacation_policy_id and planilla.vacation_policy and planilla.vacation_policy.son_vacaciones_pagadas
        )

        comprobante = db.session.execute(
            db.select(ComprobanteContable).filter_by(nomina_id=nomina.id)
        ).scalar_one_or_none()
        if comprobante:
            vac_lines = (
                db.session.execute(
                    db.select(ComprobanteContableLinea).filter_by(
                        comprobante_id=comprobante.id,
                        tipo_concepto="vacation_liability",
                        tipo_debito_credito="credito",
                    )
                )
                .scalars()
                .all()
            )
            if vac_lines:
                show_vacation_liability = True
            for line in vac_lines:
                current = vacation_liability_by_ne.get(line.nomina_empleado_id, 0.0)
                vacation_liability_by_ne[line.nomina_empleado_id] = current + float(line.credito or 0)

        employee_cols = [
            {"type": "employee_code", "header": "Codigo"},
            {"type": "employee_full_name", "header": "Nombre Completo"},
            {"type": "employee_id", "header": "ID Personal"},
            {"type": "employee_ssn", "header": "ID Seguridad Social"},
            {"type": "employee_tax_id", "header": "ID Fiscal"},
            {"type": "employee_role", "header": "Cargo"},
        ]

        income_section_cols = [{"type": "gross_salary_adjusted", "header": "Salario Bruto"}]
        income_section_cols.extend(ingresos_cols)
        income_section_cols.append({"type": "income_total", "header": "Total Ingresos"})

        deduction_section_cols = list(deducciones_cols)
        deduction_section_cols.append({"type": "deduction_total", "header": "Total Deducciones"})

        payout_section_cols = [{"type": "net_salary", "header": "Salario Neto"}]

        benefit_section_cols = list(prestaciones_cols)
        if show_vacation_liability:
            benefit_section_cols.append({"type": "vacation_liability", "header": "Provision de Vacaciones"})
        benefit_section_cols.append({"type": "benefit_total", "header": "Total Prestaciones"})

        section_specs = [
            ("Informacion del Empleado", employee_cols),
            ("Ingresos", income_section_cols),
            ("Deducciones", deduction_section_cols),
            ("Total a Pagar", payout_section_cols),
            ("Prestaciones Laborales", benefit_section_cols),
        ]

        table_columns: list[dict[str, str]] = []
        section_ranges: list[tuple[str, int, int]] = []
        for index, (section_name, section_cols) in enumerate(section_specs):
            start_col = len(table_columns) + 1
            table_columns.extend(section_cols)
            end_col = len(table_columns)
            section_ranges.append((section_name, start_col, end_col))
            if index < len(section_specs) - 1:
                table_columns.append({"type": "separator", "header": ""})

        wb = workbook_class()
        ws = wb.active
        ws.title = "Nomina"

        title_font = font_class(bold=True, size=14, color="FFFFFF")
        title_fill = pattern_fill_class(start_color="2F5F93", end_color="2F5F93", fill_type="solid")
        section_font = font_class(bold=True, size=11, color="FFFFFF")
        section_fill = pattern_fill_class(start_color="305496", end_color="305496", fill_type="solid")
        subheader_font = font_class(bold=True, size=10)
        subheader_fill = pattern_fill_class(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        separator_fill = pattern_fill_class(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        border = border_class(
            left=side_class(style="thin"),
            right=side_class(style="thin"),
            top=side_class(style="thin"),
            bottom=side_class(style="thin"),
        )

        total_columns = len(table_columns) if table_columns else 1
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
        title_cell = ws["A1"]
        title_cell.value = f"NOMINA - {planilla.nombre}"
        title_cell.font = title_font
        title_cell.fill = title_fill
        title_cell.alignment = alignment_class(horizontal="center", vertical="center")

        row = 3
        ws[f"A{row}"] = "Empresa:"
        ws[f"B{row}"] = planilla.empresa.razon_social if planilla.empresa else "N/A"
        row += 1

        ws[f"A{row}"] = "ID Empresa:"
        ws[f"B{row}"] = planilla.empresa_id or "N/A"
        row += 1

        ws[f"A{row}"] = LABEL_PLANILLA_ID
        ws[f"B{row}"] = planilla.id or "N/A"
        row += 1

        ws[f"A{row}"] = LABEL_PLANILLA_STATUS
        ws[f"B{row}"] = planilla.estado_aprobacion or "N/A"
        row += 1

        ws[f"A{row}"] = "Periodo:"
        ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - " f"{nomina.periodo_fin.strftime('%d/%m/%Y')}"
        row += 1

        ws[f"A{row}"] = "Estado Nomina:"
        ws[f"B{row}"] = nomina.estado or "N/A"
        row += 2

        row = ExportService._add_traceability_section(ws, row, nomina)
        row += 1

        section_row = row
        header_row = row + 1
        data_start_row = header_row + 1

        for section_name, start_col, end_col in section_ranges:
            if start_col < end_col:
                ws.merge_cells(
                    start_row=section_row,
                    start_column=start_col,
                    end_row=section_row,
                    end_column=end_col,
                )
            section_cell = ws.cell(row=section_row, column=start_col, value=section_name)
            section_cell.font = section_font
            section_cell.fill = section_fill
            section_cell.alignment = alignment_class(horizontal="center", vertical="center")
            section_cell.border = border
            if start_col < end_col:
                for col_idx in range(start_col + 1, end_col + 1):
                    cell = ws.cell(row=section_row, column=col_idx)
                    cell.fill = section_fill
                    cell.border = border

        for col_idx, column in enumerate(table_columns, start=1):
            if column["type"] == "separator":
                sep_cell = ws.cell(row=section_row, column=col_idx, value="")
                sep_cell.fill = separator_fill
                sep_cell.border = border
                sep_header_cell = ws.cell(row=header_row, column=col_idx, value="")
                sep_header_cell.fill = separator_fill
                sep_header_cell.border = border
                continue

            header_cell = ws.cell(row=header_row, column=col_idx, value=column["header"])
            header_cell.font = subheader_font
            header_cell.fill = subheader_fill
            header_cell.alignment = alignment_class(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )
            header_cell.border = border

        for row_offset, ne in enumerate(nomina_empleados):
            current_row = data_start_row + row_offset
            empleado = ne.empleado

            reclasificacion_total = sum(
                ingresos_catalogo_by_ne.get(ne.id, {}).get(concept_id, 0.0) for concept_id in reclasificacion_ids
            )
            salario_bruto_visual = float(ne.salario_bruto or 0) - reclasificacion_total

            total_prestaciones = (
                sum(prestaciones_catalogo_by_ne.get(ne.id, {}).values())
                + sum(prestaciones_extra_by_ne.get(ne.id, {}).values())
                + (vacation_liability_by_ne.get(ne.id, 0.0) if show_vacation_liability else 0.0)
            )

            for col_idx, column in enumerate(table_columns, start=1):
                value: str | float = ""
                col_type = column["type"]

                if col_type == "separator":
                    cell = ws.cell(row=current_row, column=col_idx, value="")
                    cell.fill = separator_fill
                    cell.border = border
                    continue

                if col_type == "employee_code":
                    value = empleado.codigo_empleado
                elif col_type == "employee_full_name":
                    value = (
                        f"{empleado.primer_nombre} {empleado.segundo_nombre or ''} "
                        f"{empleado.primer_apellido} {empleado.segundo_apellido or ''}"
                    ).strip()
                elif col_type == "employee_id":
                    value = empleado.identificacion_personal or ""
                elif col_type == "employee_ssn":
                    value = empleado.id_seguridad_social or ""
                elif col_type == "employee_tax_id":
                    value = empleado.id_fiscal or ""
                elif col_type == "employee_role":
                    value = ne.cargo_snapshot or empleado.cargo or ""
                elif col_type == "gross_salary_adjusted":
                    value = salario_bruto_visual
                elif col_type == "income_total":
                    value = salario_bruto_visual + reclasificacion_total
                elif col_type == "deduction_total":
                    value = float(ne.total_deducciones or 0)
                elif col_type == "net_salary":
                    value = float(ne.salario_neto or 0)
                elif col_type == "benefit_total":
                    value = total_prestaciones
                elif col_type == "vacation_liability":
                    value = vacation_liability_by_ne.get(ne.id, 0.0)
                elif col_type == "income_catalog":
                    value = ingresos_catalogo_by_ne.get(ne.id, {}).get(column["id"], 0.0)
                elif col_type == "income_extra":
                    value = ingresos_extra_by_ne.get(ne.id, {}).get(column["id"], 0.0)
                elif col_type == "deduction_catalog":
                    value = deducciones_catalogo_by_ne.get(ne.id, {}).get(column["id"], 0.0)
                elif col_type == "deduction_extra":
                    value = deducciones_extra_by_ne.get(ne.id, {}).get(column["id"], 0.0)
                elif col_type == "benefit_catalog":
                    value = prestaciones_catalogo_by_ne.get(ne.id, {}).get(column["id"], 0.0)
                elif col_type == "benefit_extra":
                    value = prestaciones_extra_by_ne.get(ne.id, {}).get(column["id"], 0.0)

                cell = ws.cell(row=current_row, column=col_idx, value=value)
                cell.border = border
                if isinstance(value, (int, float)):
                    cell.number_format = "#,##0.00"

        for col_idx, column in enumerate(table_columns, start=1):
            col_letter = ExportService._excel_col(col_idx)
            if column["type"] == "separator":
                ws.column_dimensions[col_letter].width = 2.8
            elif column["type"] in {"employee_full_name", "employee_role"}:
                ws.column_dimensions[col_letter].width = 22
            else:
                ws.column_dimensions[col_letter].width = 16

        ws.freeze_panes = f"A{data_start_row}"

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"nomina_{planilla.nombre}_" f"{nomina.periodo_inicio.strftime('%Y%m%d')}_" f"{nomina.id[:8]}.xlsx"
        return output, filename

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
        ws.merge_cells(TITLE_MERGE_RANGE)
        title_cell = ws["A1"]
        title_cell.value = f"PRESTACIONES LABORALES - {planilla.nombre}"
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Nomina info
        row = ExportService._write_info_block(ws, 3, planilla, nomina)
        row += 1

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

        show_vacation_liability = bool(
            planilla.vacation_policy_id and planilla.vacation_policy and planilla.vacation_policy.son_vacaciones_pagadas
        )
        vacation_liability_by_ne: dict[str, float] = {}
        comprobante = db.session.execute(
            db.select(ComprobanteContable).filter_by(nomina_id=nomina.id)
        ).scalar_one_or_none()
        if comprobante:
            liability_lines = (
                db.session.execute(
                    db.select(ComprobanteContableLinea).filter_by(
                        comprobante_id=comprobante.id,
                        tipo_concepto="vacation_liability",
                        tipo_debito_credito="credito",
                    )
                )
                .scalars()
                .all()
            )
            if liability_lines:
                show_vacation_liability = True
            for line in liability_lines:
                current = vacation_liability_by_ne.get(line.nomina_empleado_id, 0.0)
                vacation_liability_by_ne[line.nomina_empleado_id] = current + float(line.credito or 0)

        if show_vacation_liability:
            headers.append("Provisión de Vacaciones")

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

            for col_idx, (codigo, _nombre) in enumerate(prestaciones_list, start=4):
                cell = ws.cell(row=row, column=col_idx, value=prestaciones_dict.get(codigo, 0.0))
                cell.border = border

            if show_vacation_liability:
                vac_col = 4 + len(prestaciones_list)
                vac_amount = vacation_liability_by_ne.get(ne.id, 0.0)
                vac_cell = ws.cell(row=row, column=vac_col, value=vac_amount)
                vac_cell.border = border

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

        ws.merge_cells(TITLE_MERGE_RANGE)
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
        ws.merge_cells(TITLE_MERGE_RANGE)
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

        ws[f"A{row}"] = LABEL_CONCEPT
        ws[f"B{row}"] = comprobante.concepto or ""
        row += 1

        ws[f"A{row}"] = LABEL_CALCULATION_DATE
        ws[f"B{row}"] = comprobante.fecha_calculo.strftime(DATE_FORMAT)
        row += 1

        ws[f"A{row}"] = "Período:"
        ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"
        row += 1

        ws[f"A{row}"] = LABEL_PLANILLA_ID
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
            ws[f"A{row}"] = LABEL_APPLIED_BY
            ws[f"B{row}"] = comprobante.aplicado_por
            row += 1

        if comprobante.fecha_aplicacion:
            ws[f"A{row}"] = "Fecha aplicación:"
            ws[f"B{row}"] = comprobante.fecha_aplicacion.strftime(DATETIME_FORMAT)
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
                ws[f"B{row}"] = comprobante.fecha_modificacion.strftime(DATETIME_FORMAT)
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

        ws[f"A{row}"] = LABEL_CONCEPT
        ws[f"B{row}"] = comprobante.concepto or ""
        row += 1

        ws[f"A{row}"] = LABEL_CALCULATION_DATE
        ws[f"B{row}"] = comprobante.fecha_calculo.strftime(DATE_FORMAT)
        row += 1

        ws[f"A{row}"] = "Período:"
        ws[f"B{row}"] = f"{nomina.periodo_inicio.strftime('%d/%m/%Y')} - {nomina.periodo_fin.strftime('%d/%m/%Y')}"
        row += 1

        ws[f"A{row}"] = LABEL_PLANILLA_ID
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
