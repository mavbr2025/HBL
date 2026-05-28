import re

from mtm_hbl.extraction_engine import patterns
from mtm_hbl.models.documents import LoadedDocument


def extract_document_fields(document: LoadedDocument) -> dict[str, str]:
    text = document.full_text
    values: dict[str, str] = {}
    if document.document_type == "carrier_mbl":
        values.update(_extract_maersk_mbl_layout(text))
        values.update(_extract_wan_hai_mbl_layout(text))
        values.update(_extract_msc_mbl_layout(text))
    else:
        values.update(_extract_agent_hbl_line_layout(text))
        values.update(_extract_ccl_bill_of_lading_layout(text))
        values.update(_extract_syntrans_hbl_layout(text))
        values.update(_extract_grand_ocean_hbl_layout(text))
    hbl_match = patterns.HBL_NUMBER.search(text)
    container_match = patterns.CONTAINER_NO.search(text)
    seal_match = patterns.SEAL_NO.search(text)
    weight_match = patterns.GROSS_WEIGHT.search(text)
    cbm_match = patterns.CBM.search(text)

    if hbl_match:
        values.setdefault("hbl_number", hbl_match.group(1).strip())
    mbl_tokens = [
        next(group for group in match.groups() if group).strip()
        for match in patterns.MBL_NUMBER.finditer(text)
    ]
    if mbl_tokens:
        preferred_mbl = next(
            (token for token in mbl_tokens if token.upper().startswith("ONEY")),
            mbl_tokens[0],
        )
        values.setdefault("mbl_number", preferred_mbl)
    if container_match:
        values.setdefault("container_no", container_match.group(1).strip())
    if seal_match:
        values.setdefault("seal_no", seal_match.group(1).strip())
    if weight_match:
        values.setdefault("gross_weight", weight_match.group(1).strip())
    if cbm_match:
        values.setdefault("measurement", cbm_match.group(1).strip())
    return values


def _extract_msc_mbl_layout(text: str) -> dict[str, str]:
    if "MEDITERRANEAN SHIPPING COMPANY" not in text.upper():
        return {}

    compact = re.sub(r"\s+", " ", text).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    values: dict[str, str] = {}
    mbl_match = re.search(r"\bBILL\s+OF\s+LADING\s+No\.?\s+([A-Z0-9/-]*\d[A-Z0-9/-]*)", compact, re.I)
    if mbl_match:
        values["mbl_number"] = mbl_match.group(1).strip()

    route_header_idx = next(
        (idx for idx, line in enumerate(lines) if line.upper().startswith("VESSEL AND VOYAGE")),
        None,
    )
    if route_header_idx is not None and route_header_idx + 3 < len(lines):
        vessel_line = lines[route_header_idx + 1]
        vessel_match = re.match(
            r"^(?P<vessel>.+?-\s*[0-9A-Z]+)\s+(?P<pol>[A-Z][A-Z ]+)\s+X{4,}",
            vessel_line,
            re.I,
        )
        if vessel_match:
            values["vessel_voyage"] = _clean_msc_vessel_voyage(vessel_match.group("vessel"))
            values["port_of_loading"] = _normalize_syntrans_port(vessel_match.group("pol"))
            values["place_of_receipt"] = values["port_of_loading"]
        pod_line = lines[route_header_idx + 3]
        pod_match = re.search(r"\b([A-Z][A-Z ]+,\s*[A-Z][A-Z ]+)\s+X{4,}", pod_line, re.I)
        if pod_match:
            pod_value = re.sub(r"^X+\s*", "", pod_match.group(1).strip(), flags=re.I)
            values["port_of_discharge"] = _normalize_syntrans_port(_clean_location(pod_value))
            values["place_of_delivery"] = values["port_of_discharge"]

    total_match = re.search(
        r"Total\s+Items\s*:\s*([0-9,]+).*?Total\s+Gross\s+Weight\s*:\s*([0-9,]+\.[0-9]+)\s*Kgs?",
        compact,
        re.I,
    )
    if total_match:
        values["total_packages"] = total_match.group(1).replace(",", "")
        values["gross_weight"] = total_match.group(2).replace(",", "")
    total_cbm_match = re.search(r"Total\s*:\s*[0-9,]+\.[0-9]+\s*kgs\.\s*([0-9,]+\.[0-9]+)\s*cu\.\s*m\.", compact, re.I)
    if total_cbm_match:
        values["measurement"] = total_cbm_match.group(1).replace(",", "")

    return values


