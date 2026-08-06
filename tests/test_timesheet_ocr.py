from attendance_import.timesheet_ocr import DayEntry, parse_time_to_minutes


def test_parse_time_with_colon():
    assert parse_time_to_minutes("8:30") == 510
    assert parse_time_to_minutes("17:30") == 1050


def test_parse_time_missing_colon_three_digits():
    assert parse_time_to_minutes("830") == 510


def test_parse_time_missing_colon_four_digits():
    assert parse_time_to_minutes("1730") == 1050


def test_parse_time_unreadable_returns_none():
    assert parse_time_to_minutes("") is None
    assert parse_time_to_minutes("abc") is None


def test_day_entry_prefers_labor_cell_when_available():
    entry = DayEntry(day=1, labor_minutes=480, start_minutes=510, end_minutes=1050, break_minutes=60)
    assert entry.labor_or_derived == 480


def test_day_entry_derives_from_start_end_break_when_labor_missing():
    entry = DayEntry(day=1, start_minutes=510, end_minutes=1050, break_minutes=60)
    assert entry.labor_or_derived == 1050 - 510 - 60


def test_day_entry_has_any_entry():
    assert DayEntry(day=1, start_raw="8:30").has_any_entry
    assert not DayEntry(day=1).has_any_entry
