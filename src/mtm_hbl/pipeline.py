from dataclasses import dataclass, field

from mtm_hbl.config import AppConfig
from mtm_hbl.models.canonical import CanonicalHblData, QaIssue
from mtm_hbl.resolver.business_rules import (
    apply_team_hbl_business_rules,
    apply_vessel_voyage_rules,
)
from mtm_hbl.resolver.charges import populate_charges_from_clickup
from mtm_hbl.resolver.customer_rules import apply_customer_profile
from mtm_hbl.resolver.source_of_truth_resolver import Candidate, SourceOfTruthResolver
from mtm_hbl.validation.carrier_receipt import populate_carrier_receipt
from mtm_hbl.validation.validation_engine import ValidationEngine


@dataclass
class PipelineInput:
    clickup_task_id: str
    clickup_values: dict[str, str] = field(default_factory=dict)
    agent_hbl_values: dict[str, str] = field(default_factory=dict)
    carrier_mbl_values: dict[str, str] = field(default_factory=dict)
    template_path: str | None = None
    customer_slug: str = ""
    source_strategy: str = ""


def build_review_packet(pipeline_input: PipelineInput, app_config: AppConfig) -> CanonicalHblData:
    data = CanonicalHblData()
    data.shipment.clickup_task_id = pipeline_input.clickup_task_id

    clickup = pipeline_input.clickup_values
    agent = pipeline_input.agent_hbl_values
    carrier = pipeline_input.carrier_mbl_values
    use_carrier_mbl_only = _uses_carrier_mbl_only(pipeline_input)
    document_primary = carrier if use_carrier_mbl_only else agent
    document_secondary = agent if use_carrier_mbl_only else carrier

    data.scope.owner_country = clickup.get("owner_country", "")
    if data.scope.owner_country == "Guatemala":
        entity = app_config.entity_rules["entity_by_owner_country"]["Guatemala"]
        data.scope.issuing_entity = entity["issuing_entity_name"]
        data.shipment.issue_place = entity["issue_place"]

    data.parties.shipper.raw_text = document_primary.get(
        "shipper", document_secondary.get("shipper", "")
    )
    data.parties.consignee.raw_text = document_primary.get(
        "consignee", document_secondary.get("consignee", "")
    )
    agent_notify_party = agent.get("notify_party", "")
    selected_notify_party = document_primary.get(
        "notify_party", document_secondary.get("notify_party", "")
    )
    data.parties.notify_party.raw_text = selected_notify_party
    data.parties.delivery_apply_to.raw_text = document_primary.get(
        "delivery_apply_to", document_secondary.get("delivery_apply_to", "")
    )
    data.cargo.description_raw = document_primary.get(
        "cargo_description", document_secondary.get("cargo_description", "")
    )
    data.cargo.total_packages = document_primary.get(
        "total_packages", document_secondary.get("total_packages", "")
    )
    data.cargo.package_type = document_primary.get(
        "package_type", document_secondary.get("package_type", "")
    )
    data.cargo.gross_weight = document_primary.get(
        "gross_weight", document_secondary.get("gross_weight", "")
    )
    data.cargo.measurement = document_primary.get(
        "measurement", document_secondary.get("measurement", "")
    )

    data.routing.place_of_receipt = carrier.get(
        "place_of_receipt", agent.get("place_of_receipt", clickup.get("place_of_receipt", ""))
    )
    data.routing.port_of_loading = carrier.get(
        "port_of_loading", agent.get("port_of_loading", clickup.get("pol", ""))
    )
    data.routing.port_of_discharge = carrier.get(
        "port_of_discharge", agent.get("port_of_discharge", clickup.get("pod", ""))
    )
    data.routing.place_of_delivery = carrier.get(
        "place_of_delivery", agent.get("place_of_delivery", clickup.get("place_of_delivery", ""))
    )

    data.shipment.freight_term = clickup.get("freight_term", agent.get("freight_term", ""))
    populate_charges_from_clickup(data, clickup)
    if use_carrier_mbl_only:
        _append_carrier_mbl_only_warning(data)

    candidates = {
        "hbl_number": [
            Candidate("clickup", clickup.get("hbl_number", "")),
            Candidate("agent_hbl", agent.get("hbl_number", "")),
        ],
        "mbl_number": [
            Candidate("carrier_mbl", carrier.get("mbl_number", "")),
            Candidate("clickup", clickup.get("mbl_number", "")),
            Candidate("agent_hbl", agent.get("mbl_number", "")),
        ],
        "vessel_voyage": [
            Candidate("clickup", clickup.get("vessel_voyage", "")),
            Candidate("agent_hbl", agent.get("vessel_voyage", "")),
            Candidate("carrier_mbl", carrier.get("vessel_voyage", "")),
        ],
    }
    SourceOfTruthResolver().resolve(data, candidates)
    apply_team_hbl_business_rules(
        data,
        app_config,
        agent_notify_party=agent_notify_party,
        notify_party_override=clickup.get("notify_party_override", ""),
        delivery_apply_to_override=clickup.get("delivery_apply_to_override", ""),
        use_notify_default=not use_carrier_mbl_only,
    )
    apply_vessel_voyage_rules(
        data,
        app_config,
        clickup_vessel_voyage=clickup.get("vessel_voyage", ""),
    )
    apply_customer_profile(data, app_config, pipeline_input.customer_slug)
    populate_carrier_receipt(data, app_config)
    ValidationEngine(app_config).validate(data, template_path=pipeline_input.template_path)
    return data


USA_ORIGIN_TOKENS = (
    "UNITED STATES",
    " U.S.",
    " USA",
    "CHARLESTON",
    "SAVANNAH",
    "HOUSTON",
    "MIAMI",
    "LOS ANGELES",
    "LONG BEACH",
    "NORFOLK",
    "NEW YORK",
    "NEWARK",
    "OAKLAND",
    "SEATTLE",
    "TACOMA",
    "PORT EVERGLADES",
)


def _uses_carrier_mbl_only(pipeline_input: PipelineInput) -> bool:
    if pipeline_input.source_strategy == "carrier_mbl_only":
        return True
    values = pipeline_input.clickup_values | pipeline_input.agent_hbl_values | pipeline_input.carrier_mbl_values
    origin_text = " ".join(
        str(values.get(key, ""))
        for key in ["place_of_receipt", "port_of_loading", "pol"]
    ).upper()
    return any(token in origin_text for token in USA_ORIGIN_TOKENS)


def _append_carrier_mbl_only_warning(data: CanonicalHblData) -> None:
    if any(issue.id == "carrier_mbl_only_source_applied" for issue in data.qa.soft_warnings):
        return
    data.qa.soft_warnings.append(
        QaIssue(
            id="carrier_mbl_only_source_applied",
            severity="soft_warning",
            field="source_strategy",
            message=(
                "Carrier MBL-only source strategy was applied for a USA-origin bill of lading."
            ),
            blocking_scope="none",
            recommended_action="Review extracted MBL fields before approving draft generation.",
        )
    )
    data.qa.manual_review_required = True
