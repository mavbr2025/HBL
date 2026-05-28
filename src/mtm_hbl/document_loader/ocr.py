from pathlib import Path

from mtm_hbl.models.documents import LoadedDocument, PageText


def extract_pdf_with_ocr(path: Path) -> LoadedDocument:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are not installed. Install the project with the 'ocr' extra."
        ) from exc

    pages: list[PageText] = []
    images = convert_from_path(str(path))
    for index, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(image, config="--psm 3")
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confidences = []
        for raw_confidence in data.get("conf", []):
            try:
                confidence = float(raw_confidence)
            except ValueError:
                continue
            if confidence >= 0:
                confidences.append(confidence / 100)
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        pages.append(
            PageText(
                page_number=index,
                text=text,
                confidence=avg_confidence,
                extraction_method="ocr",
            )
        )
    return LoadedDocument(path=str(path), pages=pages)
