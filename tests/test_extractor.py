from mtm_hbl.extraction_engine.extractor import extract_container_details, extract_document_fields
from mtm_hbl.models.documents import LoadedDocument, PageText


def document(text: str, document_type: str = "agent_hbl") -> LoadedDocument:
    return LoadedDocument(
        path="fixture.pdf",
        document_type=document_type,
        pages=[PageText(page_number=1, text=text)],
    )


def test_extracts_line_based_agent_hbl_parties_and_routing():
    text = """N/M 315 CARTONS
MOTORCYCLE IN CBU CONDITION
45045.000KGS
199.527CBM
THREE HUNDRED AND FIFTEEN CARTONS ONLY.
CHONGQING SHINERAY MOTORCYCLE CO., LTD.
NO.8 SHINERAY ROAD,HANGU TOWN JIULONGPO DISTRICT,
CHONGQING CHINA
TEL: 86-23-65733915   FAX: 86-23-65733901
DORAL IMPORTACIONES S.A.
3 AVENIDA 8-16 ZONA 9,GUATEMALA C.A
TAX ID:4326853-6
TEL: (502) 2313-0000
SAME AS CONSIGNEE
JIANGMEN,CHINA
FU LI 388
PUERTO QUETZAL,GUATEMALA PUERTO QUETZAL,GUATEMALA
"""

    values = extract_document_fields(document(text))

    assert values["shipper"].startswith("CHONGQING SHINERAY")
    assert values["consignee"] == (
        "DORAL IMPORTACIONES S.A.\n"
        "3 AVENIDA 8-16 ZONA 9,GUATEMALA C.A\n"
        "TAX ID:4326853-6\n"
        "TEL: (502) 2313-0000"
    )
    assert values["port_of_discharge"] == "PUERTO QUETZAL,GUATEMALA"
    assert values["place_of_delivery"] == "PUERTO QUETZAL,GUATEMALA"


def test_extracts_ocr_labeled_agent_hbl_parties_and_routing():
    text = (
        "Shipper /E t AND C FASTENER TECHNOLOGY CO. LTD. 92A.NO.369 JIANG SU ROAD "
        "Consignoe MULTIMATERIALES, S.A. 7 AVENIDA,33-85,BODEGA 4 TEL: 502-2429-6700 "
        "Notity Party (complote name and address) LEON FASTENERS 5900 BALCONES DR "
        "Place of Receip/Date SHANGHAI,CHINA Port of Loading SHANGHAI,CHINA "
        "ORIGINAL BILL OF LADING Vessel Voy. No. ONE SERENITY 2612E "
        "Port of Discharge Place of Delivery PUERTO QUETZAL,GUATEMALA PUERTO QUETZAL,GUATEMALA "
        "Description of Goods"
    )

    values = extract_document_fields(document(text))

    assert "MULTIMATERIALES" in values["consignee"]
    assert values["place_of_receipt"] == "SHANGHAI,CHINA"
    assert values["port_of_loading"] == "SHANGHAI,CHINA"
    assert values["vessel_voyage"] == "ONE SERENITY 2612E"


def test_extracts_repeated_container_details():
    text = """TCLU7810866/CNCU02863/40HQ
105CARTONS/15015.000KGS/66.509CBM
ONEU0060243/CNCU02861/40HQ
105CARTONS/15015.000KGS/66.509CBM
"""

    containers = extract_container_details(document(text))

    assert len(containers) == 2
    assert containers[1]["container_no"] == "ONEU0060243"
    assert containers[1]["package_count"] == "105"


def test_extracts_syntrans_layout_and_tolerates_container_suffixes():
    text = """FRIC ROT S.A.I.C..
SYNNGB25SE061817 SYNNGB25SE06181701
REPUBLICA ORIENTAL DEL URUGUAY 2627
177YNWNWN8643EA
ROSARIO SANTA FE ARGENTINA
PH 54 11 5550 1709
SUPER AUTO REPUESTOS, S.A. MTM LOGIX GUATEMALA SOCIEDAD ANONIMA
7A. AVENIDA 1-54, ZONA 4 NIT: 109582985
GUATEMALA, GUATEMALA 3A. AV 13-78 ZONA 10 TORRE CITIBANK NIVEL 8
PH:2277-9720 GUATEMALA
NIT: 26293331 CIUDAD, Guatemala. CP:01010
cesar@mtmlogix.com
SAME AS CONSIGNEE
NINGBO
ONE SPARKLE V.2524E NINGBO
PUERTO QUETZAL PUERTO QUETZAL
PALLET NO.
SHIPPER'S LOAD,COUNT & SEAL
157 45306.770 KGS 229.928 CBM
PALLETS
SHOCK ABSORBER
CY / CY
PART OF 4X40'HQ
MSBU5279776/FX41045658/40'HQ
36 PALLETS/9229.690 KGS/49.851 CBM
UETU7080545/FX41067322/40'HQ THREE(3)
42 PALLETS/12060.700 KGS/62.220 CBM
FREIGHT COLLECT
2026/5/7
"""

    values = extract_document_fields(document(text))
    containers = extract_container_details(document(text))

    assert values["hbl_number"] == "SYNNGB25SE06181701"
    assert values["shipper"].startswith("FRIC ROT")
    assert "SUPER AUTO REPUESTOS" in values["consignee"]
    assert values["cargo_description"] == (
        "1 X 40HQ CONTAINER\n"
        "157 PALLET(S)\n"
        "SHOCK ABSORBER\n"
        "157 PALLETS IN TOTAL"
    )
    assert len(containers) == 2
    assert containers[-1]["container_no"] == "UETU7080545"


