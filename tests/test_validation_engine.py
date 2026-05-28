from mtm_hbl.models.canonical import Container, QaIssue
from mtm_hbl.validation.validation_engine import ValidationEngine

from tests.conftest import valid_data


def issue_ids(data, severity):
    issues = data.qa.hard_errors if severity == "hard" else data.qa.soft_warnings
    return {issue.id for issue in issues}


def test_owner_country_missing_blocks_draft(app_config):
    data = valid_data()
    data.scope.owner_country = ""

    ValidationEngine(app_config).validate(data)

    assert "owner_country_missing" in issue_ids(data, "hard")
    assert data.qa.draft_generation_allowed is False
    assert data.qa.final_generation_allowed is False


def test_owner_country_not_guatemala_blocks_draft(app_config):
    data = valid_data()
    data.scope.owner_country = "Mexico"

    ValidationEngine(app_config).validate(data)

    assert "owner_country_not_guatemala" in issue_ids(data, "hard")
    assert data.qa.draft_generation_allowed is False


def test_owner_country_guatemala_passes_scope(app_config):
    data = valid_data()

    ValidationEngine(app_config).validate(data)

    assert "owner_country_missing" not in issue_ids(data, "hard")
    assert "owner_country_not_guatemala" not in issue_ids(data, "hard")
    assert data.qa.final_generation_allowed is False


def test_hbl_number_missing_blocks_draft(app_config):
    data = valid_data()
    data.shipment.mtm_hbl_no = ""

    ValidationEngine(app_config).validate(data)

    assert "hbl_number_missing" in issue_ids(data, "hard")
    assert data.qa.draft_generation_allowed is False


def test_mbl_number_missing_is_hard_error(app_config):
    data = valid_data()
    data.shipment.mbl_no = ""

    ValidationEngine(app_config).validate(data)

    assert "mbl_number_missing" in issue_ids(data, "hard")
    assert data.qa.final_generation_allowed is False


def test_missing_container_number(app_config):
    data = valid_data()
    data.containers[0].container_no = ""

    ValidationEngine(app_config).validate(data)

    assert "container_number_missing" in issue_ids(data, "hard")


def test_missing_seal_number(app_config):
    data = valid_data()
    data.containers[0].seal_no = ""

    ValidationEngine(app_config).validate(data)

    assert "seal_number_missing" in issue_ids(data, "hard")


def test_missing_gross_weight(app_config):
    data = valid_data()
    data.containers[0].gross_weight = ""

    ValidationEngine(app_config).validate(data)

    assert "gross_weight_missing" in issue_ids(data, "hard")


def test_missing_cbm(app_config):
    data = valid_data()
    data.containers[0].measurement = ""

    ValidationEngine(app_config).validate(data)

    assert "cbm_missing" in issue_ids(data, "hard")


def test_missing_package_count(app_config):
    data = valid_data()
    data.containers[0].package_count = ""

    ValidationEngine(app_config).validate(data)

    assert "package_count_missing" in issue_ids(data, "hard")


def test_total_only_package_override_allows_blank_container_package_counts(app_config):
    data = valid_data()
    data.containers[0].package_count = ""
    data.qa.soft_warnings.append(
        QaIssue(
            id="package_counts_total_only",
            severity="soft_warning",
            field="containers.package_count",
            message="Only total package count was approved.",
        )
    )

    ValidationEngine(app_config).validate(data)

    assert "package_count_missing" not in issue_ids(data, "hard")


def test_package_total_mismatch(app_config):
    data = valid_data()
    data.cargo.total_packages = "9"

    ValidationEngine(app_config).validate(data)

    assert "package_total_mismatch" in issue_ids(data, "hard")


def test_gross_weight_total_mismatch(app_config):
    data = valid_data()
    data.cargo.gross_weight = "999.99"

    ValidationEngine(app_config).validate(data)

    assert "gross_weight_total_mismatch" in issue_ids(data, "hard")


def test_cbm_total_mismatch(app_config):
    data = valid_data()
    data.cargo.measurement = "12.49"

    ValidationEngine(app_config).validate(data)

    assert "cbm_total_mismatch" in issue_ids(data, "hard")


def test_notify_same_as_consignee_warning(app_config):
    data = valid_data()
    data.parties.notify_party.raw_text = "SAME AS CONSIGNEE"

    ValidationEngine(app_config).validate(data)

    assert "notify_same_as_consignee" in issue_ids(data, "soft")


def test_more_than_five_containers_warning(app_config):
    data = valid_data()
    base = data.containers[0]
    data.containers = [
        Container(
            container_no=f"ABCD123456{i}",
            seal_no=f"SEAL{i}",
            package_count="1",
            gross_weight="10",
            measurement="1",
        )
        for i in range(6)
    ]
    data.cargo.total_packages = "6"
    data.cargo.gross_weight = "60"
    data.cargo.measurement = "6"

    ValidationEngine(app_config).validate(data)

    assert base
    assert "more_than_five_containers" in issue_ids(data, "soft")


def test_multiple_seals_warning(app_config):
    data = valid_data()
    data.containers[0].seal_no = "SEAL1/SEAL2"

    ValidationEngine(app_config).validate(data)

    assert "multiple_seals" in issue_ids(data, "soft")


def test_long_cargo_description_warning(app_config):
    data = valid_data()
    data.cargo.description_raw = "A" * 901

    ValidationEngine(app_config).validate(data)

    assert "long_cargo_description" in issue_ids(data, "soft")


def test_final_generation_always_blocked_phase_1(app_config):
    data = valid_data()

    ValidationEngine(app_config).validate(data)

    assert data.qa.final_generation_allowed is False


def test_production_excel_mapping_is_resolved(app_config):
    data = valid_data()

    ValidationEngine(app_config).validate(data)

    assert "required_excel_cell_mapping_unresolved" not in issue_ids(data, "hard")
