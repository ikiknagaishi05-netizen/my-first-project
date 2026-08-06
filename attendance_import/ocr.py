"""PDF(スキャン画像)をOCRしてページごとのテキストを取り出す。"""

from __future__ import annotations

from PIL import Image, ImageOps
import pdf2image
import pytesseract


def pdf_to_images(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    """PDFの各ページをPIL Imageに変換する。"""
    return pdf2image.convert_from_path(pdf_path, dpi=dpi)


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
