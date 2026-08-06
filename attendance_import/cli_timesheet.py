"""出勤簿PDF と 勤務形態一覧表Excel の集計・突合を行うCLI。

使い方:
    # Excelへの集計列追記だけ(OCR不要・高速・正確)
    python3 -m attendance_import.cli_timesheet --excel 一覧表.xlsx --out-excel 集計付き.xlsx

    # 出勤簿PDFのOCRも行って突合レポートを出す
    python3 -m attendance_import.cli_timesheet \
        --excel 一覧表.xlsx --pdf 出勤簿.pdf --names names.json \
        --out-excel 集計付き.xlsx --out-report 相違点レポート.xlsx
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from .aggregate import summarize_sheet
from .reconcile import compare_employees, compare_roster
from .report import annotate_workbook, write_reconcile_report
from .roster import load_workbook_sheets
from .timesheet_ocr import PageResult, extract_page


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--excel", required=True, help="勤務形態一覧表のxlsx")
    parser.add_argument("--pdf", help="出勤簿兼申請書のPDF(省略時はOCRを行わない)")
    parser.add_argument("--names", help="ページ番号->氏名 の対応JSON(出勤簿の氏名欄は手書きでOCRできないため)")
    parser.add_argument("--sheet", default=None, help="突合対象のシート名(既定: ブック内の最初の月次シート)")
    parser.add_argument("--out-excel", default="勤務形態一覧表_集計付き.xlsx", help="集計列を追記した出力先")
    parser.add_argument("--out-report", default="相違点レポート.xlsx", help="相違点レポートの出力先")
    parser.add_argument("--dpi", type=int, default=300, help="PDFのラスタライズ解像度")
    parser.add_argument("--pages", help="処理するページ範囲 (例: 1-5)")
    return parser


def _rasterize(pdf_path: str, out_dir: str, dpi: int, page_range: str | None) -> list[str]:
    """PDFをPNG化する。Popplerのインストールが不要なPyMuPDFを使用。"""
    import fitz  # PyMuPDF

    if page_range:
        first, _, last = page_range.partition("-")
        first_page, last_page = int(first), int(last or first)
    else:
        first_page, last_page = None, None

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    paths = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            if first_page and not (first_page <= i <= last_page):
                continue
            pix = page.get_pixmap(matrix=matrix)
            path = os.path.join(out_dir, f"page-{i:02d}.png")
            pix.save(path)
            paths.append(path)
    return sorted(paths)


def run(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    print(f"[1] Excel一覧表を読み込み: {args.excel}", file=sys.stderr)
    sheets = load_workbook_sheets(args.excel, only=args.sheet)
    if not sheets:
        print("月次シートが見つかりません", file=sys.stderr)
        return 1
    target = sheets[0]
    summaries = summarize_sheet(target)
    print(f"    対象シート: {target.title} / 職員 {len(summaries)}名", file=sys.stderr)

    print(f"[2] 集計列を追記して保存: {args.out_excel}", file=sys.stderr)
    counts = annotate_workbook(args.excel, args.out_excel)
    for title, n in counts.items():
        print(f"    {title}: {n}名分", file=sys.stderr)

    if not args.pdf:
        print("PDFが指定されていないため、突合はスキップしました。", file=sys.stderr)
        return 0

    if not args.names:
        print("--names (ページ->氏名のJSON) が必要です。出勤簿の氏名欄は手書きのためOCRできません。", file=sys.stderr)
        return 1

    with open(args.names, encoding="utf-8") as f:
        page_names = {int(k): v for k, v in json.load(f).items()}

    print(f"[3] 出勤簿PDFをOCR中: {args.pdf}", file=sys.stderr)
    pages: dict[int, PageResult] = {}
    with tempfile.TemporaryDirectory() as tmp:
        image_paths = _rasterize(args.pdf, tmp, args.dpi, args.pages)
        for idx, path in enumerate(image_paths, start=1):
            result = extract_page(path, idx)
            pages[idx] = result
            state = result.error or f"出勤{result.work_days}日 / 未確定{len(result.unreadable_days)}日"
            print(f"    p{idx:2d} {page_names.get(idx, '?'):8s} {state}", file=sys.stderr)

    print("[4] 突合中...", file=sys.stderr)
    roster_diff = compare_roster(list(summaries.keys()), page_names)
    employee_diffs = compare_employees(summaries, pages, page_names)

    print(f"[5] 相違点レポートを出力: {args.out_report}", file=sys.stderr)
    write_reconcile_report(args.out_report, roster_diff, employee_diffs, target.title)

    review = sum(1 for d in employee_diffs if d.needs_review)
    print(f"完了: {len(employee_diffs)}名中 {review}名が要確認です。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
