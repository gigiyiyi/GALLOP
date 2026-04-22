# -------------------------------------------------
# Constants
# -------------------------------------------------
EVIDENCE_TYPE_OPTIONS = [
    "land_ownership_certificate",
    "land_lease_agreement",
    "digital_map",
    "photo_map",
    "site_photo",
    "logging_license",
    "harvest_permit",
    "invoice",
    "transport_document",
    "photo_product",
    "photo_batch_system_record",
    "photo_batch_method_description",
    "business_license",
    "bill_of_lading",
    "field_assessment_report",
]

LINK_TYPE_OPTIONS = ["txn", "node", "geo", "batch_system"]
ALLOWED_LINK_TYPES = set(LINK_TYPE_OPTIONS)

# UI hint only: evidence.type -> default fact category / anchoring level
EVIDENCE_TYPE_META = {
    "land_ownership_certificate": {"category": "source / geo", "description": "Land tenure / ownership proof for a specific location."},
    "land_lease_agreement": {"category": "source / geo", "description": "Lease agreement proving legal right to operate on the land."},
    "digital_map": {"category": "geo", "description": "Digital map / GIS file defining the boundary or location of a source area."},
    "photo_map": {"category": "geo", "description": "Photo/scanned map showing boundaries or reference points of a source area."},
    "site_photo": {"category": "geo / source", "description": "On-site photo documenting the location condition (forest/farm/operation area)."},
    "logging_license": {"category": "permit", "description": "License or concession document authorizing logging activity. Usually linked to a geo area, but it can support a specific transaction when that is how the operator manages the file."},
    "harvest_permit": {"category": "source / geo", "description": "Official harvesting/collection permit for a specific area."},
    "invoice": {"category": "transaction", "description": "Commercial invoice proving a transaction between parties."},
    "transport_document": {"category": "transaction", "description": "Transport document proving movement of goods."},
    "bill_of_lading": {"category": "transaction", "description": "Shipping document proving custody and transfer of goods."},
    "photo_product": {"category": "transaction", "description": "Photo documenting product involved in a transaction/batch."},
    "business_license": {"category": "node", "description": "Business or operating license proving legal existence of an operator, forest manager, processor, or trader."},
    "photo_batch_system_record": {"category": "batch_system", "description": "Record demonstrating batch control / segregation system in operation."},
    "photo_batch_method_description": {"category": "batch_system", "description": "Description of how batch control / segregation is implemented."},
    "field_assessment_report": {"category": "source / geo", "description": "On-site or third-party assessment report covering location facts and risk observations."},
}

EVIDENCE_TYPE_SUGGESTED_LINK = {
    "land_ownership_certificate": "geo",
    "land_lease_agreement": "geo",
    "logging_license": "geo",
    "harvest_permit": "geo",
    "digital_map": "geo",
    "photo_map": "geo",
    "site_photo": "geo",
    "field_assessment_report": "geo",
    "invoice": "txn",
    "transport_document": "txn",
    "bill_of_lading": "txn",
    "photo_product": "txn",
    "business_license": "node",
    "photo_batch_system_record": "batch_system",
    "photo_batch_method_description": "batch_system",
}

EVIDENCE_TYPE_ALLOWED_LINKS = {
    "land_ownership_certificate": ["geo"],
    "land_lease_agreement": ["geo"],
    "digital_map": ["geo"],
    "photo_map": ["geo"],
    "site_photo": ["geo", "txn"],
    "logging_license": ["geo", "txn"],
    "harvest_permit": ["geo", "txn"],
    "invoice": ["txn"],
    "transport_document": ["txn"],
    "photo_product": ["txn"],
    "photo_batch_system_record": ["batch_system", "node"],
    "photo_batch_method_description": ["batch_system", "node"],
    "business_license": ["node"],
    "bill_of_lading": ["txn"],
    "field_assessment_report": ["geo", "txn"],
}

# -------------------------
# Txn
# -------------------------
TXN_RISK_LEVEL_OPTIONS = ["", "negligible", "low", "medium", "high"]

# -------------------------
# UI labels (display only)
# -------------------------
INTEGRITY_MODE_LABELS = {
    "source_fact": "Source-fact (anchored)",
    "narrative": "Narrative (flexible)",
}

RECORD_STATUS_LABELS = {
    "draft": "Draft",
    "submitted": "Submitted",
    "sealed": "Sealed",
    "superseded": "Superseded",
}
