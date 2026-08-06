"""出勤簿PDF -> 勤務形態一覧(Excel/CSV) 変換のCLIエントリポイント。"""

from __future__ import annotations

import argparse
import sys

from .classifier import classify_all
from .config import Config
from .export import export_to_csv, export_to_excel
from .ocr import extract_text_from_pdf
from .parser import parse_pages


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="出勤簿PDF(スキャン画像)から勤務形態を自動判定してExcel/CSVに出力します。"
    )
    parser.add_argument("pdf_path", help="入力する出勤簿PDFのパス")
    parser.add_argument(
        "-o", "--output", default="attendance_result.xlsx", help="出力ファイルパス(.xlsx または .csv)"
    )
    parser.add_argument("--lang", default="jpn+eng", help="Tesseractの言語コード(既定: jpn+eng)")
    parser.add_argument("--dpi", type=int, default=300, help="PDFラスタライズ解像度(既定: 300)")
    parser.add_argument("--work-start", default="09:00", help="所定始業時刻(既定: 09:00)")
    parser.add_argument("--work-end", default="18:00", help="所定終業時刻(既定: 18:00)")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    config = Config(
        ocr_lang=args.lang,
        dpi=args.dpi,
        work_start=args.work_start,
        work_end=args.work_end,
    )

    print(f"[1/4] PDFを読み込みOCR中: {args.pdf_path}", file=sys.stderr)
    pages = extract_text_from_pdf(args.pdf_path, lang=config.ocr_lang, dpi=config.dpi)

    print("[2/4] OCR結果から出退勤データを抽出中...", file=sys.stderr)
    records = parse_pages(pages)
    print(f"  -> {len(records)}行を検出", file=sys.stderr)

    print("[3/4] 勤務形態を判定中...", file=sys.stderr)
    classified = classify_all(records, config)
    review_count = sum(1 for r in classified if r.needs_review)

    print(f"[4/4] 出力中: {args.output}", file=sys.stderr)
    if args.output.lower().endswith(".csv"):
        export_to_csv(classified, args.output)
    else:
        export_to_excel(classified, args.output)

    print(f"完了: {len(classified)}件中 {review_count}件が要確認です。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
