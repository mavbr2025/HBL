from decimal import Decimal

from mtm_hbl.config import AppConfig
from mtm_hbl.models.canonical import CanonicalHblData, QaIssue
from mtm_hbl.utils.values import decimal_from_display, is_blank, normalize_for_compare


class ValidationEngine:
    def __init__(self, app_config: AppConfig) -> None:
        self.app_config = app_config
        self.qa_rules = app_config.qa_rules

    def validate(self, data: CanonicalHblData, template_path: str | None = None) -> CanonicalHblData:
        self._validate_scope(data)
        self._validate_required_fields(data)
        self._validate_excel_mapping(data)
        self._validate_template_presence(data, template_path)
        self._validate_containers(data)
        self._validate_totals(data)
        self._validate_soft_warnings(data)
        self._finalize_flags(data)
        return data

    def _validate_scope(self, data: CanonicalHblData) -> None:
        owner_country = data.scope.owner_country.strip()
        if not owner_country:
            self._hard(data, "owner_country_missing", "scope.owner_country")
            return
        allowed = self.app_config.entity_rules["phase_1_allowed_owner_countries"]
        if owner_country not in allowed:
            self._hard(data, "owner_country_not_guatemala", "scope.owner_country", blocking_scope="draft")

    def _validate_required_fields(self, data: CanonicalHblData) -> None:
        checks = [
            ("hbl_number_missing", "shipment.mtm_hbl_no", data.shipment.mtm_hbl_no),
            ("mbl_number_missing", "shipment.mbl_no", data.shipment.mbl_no),
            ("shipper_missing", "parties.shipper.raw_text", data.parties.shipper.raw_text),
            ("consignee_missing", "parties.consignee.raw_text", data.parties.consignee.raw_text),
            ("pol_missing", "routing.port_of_loading", data.routing.port_of_loading),
            ("pod_missing", "routing.port_of_discharge", data.routing.port_of_discharge),
        ]
        for issue_id, field, value in checks:
            if is_blank(value):
                self._hard(data, issue_id, field)

    def _validate_excel_mapping(self, data: CanonicalHblData) -> None:
        mapping = self.app_config.excel_cell_mapping.get("cells", {})
        for key, spec in mapping.items():
            if spec.get("required") and not spec.get("cell"):
                self._hard(
                    data,
                    "required_excel_cell_mapping_unresolved",
                    f"excel_cell_mapping.{key}",
                    message=f"Required Excel cell mapping is unresolved for {key}.",
                    blocking_scope="draft",
                )

    def _validate_template_presence(self, data: CanonicalHblData, template_path: str | None) -> None:
        if template_path is None:
            return
        from pathlib import Path

        if not Path(template_path).exists():
            self._hard(
                data,
                "required_template_file_missing",
                "template",
                blocking_scope="draft",
            )

    def _validate_containers(self, data: CanonicalHblData) -> None:
        total_only_packages = self._has_soft_warning(data, "package_counts_total_only")
        if not data.containers:
            self._hard(data, "container_number_missing", "containers")
            self._hard(data, "seal_number_missing", "containers")
            if not total_only_packages:
                self._hard(data, "package_count_missing", "containers")
            self._hard(data, "gross_weight_missing", "containers")
            self._hard(data, "cbm_missing", "containers")
            return

        if len(data.containers) > 5:
            self._soft(data, "more_than_five_containers", "containers")

        for index, container in enumerate(data.containers):
            prefix = f"containers.{index}"
            if is_blank(container.container_no):
                self._hard(data, "container_number_missing", f"{prefix}.container_no")
            if is_blank(container.seal_no):
                self._hard(data, "seal_number_missing", f"{prefix}.seal_no")
            if is_blank(container.package_count) and not total_only_packages:
                self._hard(data, "package_count_missing", f"{prefix}.package_count")
            if is_blank(container.gross_weight):
                self._hard(data, "gross_weight_missing", f"{prefix}.gross_weight")
            if is_blank(container.measurement):
                self._hard(data, "cbm_missing", f"{prefix}.measurement")
            if "/" in container.seal_no or "\n" in container.seal_no:
                self._soft(data, "multiple_seals", f"{prefix}.seal_no")

    def _validate_totals(self, data: CanonicalHblData) -> None:
        package_sum = self._sum_decimal(container.package_count for container in data.containers)
        weight_sum = self._sum_decimal(container.gross_weight for container in data.containers)
        cbm_sum = self._sum_decimal(container.measurement for container in data.containers)

        total_packages = decimal_from_display(data.cargo.total_packages)
        total_weight = decimal_from_display(data.cargo.gross_weight)
        total_cbm = decimal_from_display(data.cargo.measurement)

        if total_packages is not None and package_sum is not None and package_sum != total_packages:
            self._hard(data, "package_total_mismatch", "cargo.total_packages")
        if total_weight is not None and weight_sum is not None and weight_sum != total_weight:
            self._hard(data, "gross_weight_total_mismatch", "cargo.gross_weight")
        if total_cbm is not None and cbm_sum is not None and cbm_sum != total_cbm:
            self._hard(data, "cbm_total_mismatch", "cargo.measurement")

    def _validate_soft_warnings(self, data: CanonicalHblData) -> None:
        if normalize_for_compare(data.parties.notify_party.raw_text) in {
            "same as consignee",
            "same as cnee",
        }:
            self._soft(data, "notify_same_as_consignee", "parties.notify_party.raw_text")

        if len(data.cargo.description_raw) > 900:
            self._soft(data, "long_cargo_description", "cargo.description_raw")

        for key, text in {
            "dangerous_goods_detected": data.cargo.description_raw,
            "reefer_cargo_detected": data.cargo.description_raw,
            "soc_container_detected": data.cargo.description_raw,
        }.items():
            lowered = text.casefold()
            if key == "dangerous_goods_detected" and any(
                token in lowered for token in ["dangerous", "hazard", "imo class", "un "]
            ):
                self._soft(data, key, "cargo.description_raw")
            if key == "reefer_cargo_detected" and any(
                token in lowered for token in ["reefer", "temperature", "temp:"]
            ):
                self._soft(data, key, "cargo.description_raw")
            if key == "soc_container_detected" and "soc" in lowered:
                self._soft(data, key, "cargo.description_raw")

    def _finalize_flags(self, data: CanonicalHblData) -> None:
        hard_ids = {issue.id for issue in data.qa.hard_errors}
        blockers = set(self.qa_rules["draft_generation"]["block_draft_when"])
        data.qa.draft_generation_allowed = not bool(hard_ids & blockers)
        data.qa.final_generation_allowed = False
        data.qa.manual_review_required = bool(data.qa.hard_errors or data.qa.soft_warnings)

    def _hard(
        self,
        data: CanonicalHblData,
        issue_id: str,
        field: str,
        message: str | None = None,
        blocking_scope: str = "final",
    ) -> None:
        if any(issue.id == issue_id and issue.field == field for issue in data.qa.hard_errors):
            return
        data.qa.hard_errors.append(
            QaIssue(
                id=issue_id,
                severity="hard_error",
                field=field,
                message=message or self.qa_rules["hard_errors"][issue_id],
                blocking_scope=blocking_scope,  # type: ignore[arg-type]
                recommended_action="Correct or manually approve handling before final/original issuance.",
            )
        )

    def _soft(self, data: CanonicalHblData, issue_id: str, field: str) -> None:
        if any(issue.id == issue_id and issue.field == field for issue in data.qa.soft_warnings):
            return
        data.qa.soft_warnings.append(
            QaIssue(
                id=issue_id,
                severity="soft_warning",
                field=field,
                message=self.qa_rules["soft_warnings"].get(issue_id, issue_id),
                blocking_scope="none",
                recommended_action="Review before approving draft generation.",
            )
        )

    @staticmethod
    def _sum_decimal(values: object) -> Decimal | None:
        total = Decimal("0")
        saw_value = False
        for value in values:
            number = decimal_from_display(str(value))
            if number is None:
                continue
            total += number
            saw_value = True
        return total if saw_value else None

    @staticmethod
    def _has_soft_warning(data: CanonicalHblData, issue_id: str) -> bool:
        return any(issue.id == issue_id for issue in data.qa.soft_warnings)
