import re

_NUMBER_TOKEN = r"([A-Z0-9/-]*\d[A-Z0-9/-]*)"

HBL_NUMBER = re.compile(rf"\b(?:HBL|HOUSE\s+B/L|HOUSE\s+BL)[\s#:.-]*{_NUMBER_TOKEN}", re.I)
MBL_NUMBER = re.compile(
    rf"\b(?:(?:MBL|MASTER\s+B/L|MASTER\s+BL|BILL\s+OF\s+LADING\s+No\.?)[\s#:.-]*{_NUMBER_TOKEN}|(ONEY[A-Z0-9]{{12}}))",
    re.I,
)
CONTAINER_NO = re.compile(r"\b([A-Z]{4}\d{7})\b")
SEAL_NO = re.compile(r"\b(?:SEAL|S\.?L\.?)[\s#:.-]*([A-Z0-9/-]{3,})", re.I)
GROSS_WEIGHT = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:KGS?|KG|KILOS?)\b", re.I)
CBM = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:CBM|M3|MTQ)\b", re.I)
CONTAINER_DETAIL = re.compile(
    r"\b(?P<container>[A-Z]{4}\d{7})/(?P<seal>[A-Z0-9]+)/(?P<type>[0-9A-Z'\"-]+)\s+"
    r"(?:[^\n]*?\s+)?"
    r"(?P<packages>[0-9,]+)\s*(?P<package_type>[A-Z]+)"
    r"/(?P<weight>[0-9,]+(?:\.[0-9]+)?)\s*KGS?"
    r"/(?P<cbm>[0-9,]+(?:\.[0-9]+)?)\s*CBM",
    re.I,
)
