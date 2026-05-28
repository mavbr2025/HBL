from pathlib import Path

import pytest

from mtm_hbl.config import AppConfig
from mtm_hbl.models.canonical import CanonicalHblData, Container


@pytest.fixture()
def app_config() -> AppConfig:
    return AppConfig(Path("config"))


def valid_data() -> CanonicalHblData:
    data = CanonicalHblData()
    data.scope.owner_country = "Guatemala"
    data.shipment.clickup_task_id = "task-1"
    data.shipment.mtm_hbl_no = "GOSZX26012025"
    data.shipment.mbl_no = "NB5BFBH19600"
    data.parties.shipper.raw_text = "SHIPPER SA\nADDRESS"
    data.parties.consignee.raw_text = "CONSIGNEE SA\nADDRESS"
    data.parties.notify_party.raw_text = "NOTIFY SA\nADDRESS"
    data.routing.port_of_loading = "YANTIAN"
    data.routing.port_of_discharge = "PUERTO QUETZAL"
    data.cargo.description_raw = "AUTO PARTS"
    data.cargo.total_packages = "10"
    data.cargo.gross_weight = "1000.00"
    data.cargo.measurement = "12.50"
    data.containers = [
        Container(
            container_no="ABCD1234567",
            seal_no="SEAL123",
            package_count="10",
            gross_weight="1000.00",
            measurement="12.50",
        )
    ]
    return data
