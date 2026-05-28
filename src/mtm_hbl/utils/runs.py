from datetime import datetime
from pathlib import Path

from mtm_hbl.config import Settings


def create_run_dir(settings: Settings, task_id: str) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_task_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in task_id)
    path = settings.runs_dir / f"{safe_task_id}_{timestamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path
