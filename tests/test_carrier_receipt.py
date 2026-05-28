from mtm_hbl.models.canonical import CanonicalHblData, Container
from mtm_hbl.validation.carrier_receipt import populate_carrier_receipt


def test_carrier_receipt_uses_words_and_number(app_config):
    data = CanonicalHblData()
    data.containers = [Container(container_no=f"ABCD123456{i}") for i in range(5)]

    populate_carrier_receipt(data, app_config)

    assert data.carrier_receipt.display_text_line_1 == "FIVE CONTAINER"
    assert data.carrier_receipt.display_text_line_2 == "5"
