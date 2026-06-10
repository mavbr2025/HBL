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
