"""「従業者の勤務の体制及び勤務形態一覧表」Excelの読み取り。

シート構造(調査済み):
  5行目 D..AH : 日付(1〜31、月により末日が異なる)
  6行目 D..AH : 曜日(月火水木金土日)
  7行目以降   : A=職種, B=勤務区分, C=氏名, D..AH=日ごとの勤務
  AI列        : 合計時間数(=SUM(D:AH)の数式)
  AJ列        : 週平均勤務時間数
  AK列        : 資格等
  AL..AS列    : 「チェック」欄(結合セル + 手書き相当のメモ)

日ごとのセルの値:
  datetime.time -> その日の勤務時間
  "公" -> 公休 / "有" -> 有給 / "欠" -> 欠勤 / "夜" -> 夜勤 / "明" -> 明け
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

DAY_COL_START = 4   # D列
DAY_COL_END = 34    # AH列
DATE_ROW = 5
WEEKDAY_ROW = 6
FIRST_EMPLOYEE_ROW = 7
NAME_COL = 3        # C列
JOB_COL = 1         # A列
CLASS_COL = 2       # B列

# 日次セルに入りうる記号
MARK_PUBLIC_HOLIDAY = "公"
MARK_PAID_LEAVE = "有"
MARK_ABSENCE = "欠"
MARK_NIGHT = "夜"
MARK_AFTER_NIGHT = "明"

WEEKEND = ("土", "日")


def normalize_name(name: str) -> str:
    """氏名の表記ゆれ(全角スペース・前後空白)を吸収する。"""
    return name.replace("　", "").replace(" ", "").strip()


@dataclass
class DayCell:
    """1人・1日分のセル。"""

    day: int
    weekday: str
    value: object

    @property
    def worked_time(self) -> datetime.time | None:
        return self.value if isinstance(self.value, datetime.time) else None

    @property
    def mark(self) -> str | None:
        return self.value.strip() if isinstance(self.value, str) and self.value.strip() else None

    @property
    def is_working(self) -> bool:
        """出勤とみなすか(実働時間が入っている、または夜勤/明け)。"""
        if self.worked_time is not None:
            return True
        return self.mark in (MARK_NIGHT, MARK_AFTER_NIGHT)

    @property
    def minutes(self) -> int:
        t = self.worked_time
        return t.hour * 60 + t.minute if t else 0


@dataclass
class EmployeeRow:
    """一覧表の1行(同じ人が複数職種を兼務すると複数行になる)。"""

    row: int
    job: str | None
    work_class: str | None
    name: str
    cells: list[DayCell] = field(default_factory=list)


@dataclass
class Employee:
    """氏名でまとめた職員(兼務者は複数のEmployeeRowを持つ)。"""

    name: str
    rows: list[EmployeeRow] = field(default_factory=list)

    @property
    def jobs(self) -> list[str]:
        return [r.job for r in self.rows if r.job]

    def cells_by_day(self) -> dict[int, list[DayCell]]:
        """日 -> その日の全行分のセル。兼務者の重複除去に使う。"""
        by_day: dict[int, list[DayCell]] = {}
        for row in self.rows:
            for cell in row.cells:
                by_day.setdefault(cell.day, []).append(cell)
        return by_day


@dataclass
class Sheet:
    """1か月分のシート。"""

    title: str
    days: list[int]
    weekdays: dict[int, str]
    employees: dict[str, Employee]


def _last_employee_row(ws) -> int:
    """氏名欄が埋まっている最終行を返す(合計行「介護職員計」の手前まで)。"""
    last = FIRST_EMPLOYEE_ROW
    for row in range(FIRST_EMPLOYEE_ROW, ws.max_row + 1):
        label = ws.cell(row=row, column=JOB_COL).value
        if isinstance(label, str) and "計" in label and not ws.cell(row=row, column=NAME_COL).value:
            break
        if ws.cell(row=row, column=NAME_COL).value:
            last = row
    return last


def load_sheet(ws) -> Sheet:
    """1シートを読み取ってSheetを返す。"""
    days: list[int] = []
    weekdays: dict[int, str] = {}
    day_columns: dict[int, int] = {}

    for col in range(DAY_COL_START, DAY_COL_END + 1):
        day = ws.cell(row=DATE_ROW, column=col).value
        if not isinstance(day, int):
            continue
        days.append(day)
        day_columns[day] = col
        weekday = ws.cell(row=WEEKDAY_ROW, column=col).value
        weekdays[day] = weekday.strip() if isinstance(weekday, str) else ""

    employees: dict[str, Employee] = {}
    for row in range(FIRST_EMPLOYEE_ROW, _last_employee_row(ws) + 1):
        raw_name = ws.cell(row=row, column=NAME_COL).value
        if not raw_name or not isinstance(raw_name, str):
            continue
        name = normalize_name(raw_name)
        if not name or name == "＊":
            continue

        job = ws.cell(row=row, column=JOB_COL).value
        work_class = ws.cell(row=row, column=CLASS_COL).value
        employee_row = EmployeeRow(
            row=row,
            job=job.replace("\n", "/") if isinstance(job, str) else None,
            work_class=work_class.strip() if isinstance(work_class, str) else None,
            name=name,
        )
        for day in days:
            employee_row.cells.append(
                DayCell(day=day, weekday=weekdays[day], value=ws.cell(row=row, column=day_columns[day]).value)
            )

        employees.setdefault(name, Employee(name=name)).rows.append(employee_row)

    return Sheet(title=ws.title, days=days, weekdays=weekdays, employees=employees)


def load_workbook_sheets(path: str, only: str | None = None) -> list[Sheet]:
    """ブック内の月次シートを全て読み取る。"""
    import openpyxl

    wb = openpyxl.load_workbook(path)
    sheets = []
    for title in wb.sheetnames:
        if only and title != only:
            continue
        if "令和" not in title:
            continue
        sheets.append(load_sheet(wb[title]))
    return sheets
