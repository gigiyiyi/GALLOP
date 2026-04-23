# rules.py

from __future__ import annotations

from typing import List, Tuple

from constants import ALLOWED_LINK_TYPES


def validate_record_v1(rec, ev_rows, txn_rows, node_rows, geo_rows) -> Tuple[List[str], List[str]]:
    """
    Validate rules (Phase 1) — kept consistent with current app.py implementation.

    Inputs are sqlite3.Row sequences (support row["field"], not row.get()).
    Returns: (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []
    geo_ids = {g["geo_id"] for g in geo_rows} if geo_rows else set()

    # Build txn id set for R007
    txn_ids = {t["txn_id"] for t in txn_rows} if txn_rows else set()
    node_name_to_type = {
        (n["name"] or "").strip().lower(): (n["type"] or "").strip().lower()
        for n in node_rows
        if (n["name"] or "").strip()
    }

    # R006
    for e in ev_rows:
        if e["link_type"] not in ALLOWED_LINK_TYPES:
            errors.append(f"R006: invalid link_type for {e['evidence_id']}: {e['link_type']}")

    # R007 (txn link)
    for e in ev_rows:
        if e["link_type"] == "txn":
            link_id = (e["link_id"] or "").strip()
            if link_id:
                if link_id not in txn_ids:
                    if rec["integrity_mode"] == "source_fact":
                        errors.append(f"R007: evidence {e['evidence_id']} links to non-existing txn.id: {link_id}")
                    else:
                        warnings.append(f"R007(warn): evidence {e['evidence_id']} links to non-existing txn.id: {link_id}")
            else:
                # link_id empty: handled by R005 for source_fact; for narrative just ignore
                pass

    # R008: link_type=node must reference existing node.id
    node_ids = {n["node_id"] for n in node_rows} if node_rows else set()

    for e in ev_rows:
        if e["link_type"] == "node":
            link_id = (e["link_id"] or "").strip()
            if link_id:
                if link_id not in node_ids:
                    if rec["integrity_mode"] == "source_fact":
                        errors.append(f"R008: evidence {e['evidence_id']} links to non-existing node.id: {link_id}")
                    else:
                        warnings.append(f"R008(warn): evidence {e['evidence_id']} links to non-existing node.id: {link_id}")
            else:
                # empty link_id is handled by R005 for source_fact; ignore for narrative
                pass

    # R010: link_type=batch_system must reference existing node.id
    for e in ev_rows:
        if e["link_type"] == "batch_system":
            link_id = (e["link_id"] or "").strip()
            if link_id:
                if link_id not in node_ids:
                    if rec["integrity_mode"] == "source_fact":
                        errors.append(f"R010: evidence {e['evidence_id']} links to non-existing node.id: {link_id}")
                    else:
                        warnings.append(f"R010(warn): evidence {e['evidence_id']} links to non-existing node.id: {link_id}")
            else:
                # empty link_id is handled by R005 for source_fact; ignore for narrative
                pass

    upstream_geo_ids = set()
    upstream_txn_count = 0
    upstream_legal_doc_count = 0
    upstream_map_doc_count = 0
    upstream_verification_doc_count = 0

    for t in txn_rows:
        input_type = node_name_to_type.get((t["input_node_name"] or "").strip().lower(), "")
        reporting_type = node_name_to_type.get((t["reporting_node_name"] or "").strip().lower(), "")
        output_type = node_name_to_type.get((t["output_node_name"] or "").strip().lower(), "")
        if not ((t["reporting_node_name"] if "reporting_node_name" in t.keys() else "") or "").strip():
            warnings.append(f"R034: reporting entity is recommended for txn {t['txn_id']}")
        if (
            input_type in {"forest", "farm"}
            or reporting_type in {"forest", "farm"}
            or output_type in {"forest", "farm"}
        ):
            upstream_txn_count += 1
            geo_id = (t["geo_id"] or "").strip()
            if not geo_id:
                errors.append(f"R030: upstream forest/farm transaction requires txn.geo_id for txn {t['txn_id']}")
            else:
                upstream_geo_ids.add(geo_id)

    if upstream_geo_ids:
        for e in ev_rows:
            link_id = (e["link_id"] or "").strip()
            if e["link_type"] == "geo" and link_id in upstream_geo_ids:
                if e["evidence_type"] in {"land_ownership_certificate", "land_lease_agreement", "logging_license", "harvest_permit"}:
                    upstream_legal_doc_count += 1
                if e["evidence_type"] in {"digital_map", "photo_map"}:
                    upstream_map_doc_count += 1
                if e["evidence_type"] in {"site_photo", "field_assessment_report"}:
                    upstream_verification_doc_count += 1

    if upstream_txn_count:
        if upstream_legal_doc_count < 1:
            warnings.append("R031: upstream forest/farm areas should include at least one legality or land-right document")
        if upstream_map_doc_count < 1:
            warnings.append("R032: upstream forest/farm areas should include at least one map or boundary document")
        if upstream_verification_doc_count < 1:
            warnings.append("R033: upstream forest/farm areas should include at least one site photo or field assessment")

    if rec["integrity_mode"] == "source_fact":
        # R021/R022/R025 (+ R023): txn assessment required and paired
        for t in txn_rows:
            risk = ((t["assessment_risk_level"] if t["assessment_risk_level"] is not None else "")).strip()
            concl = ((t["assessment_conclusion"] if t["assessment_conclusion"] is not None else "")).strip()

            if not risk:
                errors.append(f"R021: missing txn.assessment_risk_level for txn.id {t['txn_id']}")
            elif risk not in {"negligible", "low", "medium", "high"}:
                errors.append(f"R023: invalid txn.assessment_risk_level for txn.id {t['txn_id']}: {risk}")

            if not concl:
                errors.append(f"R022: missing txn.assessment_conclusion for txn.id {t['txn_id']}")

            if (bool(risk) != bool(concl)):
                errors.append(f"R025: txn assessment fields must be paired for txn.id {t['txn_id']}")

        # R005: source_fact requires evidence.link_id
        for e in ev_rows:
            if not (e["link_id"] and str(e["link_id"]).strip()):
                errors.append(f"R005: missing link_id for {e['evidence_id']}")

        # R026: source_fact requires at least one geo anchor
        if len(geo_ids) < 1:
            errors.append("R026: source_fact requires at least one geo anchor (geo.id)")

        # R028: source_fact recommends txn.geo_id (warning only)
        for t in txn_rows:
            geo_id = (t["geo_id"] or "").strip()
            if not geo_id:
                warnings.append(
                    f"R028: source_fact recommends providing txn.geo_id for txn {t['txn_id']}"
                )

        # R029: txn.geo_id must reference existing geo.id
        for t in txn_rows:
            geo_id = (t["geo_id"] or "").strip()
            if geo_id and geo_id not in geo_ids:
                errors.append(
                    f"R029: txn {t['txn_id']} references non-existing geo.id: {geo_id}"
                )

        # R009: if link_type=geo, link_id must reference existing geo.id
        for e in ev_rows:
            if e["link_type"] == "geo":
                link_id = (e["link_id"] or "").strip()
                if link_id and link_id not in geo_ids:
                    errors.append(f"R009: evidence {e['evidence_id']} links to non-existing geo.id: {link_id}")

        # R027: symbolic geo requires map evidence in source_fact mode
        # Find symbolic geo ids
        symbolic_geo_ids = {
            g["geo_id"]
            for g in geo_rows
            if g["anchor_type"] == "symbolic"
        }

        if symbolic_geo_ids:
            has_symbolic_map = False
            for e in ev_rows:
                if (
                    e["evidence_type"] in {"digital_map", "photo_map"}
                    and e["link_type"] == "geo"
                    and (e["link_id"] or "").strip() in symbolic_geo_ids
                ):
                    has_symbolic_map = True
                    break

            if not has_symbolic_map:
                errors.append(
                    "R027: symbolic geo anchors require at least one "
                    "digital_map or photo_map evidence linked to symbolic geo.id"
                )

    return errors, warnings
