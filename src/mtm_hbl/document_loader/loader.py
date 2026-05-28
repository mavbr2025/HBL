from pathlib import Path

from mtm_hbl.document_loader.ocr import extract_pdf_with_ocr
from mtm_hbl.document_loader.pdf_text import extract_pdf_text
from mtm_hbl.models.documents import LoadedDocument, PageText


def load_pdf(path: Path, allow_ocr: bool = True) -> LoadedDocument:
    document = extract_pdf_text(path)
    if len(document.full_text.strip()) >= 50 or not allow_ocr:
        return document
    try:
        return extract_pdf_with_ocr(path)
    except RuntimeError:
        return LoadedDocument(
            path=str(path),
            pages=[
                PageText(
                    page_number=1,
                    text="",
                    confidence=0.0,
                    extraction_method="ocr_unavailable",
                )
            ],
        )
