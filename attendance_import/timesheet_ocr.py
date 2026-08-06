"""出勤簿兼申請書PDF(スキャン画像)から日ごとの記入内容をOCRで抽出する。

帳票の構造(調査済み):
  - 全ページが90度回転しているため、セルを切り出したあと rotate(-90) で正立させる
  - 罫線はOpenCVのモルフォロジー処理で検出できる(横線11本・縦線41本)
  - 横線が行(残業時間/労働時間/休憩時間/終了時間/開始時間/曜日/日付)の境界
  - 縦線のうち4本目〜36本目が日付1〜31の列境界

手書きページのOCR精度は高くないため、結果は「下書き」として扱い、
必ず原本と突き合わせて人が確認すること。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image

TIME_RE = re.compile(r"(\d{1,2})[:：](\d{2})")
TIME_WHITELIST = "0123456789:"

EXPECTED_HLINES = 11
MIN_VLINES = 36


@dataclass
class DayEntry:
    """出勤簿の1日分の記入内容(全てOCR生値と解釈値)。"""

    day: int
    start_raw: str = ""
    end_raw: str = ""
    break_raw: str = ""
    labor_raw: str = ""
    overtime_raw: str = ""

    start_minutes: int | None = None
    end_minutes: int | None = None
    break_minutes: int | None = None
    labor_minutes: int | None = None
    overtime_minutes: int | None = None

    @property
    def has_any_entry(self) -> bool:
        return any([self.start_raw, self.end_raw, self.labor_raw])

    @property
    def labor_or_derived(self) -> int | None:
        """労働時間セルが読めればそれを、読めなければ開始/終了/休憩から算出する。"""
        if self.labor_minutes is not None:
            return self.labor_minutes
        if self.start_minutes is not None and self.end_minutes is not None:
            span = self.end_minutes - self.start_minutes
            if span > 0:
                return span - (self.break_minutes or 0)
        return None


@dataclass
class PageResult:
    page: int
    days: list[DayEntry] = field(default_factory=list)
    comment_text: str = ""
    error: str | None = None

    @property
    def work_days(self) -> int:
        return sum(1 for d in self.days if d.has_any_entry)

    @property
    def total_labor_minutes(self) -> int:
        return sum(d.labor_or_derived or 0 for d in self.days)

    @property
    def total_overtime_minutes(self) -> int:
        return sum(d.overtime_minutes or 0 for d in self.days)

    @property
    def unreadable_days(self) -> list[int]:
        """記入があるのに労働時間を確定できなかった日(要確認)。"""
        return [d.day for d in self.days if d.has_any_entry and d.labor_or_derived is None]


def detect_grid(gray: np.ndarray) -> tuple[list[int], list[int]]:
    """罫線を検出して、横線・縦線の位置を返す。"""
    h, w = gray.shape
    bw = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)

    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 30, 1))
    horiz = cv2.dilate(cv2.erode(bw, horiz_kernel), horiz_kernel)

    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 30))
    vert = cv2.dilate(cv2.erode(bw, vert_kernel), vert_kernel)

    return _peaks((horiz > 0).sum(axis=1), w * 0.15), _peaks((vert > 0).sum(axis=0), h * 0.15)


def _peaks(profile: np.ndarray, min_value: float, gap: int = 8) -> list[int]:
    """しきい値を超える位置をクラスタリングして中心座標のリストにする。"""
    idxs = np.where(profile > min_value)[0]
    if len(idxs) == 0:
        return []
    clusters: list[list[int]] = []
    current = [int(idxs[0])]
    for x in idxs[1:]:
        if x - current[-1] <= gap:
            current.append(int(x))
        else:
            clusters.append(current)
            current = [int(x)]
    clusters.append(current)
    return [int(np.mean(c)) for c in clusters]


def parse_time_to_minutes(text: str) -> int | None:
    """OCR文字列を分に変換する。コロンが落ちた3〜4桁も救済する。"""
    match = TIME_RE.search(text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
    else:
        digits = re.sub(r"\D", "", text)
        if len(digits) == 3:
            hour, minute = int(digits[0]), int(digits[1:])
        elif len(digits) == 4:
            hour, minute = int(digits[:2]), int(digits[2:])
        else:
            return None
    if not (0 <= hour <= 47 and 0 <= minute < 60):
        return None
    return hour * 60 + minute


def ocr_cell(image: Image.Image, box: tuple[int, int, int, int], whitelist: str | None = None,
             lang: str = "eng", psm: int = 7, scale: int = 3) -> str:
    """セルを切り出し、正立させてOCRする。"""
    cell = image.crop(box).rotate(-90, expand=True)
    if cell.width < 5 or cell.height < 5:
        return ""
    cell = cell.resize((cell.width * scale, cell.height * scale), Image.LANCZOS)
    config = f"--psm {psm}"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"
    return pytesseract.image_to_string(cell, lang=lang, config=config).strip()


def extract_page(image_path: str, page_no: int) -> PageResult:
    """1ページ分の出勤簿を抽出する。"""
    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return PageResult(page=page_no, error=f"画像を読み込めません: {image_path}")

    hlines, vlines = detect_grid(gray)
    if len(hlines) != EXPECTED_HLINES or len(vlines) < MIN_VLINES:
        return PageResult(page=page_no, error=f"罫線検出に失敗 (横{len(hlines)}本/縦{len(vlines)}本)")

    image = Image.open(image_path)

    # 横線の間が各項目の帯になっている
    y_comment = (hlines[1], hlines[2])
    y_overtime = (hlines[2], hlines[3])
    y_labor = (hlines[3], hlines[4])
    y_break = (hlines[4], hlines[5])
    y_end = (hlines[5], hlines[6])
    y_start = (hlines[7], hlines[8])

    day_bounds = vlines[3:36]  # 33本 -> 32セル、先頭31セルが1〜31日
    result = PageResult(page=page_no)

    for i in range(31):
        x0, x1 = day_bounds[i], day_bounds[i + 1]
        entry = DayEntry(day=i + 1)
        entry.start_raw = ocr_cell(image, (x0, y_start[0], x1, y_start[1]), TIME_WHITELIST)
        entry.end_raw = ocr_cell(image, (x0, y_end[0], x1, y_end[1]), TIME_WHITELIST)
        entry.break_raw = ocr_cell(image, (x0, y_break[0], x1, y_break[1]), TIME_WHITELIST)
        entry.labor_raw = ocr_cell(image, (x0, y_labor[0], x1, y_labor[1]), TIME_WHITELIST)
        entry.overtime_raw = ocr_cell(image, (x0, y_overtime[0], x1, y_overtime[1]), TIME_WHITELIST)

        entry.start_minutes = parse_time_to_minutes(entry.start_raw)
        entry.end_minutes = parse_time_to_minutes(entry.end_raw)
        entry.break_minutes = parse_time_to_minutes(entry.break_raw)
        entry.labor_minutes = parse_time_to_minutes(entry.labor_raw)
        entry.overtime_minutes = parse_time_to_minutes(entry.overtime_raw)
        result.days.append(entry)

    # 備考欄(遅刻・早退・有給理由など)はまとめて日本語OCRする
    comment_box = (day_bounds[0], y_comment[0], day_bounds[-1], y_comment[1])
    result.comment_text = ocr_cell(image, comment_box, lang="jpn+eng", psm=6, scale=2)

    return result
