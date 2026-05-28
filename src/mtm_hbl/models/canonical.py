from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Scope(BaseModel):
    country: str = "Guatemala"
    owner_country: str = ""
    issuing_entity: str = "MTM Guatemala"
    phase: str = "draft_generation_only"


class Shipment(BaseModel):
    clickup_task_id: str = ""
    mtm_hbl_no: str = ""
    agent_hbl_no: str = ""
    mbl_no: str = ""
    carrier: str = ""
    vessel: str = ""
    voyage: str = ""
    movement: str = "FCL/FCL"
    freight_term: str = ""
    issue_place: str = "GUATEMALA"
    issue_date: str = ""
    number_of_originals: str = ""

    @property
    def vessel_voyage_display(self) -> str:
        return " ".join(part for part in [self.vessel, self.voyage] if part).strip()

    @property
    def issue_place_date_display(self) -> str:
        return self.issue_date


class Party(BaseModel):
    raw_text: str = ""
    name: str = ""
    address_lines: list[str] = Field(default_factory=list)


class Parties(BaseModel):
    shipper: Party = Field(default_factory=Party)
    consignee: Party = Field(default_factory=Party)
    notify_party: Party = Field(default_factory=Party)
    delivery_apply_to: Party = Field(default_factory=Party)


class Routing(BaseModel):
    place_of_receipt: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    place_of_delivery: str = ""


class Cargo(BaseModel):
    description_raw: str = ""
    total_packages: str = ""
    package_type: str = ""
    gross_weight: str = ""
    gross_weight_unit: str = "KGS"
    measurement: str = ""
    measurement_unit: str = "CBM"


class Container(BaseModel):
    container_no: str = ""
    seal_no: str = ""
    container_type: str = ""
    package_count: str = ""
    package_type: str = ""
    gross_weight: str = ""
    gross_weight_unit: str = "KGS"
    measurement: str = ""
    measurement_unit: str = "CBM"
    marks_and_numbers: str = ""


class Charges(BaseModel):
    charge_description: str = ""
    currency: str = ""
    unit_rate: str = ""
    unit: str = ""
    prepaid_amount: str = ""
    collect_amount: str = ""
    total_freight: str = ""
    freight_payable_at: str = ""
    include_insurance: bool = False
    insurance_amount: str = ""
    line_items: list["ChargeLine"] = Field(default_factory=list)


class ChargeLine(BaseModel):
    description: str = ""
    rate: str = ""
    unit: str = "Per Container"
    currency: str = "USD"
    prepaid_amount: str = ""
    collect_amount: str = ""


class CarrierReceipt(BaseModel):
    container_count_numeric: str = ""
    container_count_words: str = ""
    display_text_line_1: str = ""
    display_text_line_2: str = ""

    @property
    def display_text(self) -> str:
        return "\n".join(
            line for line in [self.display_text_line_1, self.display_text_line_2] if line
        )


class FieldSource(BaseModel):
    field: str = ""
    value: str = ""
    source_document: str = ""
    source_page: str = ""
    source_text: str = ""
    confidence: str = ""
    target_excel_cell: str = ""


class SourceTrace(BaseModel):
    field_sources: list[FieldSource] = Field(default_factory=list)


class QaIssue(BaseModel):
    id: str
    severity: Literal["hard_error", "soft_warning"]
    field: str = ""
    message: str
    source_documents: list[str] = Field(default_factory=list)
    blocking_scope: Literal["draft", "final", "none"] = "final"
    recommended_action: str = ""


class QA(BaseModel):
    hard_errors: list[QaIssue] = Field(default_factory=list)
    soft_warnings: list[QaIssue] = Field(default_factory=list)
    manual_review_required: bool = False
    ocr_confidence: str = ""
    draft_generation_allowed: bool = True
    final_generation_allowed: bool = False


class UserEdit(BaseModel):
    field_name: str
    original_value: Any = ""
    edited_value: Any = ""
    user: str = ""
    timestamp: str = ""
    reason: str = ""


class Audit(BaseModel):
    user_edits: list[UserEdit] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class Metadata(BaseModel):
    run_id: str = ""
    routine_name: str = "MTM Guatemala HBL Draft Generator"
    routine_version: str = "0.1.0"
    input_files: dict[str, str] = Field(default_factory=dict)
    template_file_hash: str = ""


class CanonicalHblData(BaseModel):
    metadata: Metadata = Field(default_factory=Metadata)
    scope: Scope = Field(default_factory=Scope)
    shipment: Shipment = Field(default_factory=Shipment)
    parties: Parties = Field(default_factory=Parties)
    routing: Routing = Field(default_factory=Routing)
    cargo: Cargo = Field(default_factory=Cargo)
    containers: list[Container] = Field(default_factory=list)
    charges: Charges = Field(default_factory=Charges)
    carrier_receipt: CarrierReceipt = Field(default_factory=CarrierReceipt)
    source_trace: SourceTrace = Field(default_factory=SourceTrace)
    qa: QA = Field(default_factory=QA)
    audit: Audit = Field(default_factory=Audit)
