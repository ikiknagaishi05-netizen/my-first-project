import datetime

from attendance_import.aggregate import summarize_employee
from attendance_import.roster import DayCell, Employee, EmployeeRow


def make_row(row_no, job, name, values):
    """values: {day: value}"""
    cells = [DayCell(day=d, weekday="水", value=v) for d, v in values.items()]
    return EmployeeRow(row=row_no, job=job, work_class="B", name=name, cells=cells)


def test_concurrent_jobs_do_not_double_count_days():
    # 溝口昌子の実データを模した兼務ケース: 管理者(row7)と機能訓練員(row8)で
    # 一部の日が両方に記入されている(重複)。
    shared_day = {1: datetime.time(8, 0)}
    row7 = make_row(7, "管理者", "溝口昌子", {1: datetime.time(1, 0), 2: datetime.time(8, 0)})
    row8 = make_row(8, "機能訓練員", "溝口昌子", {1: datetime.time(7, 0)})  # 同じ1日を按分
    employee = Employee(name="溝口昌子", rows=[row7, row8])

    summary = summarize_employee(employee)

    assert summary.work_days == 2  # 日1と日2の2日、重複除去済み
    assert summary.total_minutes == 60 + 480 + 420  # 時間は全行合算


def test_non_concurrent_employee_counts_normally():
    row = make_row(9, "生活相談員", "松本一慶", {1: datetime.time(8, 0), 2: datetime.time(8, 0)})
    employee = Employee(name="松本一慶", rows=[row])

    summary = summarize_employee(employee)

    assert summary.work_days == 2
    assert summary.total_minutes == 960


def test_paid_leave_and_absence_counted_once_per_day():
    row1 = make_row(11, "生活相談員", "中山三保", {1: "有", 2: datetime.time(8, 0)})
    row2 = make_row(12, "介護職員", "中山三保", {1: "有"})
    employee = Employee(name="中山三保", rows=[row1, row2])

    summary = summarize_employee(employee)

    assert summary.paid_leave_days == 1
    assert summary.work_days == 1  # 日2のみ


def test_holiday_work_detected_from_weekend_weekday():
    cells = [
        DayCell(day=1, weekday="土", value=datetime.time(8, 0)),
        DayCell(day=2, weekday="日", value=None),
        DayCell(day=3, weekday="月", value=datetime.time(8, 0)),
    ]
    row = EmployeeRow(row=20, job="介護職員", work_class="B", name="テスト太郎", cells=cells)
    employee = Employee(name="テスト太郎", rows=[row])

    summary = summarize_employee(employee)

    assert summary.work_days == 2
    assert summary.holiday_work_days == 1  # 土曜のみ勤務あり


def test_night_shift_and_public_holiday_marks():
    cells = [
        DayCell(day=1, weekday="水", value="夜"),
        DayCell(day=2, weekday="木", value="明"),
        DayCell(day=3, weekday="金", value="公"),
    ]
    row = EmployeeRow(row=21, job="介護職員", work_class="B", name="テスト花子", cells=cells)
    employee = Employee(name="テスト花子", rows=[row])

    summary = summarize_employee(employee)

    assert summary.night_shifts == 1
    assert summary.work_days == 2  # 夜勤+明けは出勤扱い、公休は出勤に含めない
    assert summary.public_holidays == 1
