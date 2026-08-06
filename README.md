# my-first-project

## 複数事業所むけ 出勤簿確認・勤務形態一覧表 作成アプリ

毎月、複数事業所の「出勤簿兼申請書」PDFと「勤務形態一覧表」Excelを扱う場合は、
ブラウザで動く `app.py` を使うと簡単です。

```bash
# 初回のみ
pip3 install -r requirements.txt
sudo apt-get install -y tesseract-ocr tesseract-ocr-jpn poppler-utils

# 起動
streamlit run app.py
```

起動するとブラウザが開き、以下の流れで操作できます。

1. サイドバーで事業所を選択(初めての事業所は名前を登録)
2. その事業所の「勤務形態一覧表」Excelをアップロード
3. その事業所の「出勤簿兼申請書」PDFをアップロード
4. ページごとの氏名を確認(自動候補が出ますが手書きのため誤ることがあります。手直し可能)
5. 「集計・突合を実行」を押すと、
   - Excelに出勤日数・休日出勤・有給・欠勤・夜勤回数などの集計列を追記したファイル
   - PDFとExcelの相違点(提出漏れ・氏名の表記ゆれ・日数の食い違い)をまとめたレポート
   をその場でダウンロードできます

**注意**: このアプリは特定の出勤簿PDFのレイアウト(罫線検出込みで実測・調整済み)を前提にしています。
事業所によって様式が異なる場合は、`attendance_import/timesheet_ocr.py` の罫線・セル位置の調整が必要です。
また手書きページのOCRは誤読が起こり得るため、「要確認」と表示された職員は必ず原本と照合してください。

### CLIで実行する場合

ブラウザを使わず、コマンドで一括実行することもできます。

```bash
python3 -m attendance_import.cli_timesheet \
  --excel 勤務形態一覧表.xlsx --sheet "令和8年7月 (4)" \
  --pdf 出勤簿.pdf --names names.json \
  --out-excel 集計付き.xlsx --out-report 相違点レポート.xlsx
```

`names.json` は `{"1": "氏名A", "2": "氏名B", ...}` の形式で、PDFのページ番号と氏名の対応を指定します
(出勤簿の氏名欄は手書きのため、自動認識だけに頼らず用意することを推奨します)。

Excelへの集計だけであれば `--pdf` を省略でき、その場合はOCRを使わないため結果は完全に正確です。

---

## 出勤簿PDF → 勤務形態 自動入力ツール (プロトタイプ)

スキャン・手書きの出勤簿PDFをOCRで読み取り、日付ごとの「勤務形態」（出勤・遅刻・早退・有給休暇・欠勤など）を
自動判定してExcel/CSVに出力するプロトタイプです。

### できること

- PDFの各ページを画像化してOCR（Tesseract, 日本語対応）
- OCR結果から日付・出勤時刻・退勤時刻・備考を行単位で抽出
- 就業規則（始業・終業時刻、キーワード）に基づいて勤務形態を自動判定
  - 備考欄に「有給」「欠勤」等のキーワードがあれば優先的にそちらを採用
  - 出退勤時刻から遅刻・早退・出勤を判定
- Excel(.xlsx)またはCSVに出力。読み取れなかった行は「要確認」として黄色くハイライト

### 制限事項（重要）

- **手書き文字のOCR精度は保証できません。** 特に崩した字・薄い筆跡・罫線に重なった文字は誤読しやすいため、
  出力結果は必ず人の目で確認してください（要確認フラグの立った行は特に注意）。
- 出勤簿のレイアウトは会社ごとに異なります。現状の `attendance_import/parser.py` は
  「日付 出勤時刻 退勤時刻 備考」を1行で読み取るシンプルな表を想定した正規表現ベースの実装です。
  実際のPDFのレイアウトに合わせて調整が必要になる可能性が高いです。
- 判定ルール（始業・終業時刻、キーワード）は `attendance_import/config.py` の `Config` で変更できます。

### セットアップ

```bash
# システム依存パッケージ (Ubuntu/Debian)
sudo apt-get install -y tesseract-ocr tesseract-ocr-jpn poppler-utils

# Pythonパッケージ
pip3 install -r requirements.txt
```

### 使い方

```bash
python3 -m attendance_import.cli 出勤簿.pdf -o result.xlsx \
  --work-start 09:00 --work-end 18:00
```

サンプルの出勤簿PDF（印字体、パイプライン検証用）を生成して試すこともできます。

```bash
python3 scripts/generate_sample_pdf.py samples/sample_attendance.pdf
python3 -m attendance_import.cli samples/sample_attendance.pdf -o samples/sample_result.xlsx
```

### テスト

```bash
pip3 install pytest
python3 -m pytest
```

### 今後の改善案

- 実際の出勤簿PDFのサンプルを使ってレイアウト・OCR精度をチューニング
- テーブル構造をより厳密に認識する（罫線・セル位置ベースの抽出）
- OCRの文字ごとの信頼度スコアを使い、「要確認」判定の精度を上げる
- 複数フォーマットに対応するテンプレート機構の追加
