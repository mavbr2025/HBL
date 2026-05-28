import html
import json
import os
from decimal import Decimal

import boto3


TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    path = event.get("rawPath", "")
    verification_id = event.get("pathParameters", {}).get("verification_id", "")
    record = get_record(verification_id)

    if path.startswith("/api/verify/"):
        if not record:
            return response(
                404,
                json.dumps(
                    {
                        "status": "NOT_FOUND",
                        "verification_id": verification_id,
                    }
                ),
                "application/json",
            )
        return response(200, json.dumps(record, cls=DecimalEncoder), "application/json")

    return response(200 if record else 404, render_html(verification_id, record), "text/html; charset=utf-8")


def get_record(verification_id):
    if not verification_id:
        return None
    result = table.get_item(Key={"verification_id": verification_id})
    return result.get("Item")


def response(status_code, body, content_type):
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": content_type,
            "cache-control": "no-store",
        },
        "body": body,
    }


def render_html(verification_id, record):
    if not record:
        return f"""<!doctype html>
<html>
<head>
  <title>MTM HBL Verification</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="font-family: Arial, sans-serif; margin: 40px; max-width: 780px;">
  <h1>Document Not Found</h1>
  <p>Verification ID: <strong>{html.escape(verification_id)}</strong></p>
  <p style="color:#b00020;font-weight:bold;">
    This document could not be verified. Contact MTM Logix before accepting it.
  </p>
</body>
</html>"""

    status = str(record.get("status", "UNKNOWN"))
    warning = ""
    if status.upper() in {"VOID", "SUPERSEDED", "NOT_FOUND", "UNKNOWN"}:
        warning = (
            "<p style='color:#b00020;font-weight:bold;'>"
            f"WARNING: document status is {html.escape(status)}"
            "</p>"
        )

    document_label = " ".join(
        part
        for part in [
            str(record.get("document_type", "")),
            _sequence(record),
        ]
        if part
    )
    rows = [
        ("Status", status),
        ("HBL No.", record.get("hbl_number", "")),
        ("MBL No.", record.get("mbl_number", "")),
        ("Document", document_label),
        ("Issued at", record.get("issued_at", "")),
        ("Issued by", record.get("issued_by", "")),
        ("PDF SHA-256", record.get("pdf_sha256", "")),
        ("Package ID", record.get("package_id", "")),
    ]

    row_html = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"
        for label, value in rows
    )

    return f"""<!doctype html>
<html>
<head>
  <title>MTM HBL Verification</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="font-family: Arial, sans-serif; margin: 40px; max-width: 860px;">
  <h1>MTM Logix HBL Verification</h1>
  {warning}
  <table style="border-collapse: collapse; width: 100%;">
    {row_html}
  </table>
  <p style="font-size: 12px; color: #475467; margin-top: 20px;">
    This page verifies issuance metadata only. It does not expose the PDF publicly.
  </p>
  <style>
    th {{ text-align: left; width: 180px; background: #f3f4f6; }}
    th, td {{ border: 1px solid #d0d5dd; padding: 10px; vertical-align: top; }}
  </style>
</body>
</html>"""


def _sequence(record):
    sequence = record.get("sequence")
    total = record.get("sequence_total")
    if sequence and total:
        return f"{sequence}/{total}"
    return ""
