"""OCRで得たテキスト行から、日付・出退勤時刻・備考を抽出する。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 8/3, 8-3, 8月3日 などに対応
DATE_RE = re.compile(r"(\d{1,2})\s*[/\-月]\s*(\d{1,2})\s*日?")
# 9:15, 9：15(全角コロン) などに対応
TIME_RE = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})")


@dataclass
class AttendanceRecord:
    date: str | None  # "MM/DD" 形式に正規化
    clock_in: str | None  # "HH:MM"
    clock_out: str | None  # "HH:MM"
    note: str  # 備考欄と思われる残りのテキスト
    raw_line: str  # 元のOCR行(目視確認用)


def _normalize_date(match: re.Match) -> str:
    month, day = match.groups()
    return f"{int(month):02d}/{int(day):02d}"


def _normalize_time(match: re.Match) -> str:
    hour, minute = match.groups()
    return f"{int(hour):02d}:{minute}"


def parse_line(line: str) -> AttendanceRecord | None:
    """1行のOCRテキストを解析する。日付が見つからない行はNoneを返す(行の欄外・ヘッダ等)。"""
    stripped = line.strip()
    if not stripped:
        return None

    date_match = DATE_RE.search(stripped)
    if not date_match:
        return None

    times = TIME_RE.findall(stripped)
    clock_in = f"{int(times[0][0]):02d}:{times[0][1]}" if len(times) >= 1 else None
    clock_out = f"{int(times[1][0]):02d}:{times[1][1]}" if len(times) >= 2 else None

    # 日付・時刻表記を取り除いた残りを備考として扱う
    note = DATE_RE.sub("", stripped)
    note = TIME_RE.sub("", note).strip(" \t-~〜、,")

    return AttendanceRecord(
        date=_normalize_date(date_match),
        clock_in=clock_in,
        clock_out=clock_out,
        note=note,
        raw_line=stripped,
    )


def parse_text(text: str) -> list[AttendanceRecord]:
    """OCRテキスト(複数行)をレコードのリストに変換する。"""
    records = []
    for line in text.splitlines():
        record = parse_line(line)
        if record is not None:
            records.append(record)
    return records


def parse_pages(pages: list[str]) -> list[AttendanceRecord]:
    """複数ページ分のOCRテキストをまとめて解析する。"""
    records: list[AttendanceRecord] = []
    for page_text in pages:
        records.extend(parse_text(page_text))
    return records
