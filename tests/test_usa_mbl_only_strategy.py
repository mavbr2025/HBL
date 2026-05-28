from mtm_hbl.extraction_engine.extractor import extract_container_details, extract_document_fields
from mtm_hbl.models.documents import LoadedDocument, PageText
from mtm_hbl.pipeline import PipelineInput, build_review_packet


def test_usa_origin_uses_carrier_mbl_parties_and_cargo(app_config):
    data = build_review_packet(
        PipelineInput(
            clickup_task_id="MTMLXGT-USA",
            clickup_values={
                "owner_country": "Guatemala",
                "hbl_number": "269822577",
                "pol": "CHARLESTON",
                "vessel_voyage": "SEASPAN SAIGON / 618S",
            },
            agent_hbl_values={
                "shipper": "AGENT SHIPPER",
                "consignee": "AGENT CONSIGNEE",
                "notify_party": "AGENT NOTIFY",
                "cargo_description": "AGENT CARGO",
                "total_packages": "99",
                "gross_weight": "99.000",
                "measurement": "9.000",
                "hbl_number": "269822577",
            },
            carrier_mbl_values={
                "shipper": "TREE LOGISTICS, LLC",
                "consignee": "MTM LOGIX GUATEMALA SOCIEDAD ANONIMA",
                "notify_party": "MTM LOGIX GUATEMALA\n10, CALLE 4-99 ZONA 21",
                "cargo_description": "4 containers said to contain 30 SKIDS",
                "total_packages": "30",
                "package_type": "SKIDS",
                "gross_weight": "37285.000",
                "measurement": "0.000",
                "mbl_number": "269822577",
                "port_of_loading": "Charleston",
                "port_of_discharge": "Santo Tomas de Castilla",
            },
        ),
        app_config,
    )

    assert data.parties.shipper.raw_text == "TREE LOGISTICS, LLC"
    assert data.parties.consignee.raw_text == "MTM LOGIX GUATEMALA SOCIEDAD ANONIMA"
    assert data.parties.notify_party.raw_text == "MTM LOGIX GUATEMALA\n10, CALLE 4-99 ZONA 21"
    assert data.cargo.description_raw == "4 containers said to contain 30 SKIDS"
    assert data.cargo.total_packages == "30"
    assert "carrier_mbl_only_source_applied" in {issue.id for issue in data.qa.soft_warnings}


def test_explicit_carrier_mbl_strategy_wins_without_usa_origin(app_config):
    data = build_review_packet(
        PipelineInput(
            clickup_task_id="manual-mbl-only",
            clickup_values={"owner_country": "Guatemala", "hbl_number": "HBL123"},
            agent_hbl_values={"shipper": "AGENT SHIPPER", "hbl_number": "HBL123"},
            carrier_mbl_values={
                "shipper": "CARRIER SHIPPER",
                "mbl_number": "MBL123",
            },
            source_strategy="carrier_mbl_only",
        ),
        app_config,
    )

    assert data.parties.shipper.raw_text == "CARRIER SHIPPER"
    assert "carrier_mbl_only_source_applied" in {issue.id for issue in data.qa.soft_warnings}


def test_extracts_maersk_mbl_layout_and_container_table():
    text = """
    MAERSK
    NON-NEGOTIABLE WAYBILL                                      SCAC MAEU
    B/L No.   269822577
    Shipper (As principal, where "care of", "c/o", or other variants used.) Booking No.
    TREE LOGISTICS, LLC
    1400 NW 107TH AVE STE. 401
    MIAMI, FL 33172
    Consignee
    MTM LOGIX GUATEMALA SOCIEDAD ANONIMA
    TAX ID: 109582985 3A. AV 131 ZONA 4, CP 01004
    EDIFICIO SEPTIMO, NIVEL 3, OFICINA 306
    TEL: 502 42170389
    Notify Party (see clause 22)
    MTM LOGIX GUATEMALA SOCIEDAD ANONIMA
    TAX ID: 109582985 3A. AV 131 ZONA 4, CP 01004
    Vessel                          Voyage No.
    SEASPAN SAIGON                  618S
    Port of Loading                 Port of Discharge        Place of Delivery
    Charleston                      Santo Tomas de Castilla  Chimaltenango
    PARTICULARS FURNISHED BY SHIPPER
    Kind of Packages; Description of goods; Marks and Numbers; Container No./Seal No.
    4 containers said to contain 30 SKIDS
    37285.000 KGS
    Below freight details will not be part of Original Bill of Lading unless requested by customer
    MRSU9379801 40 DRY 9'6 7 SKIDS 10115.000 KGS
    Shipper Seal : 00107255
    """
    document = LoadedDocument(
        path="maersk.pdf",
        pages=[PageText(page_number=1, text=text, extraction_method="embedded")],
        document_type="carrier_mbl",
    )

    values = extract_document_fields(document)
    containers = extract_container_details(document)

    assert values["mbl_number"] == "269822577"
    assert values["shipper"] == "TREE LOGISTICS, LLC\n1400 NW 107TH AVE STE. 401\nMIAMI, FL 33172"
    assert values["vessel_voyage"] == "SEASPAN SAIGON / 618S"
    assert values["port_of_loading"] == "Charleston"
    assert values["port_of_discharge"] == "Santo Tomas de Castilla"
    assert values["place_of_delivery"] == "Chimaltenango"
    assert values["total_packages"] == "30"
    assert values["gross_weight"] == "37285.000"
    assert containers == [
        {
            "container_no": "MRSU9379801",
            "seal_no": "00107255",
            "container_type": "40HC",
            "package_count": "7",
            "package_type": "SKIDS",
            "gross_weight": "10115.000",
            "measurement": "",
        }
    ]
