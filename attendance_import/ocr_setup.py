"""Tesseract OCR実行ファイルの自動検出。

Windowsでは環境変数PATHを自分で編集するのはハードルが高いため、
インストーラ(UB Mannheim版)の既定インストール先を自動的に探して設定する。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytesseract

WINDOWS_DEFAULT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

INSTALL_GUIDE = (
    "以下からインストーラをダウンロードして実行してください。\n"
    "https://github.com/UB-Mannheim/tesseract/wiki\n"
    "インストール時に「Additional language data」で日本語(Japanese)にチェックを入れてください。"
)


def configure_tesseract() -> str | None:
    """tesseractのパスを設定する。見つからない場合は案内メッセージを返す。"""
    if shutil.which("tesseract"):
        return None

    for path in WINDOWS_DEFAULT_PATHS:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            return None

    try:
        pytesseract.get_tesseract_version()
        return None
    except Exception:
        return INSTALL_GUIDE
