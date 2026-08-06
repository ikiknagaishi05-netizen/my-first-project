"""勤務形態の自動判定に使う設定値。

会社の就業規則に合わせて時刻・キーワードを調整してください。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Config:
    # OCRに使う言語(Tesseractの言語コード)。日本語+英数字。
    ocr_lang: str = "jpn+eng"
    # ラスタライズ解像度(高いほど精度は上がるが処理が遅くなる)
    dpi: int = 300

    # 所定就業時間
    work_start: str = "09:00"
    work_end: str = "18:00"
    # 遅刻・早退とみなすまでの猶予(分)
    late_grace_minutes: int = 0
    early_leave_grace_minutes: int = 0

    # 備考欄のキーワードから勤務形態を直接判定するルール。
    # key: 出力される勤務形態名, value: 一致させるキーワード群
    keyword_rules: dict = field(
        default_factory=lambda: {
            "有給休暇": ["有給", "有休", "年休"],
            "特別休暇": ["特別休暇", "特休"],
            "病気休暇": ["病欠", "病気休暇"],
            "午前休": ["午前休"],
            "午後休": ["午後休"],
            "休日出勤": ["休日出勤", "休出"],
            "欠勤": ["欠勤"],
        }
    )
