"""判定結果をExcel/CSVに出力する。"""

from __future__ import annotations

import csv

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .classifier import ClassifiedRecord

HEADERS = ["日付", "出勤時刻", "退勤時刻", "勤務形態", "備考", "要確認", "OCR原文"]

REVIEW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")


def _row(record: ClassifiedRecord) -> list[str]:
    return [
        record.date or "",
        record.clock_in or "",
        record.clock_out or "",
        record.work_type,
        record.note,
        "要確認" if record.needs_review else "",
        record.raw_line,
    ]


def export_to_csv(records: list[ClassifiedRecord], out_path: str) -> None:
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for record in records:
            writer.writerow(_row(record))


def export_to_excel(records: list[ClassifiedRecord], out_path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "勤務形態"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for record in records:
        ws.append(_row(record))
        if record.needs_review:
            row_idx = ws.max_row
            for cell in ws[row_idx]:
                cell.fill = REVIEW_FILL

    for column_cells in ws.columns:
        length = max(len(str(cell.value)) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = max(10, length + 2)

    wb.save(out_path)
