import json
from pathlib import Path

from mtm_hbl.models.canonical import CanonicalHblData


def save_review_packet(data: CanonicalHblData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data.model_dump(mode="json"), handle, indent=2, ensure_ascii=False)


def load_review_packet(path: Path) -> CanonicalHblData:
    with path.open("r", encoding="utf-8") as handle:
        return CanonicalHblData.model_validate(json.load(handle))