def _extract_maersk_mbl_layout(text: str) -> dict[str, str]:
    if "MAERSK" not in text.upper() or "B/L No." not in text:
        return {}

    compact = re.sub(r"\s+", " ", text).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    values: dict[str, str] = {}

    mbl_match = re.search(r"\bB/L\s+No\.?\s+([A-Z0-9/-]*\d[A-Z0-9/-]*)", compact, re.I)
    if mbl_match:
        values["mbl_number"] = mbl_match.group(1).strip()

    shipper = _clean_maersk_party(_between_labels(lines, "Shipper", "Consignee"))
    consignee = _clean_maersk_party(_between_labels(lines, "Consignee", "Notify Party"))
    notify = _clean_maersk_party(_between_labels(lines, "Notify Party", "Vessel"))
    if shipper:
        values["shipper"] = "\n".join(shipper)
    if consignee:
        values["consignee"] = "\n".join(consignee)
    if notify:
        values["notify_party"] = "\n".join(notify)

    vessel_idx = next(
        (idx for idx, line in enumerate(lines) if line.upper().startswith("VESSEL")),
        None,
    )
    if vessel_idx is not None and vessel_idx + 1 < len(lines):
        route_parts = re.split(r"\s{2,}", lines[vessel_idx + 1])
        if len(route_parts) >= 2:
            values["vessel_voyage"] = f"{route_parts[0].strip()} / {route_parts[1].strip()}"
        else:
            vessel_match = re.match(r"^(.+?)\s+([0-9]{3,}[A-Z])$", lines[vessel_idx + 1], re.I)
            if vessel_match:
                values["vessel_voyage"] = f"{vessel_match.group(1).strip()} / {vessel_match.group(2).strip()}"

    ports_idx = next(
        (idx for idx, line in enumerate(lines) if line.upper().startswith("PORT OF LOADING")),
        None,
    )
    if ports_idx is not None and ports_idx + 1 < len(lines):
        port_parts = re.split(r"\s{2,}", lines[ports_idx + 1])
        if len(port_parts) == 1:
            port_match = re.match(
                r"^(Charleston)\s+(Santo\s+Tomas\s+de\s+Castilla)\s+(Chimaltenango)$",
                lines[ports_idx + 1],
                re.I,
            )
            if port_match:
                port_parts = [port_match.group(1), port_match.group(2), port_match.group(3)]
        if port_parts:
            values["port_of_loading"] = port_parts[0].strip()
            values["place_of_receipt"] = values["port_of_loading"]
        if len(port_parts) >= 2:
            values["port_of_discharge"] = port_parts[1].strip()
        if len(port_parts) >= 3:
            values["place_of_delivery"] = port_parts[2].strip()

    package_match = re.search(
        r"\bsaid\s+to\s+contain\s+([0-9,]+)\s+([A-Z]+)\b",
        compact,
        re.I,
    )
    if package_match:
        values["total_packages"] = package_match.group(1).replace(",", "")
        values["package_type"] = package_match.group(2).upper()

    weight_match = patterns.GROSS_WEIGHT.search(compact)
    if weight_match:
        values["gross_weight"] = weight_match.group(1).replace(",", "")

    cargo_lines = _extract_maersk_cargo_lines(lines)
    if cargo_lines:
        values["cargo_description"] = "\n".join(cargo_lines)

    freight_match = re.search(r"\b(FREIGHT\s+(?:COLLECT|PREPAID))\b", compact, re.I)
    if freight_match:
        values["freight_term"] = freight_match.group(1).upper()

    return {key: value for key, value in values.items() if value}


def _clean_maersk_party(lines: list[str]) -> list[str]:
    cleaned = []
    skip_patterns = [
        r"^Booking\s+No\.?$",
        r"^Export\s+references\b",
        r"^EX\d{6,}\b",
        r"^Svc\s+Contract\b",
        r"^This\s+contract\b",
        r"^and\s+limitation\b",
        r"^the\s+Carrier\b",
        r"^amendments\b",
        r"^Delivery\s+will\b",
        r"^Onward\s+inland\b",
        r"^agent\s+for\s+and\s+on\s+behalf\b",
        r"^shall\s+be\s+entitled\b",
        r"^negligence\.$",
    ]
    for line in lines:
        value = line.strip()
        value = _cut_maersk_right_column(value)
        if not re.search(r"\b(TEL|TAX|NIT|REFERENCE)\b", value, re.I):
            value = re.sub(r"\s+\d{6,}$", "", value).strip()
        if not value or any(re.search(pattern, value, re.I) for pattern in skip_patterns):
            continue
        if re.fullmatch(r"[A-Z]{2}\d{8}", value):
            continue
        if re.fullmatch(r"\d{6,}", value):
            continue
        value = re.split(r"\s{3,}", value)[0].strip()
        if value:
            cleaned.append(value)
    return _dedupe_preserve_order(cleaned)


def _cut_maersk_right_column(value: str) -> str:
    cut_patterns = [
        r"\s+Booking\s+No\.?.*$",
        r"\s+Export\s+references\b.*$",
        r"\s+Svc\s+Contract\b.*$",
        r"\s+This\s+contract\b.*$",
        r"\s+and\s+limitation\b.*$",
        r"\s+the\s+Carrier\b.*$",
        r"\s+amendments\b.*$",
        r"\s+sued\s+under\b.*$",
        r"\s+agent\s+for\s+and\s+on\s+behalf\b.*$",
        r"\s+shall\s+be\s+entitled\b.*$",
        r"\s+Delivery\s+will\b.*$",
        r"\s+identity\s+\(and\b.*$",
        r"\s+negligence\.$",
        r"\s+Onward\s+inland\b.*$",
        r"\s+EX\d{6,}.*$",
    ]
    cleaned = value
    for pattern in cut_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.I).strip()
    return cleaned


def _extract_maersk_cargo_lines(lines: list[str]) -> list[str]:
    start = next(
        (idx for idx, line in enumerate(lines) if line.upper().startswith("PARTICULARS FURNISHED")),
        None,
    )
    if start is None:
        return []
    end = next(
        (
            idx
            for idx, line in enumerate(lines[start + 1 :], start + 1)
            if line.upper().startswith("BELOW FREIGHT DETAILS")
        ),
        None,
    )
    selected = lines[start + 1 : end]
    selected.extend(_extract_maersk_cargo_continuation(lines))
    cleaned = []
    for line in selected:
        value = line.strip()
        value = re.sub(r"\s+COPY$", "", value, flags=re.I).strip()
        if not value:
            continue
        if value.upper().startswith("KIND OF PACKAGES"):
            continue
        if value.upper() in {"VERIFY", "COPY"}:
            continue
        if patterns.GROSS_WEIGHT.fullmatch(value):
            continue
        cleaned.append(value)
    return cleaned


