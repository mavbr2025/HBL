from mtm_hbl.models.canonical import CanonicalHblData, Cargo, Container


def test_container_accepts_clickup_agent_aliases():
    container = Container.model_validate(
        {
            "container_number": "FDCU0491394",
            "seal": "CNDY52633",
            "type": "40HQ",
            "package_count": "42",
            "package_type": "CARTONS",
            "gross_weight": "9,750.000",
            "cbm": "68.000",
            "marks_and_numbers": "MOVESA",
        }
    )

    assert container.container_no == "FDCU0491394"
    assert container.seal_no == "CNDY52633"
    assert container.container_type == "40HQ"
    assert container.measurement == "68.000"


def test_container_canonical_names_take_precedence_over_aliases():
    container = Container.model_validate(
        {
            "container_no": "CANONICAL123",
            "container_number": "ALIAS123",
            "seal_no": "CANONICALSEAL",
            "seal": "ALIASSEAL",
            "container_type": "40HQ",
            "type": "20GP",
            "measurement": "68.000",
            "cbm": "20.000",
        }
    )

    assert container.container_no == "CANONICAL123"
    assert container.seal_no == "CANONICALSEAL"
    assert container.container_type == "40HQ"
    assert container.measurement == "68.000"


def test_cargo_accepts_cbm_alias_for_measurement():
    cargo = Cargo.model_validate({"description_raw": "ATV", "cbm": "340.000"})

    assert cargo.measurement == "340.000"


def test_canonical_hbl_json_accepts_mixed_container_codes():
    data = CanonicalHblData.model_validate(
        {
            "shipment": {"mtm_hbl_no": "WH26050094", "mbl_no": "ONEYNB5BI3679700"},
            "cargo": {"description_raw": "ATV", "measurement": "340.000"},
            "containers": [
                {
                    "container_number": "FDCU0491394",
                    "seal": "CNDY52633",
                    "type": "40HQ",
                    "gross_weight": "9,750.000",
                    "cbm": "68.000",
                },
                {
                    "container_no": "ONEU1710560",
                    "seal_no": "CNDY52663",
                    "container_type": "40HQ",
                    "gross_weight": "9,750.000",
                    "measurement": "68.000",
                },
            ],
        }
    )

    assert data.containers[0].container_no == "FDCU0491394"
    assert data.containers[0].seal_no == "CNDY52633"
    assert data.containers[0].container_type == "40HQ"
    assert data.containers[0].measurement == "68.000"
    assert data.containers[1].container_no == "ONEU1710560"
