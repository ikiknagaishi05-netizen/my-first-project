"""PDF(スキャン画像)をOCRしてページごとのテキストを取り出す。"""

from __future__ import annotations

import io

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps


def pdf_to_images(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    """PDFの各ページをPIL Imageに変換する。Popplerのインストールが不要なPyMuPDFを使用。"""
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    images = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    return images


def preprocess(image: Image.Image) -> Image.Image:
    """OCR精度向上のための簡易前処理(グレースケール化+コントラスト補正)。"""
    gray = ImageOps.grayscale(image)
    return ImageOps.autocontrast(gray)


def ocr_page(image: Image.Image, lang: str = "jpn+eng") -> str:
    """1ページ分の画像からテキストを抽出する。"""
    processed = preprocess(image)
    return pytesseract.image_to_string(processed, lang=lang)


def extract_text_from_pdf(pdf_path: str, lang: str = "jpn+eng", dpi: int = 300) -> list[str]:
    """PDFの各ページをOCRし、ページごとのテキストのリストを返す。"""
    images = pdf_to_images(pdf_path, dpi=dpi)
    return [ocr_page(image, lang=lang) for image in images]