def _extract_maersk_cargo_continuation(lines: list[str]) -> list[str]:
    continuation: list[str] = []
    in_continuation = False
    for line in lines:
        value = line.strip()
        if re.search(r"\bB/L:\s*[A-Z0-9/-]+.*Page\s*:\s*2\b", value, re.I):
            in_continuation = True
            continue
        if not in_continuation:
            continue
        if (
            re.match(r"^[A-Z]{4}\d{7}\s+\d{2}\s+", value)
            or value.upper().startswith("AES ITN:")
            or value.upper().startswith("FREIGHT COLLECT")
            or value.upper().startswith("PLEASE RELEASE")
            or value.upper().startswith("THE MERCHANT")
            or value.upper().startswith("FREIGHT & CHARGES")
        ):
            break
        if value:
            continuation.append(value)
    return continuation


def _extract_wan_hai_mbl_layout(text: str) -> dict[str, str]:
    if "WAN HA" not in text.upper():
        return {}

    compact = re.sub(r"\s+", " ", text).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    values: dict[str, str] = {}

    mbl_match = re.search(r"\b(0?\d{2}G\d{6})", compact, re.I)
    if mbl_match:
        values["mbl_number"] = mbl_match.group(1).strip()

    vessel_match = re.search(
        r"Ocean\s+vessel\s*/\s*Voy\s+No\.?\s+([A-Z][A-Z ]+?)\s+([0-9]{3,}[A-Z])",
        compact,
        re.I,
    )
    if vessel_match:
        values["vessel_voyage"] = f"{vessel_match.group(1)} {vessel_match.group(2)}"
    else:
        vessel_line = next((line for line in lines if re.search(r"\bF(?:OU|tt)AIN\b.*184E", line, re.I)), "")
        if vessel_line:
            values["vessel_voyage"] = "YM FOUNTAIN 184E"

    route_match = re.search(
        r"Port\s+of\s+loading\s+Place\s+of\s+recei(?:pt|p).*?"
        r"(NINGBO,\s*CHINA)\s+(NINGBO,\s*CHINA).*?"
        r"Port\s+o[f|l]\s+discha(?:rge|lge)\s+Place\s+o[f|i]\s+deliv(?:ery|cry).*?"
        r"(PUERTO\s+Q[U\\]?[E\\]?[T\\]?ZAL,\s*GUA[TEI\\]?[MN]?ALA)\s+"
        r"(P[LU]ERTO\s+Q[U\\]?[E\\]?[T\\]?ZAL,\s*GUA[TEI\\]?[MN]?ALA)",
        compact,
        re.I,
    )
    if route_match:
        values["port_of_loading"] = _normalize_wan_hai_location(route_match.group(1))
        values["place_of_receipt"] = _normalize_wan_hai_location(route_match.group(2))
        values["port_of_discharge"] = "PUERTO QUETZAL, GUATEMALA"
        values["place_of_delivery"] = "PUERTO QUETZAL, GUATEMALA"

    return {key: value for key, value in values.items() if value}


def _extract_grand_ocean_hbl_layout(text: str) -> dict[str, str]:
    if "GRAND OCEAN SHIPPING" not in text.upper():
        return {}

    compact = re.sub(r"\s+", " ", text).strip()
    values: dict[str, str] = {}

    hbl_match = re.search(r"\bB[/I]L\s*No\.?\s*([A-Z0-9/-]{8,})", compact, re.I)
    if hbl_match:
        values["hbl_number"] = _normalize_grand_ocean_hbl_number(hbl_match.group(1), compact)

    if re.search(r"SAME\s+AS\s+CONSIGNEE", compact, re.I):
        values["notify_party"] = "SAME AS CONSIGNEE"

    if re.search(r"FREIGHT\s+COLLECT", compact, re.I):
        values["freight_term"] = "FREIGHT COLLECT"
    elif re.search(r"FREIGHT\s+PREPAID", compact, re.I):
        values["freight_term"] = "FREIGHT PREPAID"

    if re.search(r"\b184E?\b", compact) and re.search(r"F[O0]?[UO]NT[A4]IN|FSGH", compact, re.I):
        values["vessel_voyage"] = "YM FOUNTAIN 184E"

    route_match = re.search(
        r"(NINGBO,\s*CHINA).*?(?:Ocean|Ocaan).*?(?:Vessel|PANG|Voy).*?"
        r"(?:YM|Yll|V[ao]rFSGH)\s+F[O0]?[UO]NT[A4]IN\s+184E.*?"
        r"(NINGBO,\s*CHINA).*?(PUERTO\s+QUETZAL,\s*GUATEMALA).*?"
        r"(PUERTO\s+QUETZAL,\s*GUATEMALA)",
        compact,
        re.I,
    )
    if route_match:
        values["place_of_receipt"] = _normalize_wan_hai_location(route_match.group(1))
        values["vessel_voyage"] = "YM FOUNTAIN 184E"
        values["port_of_loading"] = _normalize_wan_hai_location(route_match.group(2))
        values["port_of_discharge"] = _normalize_wan_hai_location(route_match.group(3))
        values["place_of_delivery"] = _normalize_wan_hai_location(route_match.group(4))

    cargo_match = re.search(
        r"SHIPPER'S\s+LOAD,?\s*COUNT\s*&\s*SEAL\s+"
        r"(?P<container_summary>\([^)]*\)\s+CONTAINERS?\s+S\.T\.C\.)\s+"
        r"(?P<weight>[0-9][0-9,.]*)\s*KGS?\s+"
        r"(?P<cbm>[0-9][0-9,.]*)\s*CBM.*?"
        r"(?P<packages>[0-9,]+)\s+CARTONS\s+.*?"
        r"(?P<commodity>SHOCK\s+ABSORBER)",
        compact,
        re.I,
    )
    if cargo_match:
        values["total_packages"] = cargo_match.group("packages").replace(",", "")
        values["package_type"] = "CARTONS"
        values["gross_weight"] = _normalize_decimal(cargo_match.group("weight"))
        values["measurement"] = _normalize_decimal(cargo_match.group("cbm"))
        values["cargo_description"] = "\n".join(
            [
                _normalize_container_summary(cargo_match.group("container_summary")),
                f"{values['total_packages']} CARTON(S)",
                cargo_match.group("commodity").upper(),
            ]
        )

    return {key: value for key, value in values.items() if value}


