from pathlib import Path

from mtm_hbl.config import AppConfig
from mtm_hbl.document_classifier.classifier import classify_document
from mtm_hbl.document_loader.loader import load_pdf
from mtm_hbl.extraction_engine.extractor import extract_container_details, extract_document_fields
from mtm_hbl.models.canonical import Container, QaIssue
from mtm_hbl.pipeline import PipelineInput, build_review_packet
from mtm_hbl.validation.carrier_receipt import populate_carrier_receipt
from mtm_hbl.validation.validation_engine import ValidationEngine


def build_local_review(
    *,
    shipment_name: str,
    agent_hbl_pdf: Path,
    carrier_mbl_pdf: Path,
    owner_country: str = "Guatemala",
    clickup_hbl_number: str = "",
    clickup_vessel_voyage: str = "",
    notify_party_override: str = "",
    delivery_apply_to_override: str = "",
    freight_rate: str = "",
    freight_currency: str = "",
    freight_unit: str = "",
    freight_charge_description: str = "",
    freight_payable_at: str = "",
    customer_slug: str = "",
    source_strategy: str = "",
    app_config: AppConfig,
) -> object:
    agent_doc = classify_document(load_pdf(agent_hbl_pdf))
    carrier_doc = classify_document(load_pdf(carrier_mbl_pdf))
    agent_doc.document_type = "agent_hbl"
    carrier_doc.document_type = "carrier_mbl"
    agent_values = extract_document_fields(agent_doc)
    carrier_values = extract_document_fields(carrier_doc)

    data = build_review_packet(
        PipelineInput(
            clickup_task_id=shipment_name,
            clickup_values={
                "owner_country": owner_country,
                "hbl_number": clickup_hbl_number,
                "vessel_voyage": clickup_vessel_voyage,
                "notify_party_override": notify_party_override,
                "delivery_apply_to_override": delivery_apply_to_override,
                "freight_rate": freight_rate,
                "freight_currency": freight_currency,
                "freight_unit": freight_unit,
                "freight_charge_description": freight_charge_description,
                "freight_payable_at": freight_payable_at,
            },
            agent_hbl_values=agent_values,
            carrier_mbl_values=carrier_values,
            customer_slug=customer_slug,
            source_strategy=source_strategy,
        ),
        app_config=app_config,
    )

    if source_strategy == "carrier_mbl_only":
        extracted_containers = extract_container_details(carrier_doc) or extract_container_details(agent_doc)
    else:
        extracted_containers = extract_container_details(agent_doc) or extract_container_details(carrier_doc)
    if data.containers:
        if extracted_containers:
            data.qa.soft_warnings.append(
                QaIssue(
                    id="learned_container_rows_preserved",
                    severity="soft_warning",
                    field="containers",
                    message=(
                        "Customer-learned container rows were preserved instead of replacing them "
                        "with lower-priority extracted container rows."
                    ),
                    blocking_scope="none",
                    recommended_action="Validate learned container rows against the team-issued HBL.",
                )
            )
            data.qa.manual_review_required = True
    elif extracted_containers:
        data.containers = [
            Container(
                container_no=item.get("container_no", ""),
                seal_no=item.get("seal_no", ""),
                container_type=item.get("container_type", ""),
                package_count=item.get("package_count", ""),
                package_type=item.get("package_type", ""),
                gross_weight=item.get("gross_weight", ""),
                measurement=item.get("measurement", ""),
            )
            for item in extracted_containers
        ]
    elif agent_values.get("container_no") or carrier_values.get("container_no"):
        primary_values = carrier_values if source_strategy == "carrier_mbl_only" else agent_values
        secondary_values = agent_values if source_strategy == "carrier_mbl_only" else carrier_values
        data.containers = [
            Container(
                container_no=primary_values.get("container_no") or secondary_values.get("container_no", ""),
                seal_no=primary_values.get("seal_no") or secondary_values.get("seal_no", ""),
                gross_weight=primary_values.get("gross_weight") or secondary_values.get("gross_weight", ""),
                measurement=primary_values.get("measurement") or secondary_values.get("measurement", ""),
            )
        ]
    if data.containers:
        data.qa.hard_errors = []
        populate_carrier_receipt(data, app_config)
        ValidationEngine(app_config).validate(data)
    if any(page.extraction_method == "ocr" for page in agent_doc.pages + carrier_doc.pages):
        data.qa.soft_warnings.append(
            QaIssue(
                id="low_document_quality",
                severity="soft_warning",
                field="documents",
                message="A source PDF required OCR; extracted values need manual review.",
                blocking_scope="none",
                recommended_action="Review OCR-derived fields before approving draft generation.",
            )
        )
        data.qa.manual_review_required = True
    if any(page.extraction_method == "ocr_unavailable" for page in agent_doc.pages + carrier_doc.pages):
        data.qa.soft_warnings.append(
            QaIssue(
                id="low_ocr_confidence",
                severity="soft_warning",
                field="documents",
                message="A source PDF did not contain embedded text and OCR is not installed.",
                blocking_scope="none",
                recommended_action="Install OCR dependencies or review this document manually.",
            )
        )
        data.qa.manual_review_required = True
    return data
