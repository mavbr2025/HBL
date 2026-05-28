from mtm_hbl.models.canonical import CanonicalHblData, QaIssue
from mtm_hbl.resolver.customer_rules import apply_customer_profile


def test_applies_learned_customer_charge_rows(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-2258"
    data.shipment.mtm_hbl_no = "CSA00049112"
    data.parties.consignee.raw_text = "CONSIGNEE SA"
    data.parties.notify_party.raw_text = "CONSIGNEE SA"
    data.qa.soft_warnings.append(
        QaIssue(
            id="freight_rate_missing_clickup",
            severity="soft_warning",
            message="missing",
        )
    )

    apply_customer_profile(data, app_config, "repuestos_acquaroni")

    assert len(data.charges.line_items) == 6
    assert data.charges.line_items[0].description == "Basic Ocean Freight 40HC"
    assert data.charges.line_items[0].rate == "2900.00"
    assert data.parties.notify_party.raw_text == "SAME AS CONSIGNEE"
    assert {issue.id for issue in data.qa.soft_warnings} == {
        "training_charge_rows_from_finished_hbl"
    }
    assert data.qa.manual_review_required


def test_applies_acquaroni_party_override_and_second_learned_example(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-2223"
    data.parties.consignee.raw_text = "SUPER AUTO REPUESTOS, S.A.\nGUATEMALA"
    data.parties.notify_party.raw_text = data.parties.consignee.raw_text

    apply_customer_profile(data, app_config, "repuestos_acquaroni")

    assert data.parties.consignee.raw_text.startswith("SUPER AUTO REPUESTOS SOCIEDAD ANONIMA")
    assert data.parties.delivery_apply_to.raw_text == data.parties.consignee.raw_text
    assert data.parties.notify_party.raw_text == "SAME AS CONSIGNEE"
    assert data.shipment.issue_date == "GUATEMALA, 17 DE JULIO DE 2025."
    assert data.shipment.number_of_originals == "THREE"
    assert len(data.charges.line_items) == 4
    assert data.charges.line_items[0].collect_amount == "26000.00"


def test_applies_approved_team_override_for_mtmlxgt_25972(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-25972"
    data.shipment.mtm_hbl_no = "GOSZX26042213"

    apply_customer_profile(data, app_config, "repuestos_acquaroni")

    assert len(data.containers) == 2
    assert data.containers[0].container_no == "TXGU8147634"
    assert data.containers[0].seal_no == "WHLX752778"
    assert data.containers[1].container_no == "WHSU5177865"
    assert data.cargo.total_packages == "1730"
    assert data.cargo.gross_weight == "37470.000"
    assert [line.description for line in data.charges.line_items] == [
        "Basic Ocean Freight 40HC",
        "Equipment Handling Charge 40HC",
        "Destination THC 40HC",
        "Doc Fee Destination",
    ]
    assert data.charges.line_items[-1].collect_amount == "200.00"
    assert {"approved_team_override_applied", "package_counts_total_only"} <= {
        issue.id for issue in data.qa.soft_warnings
    }


def test_applies_validated_acquaroni_rule_for_mtmlxgt_25811(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-25811"
    data.shipment.mtm_hbl_no = "GOSZX26041381"

    apply_customer_profile(data, app_config, "repuestos_acquaroni")

    assert data.shipment.mbl_no == "031G533916"
    assert data.shipment.vessel_voyage_display == "KOTA MANZANILLO / 025E"
    assert data.containers[0].container_no == "TXGU8147634"
    assert data.containers[0].seal_no == "WHLX752778"
    assert data.containers[0].package_count == "878"
    assert data.containers[1].container_no == "WHSU5177865"
    assert data.containers[1].package_count == "852"
    assert data.cargo.total_packages == "1730"
    assert data.cargo.gross_weight == "37470.000"
    assert [line.description for line in data.charges.line_items] == [
        "Basic Ocean Freight 40HC",
        "Equipment Handling Charge 40HC",
        "Destination THC 40HC",
        "Handling Fee",
        "Document Fee",
    ]
    assert data.charges.line_items[0].collect_amount == "6000.00"
    assert data.charges.line_items[-1].collect_amount == "200.00"


def test_applies_validated_eskolor_rule_for_mtmlxgt_25822(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-25822"
    data.shipment.mtm_hbl_no = "WH26040201"

    apply_customer_profile(data, app_config, "eskolor")

    assert data.shipment.mbl_no == "ONEYTPEG24594800"
    assert data.shipment.vessel_voyage_display == "HUMBOLDT EXPRESS 2617E"
    assert data.parties.notify_party.raw_text == "SAME AS CONSIGNEE"
    assert data.containers[0].container_no == "TRHU2244140"
    assert data.containers[0].seal_no == "TW49541AE"
    assert data.containers[0].container_type == "20GP"
    assert data.cargo.total_packages == "20"
    assert data.cargo.gross_weight == "17760.000"
    assert [line.description for line in data.charges.line_items] == [
        "Basic Ocean Freight 20GP",
        "Emergency Bunker Surcharge",
        "Handling Fee",
        "Doc Fee Destination",
        "Destination Charges",
    ]
    assert sum(float(line.collect_amount) for line in data.charges.line_items) == 3360.00


def test_applies_validated_antique_rule_for_mtmlxgt_25696(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-25696"
    data.shipment.mtm_hbl_no = "WH26040089"

    apply_customer_profile(data, app_config, "antique")

    assert data.shipment.mbl_no == "ONEYTAOG72023700"
    assert data.shipment.vessel_voyage_display == "HYUNDAI COURAGE / 0123E"
    assert data.parties.notify_party.raw_text == "SAME AS CONSIGNEE"
    assert data.containers[0].container_no == "TRHU2483015"
    assert data.containers[0].seal_no == "CN44692AW"
    assert data.containers[0].container_type == "20GP"
    assert data.cargo.total_packages == "7"
    assert data.cargo.gross_weight == "26300.000"
    assert [line.description for line in data.charges.line_items] == [
        "Basic Ocean Freight 20GP",
        "Emergency Bunker Surcharge",
        "Handling Fee",
        "Doc Fee Destination",
        "Destination Charges",
    ]
    assert sum(float(line.collect_amount) for line in data.charges.line_items) == 4360.00


def test_applies_validated_masesa_rule_for_mtmlxgt_25697(app_config):
    data = CanonicalHblData()
    data.shipment.clickup_task_id = "MTMLXGT-25697"
    data.shipment.mtm_hbl_no = "WH26040108"

    apply_customer_profile(data, app_config, "masesa")

    assert data.shipment.mbl_no == "ONEYNB5BI2587400"
    assert data.shipment.vessel_voyage_display == "HYUNDAI COURAGE / 123E"
    assert data.parties.notify_party.raw_text == "SAME AS CONSIGNEE"
    assert data.containers[0].container_no == "ONEU6264990"
    assert data.containers[0].seal_no == "CNDY08644"
    assert data.containers[0].container_type == "40HQ"
    assert data.cargo.total_packages == "119"
    assert data.cargo.gross_weight == "11282.000"
    assert [line.description for line in data.charges.line_items] == [
        "Basic Ocean Freight 40HC",
        "Emergency Bunker Surcharge",
        "Handling Fee",
        "Doc Fee Destination",
        "Destination Charges",
        "Inland Destination",
        "Customs Broker Destination",
    ]
    assert sum(float(line.collect_amount) for line in data.charges.line_items) == 4531.29
