from mtm_hbl.models.canonical import CanonicalHblData
from mtm_hbl.resolver.source_of_truth_resolver import Candidate, SourceOfTruthResolver


def test_hbl_mismatch_between_clickup_and_agent_is_hard_error():
    data = CanonicalHblData()
    SourceOfTruthResolver().resolve(
        data,
        {
            "hbl_number": [
                Candidate("clickup", "GOSZX26012025"),
                Candidate("agent_hbl", "OTHER26012025"),
            ]
        },
    )

    assert {issue.id for issue in data.qa.hard_errors} == {"hbl_number_conflict"}


def test_hbl_requires_clickup_custom_field_and_ignores_agent_fallback():
    data = CanonicalHblData()
    SourceOfTruthResolver().resolve(
        data,
        {
            "hbl_number": [
                Candidate("clickup", ""),
                Candidate("agent_hbl", "GOSZX26012025"),
            ]
        },
    )

    assert data.shipment.mtm_hbl_no == ""
    assert data.shipment.agent_hbl_no == "GOSZX26012025"
    assert {issue.id for issue in data.qa.hard_errors} == {"hbl_number_missing"}
    assert {issue.id for issue in data.qa.soft_warnings} == {"agent_hbl_number_ignored"}


def test_hbl_conflict_blocks_when_clickup_and_agent_differ():
    data = CanonicalHblData()
    SourceOfTruthResolver().resolve(
        data,
        {
            "hbl_number": [
                Candidate("clickup", "GOSZX26041381"),
                Candidate("agent_hbl", "GOSZX26042213"),
            ]
        },
    )

    assert data.shipment.mtm_hbl_no == ""
    assert {issue.id for issue in data.qa.hard_errors} == {"hbl_number_conflict"}


def test_mbl_mismatch_between_carrier_and_clickup_is_hard_error():
    data = CanonicalHblData()
    SourceOfTruthResolver().resolve(
        data,
        {
            "mbl_number": [
                Candidate("carrier_mbl", "NB5BFBH19600"),
                Candidate("clickup", "DIFFERENT"),
            ]
        },
    )

    assert data.shipment.mbl_no == "NB5BFBH19600"
    assert {issue.id for issue in data.qa.hard_errors} == {"mbl_number_conflict"}
