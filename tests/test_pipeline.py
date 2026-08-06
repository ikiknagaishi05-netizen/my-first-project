"""生成した疑似出勤簿PDFを使ったOCR〜判定の結合テスト。"""

import shutil

import pytest

from attendance_import.classifier import classify_all
from attendance_import.config import Config
from attendance_import.ocr import extract_text_from_pdf
from attendance_import.parser import parse_pages

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None or shutil.which("pdftoppm") is None,
    reason="tesseract/poppler が未インストールの環境ではスキップ",
)


def test_end_to_end_with_sample_pdf(tmp_path):
    from scripts.generate_sample_pdf import generate

    pdf_path = tmp_path / "sample.pdf"
    generate(str(pdf_path))

    config = Config()
    pages = extract_text_from_pdf(str(pdf_path), lang=config.ocr_lang, dpi=config.dpi)
    records = parse_pages(pages)
    classified = classify_all(records, config)

    work_types = [r.work_type for r in classified]
    assert "出勤" in work_types
    assert "遅刻" in work_types
    assert "早退" in work_types
    assert "有給休暇" in work_types
    assert "欠勤" in work_types
