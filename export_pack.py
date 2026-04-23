import io
import json
import zipfile
from pathlib import Path

import hashlib
from i18n import (
    evidence_type_label_lang,
    link_type_label_lang,
    mode_label_lang,
    option_label_lang,
    status_label_lang,
    t_lang,
)


def _row_value(row, key: str):
    try:
        return row[key]
    except Exception:
        return None


def _referenced_geo_rows(ev_rows, txn_rows, geo_rows):
    referenced_geo_ids = {
        (t["geo_id"] or "").strip()
        for t in txn_rows
        if (t["geo_id"] or "").strip()
    }
    referenced_geo_ids.update(
        (e["link_id"] or "").strip()
        for e in ev_rows
        if e["link_type"] == "geo" and (e["link_id"] or "").strip()
    )
    return [g for g in geo_rows if g["geo_id"] in referenced_geo_ids]

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def compute_manifest_hash(evidence_rows) -> str:
    parts = [f"{e['evidence_id']}:{e['file_hash']}" for e in sorted(evidence_rows, key=lambda x: x["evidence_id"])]
    return sha256_bytes("\n".join(parts).encode("utf-8"))

    
def build_manifest_json(rec, ev_rows, txn_rows, geo_rows):
    referenced_geo_rows = _referenced_geo_rows(ev_rows, txn_rows, geo_rows)
    return {
        "record": {
            "record_id": rec["record_id"],
            "case_id": rec["case_id"],
            "case_title": rec["case_title"],
            "owner_org_id": rec["owner_org_id"],
            "review_coordinator_name": _row_value(rec, "review_coordinator_name"),
            "review_coordinator_email": _row_value(rec, "review_coordinator_email"),
            "review_coordinator_note": _row_value(rec, "review_coordinator_note"),
            "integrity_mode": rec["integrity_mode"],
            "mode_origin": rec["mode_origin"],
            "status": rec["status"],
            "created_at": rec["created_at"],
            "submitted_at": rec["submitted_at"],
            "sealed_at": rec["sealed_at"],
            "manifest_hash": rec["manifest_hash"],
            "downgraded_at": rec["downgraded_at"],
            "downgraded_by": rec["downgraded_by"],
            "downgrade_reason": rec["downgrade_reason"],
        },
        "transactions": [
            {
                "transaction_id": t["txn_id"],
                "product_name": t["product_name"],
                "from_entity_id": _row_value(t, "input_node_id"),
                "from_entity_name": t["input_node_name"],
                "reporting_entity_id": _row_value(t, "reporting_node_id"),
                "reporting_entity_name": _row_value(t, "reporting_node_name"),
                "to_entity_id": _row_value(t, "output_node_id"),
                "to_entity_name": t["output_node_name"],
                "species_common_name": t["species_common"],
                "species_latin_name": t["species_latin"],
                "product_weight": t["product_weight"],
                "product_volume": t["product_volume"],
                "linked_source_location_id": t["geo_id"],
                "quantity_unit": t["quantity_unit"],
                "input_quantity": t["input_quantity"],
                "output_quantity": t["output_quantity"],
                "production_start_date": t["production_start_date"],
                "production_end_date": t["production_end_date"],
                "batch_label": t["batch_label"],
                "risk_level": t["assessment_risk_level"],
                "risk_assessment_conclusion": t["assessment_conclusion"],
            }
            for t in txn_rows
        ],
        "supporting_documents": [
            {
                "document_id": e["evidence_id"],
                "document_type": e["evidence_type"],
                "file_name": e["file_name"],
                "uploaded_at": e["uploaded_at"],
                "record_id": e["record_id"],
                "linked_object_type": e["link_type"],
                "linked_object_id": e["link_id"],
                "file_hash": e["file_hash"],
            }
            for e in ev_rows
        ],
        "source_locations": [
            {
                "source_location_id": g["geo_id"],
                "source_location_type": g["anchor_type"],
                "file_name": g["file_name"],
                "created_at": g["created_at"],
            }
            for g in referenced_geo_rows
        ],
    }


