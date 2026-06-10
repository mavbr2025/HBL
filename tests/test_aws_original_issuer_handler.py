import importlib
import json


def _handler_module(monkeypatch):
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    return importlib.import_module("mtm_hbl.aws_handlers.original_issuer")


def test_extract_task_id_accepts_clickup_task_url(monkeypatch):
    handler = _handler_module(monkeypatch)

    assert (
        handler._extract_task_id({"task_id": "https://app.clickup.com/t/8451352/86e1qfama"})
        == "86e1qfama"
    )


def test_extract_task_id_accepts_clickup_automation_labels(monkeypatch):
    handler = _handler_module(monkeypatch)

    assert handler._extract_task_id({"Task ID": "86e1qfama"}) == "86e1qfama"
    assert handler._extract_task_id({"task": {"id": "86e1qfama"}}) == "86e1qfama"
    assert handler._extract_task_id({"data": {"taskId": "86e1qfama"}}) == "86e1qfama"


def test_extract_task_id_accepts_query_parameters(monkeypatch):
    handler = _handler_module(monkeypatch)

    assert (
        handler._extract_task_id({}, {"queryStringParameters": {"Task ID": "86e1qfama"}})
        == "86e1qfama"
    )


def test_webhook_rejects_missing_secret(monkeypatch):
    handler = _handler_module(monkeypatch)
    monkeypatch.setenv("HBL_WEBHOOK_SECRET", "expected")

    response = handler.webhook_handler(
        {
            "headers": {},
            "body": json.dumps({"task_id": "86e1qfama"}),
        },
        object(),
    )

    assert response["statusCode"] == 401


def test_webhook_dry_run_does_not_require_task_id(monkeypatch):
    handler = _handler_module(monkeypatch)
    monkeypatch.setenv("HBL_WEBHOOK_SECRET", "expected")

    response = handler.webhook_handler(
        {
            "headers": {"X-MTM-HBL-Webhook-Secret": "expected"},
            "queryStringParameters": {"dry_run": "true"},
            "body": json.dumps({}),
        },
        object(),
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "DRY_RUN_OK"


def test_webhook_accepts_and_enqueues_task(monkeypatch):
    handler = _handler_module(monkeypatch)
    sent_messages = []

    class FakeSqs:
        def send_message(self, **kwargs):
            sent_messages.append(kwargs)
            return {"MessageId": "msg-1"}

    monkeypatch.setenv("HBL_WEBHOOK_SECRET", "expected")
    monkeypatch.setenv("HBL_ORIGINAL_ISSUER_QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setattr(handler, "sqs", FakeSqs())

    response = handler.webhook_handler(
        {
            "headers": {"X-MTM-HBL-Webhook-Secret": "expected"},
            "body": json.dumps({"task_id": "https://app.clickup.com/t/8451352/86e1qfama"}),
        },
        object(),
    )

    assert response["statusCode"] == 202
    assert json.loads(response["body"])["task_id"] == "86e1qfama"
    assert json.loads(sent_messages[0]["MessageBody"])["task_id"] == "86e1qfama"
    assert json.loads(sent_messages[0]["MessageBody"])["mode"] == "issue"


def test_webhook_draft_route_enqueues_draft_mode(monkeypatch):
    handler = _handler_module(monkeypatch)
    sent_messages = []

    class FakeSqs:
        def send_message(self, **kwargs):
            sent_messages.append(kwargs)
            return {"MessageId": "msg-1"}

    monkeypatch.setenv("HBL_WEBHOOK_SECRET", "expected")
    monkeypatch.setenv("HBL_ORIGINAL_ISSUER_QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setattr(handler, "sqs", FakeSqs())

    response = handler.webhook_handler(
        {
            "headers": {"X-MTM-HBL-Webhook-Secret": "expected"},
            "rawPath": "/webhooks/clickup/hbl-draft",
            "body": json.dumps({"Task ID": "86e1qfama"}),
        },
        object(),
    )

    message = json.loads(sent_messages[0]["MessageBody"])
    assert response["statusCode"] == 202
    assert json.loads(response["body"])["mode"] == "draft"
    assert message["task_id"] == "86e1qfama"
    assert message["mode"] == "draft"


def test_draft_job_id_is_repeatable(monkeypatch):
    handler = _handler_module(monkeypatch)

    first = handler._job_id("draft", "86e1qfama", {"request_id": "first"})
    second = handler._job_id("draft", "86e1qfama", {"request_id": "second"})

    assert first == "draft#86e1qfama#first"
    assert second == "draft#86e1qfama#second"
    assert first != second


def test_failure_comment_text_for_draft_lists_missing_data(monkeypatch):
    handler = _handler_module(monkeypatch)

    text = handler._failure_comment_text("draft", "HBL No. is missing.\nMBL No. is missing.")

    assert text.startswith("Draft HBL generation failed.")
    assert "- HBL No. is missing." in text
    assert "- MBL No. is missing." in text
    assert "No draft was issued." in text
