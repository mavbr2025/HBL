from pathlib import Path

from mtm_hbl.config import AppConfig


def safe_filename_component(value: str) -> str:
    """Reject unsafe identities rather than silently renaming shipment data."""
    if not value or value in {".", ".."} or any(
        char in '/\\:' or ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ValueError("Shipment identifier must be a nonempty safe filename component.")
    return value


def contained_output_path(directory: Path, filename: str) -> Path:
    safe_filename_component(filename)
    root = directory.resolve()
    candidate = directory / filename
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("Output path escapes the selected output directory.")
    return candidate


def build_draft_pdf_name(app_config: AppConfig, hbl_number: str, version: int) -> str:
    safe_filename_component(hbl_number)
    pattern = app_config.file_naming_rules["draft"]["pattern"]
    return pattern.format(hbl_number=hbl_number, version=version)


def build_draft_excel_name(app_config: AppConfig, hbl_number: str, version: int) -> str:
    safe_filename_component(hbl_number)
    pattern = app_config.file_naming_rules["populated_excel"]["pattern"]
    return pattern.format(hbl_number=hbl_number, version=version)


def next_versioned_path(directory: Path, filename: str) -> Path:
    path = directory / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
