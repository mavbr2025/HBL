from mtm_hbl.models.canonical import CanonicalHblData
from mtm_hbl.resolver.charges import populate_charges_from_clickup


def test_populate_charges_from_clickup_formats_rate():
    data = CanonicalHblData()

    populate_charges_from_clickup(
        data,
        {
            "freight_rate": "USD 3,000",
            "freight_currency": "USD",
            "freight_unit": "Per Container",
            "freight_charge_description": "Ocean Basic Freight",
            "freight_payable_at": "GUATEMALA CITY, GUATEMALA",
        },
    )

    assert data.charges.unit_rate == "3000.00"
    assert data.charges.currency == "USD"
    assert data.charges.unit == "Per Container"
    assert data.charges.charge_description == "Ocean Basic Freight"
    assert not data.qa.soft_warnings


def test_missing_freight_rate_warns():
    data = CanonicalHblData()

    populate_charges_from_clickup(data, {})

    assert data.charges.unit_rate == ""
    assert {issue.id for issue in data.qa.soft_warnings} == {"freight_rate_missing_clickup"}
