from mtm_hbl.config import AppConfig
from mtm_hbl.models.canonical import CanonicalHblData


def populate_carrier_receipt(data: CanonicalHblData, app_config: AppConfig) -> CanonicalHblData:
    count = len(data.containers)
    words = app_config.container_words.get(count, str(count))
    data.carrier_receipt.container_count_numeric = str(count) if count else ""
    data.carrier_receipt.container_count_words = words if count else ""
    if count:
        data.carrier_receipt.display_text_line_1 = f"{words} CONTAINER"
        data.carrier_receipt.display_text_line_2 = str(count)
    return data
