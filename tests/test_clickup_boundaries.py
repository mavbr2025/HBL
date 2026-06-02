from mtm_hbl.config import AppConfig, Settings
from mtm_hbl.clickup_connector.client import ClickUpClient
from mtm_hbl.models.clickup import ClickUpCustomField, ClickUpTaskData


def test_clickup_final_pdf_field_is_configured_as_final_only():
    config = AppConfig()

    final_pdf = config.clickup_fields["final_pdf"]

    assert final_pdf["field_id"] == "fb02fca6-7626-4be9-9ba9-7a55c5b6684f"
    assert final_pdf["use_only_after_final_approval"] is True


def test_clickup_hbl_output_fields_are_separate_for_draft_and_original():
    config = AppConfig()

    outputs = config.clickup_fields["hbl_outputs"]

    assert outputs["draft_pdf"]["field_id"] == "85b0aff3-ccc5-4f90-b625-ed55592e07b7"
    assert outputs["original_pdf"]["field_id"] == "b7c70ef7-1c86-4c11-8022-a5c4913216ed"
    assert outputs["original_pdf"]["use_only_after_final_approval"] is True


def test_clickup_original_approval_requires_three_fields():
    config = AppConfig()

    approval = config.clickup_fields["approval"]

    assert approval["field_names"]
    assert approval["require_approved_by"] is True
    assert approval["require_approved_at"] is True


def test_clickup_configured_field_extraction_uses_hbl_custom_field(app_config):
    task = ClickUpTaskData(
        id="task-1",
        custom_fields=[
            ClickUpCustomField(id="owner", name="Owner Country", value="Guatemala"),
            ClickUpCustomField(
                id="8108af0b-9b7c-45aa-8d74-8e70567b93f0",
                name="HBL No.",
                value="GOSZX26012025",
            ),
        ],
    )
    client = ClickUpClient(Settings(), "token")

    values = client.extract_configured_fields(task, app_config)

    assert values["owner_country"] == "Guatemala"
    assert values["hbl_number"] == "GOSZX26012025"


def test_clickup_configured_field_extraction_reads_freight_rate_alias(app_config):
    task = ClickUpTaskData(
        id="task-1",
        custom_fields=[
            ClickUpCustomField(id="rate", name="Ocean Freight Rate", value="$3,000.00"),
        ],
    )
    client = ClickUpClient(Settings(), "token")

    values = client.extract_configured_fields(task, app_config)

    assert values["freight_rate"] == "$3,000.00"
    assert values["freight_currency"] == "USD"
    assert values["freight_unit"] == "Per Container"


def test_clickup_task_parser_reads_assignees():
    task = ClickUpClient._parse_task(
        {
            "id": "task-1",
            "assignees": [
                {"id": 12345, "username": "Operator", "email": "operator@example.com"},
            ],
        }
    )

    assert len(task.assignees) == 1
    assert task.assignees[0].id == "12345"
    assert task.assignees[0].username == "Operator"