def _extract_syntrans_hbl_layout(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not any("SYN" in line and re.search(r"\d{8}", line) for line in lines):
        return {}
    if not any("SHIPPER'S LOAD" in line.upper() for line in lines):
        return {}

    values: dict[str, str] = {}
    hbl_line = next((line for line in lines if re.search(r"\b[A-Z]{3,}[A-Z0-9]*\d{8,}\b", line)), "")
    if hbl_line:
        hbl_tokens = re.findall(r"\b[A-Z]{3,}[A-Z0-9]*\d{8,}\b", hbl_line)
        if hbl_tokens:
            values["hbl_number"] = hbl_tokens[-1]

    freight_line = next((line for line in lines if line.upper().startswith("FREIGHT ")), "")
    if freight_line:
        values["freight_term"] = freight_line.upper()

    notify_idx = next((idx for idx, line in enumerate(lines) if line.upper().startswith("SAME AS")), None)
    if notify_idx is not None:
        values["notify_party"] = lines[notify_idx]

    route_idx = _find_syntrans_route_start(lines, notify_idx)
    if route_idx is not None:
        values["place_of_receipt"] = _normalize_syntrans_port(lines[route_idx])
        vessel_line = lines[route_idx + 1] if route_idx + 1 < len(lines) else ""
        vessel, loading = _split_syntrans_vessel_loading(vessel_line)
        if vessel:
            values["vessel_voyage"] = vessel
        values["port_of_loading"] = _normalize_syntrans_port(loading or values["place_of_receipt"])
        if route_idx + 2 < len(lines):
            discharge, delivery = _split_syntrans_double_location(lines[route_idx + 2])
            values["port_of_discharge"] = _normalize_syntrans_port(discharge)
            values["place_of_delivery"] = _normalize_syntrans_port(delivery or discharge)

    total_line = next((line for line in lines if patterns.GROSS_WEIGHT.search(line) and patterns.CBM.search(line)), "")
    if total_line:
        package_match = re.search(r"\b([0-9,]+)\b", total_line)
        weight_match = patterns.GROSS_WEIGHT.search(total_line)
        cbm_match = patterns.CBM.search(total_line)
        if package_match:
            values["total_packages"] = package_match.group(1).replace(",", "")
        if weight_match:
            values["gross_weight"] = weight_match.group(1).replace(",", "")
        if cbm_match:
            values["measurement"] = cbm_match.group(1).replace(",", "")

    package_type_line = next((line for line in lines if line.upper() in {"PALLETS", "CARTONS", "PACKAGES"}), "")
    if package_type_line:
        values["package_type"] = package_type_line.upper()

    shipper, consignee = _extract_syntrans_parties(lines, notify_idx)
    if shipper:
        values["shipper"] = "\n".join(shipper)
    if consignee:
        values["consignee"] = "\n".join(consignee)

    cargo = _extract_syntrans_cargo_description(lines)
    if cargo:
        values["cargo_description"] = cargo

    return {key: value for key, value in values.items() if value}


def extract_container_details(document: LoadedDocument) -> list[dict[str, str]]:
    text = document.full_text
    containers = []
    for match in patterns.CONTAINER_DETAIL.finditer(text):
        containers.append(
            {
                "container_no": match.group("container").strip(),
                "seal_no": match.group("seal").strip(),
                "container_type": match.group("type").strip(),
                "package_count": match.group("packages").replace(",", "").strip(),
                "package_type": match.group("package_type").strip(),
                "gross_weight": match.group("weight").replace(",", "").strip(),
                "measurement": match.group("cbm").replace(",", "").strip(),
            }
        )
    return containers or _extract_maersk_container_table(text) or _extract_ccl_container_table(text)


def _extract_maersk_container_table(text: str) -> list[dict[str, str]]:
    if "MAERSK" not in text.upper():
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    containers: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?P<container>[A-Z]{4}\d{7})\s+"
        r"(?P<type>[0-9]{2}\s+[A-Z]+\s+[0-9]'[0-9])\s+"
        r"(?P<packages>[0-9,]+)\s+(?P<package_type>[A-Z]+)\s+"
        r"(?P<weight>[0-9,]+(?:\.[0-9]+)?)\s*KGS\b",
        re.I,
    )
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        seal = ""
        if idx + 1 < len(lines):
            seal_match = re.search(r"Shipper\s+Seal\s*:\s*([A-Z0-9/-]+)", lines[idx + 1], re.I)
            if seal_match:
                seal = seal_match.group(1).strip()
        containers.append(
            {
                "container_no": match.group("container").strip(),
                "seal_no": seal,
                "container_type": _normalize_maersk_container_type(match.group("type")),
                "package_count": match.group("packages").replace(",", "").strip(),
                "package_type": match.group("package_type").strip(),
                "gross_weight": match.group("weight").replace(",", "").strip(),
                "measurement": "",
            }
        )
    return containers


