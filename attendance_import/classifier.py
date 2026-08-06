"""AttendanceRecordから「勤務形態」を判定する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .config import Config
from .parser import AttendanceRecord

UNKNOWN = "要確認"


@dataclass
class ClassifiedRecord:
    date: str | None
    clock_in: str | None
    clock_out: str | None
    note: str
    work_type: str
    needs_review: bool
    raw_line: str


def _to_minutes(hhmm: str) -> int:
    dt = datetime.strptime(hhmm, "%H:%M")
    return dt.hour * 60 + dt.minute


def classify(record: AttendanceRecord, config: Config) -> ClassifiedRecord:
    # 1. 備考欄のキーワードによる判定(有給・欠勤など)を優先する
    for work_type, keywords in config.keyword_rules.items():
        if any(keyword in record.note for keyword in keywords):
            return ClassifiedRecord(
                date=record.date,
                clock_in=record.clock_in,
                clock_out=record.clock_out,
                note=record.note,
                work_type=work_type,
                needs_review=False,
                raw_line=record.raw_line,
            )

    # 2. 出退勤時刻がどちらも読み取れない場合は自動判定不可
    if not record.clock_in and not record.clock_out:
        return ClassifiedRecord(
            date=record.date,
            clock_in=record.clock_in,
            clock_out=record.clock_out,
            note=record.note,
            work_type=UNKNOWN,
            needs_review=True,
            raw_line=record.raw_line,
        )

    # 3. 出退勤時刻から遅刻・早退・出勤を判定する
    work_start = _to_minutes(config.work_start) + config.late_grace_minutes
    work_end = _to_minutes(config.work_end) - config.early_leave_grace_minutes

    is_late = record.clock_in is not None and _to_minutes(record.clock_in) > work_start
    is_early = record.clock_out is not None and _to_minutes(record.clock_out) < work_end

    if is_late and is_early:
        work_type = "遅刻・早退"
    elif is_late:
        work_type = "遅刻"
    elif is_early:
        work_type = "早退"
    else:
        work_type = "出勤"

    # 出勤・退勤いずれか一方しか読み取れなかった場合は確認を促す
    needs_review = record.clock_in is None or record.clock_out is None

    return ClassifiedRecord(
        date=record.date,
        clock_in=record.clock_in,
        clock_out=record.clock_out,
        note=record.note,
        work_type=work_type,
        needs_review=needs_review,
        raw_line=record.raw_line,
    )


def classify_all(records: list[AttendanceRecord], config: Config) -> list[ClassifiedRecord]:
    return [classify(record, config) for record in records]