def build_localized_manifest_json(rec, ev_rows, txn_rows, geo_rows, lang: str):
    referenced_geo_rows = _referenced_geo_rows(ev_rows, txn_rows, geo_rows)
    return {
        "language": lang,
        "record": {
            "record_id": rec["record_id"],
            "package_name": rec["case_title"],
            "package_mode": mode_label_lang(lang, rec["integrity_mode"]),
            "package_status": status_label_lang(lang, rec["status"]),
            "created_at": rec["created_at"],
            "submitted_at": rec["submitted_at"],
            "sealed_at": rec["sealed_at"],
            "review_contact": {
                "name": _row_value(rec, "review_coordinator_name"),
                "email": _row_value(rec, "review_coordinator_email"),
                "note": _row_value(rec, "review_coordinator_note"),
            },
            "downgrade_reason": _row_value(rec, "downgrade_reason"),
        },
        "transactions": [
            {
                "transaction_id": t["txn_id"],
                "product_name": t["product_name"],
                "from_entity_id": _row_value(t, "input_node_id"),
                "from_entity_name": t["input_node_name"],
                "reporting_entity_id": _row_value(t, "reporting_node_id"),
                "reporting_entity_name": _row_value(t, "reporting_node_name"),
                "to_entity_id": _row_value(t, "output_node_id"),
                "to_entity_name": t["output_node_name"],
                "species_common_name": t["species_common"],
                "species_latin_name": t["species_latin"],
                "product_weight": t["product_weight"],
                "product_volume": t["product_volume"],
                "linked_source_location_id": t["geo_id"],
                "quantity_unit": t["quantity_unit"],
                "input_quantity": t["input_quantity"],
                "output_quantity": t["output_quantity"],
                "production_start_date": t["production_start_date"],
                "production_end_date": t["production_end_date"],
                "batch_label": t["batch_label"],
                "risk_level": option_label_lang(lang, "risk", t["assessment_risk_level"]) if t["assessment_risk_level"] else "",
                "risk_assessment_conclusion": t["assessment_conclusion"],
            }
            for t in txn_rows
        ],
        "supporting_documents": [
            {
                "document_id": e["evidence_id"],
                "document_type": evidence_type_label_lang(lang, e["evidence_type"]),
                "file_name": e["file_name"],
                "uploaded_at": e["uploaded_at"],
                "linked_object_type": link_type_label_lang(lang, e["link_type"]) if e["link_type"] else "",
                "linked_object_id": e["link_id"],
                "file_hash": e["file_hash"],
            }
            for e in ev_rows
        ],
        "source_locations": [
            {
                "source_location_id": g["geo_id"],
                "source_location_type": option_label_lang(lang, "geo_anchor", g["anchor_type"]) if g["anchor_type"] else "",
                "file_name": g["file_name"],
                "created_at": g["created_at"],
            }
            for g in referenced_geo_rows
        ],
        "notes": {
            "review_contact_label": t_lang(lang, "manifest.review_contact_label"),
            "localized_manifest_note": t_lang(lang, "manifest.localized_note"),
        },
    }


def build_full_package_zip(manifest_obj, ev_rows, txn_rows, geo_rows, localized_manifest_obj=None, localized_lang: str | None = None):
    referenced_geo_rows = _referenced_geo_rows(ev_rows, txn_rows, geo_rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest_obj, ensure_ascii=False, indent=2))
        if localized_manifest_obj and localized_lang:
            z.writestr(f"manifest.{localized_lang}.json", json.dumps(localized_manifest_obj, ensure_ascii=False, indent=2))
        for e in ev_rows:
            p = Path(e["file_path"])
            if p.exists():
                z.write(p, arcname=f"evidence/{p.name}")
        for g in referenced_geo_rows:
            p = Path(g["file_path"])
            if p.exists():
                z.write(p, arcname=f"geo/{p.name}")
    buf.seek(0)
    return buf
