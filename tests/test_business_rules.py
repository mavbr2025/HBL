from mtm_hbl.models.canonical import CanonicalHblData
from mtm_hbl.resolver.business_rules import (
    apply_team_hbl_business_rules,
    apply_vessel_voyage_rules,
)


def issue_ids(data):
    return {issue.id for issue in data.qa.soft_warnings}


def test_notify_and_delivery_apply_to_default_to_consignee(app_config):
    data = CanonicalHblData()
    data.parties.consignee.raw_text = "CONSIGNEE SA\nADDRESS"

    apply_team_hbl_business_rules(
        data,
        app_config,
        agent_notify_party="DIFFERENT NOTIFY",
    )

    assert data.parties.notify_party.raw_text == "CONSIGNEE SA\nADDRESS"
    assert data.parties.delivery_apply_to.raw_text == "CONSIGNEE SA\nADDRESS"
    assert "agent_notify_party_differs_from_mtm_default" in issue_ids(data)


def test_notify_override_wins_over_consignee_default(app_config):
    data = CanonicalHblData()
    data.parties.consignee.raw_text = "CONSIGNEE SA"

    apply_team_hbl_business_rules(
        data,
        app_config,
        notify_party_override="OVERRIDE NOTIFY",
    )

    assert data.parties.notify_party.raw_text == "OVERRIDE NOTIFY"


def test_vessel_voyage_requires_clickup_value(app_config):
    data = CanonicalHblData()
    data.shipment.vessel = "AGENT VESSEL"

    apply_vessel_voyage_rules(data, app_config, clickup_vessel_voyage="")

    assert data.shipment.vessel == ""
    assert "vessel_voyage_missing_clickup" in issue_ids(data)


def test_clickup_vessel_voyage_populates_shipment(app_config):
    data = CanonicalHblData()

    apply_vessel_voyage_rules(data, app_config, clickup_vessel_voyage="NYK LAURA 0665E")

    assert data.shipment.vessel == "NYK LAURA 0665E"