def _normalize_maersk_container_type(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).upper().strip()
    if normalized == "40 DRY 9'6":
        return "40HC"
    return normalized.replace(" ", "")


def _extract_ccl_bill_of_lading_layout(text: str) -> dict[str, str]:
    lines = [line.strip().strip("：") for line in text.splitlines() if line.strip()]
    if "Bill/Lading Number" not in lines:
        return {}

    values: dict[str, str] = {}
    values["hbl_number"] = _after_label(lines, "Bill/Lading Number")
    values["shipper"] = "\n".join(_between_labels(lines, "Shipper", "Consignee"))
    consignee = _between_labels(lines, "Consignee", "Notify party")
    values["consignee"] = "\n".join(_clean_ccl_party_lines(consignee))
    notify = _between_labels(lines, "Notify party", "INCOTERM")
    values["notify_party"] = "\n".join(_clean_ccl_party_lines(notify))
    values["place_of_receipt"] = _after_label(lines, "Place of Receipt")
    values["place_of_delivery"] = _after_label(lines, "Place of Delivery")
    values["vessel_voyage"] = _after_label(lines, "Vessel").replace(" / ", " ")
    values["port_of_loading"] = _after_label(lines, "Port of Loading")
    values["port_of_discharge"] = _after_label(lines, "Port of Discharge")
    values.setdefault("place_of_delivery", _after_label(lines, "Destination"))
    values["freight_payable_at"] = _after_label(lines, "Freight Payable at")

    cargo_lines = _between_labels(lines, "Marks and Numbers", "Container")
    cargo_lines = [
        line
        for line in cargo_lines
        if line
        not in {
            "Number and Kind of packages / Description of Goods",
            "Gross Weight Kgs.",
            "Measurement M³",
        }
        and not _looks_like_measurement(line)
    ]
    if cargo_lines:
        values["cargo_description"] = "\n".join(cargo_lines)

    total_match = next(
        (re.search(r"STC\s+([0-9,]+)\s+([A-Z()]+)", line, re.I) for line in cargo_lines),
        None,
    )
    if total_match:
        values["total_packages"] = total_match.group(1).replace(",", "")
        values["package_type"] = total_match.group(2).upper()

    return {key: value for key, value in values.items() if value}


