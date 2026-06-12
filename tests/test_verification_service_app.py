from __future__ import annotations

import importlib.util
from pathlib import Path

import boto3


class FakeDynamoTable:
    def __init__(self, record: dict | None) -> None:
        self.record = record

    def get_item(self, Key):
        if self.record and Key["verification_id"] == self.record["verification_id"]:
            return {"Item": self.record}
        return {}


class FakeDynamoResource:
    def __init__(self, record: dict | None) -> None:
        self.record = record

    def Table(self, _name):
        return FakeDynamoTable(self.record)


def _load_app(monkeypatch, record: dict | None = None):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setattr(boto3, "resource", lambda _service: FakeDynamoResource(record))
    path = Path("aws/verification-service/src/app.py").resolve()
    spec = importlib.util.spec_from_file_location("verification_service_app_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _record() -> dict:
    return {
        "verification_id": "WH26040006-O1-TEST",
        "status": "ISSUED",
        "hbl_number": "WH26040006",
        "mbl_number": "ONEYTAOG71637300",
        "document_type": "ORIGINAL",
        "sequence": 1,
        "sequence_total": 3,
        "page_number": 1,
        "page_total": 1,
        "issued_at": "2026-06-11T12:00:00+00:00",
        "issued_by": "Andrea Piedad Velasquez Castellon",
        "terms_version": "3.0",
        "terms_effective_date_display": "11-JUN-2026",
        "pdf_sha256": "abc123",
        "package_id": "pkg_test",
    }


def test_verification_page_renders_terms_below_hbl_metadata(monkeypatch):
    app = _load_app(monkeypatch, _record())

    response = app.lambda_handler(
        {
            "rawPath": "/verify/WH26040006-O1-TEST",
            "pathParameters": {"verification_id": "WH26040006-O1-TEST"},
            "queryStringParameters": {},
        },
        None,
    )

    assert response["statusCode"] == 200
    body = response["body"]
    assert "HBL Specific Information" in body
    assert "WH26040006" in body
    assert "MTM Logix Freight Forwarder" in body
    assert "Version 3.0" in body
    assert "These Terms and Conditions are incorporated into and form part" in body
    assert "Application and Incorporation" in body


def test_verification_page_supports_spanish_terms_selection(monkeypatch):
    app = _load_app(monkeypatch, _record())

    response = app.lambda_handler(
        {
            "rawPath": "/verify/WH26040006-O1-TEST",
            "pathParameters": {"verification_id": "WH26040006-O1-TEST"},
            "queryStringParameters": {"lang": "es"},
        },
        None,
    )

    assert response["statusCode"] == 200
    body = response["body"]
    assert "Términos y Condiciones" in body
    assert "Aplicación e incorporación" in body
    assert "class='active' href='/verify/WH26040006-O1-TEST?lang=es'" in body


def test_verification_page_keeps_terms_off_not_found_response(monkeypatch):
    app = _load_app(monkeypatch, None)

    response = app.lambda_handler(
        {
            "rawPath": "/verify/UNKNOWN",
            "pathParameters": {"verification_id": "UNKNOWN"},
            "queryStringParameters": {},
        },
        None,
    )

    assert response["statusCode"] == 404
    assert "Document Not Found" in response["body"]
    assert "Terms and Conditions are incorporated" not in response["body"]
