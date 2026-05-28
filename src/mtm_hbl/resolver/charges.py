from decimal import Decimal, InvalidOperation
import re

from mtm_hbl.models.canonical import CanonicalHblData, QaIssue


def populate_charges_from_clickup(data: CanonicalHblData, clickup_values: dict[str, str]) -> None:
    rate = _format_money(clickup_values.get("freight_rate", ""))
    data.charges.charge_description = (
        clickup_values.get("freight_charge_description", "") or "Ocean Basic Freight"
    )
    data.charges.currency = clickup_values.get("freight_currency", "") or "USD"
    data.charges.unit = clickup_values.get("freight_unit", "") or "Per Container"
    data.charges.freight_payable_at = (
        clickup_values.get("freight_payable_at", "") or "GUATEMALA CITY, GUATEMALA"
    )
    data.charges.unit_rate = rate

    if not rate:
        data.qa.soft_warnings.append(
            QaIssue(
                id="freight_rate_missing_clickup",
                severity="soft_warning",
                field="charges.unit_rate",
                message="Freight rate was not found in ClickUp; charge row was left for review.",
                blocking_scope="none",
                recommended_action="Populate ClickUp freight rate or provide a manual override.",
            )
        )


def _format_money(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"-?[0-9][0-9,]*(?:\.[0-9]+)?", value)
    if not match:
        return ""
    try:
        number = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return ""
    return f"{number:.2f}"
