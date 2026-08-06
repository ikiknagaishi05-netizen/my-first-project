from attendance_import.classifier import classify
from attendance_import.config import Config
from attendance_import.parser import AttendanceRecord

CONFIG = Config()


def _record(date="08/03", clock_in=None, clock_out=None, note=""):
    return AttendanceRecord(date=date, clock_in=clock_in, clock_out=clock_out, note=note, raw_line="")


def test_normal_attendance():
    result = classify(_record(clock_in="08:55", clock_out="18:02"), CONFIG)
    assert result.work_type == "出勤"
    assert result.needs_review is False


def test_late_arrival():
    result = classify(_record(clock_in="09:20", clock_out="18:00"), CONFIG)
    assert result.work_type == "遅刻"


def test_early_leave():
    result = classify(_record(clock_in="09:00", clock_out="17:10"), CONFIG)
    assert result.work_type == "早退"


def test_late_and_early():
    result = classify(_record(clock_in="09:30", clock_out="17:00"), CONFIG)
    assert result.work_type == "遅刻・早退"


def test_paid_leave_keyword_overrides_times():
    result = classify(_record(note="有給"), CONFIG)
    assert result.work_type == "有給休暇"
    assert result.needs_review is False


def test_absence_keyword():
    result = classify(_record(note="欠勤"), CONFIG)
    assert result.work_type == "欠勤"


def test_no_data_needs_review():
    result = classify(_record(), CONFIG)
    assert result.work_type == "要確認"
    assert result.needs_review is True


def test_missing_clock_out_needs_review():
    result = classify(_record(clock_in="09:00"), CONFIG)
    assert result.needs_review is True
