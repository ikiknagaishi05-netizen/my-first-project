"""複数事業所の出勤簿PDF確認・勤務形態一覧表作成を支援するアプリ。

毎月の作業手順:
  1. 事業所を選ぶ(初めての事業所は名前を登録)
  2. その事業所の「勤務形態一覧表」Excelをアップロード
  3. その事業所の「出勤簿兼申請書」PDFをアップロード
  4. 各ページの氏名を確認(自動候補+手直し)
  5. 実行ボタンで集計・突合し、結果をダウンロード

起動方法:
    streamlit run app.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import streamlit as st

from attendance_import.aggregate import summarize_sheet
from attendance_import.ocr_setup import configure_tesseract
from attendance_import.reconcile import compare_employees, compare_roster, resolve_name
from attendance_import.report import annotate_workbook, write_reconcile_report
from attendance_import.roster import load_workbook_sheets
from attendance_import.timesheet_ocr import extract_page

FACILITIES_FILE = Path(__file__).parent / "facilities.json"

tesseract_error = configure_tesseract()

st.set_page_config(page_title="出勤簿・勤務形態一覧表 作成支援", layout="wide")


def load_facilities() -> dict:
    if FACILITIES_FILE.exists():
        return json.loads(FACILITIES_FILE.read_text(encoding="utf-8"))
    return {}


def save_facilities(data: dict) -> None:
    FACILITIES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rasterize_pdf(pdf_bytes: bytes, out_dir: Path, dpi: int = 300) -> list[Path]:
    """PDFの各ページをPNG化する。Popplerのインストールが不要なPyMuPDFを使用。"""
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    paths = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix)
        path = out_dir / f"page-{i:02d}.png"
        pix.save(str(path))
        paths.append(path)
    return paths


def guess_page_name(image_path: Path) -> str:
    """氏名欄をOCRして候補を出す(手書きのため精度は低い。人の確認が前提)。"""
    from PIL import Image
    import pytesseract

    img = Image.open(image_path)
    w, h = img.size
    crop = img.crop((0, 143, min(522, w), min(933, h))).rotate(-90, expand=True)
    text = pytesseract.image_to_string(crop, lang="jpn", config="--psm 6").strip()
    for line in text.splitlines():
        line = line.strip()
        if 2 <= len(line) <= 10 and not any(ch.isascii() and ch.isalnum() for ch in line):
            return line
    return ""


st.title("出勤簿・勤務形態一覧表 作成支援")
st.caption("毎月の複数事業所分の出勤簿確認と勤務形態一覧表への集計をまとめて行います。")

if tesseract_error:
    st.error(
        "文字認識ソフト(Tesseract OCR)が見つかりません。\n\n"
        + tesseract_error
        + "\n\nインストール後、このアプリを再起動(ウィンドウを閉じてstart.batを再実行)してください。\n"
        "※Excelへの集計だけならOCRは不要なので、PDFをアップロードしなければこのまま使えます。"
    )

facilities = load_facilities()

with st.sidebar:
    st.header("事業所")
    facility_names = list(facilities.keys())
    choice = st.selectbox("事業所を選択", ["(新規登録)"] + facility_names)
    if choice == "(新規登録)":
        new_name = st.text_input("事業所名を入力")
        if st.button("登録") and new_name:
            facilities[new_name] = {}
            save_facilities(facilities)
            st.success(f"「{new_name}」を登録しました。再読み込みしてください。")
        facility = None
    else:
        facility = choice
        if st.button(f"「{facility}」を削除"):
            del facilities[facility]
            save_facilities(facilities)
            st.rerun()

if not facility:
    st.info("左のサイドバーで事業所を選択、または新規登録してください。")
    st.stop()

st.subheader(f"事業所: {facility}")

col1, col2 = st.columns(2)
with col1:
    excel_file = st.file_uploader("勤務形態一覧表 Excel", type=["xlsx"], key="excel")
with col2:
    pdf_file = st.file_uploader("出勤簿兼申請書 PDF", type=["pdf"], key="pdf")

if not excel_file:
    st.stop()

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    excel_path = tmp_path / "roster.xlsx"
    excel_path.write_bytes(excel_file.getvalue())

    sheets = load_workbook_sheets(str(excel_path))
    if not sheets:
        st.error("Excelから月次シートを読み取れませんでした(シート名に「令和」等の元号が含まれている必要があります)。")
        st.stop()

    sheet_names = [s.title for s in sheets]
    sheet_title = st.selectbox("突合対象のシート(月)", sheet_names)
    target_sheet = next(s for s in sheets if s.title == sheet_title)
    summaries = summarize_sheet(target_sheet)

    st.markdown(f"**{sheet_title}**: 職員 {len(summaries)}名")

    with st.expander("Excel集計プレビュー", expanded=False):
        st.dataframe(
            [
                {
                    "氏名": s.name,
                    "職種": " / ".join(s.jobs),
                    "出勤日数": s.work_days,
                    "休日出勤": s.holiday_work_days,
                    "勤務時間": s.total_hhmm,
                    "有給": s.paid_leave_days,
                    "欠勤": s.absence_days,
                    "夜勤": s.night_shifts,
                }
                for s in summaries.values()
            ],
            use_container_width=True,
        )

    page_names: dict[int, str] = {}
    image_paths: list[Path] = []

    if pdf_file:
        pdf_dir = tmp_path / "pages"
        pdf_dir.mkdir()
        with st.spinner("PDFを画像化しています..."):
            image_paths = rasterize_pdf(pdf_file.getvalue(), pdf_dir)
        st.success(f"{len(image_paths)}ページを読み込みました。")

        st.markdown("### ページごとの氏名を確認してください")
        st.caption("氏名は手書きのため自動認識できないことがあります。誤りは手直しできます。")

        cache_key = f"names_{facility}_{sheet_title}_{len(image_paths)}"
        if cache_key not in st.session_state:
            with st.spinner("氏名を推定しています..."):
                st.session_state[cache_key] = {
                    i + 1: guess_page_name(p) for i, p in enumerate(image_paths)
                }
        guessed = st.session_state[cache_key]

        name_cols = st.columns(4)
        for i, path in enumerate(image_paths, start=1):
            col = name_cols[(i - 1) % 4]
            with col:
                st.image(str(path), caption=f"{i}ページ目", use_container_width=True)
                page_names[i] = st.text_input(
                    f"氏名(p{i})", value=guessed.get(i, ""), key=f"name_{i}"
                )

    run = st.button("集計・突合を実行", type="primary")

    if run:
        with st.spinner("Excelに集計列を追記しています..."):
            out_excel = tmp_path / f"{facility}_{sheet_title}_集計付き.xlsx"
            annotate_workbook(str(excel_path), str(out_excel))

        st.success("Excelの集計が完了しました。")
        st.download_button(
            "集計付きExcelをダウンロード",
            data=out_excel.read_bytes(),
            file_name=out_excel.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if pdf_file and any(page_names.values()):
            named_pages = {p: n for p, n in page_names.items() if n.strip()}
            with st.spinner(f"出勤簿PDFをOCR中... ({len(named_pages)}ページ)"):
                progress = st.progress(0.0)
                pages = {}
                for idx, (page_no, path) in enumerate(zip(named_pages.keys(), image_paths), start=1):
                    pages[page_no] = extract_page(str(image_paths[page_no - 1]), page_no)
                    progress.progress(idx / len(named_pages))

            roster_diff = compare_roster(list(summaries.keys()), named_pages)
            employee_diffs = compare_employees(summaries, pages, named_pages)

            out_report = tmp_path / f"{facility}_{sheet_title}_相違点レポート.xlsx"
            write_reconcile_report(str(out_report), roster_diff, employee_diffs, sheet_title)

            st.success("PDFとの突合が完了しました。")

            review_count = sum(1 for d in employee_diffs if d.needs_review)
            st.metric("要確認の職員数", f"{review_count} / {len(employee_diffs)}名")

            if roster_diff.missing_timesheets:
                st.warning("出勤簿PDFが見当たらない職員: " + "、".join(roster_diff.missing_timesheets))
            if roster_diff.name_variants:
                st.warning(
                    "氏名の表記ゆれ: "
                    + "、".join(f"PDF「{a}」/Excel「{b}」" for a, b in roster_diff.name_variants)
                )

            st.download_button(
                "相違点レポートをダウンロード",
                data=out_report.read_bytes(),
                file_name=out_report.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            st.dataframe(
                [
                    {
                        "氏名": d.name,
                        "ページ": d.page,
                        "Excel出勤日数": d.excel_work_days,
                        "PDF出勤日数(OCR)": d.pdf_work_days,
                        "差": d.work_day_diff,
                        "要確認": "●" if d.needs_review else "",
                        "備考": " / ".join(d.notes),
                    }
                    for d in employee_diffs
                ],
                use_container_width=True,
            )

            st.info(
                "PDFのOCR結果は下書きです。特に手書きページは読み取り誤りが起きやすいため、"
                "「要確認」の職員は必ず原本と照合してください。"
            )
