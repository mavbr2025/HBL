from mtm_hbl.models.documents import LoadedDocument


def classify_document(document: LoadedDocument) -> LoadedDocument:
    text = document.full_text.casefold()
    if any(token in text for token in ["house bill of lading", "hbl", "shipper", "consignee"]):
        document.document_type = "agent_hbl"
    if any(token in text for token in ["master bill", "sea waybill", "ocean bill", "carrier"]):
        if document.document_type == "agent_hbl":
            document.document_type = "ambiguous"
        else:
            document.document_type = "carrier_mbl"
    return document
