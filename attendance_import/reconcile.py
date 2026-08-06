"""Excel一覧表の集計と、出勤簿PDFのOCR下書きを突き合わせる。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .aggregate import EmployeeSummary
from .roster import normalize_name
from .timesheet_ocr import PageResult

# PDFの氏名表記 -> Excelの氏名表記(スキャン字形が紛らわしく、要目視確認のもの)
NAME_ALIASES = {
    "岡本大佑": "岡本大祐",
    "藤川敬子": "藤川敏子",
}


@dataclass
class RosterDiff:
    """名簿レベルの相違。"""

    missing_timesheets: list[str] = field(default_factory=list)   # Excelにあるが出勤簿PDFが無い
    unmatched_pages: list[tuple[int, str]] = field(default_factory=list)  # PDFにあるがExcelに無い
    name_variants: list[tuple[str, str]] = field(default_factory=list)    # 表記ゆれ(PDF, Excel)


@dataclass
class EmployeeDiff:
    """職員1名分の集計値の突合結果。"""

    name: str
    page: int | None
    excel_work_days: int | None
    pdf_work_days: int | None
    excel_minutes: int | None
    pdf_minutes: int | None
    pdf_overtime_minutes: int | None
    unreadable_days: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def work_day_diff(self) -> int | None:
        if self.excel_work_days is None or self.pdf_work_days is None:
            return None
        return self.pdf_work_days - self.excel_work_days

    @property
    def needs_review(self) -> bool:
        """OCRの読み残しがある、または日数が食い違う場合は要確認。"""
        if self.unreadable_days:
            return True
        diff = self.work_day_diff
        return diff is not None and diff != 0


def resolve_name(pdf_name: str) -> str:
    """PDF側の氏名をExcel側の表記に寄せる。"""
    normalized = normalize_name(pdf_name)
    return NAME_ALIASES.get(normalized, normalized)


def compare_roster(excel_names: list[str], page_names: dict[int, str]) -> RosterDiff:
    """名簿を突き合わせる。"""
    diff = RosterDiff()
    excel_set = {normalize_name(n) for n in excel_names}
    resolved = {page: resolve_name(name) for page, name in page_names.items()}

    for page, name in sorted(resolved.items()):
        if name not in excel_set:
            diff.unmatched_pages.append((page, page_names[page]))

    covered = set(resolved.values())
    diff.missing_timesheets = sorted(excel_set - covered)

    for pdf_name, excel_name in NAME_ALIASES.items():
        if pdf_name in {normalize_name(n) for n in page_names.values()} and excel_name in excel_set:
            diff.name_variants.append((pdf_name, excel_name))

    return diff


def compare_employees(
    summaries: dict[str, EmployeeSummary],
    pages: dict[int, PageResult],
    page_names: dict[int, str],
) -> list[EmployeeDiff]:
    """職員ごとに Excel集計 と PDF OCR を突き合わせる。"""
    diffs: list[EmployeeDiff] = []
    matched_names = set()

    for page in sorted(page_names):
        pdf_name = page_names[page]
        name = resolve_name(pdf_name)
        matched_names.add(name)
        summary = summaries.get(name)
        result = pages.get(page)

        entry = EmployeeDiff(
            name=name,
            page=page,
            excel_work_days=summary.work_days if summary else None,
            pdf_work_days=result.work_days if result and not result.error else None,
            excel_minutes=summary.total_minutes if summary else None,
            pdf_minutes=result.total_labor_minutes if result and not result.error else None,
            pdf_overtime_minutes=result.total_overtime_minutes if result and not result.error else None,
            unreadable_days=result.unreadable_days if result and not result.error else [],
        )
        if summary is None:
            entry.notes.append("Excel一覧表に該当する氏名がありません")
        if result is None:
            entry.notes.append("PDFの抽出結果がありません")
        elif result.error:
            entry.notes.append(f"PDF抽出エラー: {result.error}")
        if pdf_name != name:
            entry.notes.append(f"PDF表記「{pdf_name}」/ Excel表記「{name}」(要目視確認)")
        diffs.append(entry)

    for name, summary in sorted(summaries.items()):
        if name in matched_names:
            continue
        diffs.append(
            EmployeeDiff(
                name=name,
                page=None,
                excel_work_days=summary.work_days,
                pdf_work_days=None,
                excel_minutes=summary.total_minutes,
                pdf_minutes=None,
                pdf_overtime_minutes=None,
                notes=["出勤簿PDFが見当たりません(提出漏れの可能性)"],
            )
        )

    return diffs
