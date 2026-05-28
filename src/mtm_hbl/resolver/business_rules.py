from mtm_hbl.config import AppConfig
from mtm_hbl.models.canonical import CanonicalHblData, QaIssue
from mtm_hbl.utils.values import is_blank, normalize_for_compare


def apply_team_hbl_business_rules(
    data: CanonicalHblData,
    app_config: AppConfig,
    *,
    agent_notify_party: str = "",
    notify_party_override: str = "",
    delivery_apply_to_override: str = "",
    use_notify_default: bool = True,
) -> CanonicalHblData:
    rules = app_config.hbl_business_rules.get("party_blocks", {})
    consignee = data.parties.consignee.raw_text

    notify_rules = rules.get("notify_party", {})
    if notify_party_override:
        data.parties.notify_party.raw_text = notify_party_override
    elif use_notify_default and notify_rules.get("default_source") == "consignee":
        data.parties.notify_party.raw_text = consignee

    if (
        use_notify_default
        and
        notify_rules.get("warn_when_agent_notify_differs")
        and agent_notify_party
        and data.parties.notify_party.raw_text
        and normalize_for_compare(agent_notify_party)
        != normalize_for_compare(data.parties.notify_party.raw_text)
    ):
        data.qa.soft_warnings.append(
            QaIssue(
                id="agent_notify_party_differs_from_mtm_default",
                severity="soft_warning",
                field="parties.notify_party.raw_text",
                message=(
                    "Agent HBL Notify Party differs from MTM HBL default; "
                    "MTM draft uses consignee per team-produced HBL rule."
                ),
                blocking_scope="none",
                recommended_action="Review whether an explicit notify override is needed.",
            )
        )

    delivery_rules = rules.get("delivery_apply_to", {})
    if delivery_apply_to_override:
        data.parties.delivery_apply_to.raw_text = delivery_apply_to_override
    elif delivery_rules.get("default_source") == "consignee":
        data.parties.delivery_apply_to.raw_text = consignee

    return data


def apply_vessel_voyage_rules(
    data: CanonicalHblData,
    app_config: AppConfig,
    *,
    clickup_vessel_voyage: str = "",
) -> CanonicalHblData:
    rules = app_config.hbl_business_rules.get("vessel_voyage", {})
    if clickup_vessel_voyage:
        parts = clickup_vessel_voyage.split("/", maxsplit=1)
        if len(parts) == 2:
            data.shipment.vessel = parts[0].strip()
            data.shipment.voyage = parts[1].strip()
        else:
            data.shipment.vessel = clickup_vessel_voyage.strip()
            data.shipment.voyage = ""
        return data

    if rules.get("primary_source") == "clickup" and not rules.get("allow_agent_hbl_fallback", True):
        data.shipment.vessel = ""
        data.shipment.voyage = ""
        if rules.get("warn_when_missing_clickup"):
            data.qa.soft_warnings.append(
                QaIssue(
                    id="vessel_voyage_missing_clickup",
                    severity="soft_warning",
                    field="shipment.vessel",
                    message="Vessel/voyage must come from ClickUp; no ClickUp value was provided.",
                    blocking_scope="none",
                    recommended_action="Add/confirm Vessel/Voyage in ClickUp or review override.",
                )
            )
    return data
