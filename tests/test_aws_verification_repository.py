from pathlib import Path

import boto3

from mtm_hbl.verification.aws_repository import AwsVerificationConfig, register_issued_package
from tests.test_hbl_package_pdf import package_data
from mtm_hbl.pdf.hbl_package import generate_bill_of_lading_package


class FakeS3Client:
    def __init__(self) -> None:
        self.uploads = []
        self.objects = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.uploads.append(
            {
                "filename": filename,
                "bucket": bucket,
                "key": key,
                "extra_args": ExtraArgs or {},
            }
        )

    def put_object(self, **kwargs):
        self.objects.append(kwargs)


class FakeTable:
    def __init__(self) -> None:
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


class FakeDynamoResource:
    def __init__(self, table: FakeTable) -> None:
        self.table = table

    def Table(self, _name):
        return self.table


def test_register_issued_package_uploads_encrypted_private_artifacts(monkeypatch, tmp_path):
    data = package_data()
    pdf_path = tmp_path / "HBL_Package_WH26040006.pdf"
    generate_bill_of_lading_package(data, pdf_path, verification_base_url="https://verify.example.com/")

    fake_s3 = FakeS3Client()
    fake_table = FakeTable()

    monkeypatch.setattr(boto3, "client", lambda service, region_name=None: fake_s3)
    monkeypatch.setattr(
        boto3,
        "resource",
        lambda service, region_name=None: FakeDynamoResource(fake_table),
    )

    registration = register_issued_package(
        data,
        pdf_path,
        AwsVerificationConfig(
            bucket_name="test-bucket",
            table_name="test-table",
            region_name="us-east-1",
            verification_base_url="https://verify.example.com/",
        ),
        package_id="pkg_test",
        status="issued",
    )

    assert len(fake_s3.uploads) == 1
    assert fake_s3.uploads[0]["extra_args"]["ServerSideEncryption"] == "AES256"
    assert fake_s3.uploads[0]["extra_args"]["ContentType"] == "application/pdf"
    assert len(fake_s3.objects) == 1
    assert fake_s3.objects[0]["ServerSideEncryption"] == "AES256"
    assert fake_s3.objects[0]["ContentType"] == "application/json"
    assert len(fake_table.items) == 6
    assert fake_table.items[0]["status"] == "ISSUED"
    assert fake_table.items[0]["verification_url"] == "https://verify.example.com/verify/WH26040006-O1"
    assert registration.verification_urls["WH26040006-O1"] == (
        "https://verify.example.com/verify/WH26040006-O1"
    )
    assert registration.pdf_sha256
    assert registration.canonical_json_sha256
