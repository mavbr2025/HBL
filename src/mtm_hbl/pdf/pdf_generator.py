import subprocess
from pathlib import Path


class PdfGenerationError(RuntimeError):
    pass


def export_excel_to_pdf(excel_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(excel_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise PdfGenerationError(result.stderr or result.stdout or "LibreOffice PDF export failed.")
    pdf_path = output_dir / f"{excel_path.stem}.pdf"
    if not pdf_path.exists():
        raise PdfGenerationError(f"Expected PDF was not created: {pdf_path}")
    return pdf_path