def test_extracts_msc_mbl_number_and_route():
    text = """MEDITERRANEAN SHIPPING COMPANY S.A. BILL OF LADING No. MEDUJL116244
VESSEL AND VOYAGE NO (see Clause 8 & 9) PORT OF LOADING PLACE OF RECEIPT: (Combined Transport ONLY - see Clause 1 & 5.2)
ONE SPARKLE - 2524E NINGBO XXXXXXXXXXXXXXXX
BOOKING REF. (or) SHIPPER'S REF. PORT OF DISCHARGE PLACE OF DELIVERY : (Combined Transport ONLY - see Clause 1 & 5.2)
177YNWNWN8643EA XXXXXXXXXXXXXXXX PUERTO QUETZAL, GUATEMALA XXXXXXXXXXXXXXXX
Total Items : 157
Total Gross Weight : 45306.770 Kgs.
Total : 45,306.770 kgs. 229.928 cu. m.
"""

    values = extract_document_fields(document(text, "carrier_mbl"))

    assert values["mbl_number"] == "MEDUJL116244"
    assert values["vessel_voyage"] == "ONE SPARKLE 2524E"
    assert values["port_of_loading"] == "NINGBO PT, CHINA"
    assert values["port_of_discharge"] == "PUERTO QUETZAL, GUATEMALA"


def test_prefers_full_one_mbl_when_short_number_appears_first():
    text = """BILL OF LADING NO.
OSAG08019900 ONEYOSAG08019900
VESSEL VOYAGE: SMOOTH WIND 016S B/L NO.: ONEYOSAG08019900
"""

    values = extract_document_fields(document(text, "carrier_mbl"))

    assert values["mbl_number"] == "ONEYOSAG08019900"


def test_extracts_grand_ocean_hbl_layout_with_ocr_hbl_correction():
    text = """
1.Shipper ZHEJIANG SENGEN AUTO PARTS CO.. LTD.
| BILNo. GOSZX28042213
GRAND OCEAN SHIPPING CO.,LTD
3 Notify party (No claim shall attach for failure to notify)
SAME AS CONSIGNEE
NINGBO,CHINA
Ocaan PANG 184 Portal loadin
VarFSGH 184 NINGBO,CHINA
PUERTO QUETZAL,GUATEMALA | PUERTO QUETZAL,GUATEMALA
SHIPPER'S LOAD,COUNT & SEAL
(1X20'GP, 2X40'HQ) CONTAINERS S.T.C. 47855.000KGS 164.0000CBM
SHOSEN 2114
CARTONS
GUATEMALA.C.B. SHOCK ABSORBER
FREIGHT COLLECT
2026/5/7
"""

    values = extract_document_fields(document(text, "agent_hbl"))

    assert values["hbl_number"] == "GOSZX26042213"
    assert values["vessel_voyage"] == "YM FOUNTAIN 184E"
    assert values["total_packages"] == "2114"
    assert values["cargo_description"].endswith("SHOCK ABSORBER")
    assert values["freight_term"] == "FREIGHT COLLECT"


def test_extracts_wan_hai_mbl_number_and_vessel():
    text = """
WAN HAI
Shipper B/L IINb: 031G537638
Ocean vessel/Voy No
YM FOUNTAIN 184E
Port of loading Place of receipt
NINGBO, CHINA NINGBO, CHINA
Port of discharge Place of delivery
PUERTO QUETZAL, GUATEMALA PUERTO QUETZAL, GUATEMALA
"""

    values = extract_document_fields(document(text, "carrier_mbl"))

    assert values["mbl_number"] == "031G537638"
    assert values["vessel_voyage"] == "YM FOUNTAIN 184E"
