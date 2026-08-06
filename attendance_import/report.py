"""集計結果のExcel書き込みと、相違点レポートの出力。

一覧表への書き込みは AU列以降の新規列に対して行う。
既存の AI/AJ列(数式)、AK列(資格等)、AL:AS列(「チェック」欄の結合セルとメモ)は
一切変更しない。
"""

from __future__ import annotations

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from .aggregate import EmployeeSummary, summarize_sheet
from .reconcile import EmployeeDiff, RosterDiff
from .roster import FIRST_EMPLOYEE_ROW, NAME_COL, load_sheet, normalize_name

# 追記する集計列(AU列=47 から右へ)
SUMMARY_COLUMNS = [
    ("出勤日数", "work_days"),
    ("休日出勤", "holiday_work_days"),
    ("勤務時間計", "total_hhmm"),
    ("有給日数", "paid_leave_days"),
    ("欠勤日数", "absence_days"),
    ("夜勤回数", "night_shifts"),
    ("公休日数", "public_holidays"),
]
SUMMARY_START_COL = 47  # AU列
HEADER_ROW = 6

THIN = Side(style="thin")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")
REVIEW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
DIFF_FILL = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")


def write_summary_columns(ws, summaries: dict[str, EmployeeSummary]) -> int:
    """シートのAU列以降に集計値を書き込む。書き込んだ行数を返す。

    兼務者は複数行あるため、集計値は各人の先頭行にのみ書き込み、
    2行目以降は空欄にして二重計上に見えないようにする。
    """
    for offset, (label, _) in enumerate(SUMMARY_COLUMNS):
        cell = ws.cell(row=HEADER_ROW, column=SUMMARY_START_COL + offset, value=label)
        cell.font = Font(bold=True)
        cell.border = BORDER
        cell.alignment = CENTER

    written = 0
    seen: set[str] = set()
    for row in range(FIRST_EMPLOYEE_ROW, ws.max_row + 1):
        raw_name = ws.cell(row=row, column=NAME_COL).value
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        name = normalize_name(raw_name)
        summary = summaries.get(name)
        if summary is None or name in seen:
            continue
        seen.add(name)

        for offset, (_, attr) in enumerate(SUMMARY_COLUMNS):
            cell = ws.cell(row=row, column=SUMMARY_START_COL + offset, value=getattr(summary, attr))
            cell.border = BORDER
            cell.alignment = CENTER
        written += 1

    for offset in range(len(SUMMARY_COLUMNS)):
        letter = ws.cell(row=HEADER_ROW, column=SUMMARY_START_COL + offset).column_letter
        ws.column_dimensions[letter].width = 11

    return written


def annotate_workbook(src_path: str, dst_path: str) -> dict[str, int]:
    """ブック内の全月次シートに集計列を追記して保存する。"""
    wb = openpyxl.load_workbook(src_path)
    counts = {}
    for title in wb.sheetnames:
        if "令和" not in title:
            continue
        ws = wb[title]
        summaries = summarize_sheet(load_sheet(ws))
        counts[title] = write_summary_columns(ws, summaries)
    wb.save(dst_path)
    return counts


def write_reconcile_report(
    path: str,
    roster_diff: RosterDiff,
    employee_diffs: list[EmployeeDiff],
    sheet_title: str,
) -> None:
    """相違点レポートを新規ブックとして書き出す。"""
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "名簿相違"
    ws.append([f"対象シート: {sheet_title}"])
    ws.append([])
    ws.append(["区分", "内容", "対応"])
    for cell in ws[3]:
        cell.font = Font(bold=True)

    for name in roster_diff.missing_timesheets:
        ws.append(["出勤簿PDF未提出", name, "提出漏れか別ファイルでの提出かを確認してください"])
    for page, name in roster_diff.unmatched_pages:
        ws.append([f"Excel名簿に無い(PDF {page}ページ)", name, "氏名の確認、または一覧表への追加が必要です"])
    for pdf_name, excel_name in roster_diff.name_variants:
        ws.append(["氏名の表記ゆれ", f"PDF「{pdf_name}」 / Excel「{excel_name}」", "原本で正しい表記を確認してください"])
    if ws.max_row == 3:
        ws.append(["相違なし", "", ""])

    ws2 = wb.create_sheet("日数・時間の突合")
    headers = [
        "氏名", "PDFページ", "Excel出勤日数", "PDF出勤日数(OCR)", "差",
        "Excel勤務時間", "PDF労働時間(OCR)", "PDF残業時間(OCR)", "OCR未確定の日", "備考",
    ]
    ws2.append(headers)
    for cell in ws2[1]:
        cell.font = Font(bold=True)
        cell.alignment = CENTER

    for diff in employee_diffs:
        ws2.append([
            diff.name,
            diff.page if diff.page else "",
            diff.excel_work_days if diff.excel_work_days is not None else "",
            diff.pdf_work_days if diff.pdf_work_days is not None else "",
            diff.work_day_diff if diff.work_day_diff is not None else "",
            _hhmm(diff.excel_minutes),
            _hhmm(diff.pdf_minutes),
            _hhmm(diff.pdf_overtime_minutes),
            ", ".join(str(d) for d in diff.unreadable_days),
            " / ".join(diff.notes),
        ])
        if diff.needs_review:
            fill = DIFF_FILL if diff.work_day_diff not in (None, 0) else REVIEW_FILL
            for cell in ws2[ws2.max_row]:
                cell.fill = fill

    for column_cells in ws2.columns:
        length = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
        ws2.column_dimensions[column_cells[0].column_letter].width = min(40, max(10, length + 2))

    ws3 = wb.create_sheet("注意事項")
    for line in [
        "このレポートの読み方",
        "",
        "1. 「Excel出勤日数」は勤務形態一覧表の日次セルから算出した値です。OCRを使っていないため正確です。",
        "   兼務者(1人が複数職種の行を持つ場合)は、同じ日を二重に数えないよう重複除去しています。",
        "",
        "2. 「PDF出勤日数(OCR)」は手書きの出勤簿を文字認識した下書きです。",
        "   特に手書きページでは読み取れないセルが多く、実際より少なく出る傾向があります。",
        "   数値が食い違う場合、多くはOCRの読み落としであり、必ず原本を確認してください。",
        "",
        "3. 赤色の行は出勤日数が食い違う行、黄色の行はOCRが読み切れなかったセルがある行です。",
        "",
        "4. 給与や指定申請に関わる書類です。この集計結果をそのまま提出せず、必ず人の目で確認してください。",
    ]:
        ws3.append([line])
    ws3.column_dimensions["A"].width = 100

    wb.save(path)


def _hhmm(minutes: int | None) -> str:
    if minutes is None:
        return ""
    return f"{minutes // 60}:{minutes % 60:02d}"
