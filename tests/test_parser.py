from attendance_import.parser import parse_line, parse_text


def test_parse_line_with_both_times():
    record = parse_line("8/3    8:55 18:02")
    assert record.date == "08/03"
    assert record.clock_in == "08:55"
    assert record.clock_out == "18:02"
    assert record.note == ""


def test_parse_line_with_note_only():
    record = parse_line("8/6                         有給")
    assert record.date == "08/06"
    assert record.clock_in is None
    assert record.clock_out is None
    assert record.note == "有給"


def test_parse_line_without_date_is_ignored():
    assert parse_line("日付      出勤      退勤      備考") is None
    assert parse_line("") is None


def test_parse_text_multiple_lines():
    text = "8/3    8:55 18:02\n8/4    9:20 18:00\n"
    records = parse_text(text)
    assert len(records) == 2
    assert records[0].date == "08/03"
    assert records[1].date == "08/04"
