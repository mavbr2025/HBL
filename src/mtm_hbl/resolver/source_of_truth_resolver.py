from dataclasses import dataclass
from typing import Any

from mtm_hbl.models.canonical import CanonicalHblData, FieldSource, QaIssue
from mtm_hbl.utils.values import is_blank, normalize_for_compare


@dataclass(frozen=True)
class Candidate:
    source: str
    value: str
    source_document: str = ""
    source_page: str = ""
    source_text: str = ""
    confidence: str = ""


class SourceOfTruthResolver:
    def resolve(self, data: CanonicalHblData, candidates: dict[str, list[Candidate]]) -> CanonicalHblData:
        self._resolve_hbl_number(data, candidates.get("hbl_number", []))
        self._resolve_mbl_number(data, candidates.get("mbl_number", []))
        self._resolve_vessel_voyage(data, candidates.get("vessel_voyage", []))
        self._trace_candidates(data, candidates)
        return data

    def _resolve_hbl_number(self, data: CanonicalHblData, candidates: list[Candidate]) -> None:
        if not candidates:
            return
        clickup = self._first(candidates, "clickup")
        agent = self._first(candidates, "agent_hbl")

        if agent and not is_blank(agent.value):
            data.shipment.agent_hbl_no = agent.value

        if (
            clickup
            and agent
            and not is_blank(clickup.value)
            and not is_blank(agent.value)
            and not self._matches(clickup.value, agent.value)
        ):
            self._add_hard_error(
                data,
                "hbl_number_conflict",
                "shipment.mtm_hbl_no",
                "HBL number conflicts between ClickUp and Agent HBL.",
            )
            return

        if clickup and not is_blank(clickup.value):
            data.shipment.mtm_hbl_no = clickup.value
            return

        self._add_hard_error(
            data,
            "hbl_number_missing",
            "shipment.mtm_hbl_no",
            (
                "ClickUp HBL custom field 8108af0b-9b7c-45aa-8d74-8e70567b93f0 "
                "is missing or was not provided. BL No. must come from this field."
            ),
        )
        if agent and not is_blank(agent.value):
            self._add_soft_warning(
                data,
                "agent_hbl_number_ignored",
                "shipment.agent_hbl_no",
                (
                    "Agent HBL number was extracted for trace only and was not used as BL No.; "
                    "ClickUp HBL custom field is the required source."
                ),
            )

    def _resolve_mbl_number(self, data: CanonicalHblData, candidates: list[Candidate]) -> None:
        carrier = self._first(candidates, "carrier_mbl")
        others = [candidate for candidate in candidates if candidate.source != "carrier_mbl"]

        if carrier and not is_blank(carrier.value):
            conflicts = [
                candidate
                for candidate in others
                if candidate.value and not self._matches(carrier.value, candidate.value)
            ]
            if conflicts:
                self._add_hard_error(
                    data,
                    "mbl_number_conflict",
                    "shipment.mbl_no",
                    "MBL number conflicts between Carrier MBL and another source.",
                )
            data.shipment.mbl_no = carrier.value
            return

        fallback = next((candidate for candidate in others if not is_blank(candidate.value)), None)
        if fallback:
            data.shipment.mbl_no = fallback.value
            self._add_soft_warning(
                data,
                "mbl_number_from_secondary_source",
                "shipment.mbl_no",
                "Carrier MBL number was not extracted; using secondary source for draft review.",
            )

    def _resolve_vessel_voyage(self, data: CanonicalHblData, candidates: list[Candidate]) -> None:
        clickup = self._first(candidates, "clickup")
        selected = clickup if clickup and clickup.value else next(
            (candidate for candidate in candidates if candidate.value),
            None,
        )
        if not selected:
            return

        parts = selected.value.split("/", maxsplit=1)
        if len(parts) == 2:
            data.shipment.vessel = parts[0].strip()
            data.shipment.voyage = parts[1].strip()
        else:
            data.shipment.vessel = selected.value.strip()

        unique_values = {
            normalize_for_compare(candidate.value)
            for candidate in candidates
            if not is_blank(candidate.value)
        }
        if len(unique_values) > 1:
            self._add_soft_warning(
                data,
                "vessel_voyage_disagreement",
                "shipment.vessel",
                "Agent HBL and Carrier MBL disagree on vessel/voyage.",
            )

    def _trace_candidates(
        self, data: CanonicalHblData, candidates: dict[str, list[Candidate]]
    ) -> None:
        for field, field_candidates in candidates.items():
            for candidate in field_candidates:
                data.source_trace.field_sources.append(
                    FieldSource(
                        field=field,
                        value=candidate.value,
                        source_document=candidate.source_document or candidate.source,
                        source_page=candidate.source_page,
                        source_text=candidate.source_text,
                        confidence=candidate.confidence,
                    )
                )

    @staticmethod
    def _first(candidates: list[Candidate], source: str) -> Candidate | None:
        return next((candidate for candidate in candidates if candidate.source == source), None)

    @staticmethod
    def _matches(left: str, right: str) -> bool:
        return normalize_for_compare(left) == normalize_for_compare(right)

    @staticmethod
    def _add_hard_error(
        data: CanonicalHblData, issue_id: str, field: str, message: str
    ) -> None:
        data.qa.hard_errors.append(
            QaIssue(
                id=issue_id,
                severity="hard_error",
                field=field,
                message=message,
                blocking_scope="final",
                recommended_action="Resolve before final/original generation.",
            )
        )

    @staticmethod
    def _add_soft_warning(
        data: CanonicalHblData, issue_id: str, field: str, message: str
    ) -> None:
        data.qa.soft_warnings.append(
            QaIssue(
                id=issue_id,
                severity="soft_warning",
                field=field,
                message=message,
                blocking_scope="none",
                recommended_action="Review before approving draft generation.",
            )
        )
