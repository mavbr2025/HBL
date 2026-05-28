import json
from pathlib import Path

from mtm_hbl.models.canonical import CanonicalHblData


def save_qa_json(data: CanonicalHblData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data.qa.model_dump(mode="json"), handle, indent=2, ensure_ascii=False)


def save_qa_markdown(data: CanonicalHblData, path: Path) -> None:
    lines = [
        "# MTM Guatemala HBL Draft QA Report",
        "",
        f"Task ID: {data.shipment.clickup_task_id}",
        f"HBL No.: {data.shipment.mtm_hbl_no}",
        f"Draft generation allowed: {data.qa.draft_generation_allowed}",
        f"Final generation allowed: {data.qa.final_generation_allowed}",
        f"Manual review required: {data.qa.manual_review_required}",
        "",
        "## Hard Errors",
    ]
    if data.qa.hard_errors:
        for issue in data.qa.hard_errors:
            lines.append(f"- `{issue.id}` `{issue.field}`: {issue.message}")
    else:
        lines.append("- None")

    lines.extend(["", "## Soft Warnings"])
    if data.qa.soft_warnings:
        for issue in data.qa.soft_warnings:
            lines.append(f"- `{issue.id}` `{issue.field}`: {issue.message}")
    else:
        lines.append("- None")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
