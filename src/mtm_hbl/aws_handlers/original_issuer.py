from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from mtm_hbl.clickup_connector.client import ClickUpClient
from mtm_hbl.clickup_hbl_generator import generate_hbl_from_clickup, parse_clickup_task_id
from mtm_hbl.config import AppConfig, Settings


sqs = boto3.client("sqs")
secretsmanager = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")


def webhook_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    if not _webhook_secret_matches(event):
        return _json_response(401, {"status": "UNAUTHORIZED"})

    try:
        payload = _json_body(event)
        task_id = _extract_task_id(payload)
    except ValueError as exc:
        return _json_response(400, {"status": "BAD_REQUEST", "error": str(exc)})

    queue_url = _required_env("HBL_ORIGINAL_ISSUER_QUEUE_URL")
    message = {
        "task_id": task_id,
        "source": payload.get("source", "clickup_webhook"),
        "webhook_payload_sha256": sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "received_at": _now(),
        "request_id": getattr(context, "aws_request_id", ""),
    }
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
    return _json_response(202, {"status": "ACCEPTED", "task_id": task_id})


def worker_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    results = []
    for record in event.get("Records", []):
        try:
            payload = json.loads(record.get("body") or "{}")
            result = asyncio.run(_process_message(payload))
        except Exception as exc:  # Keep the queue from retrying permanent document-control failures.
            result = {"status": "FAILED", "error": str(exc)}
        results.append(result)
    return {"results": results}


async def _process_message(payload: dict[str, Any]) -> dict[str, Any]:
    task_id = parse_clickup_task_id(str(payload.get("task_id", "")))
    job_id = f"original#{task_id}"
    jobs_table = _jobs_table()

    started = _start_job(jobs_table, job_id, task_id, payload)
    if not started:
        return {"status": "SKIPPED", "reason": "job already running or issued", "task_id": task_id}

    settings = _lambda_settings()
    token = _clickup_access_token()
    client = ClickUpClient(settings, token)

    try:
        result = await generate_hbl_from_clickup(
            task_ref=task_id,
            client=client,
            settings=settings,
            app_config=AppConfig(settings.config_dir),
            mode="issue",
            output_dir=Path("/tmp") / "hbl_runs" / task_id,
            logo_path=Path(os.getenv("HBL_LOGO_PATH", "assets/mtm_logix_logo.png")),
            attach_to_clickup=True,
            post_comment=True,
            verification_base_url=settings.hbl_verification_base_url,
            bucket=settings.hbl_verification_bucket,
            table=settings.hbl_verification_table,
            region=settings.aws_region,
            issued_by=os.getenv("HBL_ISSUED_BY", "Andrea Piedad Velasquez Castellon"),
            prevent_original_overwrite=True,
        )
    except Exception as exc:
        _mark_job_failed(jobs_table, job_id, exc)
        await _post_failure_comment(client, task_id, str(exc))
        return {"status": "FAILED", "task_id": task_id, "error": str(exc)}

    _mark_job_issued(jobs_table, job_id, result.model_dump())
    return {
        "status": "ISSUED",
        "task_id": task_id,
        "hbl_number": result.hbl_number,
        "package_id": result.package_id,
    }


def _webhook_secret_matches(event: dict[str, Any]) -> bool:
    expected = _webhook_secret()
    if not expected:
        return False
    headers = {str(k).casefold(): str(v) for k, v in (event.get("headers") or {}).items()}
    supplied = headers.get("x-mtm-hbl-webhook-secret", "")
    return bool(supplied) and supplied == expected


def _webhook_secret() -> str:
    direct = os.getenv("HBL_WEBHOOK_SECRET", "").strip()
    if direct:
        return direct
    name = os.getenv("HBL_WEBHOOK_SECRET_NAME", "").strip()
    return _secret_string(name).strip() if name else ""


def _clickup_access_token() -> str:
    direct = os.getenv("CLICKUP_ACCESS_TOKEN", "").strip()
    if direct:
        return direct
    name = _required_env("CLICKUP_ACCESS_TOKEN_SECRET_NAME")
    secret = _secret_string(name)
    try:
        payload = json.loads(secret)
    except json.JSONDecodeError:
        return secret.strip()
    return str(payload.get("access_token", "")).strip()


def _secret_string(name: str) -> str:
    response = secretsmanager.get_secret_value(SecretId=name)
    return response.get("SecretString", "")


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Webhook body must be JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Webhook body must be a JSON object.")
    return payload


def _extract_task_id(payload: dict[str, Any]) -> str:
    candidates = [
        payload.get("task_id"),
        payload.get("taskId"),
        payload.get("id"),
        payload.get("task", {}).get("id") if isinstance(payload.get("task"), dict) else "",
        payload.get("data", {}).get("task_id") if isinstance(payload.get("data"), dict) else "",
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return parse_clickup_task_id(value)
    raise ValueError("Webhook payload did not include a ClickUp task_id.")


def _lambda_settings() -> Settings:
    return Settings(
        runs_dir=Path(os.getenv("RUNS_DIR", "/tmp/runs")),
        config_dir=Path(os.getenv("CONFIG_DIR", "config")),
        token_store_path=Path("/tmp/clickup_token.json"),
    )


def _jobs_table():
    return dynamodb.Table(_required_env("HBL_ISSUER_JOBS_TABLE"))


def _start_job(table, job_id: str, task_id: str, payload: dict[str, Any]) -> bool:
    now = _now()
    item = {
        "job_id": job_id,
        "task_id": task_id,
        "status": "RUNNING",
        "created_at": now,
        "updated_at": now,
        "payload_sha256": sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
        "attempts": 1,
    }
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(job_id)")
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
    existing = table.get_item(Key={"job_id": job_id}).get("Item", {})
    if existing.get("status") in {"RUNNING", "ISSUED"}:
        return False
    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s = :running, updated_at = :now ADD attempts :one",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":running": "RUNNING", ":now": now, ":one": 1},
    )
    return True


def _mark_job_issued(table, job_id: str, result: dict[str, Any]) -> None:
    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET #s = :issued, updated_at = :now, hbl_number = :hbl, "
            "package_id = :package_id, pdf_sha256 = :pdf_sha256, result_json = :result"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":issued": "ISSUED",
            ":now": _now(),
            ":hbl": result.get("hbl_number", ""),
            ":package_id": result.get("package_id", ""),
            ":pdf_sha256": result.get("pdf_sha256", ""),
            ":result": json.dumps(result, ensure_ascii=False),
        },
    )


def _mark_job_failed(table, job_id: str, exc: Exception) -> None:
    table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s = :failed, updated_at = :now, error_message = :error",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":failed": "FAILED",
            ":now": _now(),
            ":error": str(exc)[:1500],
        },
    )


async def _post_failure_comment(client: ClickUpClient, task_id: str, error: str) -> None:
    try:
        await client.post_comment(
            task_id,
            "Automatic ORIGINAL HBL issuance failed.\n"
            f"Reason: {error}\n"
            "No original was issued by the AWS automation.",
        )
    except Exception:
        return


def _json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(payload),
    }


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured.")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
