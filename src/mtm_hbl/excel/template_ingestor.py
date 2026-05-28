import json
import shutil
from hashlib import sha256
from pathlib import Path

from mtm_hbl.excel.template_inspector import inspect_template


def ingest_template(source_path: Path, templates_dir: Path) -> dict:
    if not source_path.exists():
        raise FileNotFoundError(f"Template not found: {source_path}")
    if source_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("Template must be an Excel workbook with .xlsx or .xlsm extension.")

    templates_dir.mkdir(parents=True, exist_ok=True)
    file_hash = _sha256_file(source_path)
    stored_path = templates_dir / f"mtm_guatemala_hbl_template_{file_hash[:12]}{source_path.suffix.lower()}"
    if source_path.resolve() != stored_path.resolve():
        shutil.copy2(source_path, stored_path)

    profile = inspect_template(stored_path)
    profile.update(
        {
            "stored_template_path": str(stored_path),
            "sha256": file_hash,
        }
    )
    profile_path = templates_dir / f"{stored_path.stem}_profile.json"
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    profile["profile_path"] = str(profile_path)
    return profile


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
