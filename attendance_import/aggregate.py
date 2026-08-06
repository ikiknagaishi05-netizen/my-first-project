"""勤務形態一覧表から職員ごとの集計値を算出する。

兼務者(1人が複数職種の行を持つ)は、同じ日が複数行に現れるため、
出勤日数などの「日数」は日を集合として重複除去して数える。
一方「勤務時間」は職種ごとの按分なので全行を合算する。
"""

from __future__ import annotations

from dataclasses import dataclass

from .roster import (
    MARK_ABSENCE,
    MARK_NIGHT,
    MARK_PAID_LEAVE,
    MARK_PUBLIC_HOLIDAY,
    WEEKEND,
    Employee,
    Sheet,
)


@dataclass
class EmployeeSummary:
    name: str
    jobs: list[str]
    work_days: int          # 出勤日数(重複除去)
    holiday_work_days: int  # 休日出勤日数(土日に勤務)
    total_minutes: int      # 勤務時間合計(全職種合算)
    paid_leave_days: int    # 有給日数
    absence_days: int       # 欠勤日数
    night_shifts: int       # 夜勤回数
    public_holidays: int    # 公休日数

    @property
    def total_hhmm(self) -> str:
        return f"{self.total_minutes // 60}:{self.total_minutes % 60:02d}"


def summarize_employee(employee: Employee) -> EmployeeSummary:
    by_day = employee.cells_by_day()

    work_days = 0
    holiday_work_days = 0
    paid_leave_days = 0
    absence_days = 0
    public_holidays = 0
    total_minutes = 0
    night_shifts = 0

    for day, cells in by_day.items():
        # 日数系は「その日に1つでも該当があれば1日」と数える(兼務による二重計上を防ぐ)
        if any(c.is_working for c in cells):
            work_days += 1
            if cells[0].weekday in WEEKEND:
                holiday_work_days += 1
        if any(c.mark == MARK_PAID_LEAVE for c in cells):
            paid_leave_days += 1
        if any(c.mark == MARK_ABSENCE for c in cells):
            absence_days += 1
        if any(c.mark == MARK_PUBLIC_HOLIDAY for c in cells):
            public_holidays += 1

        # 時間と夜勤回数は職種ごとの実績なので全行合算
        for cell in cells:
            total_minutes += cell.minutes
            if cell.mark == MARK_NIGHT:
                night_shifts += 1

    return EmployeeSummary(
        name=employee.name,
        jobs=employee.jobs,
        work_days=work_days,
        holiday_work_days=holiday_work_days,
        total_minutes=total_minutes,
        paid_leave_days=paid_leave_days,
        absence_days=absence_days,
        night_shifts=night_shifts,
        public_holidays=public_holidays,
    )


def summarize_sheet(sheet: Sheet) -> dict[str, EmployeeSummary]:
    return {name: summarize_employee(emp) for name, emp in sheet.employees.items()}