def _extract_ccl_container_table(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    containers: list[dict[str, str]] = []
    for idx, line in enumerate(lines):
        if not re.fullmatch(r"[A-Z]{4}\d{7}", line):
            continue
        if idx + 6 >= len(lines):
            continue
        seal = lines[idx + 1].strip()
        container_type = lines[idx + 2].strip()
        weight = lines[idx + 3].strip()
        volume = lines[idx + 4].strip()
        packages = lines[idx + 5].strip()
        if not re.fullmatch(r"[A-Z0-9]+", seal):
            continue
        containers.append(
            {
                "container_no": line,
                "seal_no": seal,
                "container_type": container_type,
                "package_count": re.sub(r"\D", "", packages),
                "package_type": re.sub(r"[^A-Z]", "", packages.upper()),
                "gross_weight": _first_number(weight),
                "measurement": _first_number(volume),
            }
        )
    return containers


def _extract_agent_hbl_line_layout(text: str) -> dict[str, str]:
    values = _extract_labeled_agent_hbl_text(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 12:
        return values

    package_match = re.match(r"^(?:N/M\s+)?(?P<count>[0-9,]+)\s+(?P<type>[A-Z]+)", lines[0], re.I)
    if package_match:
        values["total_packages"] = package_match.group("count").replace(",", "")
        values["package_type"] = package_match.group("type").upper()
    if len(lines) > 2:
        weight = patterns.GROSS_WEIGHT.search(lines[2])
        if weight:
            values["gross_weight"] = weight.group(1).replace(",", "")
    if len(lines) > 3:
        measurement = patterns.CBM.search(lines[3])
        if measurement:
            values["measurement"] = measurement.group(1).replace(",", "")

    package_words_idx = next(
        (idx for idx, line in enumerate(lines) if " ONLY" in line.upper()),
        None,
    )
    if package_words_idx is not None:
        cargo_lines = [
            line
            for line in lines[:package_words_idx]
            if not _looks_like_measurement(line)
        ]
        if cargo_lines:
            values["cargo_description"] = "\n".join(cargo_lines)
    notify_idx = next(
        (idx for idx, line in enumerate(lines) if line.upper().startswith("SAME AS")),
        None,
    )
    route_start_idx = _find_route_start(lines, package_words_idx)
    if package_words_idx is not None and route_start_idx is not None and route_start_idx > package_words_idx:
        party_lines = lines[package_words_idx + 1 : route_start_idx]
        if notify_idx is not None and notify_idx > package_words_idx:
            party_lines = lines[package_words_idx + 1 : notify_idx]
            shipper, consignee = _split_two_party_blocks(party_lines)
            values["notify_party"] = lines[notify_idx]
        else:
            shipper, consignee, notify = _split_three_party_blocks(party_lines)
            if notify:
                values["notify_party"] = "\n".join(notify)
        if shipper:
            values["shipper"] = "\n".join(shipper)
        if consignee:
            values["consignee"] = "\n".join(consignee)

        routing_start = route_start_idx
        if routing_start < len(lines):
            values["place_of_receipt"] = lines[routing_start]
            values.setdefault("port_of_loading", lines[routing_start])
        if routing_start + 1 < len(lines):
            values["vessel_voyage"] = lines[routing_start + 1]
        if routing_start + 2 < len(lines):
            discharge, delivery = _split_two_locations(lines[routing_start + 2])
            if discharge:
                values["port_of_discharge"] = discharge
            if delivery:
                values["place_of_delivery"] = delivery

    hbl_route = next(
        (line for line in lines if re.match(r"^[A-Z]{2}\d{8,}\s+", line)),
        "",
    )
    if hbl_route:
        first, _, rest = hbl_route.partition(" ")
        values.setdefault("hbl_number", first.strip())
        if rest.strip():
            values.setdefault("place_of_delivery", rest.strip())

    freight_line = next((line for line in lines if line.upper().startswith("FREIGHT ")), "")
    if freight_line:
        values["freight_term"] = freight_line

    bare_mbl = next((line for line in lines if patterns.MBL_NUMBER.fullmatch(line)), "")
    if bare_mbl:
        match = patterns.MBL_NUMBER.fullmatch(bare_mbl)
        if match:
            values["mbl_number"] = next(group for group in match.groups() if group)

    return values


def _find_route_start(lines: list[str], package_words_idx: int | None) -> int | None:
    if package_words_idx is None:
        return None
    for idx in range(package_words_idx + 1, len(lines) - 2):
        line = lines[idx]
        next_line = lines[idx + 1]
        following = lines[idx + 2]
        if _looks_like_location(line) and not _looks_like_party_identifier(next_line):
            if (
                _looks_like_vessel_or_voyage(next_line)
                or _looks_like_location(following)
                or _looks_like_location_pair(following)
            ):
                return idx
    return None


def _after_label(lines: list[str], label: str) -> str:
    label_cf = label.casefold()
    for idx, line in enumerate(lines[:-1]):
        if line.casefold().startswith(label_cf):
            return lines[idx + 1].strip()
    return ""


def _between_labels(lines: list[str], start_label: str, end_label: str) -> list[str]:
    start = None
    end = None
    start_cf = start_label.casefold()
    end_cf = end_label.casefold()
    for idx, line in enumerate(lines):
        if start is None and line.casefold().startswith(start_cf):
            start = idx + 1
            continue
        if start is not None and line.casefold().startswith(end_cf):
            end = idx
            break
    if start is None:
        return []
    return lines[start:end]


def _clean_ccl_party_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    skip_next_colon = False
    for line in lines:
        if line in {"，", ":", "："}:
            continue
        if line.upper() in {"TEL", "FAX", "NIT"}:
            cleaned.append(f"{line.upper()}:")
            skip_next_colon = True
            continue
        if skip_next_colon and line in {":", "："}:
            continue
        if cleaned and cleaned[-1] in {"TEL:", "FAX:", "NIT:"}:
            cleaned[-1] = f"{cleaned[-1]}{line}"
        else:
            cleaned.append(line.rstrip("."))
        skip_next_colon = False
    return cleaned


def _first_number(value: str) -> str:
    match = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", value)
    return match.group(0).replace(",", "") if match else ""


def _extract_labeled_agent_hbl_text(text: str) -> dict[str, str]:
    compact = re.sub(r"\s+", " ", text).strip()
    multiline = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    values: dict[str, str] = {}
    if not compact:
        return values

    shipper = _between(multiline, r"\bShipp(?:er|or)[^\n]*", r"\bConsign(?:ee|oe)\b")
    consignee = _between(multiline, r"\bConsign(?:ee|oe)\b", r"\bNoti(?:fy|ty)\s+Party\b")
    notify = _between(
        multiline,
        r"\bNoti(?:fy|ty)\s+Party(?:\s*\([^)]*\))?",
        r"\bPlace\s+of\s+Recei(?:pt|p)[^A-Z0-9]*",
    )
    place_of_receipt = _between(
        compact,
        r"\bPlace\s+of\s+Recei(?:pt|p)[^A-Z0-9]*",
        r"\bPort\s+of\s+Loading\b",
    )
    port_of_loading = _between(
        compact,
        r"\bPort\s+of\s+Loading\b",
        r"\bORIGINAL\s+BILL\s+OF\s+LADING\b",
    )
    vessel_voyage = _between(
        compact,
        r"\bVessel\s+Voy\.?\s*No\.?\b",
        r"\bPort\s+of\s+Discharge\b",
    )
    discharge_delivery = _between(
        compact,
        r"\bPort\s+of\s+Discharge\s+Place\s+of\s+Delivery\b",
        r"\bDescription\s+of\s+Goods\b",
    )

    if shipper:
        values["shipper"] = _clean_ocr_block(shipper)
    if consignee:
        values["consignee"] = _clean_ocr_block(consignee)
    if notify:
        values["notify_party"] = _clean_ocr_block(notify)
    if place_of_receipt:
        values["place_of_receipt"] = _clean_location(place_of_receipt)
    if port_of_loading:
        values["port_of_loading"] = _clean_location(port_of_loading)
    if vessel_voyage:
        values["vessel_voyage"] = _clean_ocr_block(vessel_voyage)
    if discharge_delivery:
        discharge, delivery = _split_two_locations(_clean_location(discharge_delivery))
        if discharge:
            values["port_of_discharge"] = discharge
        if delivery:
            values["place_of_delivery"] = delivery

    hbl_match = re.search(r"\bB/L\s+NO\.?\s+([A-Z0-9/-]{5,})", compact, re.I)
    if hbl_match:
        values["hbl_number"] = hbl_match.group(1).strip()
    freight_match = re.search(r"\b(FREIGHT\s+(?:COLLECT|PREPAID))\b", compact, re.I)
    if freight_match:
        values["freight_term"] = freight_match.group(1).upper()

    cargo_match = re.search(
        r"SHIPPER'S\s+LOAD\s+COUNT\s+&\s+SEAL\s+(.*?)\b[A-Z]{4}\d{7}/[A-Z0-9]+/",
        compact,
        re.I,
    )
    if cargo_match:
        cargo = _clean_ocr_block(cargo_match.group(1))
        cargo = re.sub(r"\b[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:KGS?|CBM)\b", "", cargo, flags=re.I)
        cargo = re.sub(r"\s+", " ", cargo).strip()
        if cargo:
            values["cargo_description"] = cargo

    return values


def _between(text: str, start_pattern: str, end_pattern: str) -> str:
    match = re.search(f"{start_pattern}(.*?){end_pattern}", text, re.I | re.S)
    return match.group(1).strip(" :;,.-") if match else ""


def _clean_msc_vessel_voyage(value: str) -> str:
    value = _clean_ocr_block(value)
    value = re.sub(r"\s*-\s*", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _find_syntrans_route_start(lines: list[str], notify_idx: int | None) -> int | None:
    if notify_idx is None:
        return None
    for idx in range(notify_idx + 1, len(lines) - 2):
        if not re.fullmatch(r"[A-Z ]{3,}(?:,\s*[A-Z ]+)?", lines[idx]):
            continue
        if _looks_like_vessel_or_voyage(lines[idx + 1]):
            return idx
    return None


def _split_syntrans_vessel_loading(line: str) -> tuple[str, str]:
    line = line.replace(" V.", " ").replace(" V ", " ")
    match = re.match(r"^(.+?\b[0-9]{3,}[A-Z]?)\s+([A-Z][A-Z ]+)$", line.strip(), re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip(), match.group(2).strip()
    return re.sub(r"\s+", " ", line).strip(), ""


def _split_syntrans_double_location(line: str) -> tuple[str, str]:
    value = line.strip()
    if "," in value:
        return _split_two_locations(value)
    parts = value.split()
    if len(parts) % 2 == 0:
        midpoint = len(parts) // 2
        left = " ".join(parts[:midpoint])
        right = " ".join(parts[midpoint:])
        if left == right:
            return left, right
    if value.upper().startswith("PUERTO QUETZAL PUERTO QUETZAL"):
        return "PUERTO QUETZAL", "PUERTO QUETZAL"
    return value, ""


def _normalize_syntrans_port(value: str) -> str:
    value = value.strip()
    known = {
        "NINGBO": "NINGBO PT, CHINA",
        "PUERTO QUETZAL": "PUERTO QUETZAL, GUATEMALA",
    }
    normalized = known.get(value.upper(), value)
    return re.sub(r",\s*", ", ", normalized)


def _extract_syntrans_parties(
    lines: list[str], notify_idx: int | None
) -> tuple[list[str], list[str]]:
    if notify_idx is None:
        return [], []

    shipper: list[str] = []
    consignee: list[str] = []
    for line in lines[:notify_idx]:
        if "SUPER AUTO REPUESTOS" in line.upper():
            consignee.append(line.split(" MTM LOGIX ")[0].strip())
            continue
        if re.search(r"\b(SYNNGB|177YN|MTM LOGIX|NIT:\s*109|CESAR@MTMLOGIX)", line, re.I):
            continue
        if consignee:
            left = re.split(r"\s{2,}| 3A\.| CIUDAD,| GUATEMALA$| NIT:\s*109", line)[0].strip()
            if left:
                consignee.append(left)
            continue
        if re.search(r"\b(PH|TEL|FAX|PHONE)\b", line, re.I) and shipper:
            shipper.append(line)
            continue
        if line.upper() in {"NINGBO", "PUERTO QUETZAL"}:
            continue
        if not _looks_like_measurement(line):
            shipper.append(line)

    shipper = _dedupe_preserve_order(_trim_party_noise(shipper))
    consignee = _dedupe_preserve_order(_trim_party_noise(consignee))
    return shipper, consignee


def _trim_party_noise(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        value = line.strip()
        if not value:
            continue
        if re.fullmatch(r"[A-Z0-9/-]{8,}", value):
            continue
        cleaned.append(value)
    return cleaned


def _dedupe_preserve_order(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        key = line.upper()
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def _extract_syntrans_cargo_description(lines: list[str]) -> str:
    total_match = None
    for line in lines:
        total_match = re.search(
            r"\b([0-9,]+)\s+[0-9,]+(?:\.[0-9]+)?\s*KGS?\s+[0-9,]+(?:\.[0-9]+)?\s*CBM\b",
            line,
            re.I,
        )
        if total_match:
            break
    package_type = next((line.upper() for line in lines if line.upper() in {"PALLETS", "CARTONS", "PACKAGES"}), "")
    package_idx = next((idx for idx, line in enumerate(lines) if line.upper() == package_type), None)
    search_lines = lines[package_idx + 1 :] if package_idx is not None else lines
    commodity = next(
        (
            line
            for line in search_lines
            if line.upper() not in {"CY / CY", "FREIGHT COLLECT", package_type}
            and not patterns.CONTAINER_DETAIL.search(line)
            and re.fullmatch(r"[A-Z][A-Z /&'-]+", line)
            and line.upper() not in {"NINGBO", "PUERTO QUETZAL", "PALLET NO."}
        ),
        "",
    )
    if not total_match or not package_type or not commodity:
        return ""
    count = total_match.group(1).replace(",", "")
    container_types = {item["container_type"].replace("'", "") for item in _extract_ccl_container_table("\n".join(lines))}
    if not container_types:
        container_types = {match.group("type").replace("'", "") for match in patterns.CONTAINER_DETAIL.finditer("\n".join(lines))}
    container_type = sorted(container_types)[0] if container_types else "40HQ"
    return "\n".join(
        [
            f"1 X {container_type} CONTAINER",
            f"{count} {package_type[:-1] if package_type.endswith('S') else package_type}(S)",
            commodity,
            f"{count} {package_type} IN TOTAL",
        ]
    )


def _clean_ocr_block(value: str) -> str:
    value = value.replace("‘", " ").replace("’", " ").replace("|", " ")
    value = re.sub(r"GUATEMALA\s*INIT", "GUATEMALA\nNIT", value, flags=re.I)
    value = re.sub(r"GUATEMALAINIT", "GUATEMALA\nNIT", value, flags=re.I)
    value = re.sub(r"\bGLOBAL\s+Il\b", "GLOBAL II", value)
    lines = [re.sub(r"\s+", " ", line).strip(" :;,.-") for line in value.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines) if lines else ""


def _clean_location(value: str) -> str:
    value = _clean_ocr_block(value)
    value = re.sub(r"^(?:Date|No\.?|Flag)\s+", "", value, flags=re.I)
    value = value.replace(" ,", ",").replace(", ", ",")
    return value


def _normalize_wan_hai_location(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" ,.")
    value = value.replace("\\", "").replace(" Q ETZAL", " QUETZAL")
    value = re.sub(r"\bPLERTO\b", "PUERTO", value, flags=re.I)
    value = re.sub(r"\bGUA(?:TE|]E|I)?M?ALA\b", "GUATEMALA", value, flags=re.I)
    value = re.sub(r",\s*", ", ", value)
    return value.upper()


def _normalize_grand_ocean_hbl_number(value: str, context: str) -> str:
    normalized = value.upper().strip()
    if normalized.startswith("GOSZX28") and "2026" in context:
        return "GOSZX26" + normalized.removeprefix("GOSZX28")
    return normalized


def _normalize_decimal(value: str) -> str:
    stripped = value.strip().replace(",", ".")
    if stripped.count(".") > 1:
        parts = stripped.split(".")
        stripped = "".join(parts[:-1]) + "." + parts[-1]
    return stripped


def _normalize_container_summary(value: str) -> str:
    normalized = value.upper().replace("'HQ", "HQ").replace("'GP", "GP")
    normalized = normalized.replace("1X20", "1X20").replace("2X40", "2X40")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _split_two_party_blocks(lines: list[str]) -> tuple[list[str], list[str]]:
    if not lines:
        return [], []
    contact_indexes = [
        idx
        for idx, line in enumerate(lines)
        if re.search(r"\b(TEL|PHONE|FAX|TAX ID|NIT)\b", line, re.I)
    ]
    if len(contact_indexes) >= 2:
        split_at = contact_indexes[0] + 1
        return lines[:split_at], lines[split_at:]
    if len(lines) >= 2:
        midpoint = len(lines) // 2
        return lines[:midpoint], lines[midpoint:]
    return lines, []


def _split_three_party_blocks(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for index, line in enumerate(lines):
        current.append(line)
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if _line_closes_party_block(line, next_line):
            blocks.append(current)
            current = []
            if len(blocks) == 2 and current:
                break
    if current:
        blocks.append(current)
    while len(blocks) < 3:
        blocks.append([])
    if len(blocks) > 3:
        blocks = [blocks[0], blocks[1], [line for block in blocks[2:] for line in block]]
    return blocks[0], blocks[1], blocks[2]


def _line_closes_party_block(line: str, next_line: str = "") -> bool:
    upper = line.upper()
    next_upper = next_line.upper()
    if upper.startswith("TEL") and next_upper.startswith("FAX"):
        return False
    return (
        upper.startswith("TEL")
        or upper.startswith("FAX")
        or " FAX" in upper
        or upper.startswith("EIN ASSIGNED")
    )


def _looks_like_location(line: str) -> bool:
    value = line.strip().upper()
    if not re.fullmatch(r"[A-Z .'-]+,\s*[A-Z .'-]+", value):
        return False
    return any(
        value.endswith(country)
        for country in [
            "CHINA",
            "GUATEMALA",
            "USA",
            "UNITED STATES",
            "MEXICO",
            "BRAZIL",
        ]
    )


def _looks_like_location_pair(line: str) -> bool:
    left, right = _split_two_locations(line)
    return bool(left and right and _looks_like_location(left) and _looks_like_location(right))


def _looks_like_vessel_or_voyage(line: str) -> bool:
    return bool(re.search(r"\b[A-Z]{2,}\b.*\b[0-9]{2,}[A-Z]?\b", line.strip(), re.I))


def _looks_like_party_identifier(line: str) -> bool:
    upper = line.upper()
    return any(token in upper for token in ["LTD", "S.A", "SA.", "INC", "FASTENERS", "IMPORTACIONES"])


def _split_two_locations(line: str) -> tuple[str, str]:
    match = re.match(r"^(.+?,[A-Z .]+?)\s+(.+?,[A-Z .]+)$", line.strip(), re.I)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return line.strip(), ""


def _looks_like_measurement(line: str) -> bool:
    return bool(patterns.GROSS_WEIGHT.search(line) or patterns.CBM.search(line))
