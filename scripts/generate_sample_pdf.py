"""動作確認用の出勤簿サンプルPDFを生成する。

実際の手書き・スキャンPDFではなく、印字体で疑似的な出勤簿を作成し、
OCR〜Excel出力までの一連のパイプラインを検証するためのもの。
"""

from __future__ import annotations

import sys

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"

# (日付, 出勤時刻, 退勤時刻, 備考)
SAMPLE_ROWS = [
    ("8/3", "8:55", "18:02", ""),
    ("8/4", "9:20", "18:00", ""),  # 遅刻
    ("8/5", "9:00", "17:10", ""),  # 早退
    ("8/6", "", "", "有給"),
    ("8/7", "", "", "欠勤"),
]


def generate(out_path: str) -> None:
    width, height = 1240, 1754  # A4相当(150dpi程度)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    title_font = ImageFont.truetype(FONT_PATH, 40)
    row_font = ImageFont.truetype(FONT_PATH, 32)

    draw.text((60, 60), "出勤簿サンプル 2026年8月", font=title_font, fill="black")

    y = 160
    draw.text((60, y), "日付      出勤      退勤      備考", font=row_font, fill="black")
    y += 60
    for date, clock_in, clock_out, note in SAMPLE_ROWS:
        line = f"{date}   {clock_in:>5}   {clock_out:>5}   {note}"
        draw.text((60, y), line, font=row_font, fill="black")
        y += 55

    image.save(out_path, "PDF", resolution=150.0)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "samples/sample_attendance.pdf"
    generate(out)
    print(f"generated: {out}")
