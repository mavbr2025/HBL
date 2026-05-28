from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from mtm_hbl.models.documents import LoadedDocument, PageText


def extract_pdf_text(path: Path) -> LoadedDocument:
    try:
        return _extract_with_pdfplumber(path)
    except Exception:
        return _extract_with_pypdf(path)


def _extract_with_pdfplumber(path: Path) -> LoadedDocument:
    pages: list[PageText] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            pages.append(
                PageText(
                    page_number=index,
                    text=text,
                    confidence=1.0 if text.strip() else None,
                    extraction_method="embedded_text",
                )
            )
    return LoadedDocument(path=str(path), pages=pages)


def _extract_with_pypdf(path: Path) -> LoadedDocument:
    reader = PdfReader(str(path))
    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(
            PageText(
                page_number=index,
                text=text,
                confidence=1.0 if text.strip() else None,
                extraction_method="embedded_text",
            )
        )
    return LoadedDocument(path=str(path), pages=pages)
