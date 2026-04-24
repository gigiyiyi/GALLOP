# ui/workspace.py

import streamlit as st
import pandas as pd
import uuid
from i18n import evidence_type_label, link_type_label, option_label, t

from constants import (
    EVIDENCE_TYPE_OPTIONS,
    LINK_TYPE_OPTIONS,
    EVIDENCE_TYPE_META,
    EVIDENCE_TYPE_SUGGESTED_LINK,
    EVIDENCE_TYPE_ALLOWED_LINKS,
    TXN_RISK_LEVEL_OPTIONS,
)

import re

SOURCE_PAGE_EVIDENCE_TYPES = [
    "land_ownership_certificate",
    "land_lease_agreement",
    "logging_license",
    "harvest_permit",
    "digital_map",
    "photo_map",
    "site_photo",
    "field_assessment_report",
]

def _issues_key(selected: str) -> str:
    return f"issues_{selected}"


def _rerun_workspace(selected: str):
    st.session_state["workspace_selected_record"] = selected
    st.session_state["nav_target"] = t("nav.workspace")
    st.rerun()


def _build_evidence_target_options(txn_rows, node_rows, geo_rows) -> dict[str, list[tuple[str, str]]]:
    txn_options = []
    for txn in txn_rows:
        product = (txn["product_name"] or "").strip() or t("workspace.txn_product_fallback")
        output = (txn["output_node_name"] or "").strip() or t("workspace.txn_to_fallback")
        txn_options.append((txn["txn_id"], f"{product} -> {output}"))

    node_options = []
    for n in node_rows:
        name = (n["name"] or "").strip() or t("workspace.node_fallback")
        node_type = (n["type"] or "").strip()
        label = f"{name} ({option_label('node_type', node_type)})" if node_type else name
        node_options.append((n["node_id"], label))

    geo_options = []
    for g in geo_rows:
        anchor_type = option_label("geo_anchor", (g["anchor_type"] or "").strip()) if (g["anchor_type"] or "").strip() else link_type_label("geo")
        file_name = (g["file_name"] or "").strip() or t("workspace.file_fallback")
        geo_options.append((g["geo_id"], f"{anchor_type} - {file_name}"))

    return {
        "txn": txn_options,
        "node": node_options,
        "geo": geo_options,
        "batch_system": node_options,
    }


def _allowed_link_types(evidence_type: str) -> list[str]:
    return EVIDENCE_TYPE_ALLOWED_LINKS.get(evidence_type, LINK_TYPE_OPTIONS)


def _render_link_target_selector(selected: str, scope: str, link_type: str, target_options: dict[str, list[tuple[str, str]]], current_link_id: str | None = None):
    options = [("", t("workspace.evidence_target_empty"))]
    options.extend(target_options.get(link_type, []))

    option_ids = [opt_id for opt_id, _ in options]
    if current_link_id and current_link_id not in option_ids:
        options.append((current_link_id, t("workspace.evidence_target_current", target_id=current_link_id)))
        option_ids.append(current_link_id)

    labels = {opt_id: label for opt_id, label in options}
    widget_key = f"{scope}_{selected}_{link_type}"
    return st.selectbox(
        t("workspace.evidence_target"),
        option_ids,
        index=option_ids.index(current_link_id) if current_link_id in option_ids else 0,
        format_func=lambda opt_id: labels.get(opt_id, opt_id),
        key=widget_key,
    )


def _localized_evidence_meta(evidence_type: str) -> dict | None:
    meta = EVIDENCE_TYPE_META.get(evidence_type)
    if not meta:
        return None
    category_map = {
        "source / geo": "evidence_category.source_geo",
        "geo": "evidence_category.geo",
        "geo / source": "evidence_category.geo_source",
        "permit": "evidence_category.permit",
        "transaction": "evidence_category.transaction",
        "node": "evidence_category.node",
        "batch_system": "evidence_category.batch_system",
    }
    return {
        "category": t(category_map.get(meta["category"], meta["category"])),
        "description": t(f"evidence_desc.{evidence_type}"),
    }


def _reporting_upstream_nodes(node_rows, txn_rows):
    reporting_names = {
        (txn.get("reporting_node_name") or "").strip().lower()
        for txn in txn_rows
        if (txn.get("reporting_node_name") or "").strip()
    }
    return [
        dict(n)
        for n in node_rows
        if (n["type"] or "").strip() in {"forest", "farm"}
        and (n["name"] or "").strip().lower() in reporting_names
    ]


def _txns_for_node(txn_rows, node_name: str):
    node_name = (node_name or "").strip().lower()
    if not node_name:
        return []
    matched = []
    for txn in txn_rows:
        input_name = (txn["input_node_name"] or "").strip().lower()
        reporting_name = (txn.get("reporting_node_name") or "").strip().lower()
        output_name = (txn["output_node_name"] or "").strip().lower()
        if node_name in {input_name, reporting_name, output_name}:
            matched.append(dict(txn))
    return matched


def source_page_applies(node_rows, txn_rows) -> bool:
    return bool(_reporting_upstream_nodes(node_rows, txn_rows))


def _geo_labels_map(geo_rows):
    labels = {}
    for geo in geo_rows:
        anchor_type = option_label("geo_anchor", (geo["anchor_type"] or "").strip()) if (geo["anchor_type"] or "").strip() else link_type_label("geo")
        file_name = (geo["file_name"] or "").strip() or t("workspace.file_fallback")
        labels[geo["geo_id"]] = f"{anchor_type} - {file_name}"
    return labels

def _parse_issue(msg: str) -> dict:
    """
    Convert your rule message string into a minimal structured issue.
    Examples of messages:
      'R005: missing link_id for <evidence_id>'
      'R021: missing txn.assessment_risk_level for txn.id <txn_id>'
      'R029: txn <txn_id> references non-existing geo.id: <geo_id>'
    """
    rule_id = msg.split(":", 1)[0].strip() if ":" in msg else "N/A"
    issue = {
        "rule_id": rule_id,
        "severity": "error",   # default; warnings handled outside
        "message": msg,
        "scope": "record",
        "target_id": "",
    }

    # txn.id patterns
    m = re.search(r"txn\.id\s+([0-9a-fA-F-]{8,})", msg)
    if not m:
        m = re.search(r"txn\s+([0-9a-fA-F-]{8,})", msg)
    if m:
        issue["scope"] = "txn"
        issue["target_id"] = m.group(1)
        return issue

    # evidence id patterns
    m = re.search(r"evidence\s+([0-9a-fA-F-]{8,})", msg)
    if not m:
        m = re.search(r"for\s+([0-9a-fA-F-]{8,})", msg)  # e.g. missing link_id for <id>
    if m:
        issue["scope"] = "evidence"
        issue["target_id"] = m.group(1)
        return issue

    # geo id patterns
    m = re.search(r"geo\.id:\s*([0-9a-fA-F-]{8,})", msg)
    if m:
        issue["scope"] = "geo"
        issue["target_id"] = m.group(1)
        return issue

    return issue

def render_workspace_header(rec):
    st.markdown(f"## {t('workspace.title')} — {rec['case_title']}")


def _record_is_finalized(rec) -> bool:
    return rec["status"] in {"submitted", "sealed", "superseded"}

def render_transactions_section(selected, u, rec, list_txns, replace_txns, can_edit, list_geos):
    """
    Thin wrapper to keep app.py stable during refactor.
    Currently reuses render_workspace_main (txn-only at this stage).
    """
    render_workspace_main(
        selected=selected,
        u=u,
        rec=rec,
        can_edit=can_edit,
        list_txns=list_txns,
        replace_txns=replace_txns,
        list_geos=list_geos,
    )

def render_nodes_section(selected, u, rec, can_edit, list_nodes, update_nodes, resolve_nodes_for_record):
    st.markdown(f"### {t('workspace.nodes_title')}")
    editable = can_edit(u["role"]) and not _record_is_finalized(rec)

    node_rows = list_nodes(selected)

    if node_rows:
        node_df = pd.DataFrame([dict(n) for n in node_rows])

        node_df = node_df[
            [
                "node_id",
                "name",
                "registration_number",
                "type",
                "address_production",
                "address_registration",
                "country",
                "batch_method",
                "third_party_cert",
            ]
        ]

        st.markdown(f"#### {t('workspace.nodes_editable')}")

        edited_nodes = st.data_editor(
            node_df,
            use_container_width=True,
            hide_index=True,
            disabled=True if not editable else ["node_id", "name"],
            column_config={
                "node_id": st.column_config.TextColumn(t("field.node_id")),
                "name": st.column_config.TextColumn(t("field.node_name")),
                "registration_number": st.column_config.TextColumn(t("field.node_registration_number")),
                "type": st.column_config.SelectboxColumn(
                    t("field.node_type"),
                    options=["", "forest", "farm", "processor", "trader"],
                    format_func=lambda value: option_label("node_type", value) if value else "",
                ),
                "address_production": st.column_config.TextColumn(t("field.node_address_production")),
                "address_registration": st.column_config.TextColumn(t("field.node_address_registration")),
                "country": st.column_config.TextColumn(t("field.node_country")),
                "batch_method": st.column_config.SelectboxColumn(
                    t("field.node_batch_method"),
                    options=[
                        "",
                        "time_segment",
                        "source_restricted",
                        "physical_separation",
                        "order_driven",
                        "identity_preserved",
                        "book_and_claim",
                        "no_control",
                    ],
                    format_func=lambda value: option_label("batch_method", value) if value else "",
                ),
                "third_party_cert": st.column_config.TextColumn(t("field.node_third_party_cert")),
            },
            key=f"nodes_editor_{selected}",
        )

        if editable:
            if st.button(t("workspace.nodes_save"), key=f"save_nodes_{selected}"):
                update_nodes(selected, edited_nodes.to_dict(orient="records"))
                st.success(t("workspace.nodes_saved"))
                _rerun_workspace(selected)
        else:
            st.info(t("workspace.read_only"))
    else:
        st.info(t("workspace.nodes_empty"))

    if editable:
        if st.button(t("workspace.nodes_resolve"), key=f"resolve_nodes_{selected}"):
            resolve_nodes_for_record(selected)
            st.success(t("workspace.nodes_resolved"))
            _rerun_workspace(selected)
    else:
        st.info(t("workspace.read_only"))

def render_geo_section(selected, u, rec, can_edit, list_geos, insert_geo):
    st.markdown(f"### {t('workspace.geo_title')}")
    editable = can_edit(u["role"]) and not _record_is_finalized(rec)

    geo_rows = list_geos(selected)

    if geo_rows:
        st.dataframe(
            [
                {
                    t("field.geo_id"): g["geo_id"],
                    t("field.geo_anchor_type"): option_label("geo_anchor", g["anchor_type"]) if g["anchor_type"] else "",
                    t("field.geo_file_name"): g["file_name"],
                    t("field.geo_created_at"): g["created_at"],
                }
                for g in geo_rows
            ],
            use_container_width=True,
        )
    else:
        st.info(t("workspace.geo_empty"))

    if editable:
        with st.form(key=f"geo_form_{selected}", clear_on_submit=True):
            geo_anchor_type = st.selectbox(
                t("workspace.geo_anchor_type"),
                ["point", "polygon", "symbolic"],
                format_func=lambda value: option_label("geo_anchor", value),
                key=f"geo_anchor_type_{selected}",
            )
            geo_file = st.file_uploader(
                t("workspace.geo_file"),
                accept_multiple_files=False,
                key=f"geo_uploader_{selected}",
            )
            geo_submitted = st.form_submit_button(t("workspace.geo_add"))

        if geo_submitted:
            if not geo_file:
                st.error(t("workspace.geo_missing_file"))
            else:
                gid = insert_geo(
                    record_id=selected,
                    anchor_type=geo_anchor_type,
                    original_name=geo_file.name,
                    content_bytes=geo_file.getvalue(),
                )
                st.success(t("workspace.geo_created", geo_id=gid))
                _rerun_workspace(selected)
    else:
        st.info(t("workspace.read_only"))


def render_source_page_section(
    selected,
    u,
    rec,
    can_edit,
    list_nodes,
    list_txns,
    list_geos,
    list_evidences,
    insert_evidence,
):
    st.markdown(f"### {t('workspace.source_page_title')}")
    editable = can_edit(u["role"]) and not _record_is_finalized(rec)

    node_rows = list_nodes(selected)
    txn_rows = list_txns(selected)
    geo_rows = list_geos(selected)
    evidence_rows = list_evidences(selected)
    upstream_nodes = _reporting_upstream_nodes(node_rows, txn_rows)

    st.caption(t("workspace.source_page_intro"))

    if not upstream_nodes:
        st.info(t("workspace.source_page_empty"))
        if (u.get("org_type") or "").strip() in {"forest", "farm"}:
            st.caption(t("workspace.source_page_user_hint"))
        return

    st.info(t("workspace.source_page_logic"))
    geo_label_map = _geo_labels_map(geo_rows)

    for node in upstream_nodes:
        node_name = (node.get("name") or "").strip() or t("workspace.node_fallback")
        node_type = option_label("node_type", node.get("type") or "")
        related_txns = _txns_for_node(txn_rows, node_name)
        related_geo_ids = sorted({(txn.get("geo_id") or "").strip() for txn in related_txns if (txn.get("geo_id") or "").strip()})
        geo_evidence = [
            dict(e)
            for e in evidence_rows
            if e["link_type"] == "geo" and (e["link_id"] or "").strip() in related_geo_ids
        ]
        source_docs = [e for e in geo_evidence if e["evidence_type"] in SOURCE_PAGE_EVIDENCE_TYPES]
        legality_docs = [
            e for e in source_docs
            if e["evidence_type"] in {"land_ownership_certificate", "land_lease_agreement", "logging_license", "harvest_permit"}
        ]
        map_docs = [e for e in source_docs if e["evidence_type"] in {"digital_map", "photo_map"}]
        verification_docs = [e for e in source_docs if e["evidence_type"] in {"site_photo", "field_assessment_report"}]
        missing_geo_links = [txn for txn in related_txns if not (txn.get("geo_id") or "").strip()]

        with st.container(border=True):
            st.markdown(f"**{node_name}**")
            st.caption(t("workspace.source_page_node_meta", node_type=node_type or t("workspace.source_page_unknown_type")))

            summary_cols = st.columns(4)
            summary_cols[0].metric(t("workspace.source_page_metric_txns"), len(related_txns))
            summary_cols[1].metric(t("workspace.source_page_metric_locations"), len(related_geo_ids))
            summary_cols[2].metric(t("workspace.source_page_metric_docs"), len(source_docs))
            summary_cols[3].metric(t("workspace.source_page_metric_missing"), len(missing_geo_links))

            if related_txns:
                txn_lines = []
                for txn in related_txns:
                    product = (txn.get("product_name") or "").strip() or t("workspace.txn_product_fallback")
                    geo_id = (txn.get("geo_id") or "").strip()
                    geo_label = geo_label_map.get(geo_id, t("workspace.source_page_no_location"))
                    txn_lines.append(f"- {product}: {geo_label}")
                st.markdown(f"**{t('workspace.source_page_related_txns')}**")
                st.markdown("\n".join(txn_lines))
            else:
                st.info(t("workspace.source_page_no_related_txns"))

            st.markdown(f"**{t('workspace.source_page_checklist')}**")
            checklist_lines = [
                t(
                    "workspace.source_page_check_required_geo",
                    status=t("workspace.status_done") if not missing_geo_links and related_txns else t("workspace.status_pending"),
                ),
                t(
                    "workspace.source_page_check_required_legal",
                    status=t("workspace.status_done") if legality_docs else t("workspace.status_pending"),
                ),
                t(
                    "workspace.source_page_check_recommended_map",
                    status=t("workspace.status_done") if map_docs else t("workspace.status_recommended"),
                ),
                t(
                    "workspace.source_page_check_recommended_verification",
                    status=t("workspace.status_done") if verification_docs else t("workspace.status_recommended"),
                ),
            ]
            st.markdown("\n".join([f"- {line}" for line in checklist_lines]))

            if related_geo_ids:
                st.markdown(f"**{t('workspace.source_page_locations')}**")
                st.markdown("\n".join([f"- {geo_label_map.get(geo_id, geo_id)}" for geo_id in related_geo_ids]))

            if source_docs:
                st.markdown(f"**{t('workspace.source_page_existing_docs')}**")
                st.markdown(
                    "\n".join(
                        [
                            f"- {evidence_type_label(e['evidence_type'])}: {e['file_name']}"
                            for e in source_docs[:8]
                        ]
                    )
                )
            else:
                st.caption(t("workspace.source_page_no_docs"))

    st.markdown(f"#### {t('workspace.source_page_upload_title')}")
    if not editable:
        st.warning(t("workspace.read_only"))
        return

    if not geo_rows:
        st.warning(t("workspace.source_page_upload_no_geo"))
        return

    geo_option_ids = [g["geo_id"] for g in geo_rows]
    geo_labels = {g["geo_id"]: geo_label_map.get(g["geo_id"], g["geo_id"]) for g in geo_rows}

    with st.form(key=f"source_page_upload_{selected}", clear_on_submit=True):
        upload_cols = st.columns([2, 2])
        with upload_cols[0]:
            evidence_type = st.selectbox(
                t("workspace.source_page_upload_type"),
                SOURCE_PAGE_EVIDENCE_TYPES,
                format_func=evidence_type_label,
                key=f"source_page_type_{selected}",
            )
        with upload_cols[1]:
            link_id = st.selectbox(
                t("workspace.source_page_upload_location"),
                geo_option_ids,
                format_func=lambda geo_id: geo_labels.get(geo_id, geo_id),
                key=f"source_page_geo_{selected}",
            )

        files = st.file_uploader(
            t("workspace.source_page_upload_files"),
            accept_multiple_files=True,
            key=f"source_page_files_{selected}",
        )
        submitted = st.form_submit_button(t("workspace.source_page_upload_button"))

    if submitted:
        if not files:
            st.error(t("workspace.evidence_select_files_error"))
        else:
            for f in files:
                insert_evidence(
                    record_id=selected,
                    evidence_type=evidence_type,
                    original_name=f.name,
                    content_bytes=f.getvalue(),
                    link_type="geo",
                    link_id=link_id,
                )
            st.success(t("workspace.source_page_uploaded"))
            _rerun_workspace(selected)

def render_evidence_section(
    selected,
    u,
    rec,
    can_edit,
    list_evidences,
    insert_evidence,
    update_evidence_link,
    list_txns,
    list_nodes,
    list_geos,
):
    st.markdown(f"### {t('workspace.evidence_title')}")
    editable = can_edit(u["role"]) and not _record_is_finalized(rec)
    ev_rows = list_evidences(selected)
    txn_rows = list_txns(selected)
    node_rows = list_nodes(selected)
    geo_rows = list_geos(selected)
    target_options = _build_evidence_target_options(txn_rows, node_rows, geo_rows)

    st.markdown(f"#### {t('workspace.evidence_list')}")

    if ev_rows:
        st.dataframe(
            [
                {
                    t("field.evidence_id"): e["evidence_id"],
                    t("field.evidence_type"): evidence_type_label(e["evidence_type"]),
                    t("field.evidence_file_name"): e["file_name"],
                    t("field.evidence_date"): e["uploaded_at"],
                    t("field.evidence_record_id"): e["record_id"],
                    t("field.evidence_link_type"): link_type_label(e["link_type"]) if e["link_type"] else "",
                    t("field.evidence_link_id"): e["link_id"] or "",
                    t("field.evidence_file_hash"): e["file_hash"],
                }
                for e in ev_rows
            ],
            use_container_width=True,
        )
    else:
        st.info(t("workspace.evidence_empty"))

    # Edit evidence
    st.markdown(f"### {t('workspace.evidence_edit')}")
    if not ev_rows:
        st.info(t("workspace.evidence_edit_empty"))
    elif not editable:
        st.warning(t("workspace.read_only"))
    else:
        focus_evidence = st.session_state.get("focus_evidence_id")
        ordered_ev_rows = ev_rows
        if focus_evidence:
            ordered_ev_rows = sorted(
                ev_rows,
                key=lambda evidence: 0 if evidence["evidence_id"] == focus_evidence else 1,
            )

        for e in ordered_ev_rows:
            expander_title = f"{e['file_name']} ({evidence_type_label(e['evidence_type'])})"
            with st.expander(expander_title, expanded=(focus_evidence == e["evidence_id"])):
                if focus_evidence == e["evidence_id"]:
                    st.info(t("workspace.evidence_focus_hint"))
                    st.session_state["focus_evidence_id"] = None
                current_type = e["evidence_type"]
                allowed_link_types = _allowed_link_types(current_type)
                default_link_type = e["link_type"] if e["link_type"] in allowed_link_types else EVIDENCE_TYPE_SUGGESTED_LINK.get(current_type, allowed_link_types[0])

                with st.form(key=f"edit_evidence_form_{e['evidence_id']}"):
                    evidence_type = st.selectbox(
                        t("field.evidence_type"),
                        EVIDENCE_TYPE_OPTIONS,
                        index=EVIDENCE_TYPE_OPTIONS.index(current_type) if current_type in EVIDENCE_TYPE_OPTIONS else 0,
                        format_func=evidence_type_label,
                        key=f"edit_evidence_type_{e['evidence_id']}",
                    )
                    meta = _localized_evidence_meta(evidence_type)
                    if meta:
                        st.caption(f"{meta['category']}: {meta['description']}")

                    allowed_link_types = _allowed_link_types(evidence_type)
                    suggested_link_type = EVIDENCE_TYPE_SUGGESTED_LINK.get(evidence_type, allowed_link_types[0])
                    link_type = st.selectbox(
                        t("workspace.evidence_supports"),
                        allowed_link_types,
                        index=allowed_link_types.index(default_link_type) if default_link_type in allowed_link_types else allowed_link_types.index(suggested_link_type),
                        format_func=lambda value: t("workspace.evidence_recommended", label=link_type_label(value)) if value == suggested_link_type else link_type_label(value),
                        key=f"edit_link_type_{e['evidence_id']}",
                    )
                    link_id = _render_link_target_selector(
                        selected,
                        f"edit_link_id_{e['evidence_id']}",
                        link_type,
                        target_options,
                        e["link_id"] or "",
                    )
                    save_row = st.form_submit_button(t("workspace.evidence_save_mapping"))

                if save_row:
                    update_evidence_link(
                        evidence_id=e["evidence_id"],
                        record_id=selected,
                        evidence_type=evidence_type,
                        link_type=link_type,
                        link_id=link_id or None,
                    )
                    st.success(t("workspace.evidence_saved"))
                    _rerun_workspace(selected)

    # Upload evidence with semantic hint (real-time)
    st.markdown(f"### {t('workspace.evidence_upload')}")

    colA, colB = st.columns([2, 2])
    with colA:
        evidence_type = st.selectbox(
            t("field.evidence_type"),
            EVIDENCE_TYPE_OPTIONS,
            format_func=evidence_type_label,
            key=f"ev_type_live_{selected}",
        )
    with colB:
        allowed_link_types = _allowed_link_types(evidence_type)
        suggested_link_type = EVIDENCE_TYPE_SUGGESTED_LINK.get(evidence_type, allowed_link_types[0])
        link_type = st.selectbox(
            t("workspace.evidence_supports"),
            allowed_link_types,
            index=allowed_link_types.index(suggested_link_type),
            format_func=lambda value: t("workspace.evidence_recommended", label=link_type_label(value)) if value == suggested_link_type else link_type_label(value),
            key=f"ev_link_type_live_{selected}",
        )

    meta = _localized_evidence_meta(evidence_type)
    if meta:
        st.info(f"**{t('workspace.evidence_type_category')}:** {meta['category']}\n\n**{t('workspace.evidence_meaning')}:** {meta['description']}")

    # Optional: keep a light recommendation too
    suggested = EVIDENCE_TYPE_SUGGESTED_LINK.get(evidence_type)
    if suggested and link_type != suggested:
        st.caption(
            f"💡 {t('workspace.evidence_anchor_hint', evidence_type=evidence_type_label(evidence_type), suggested=link_type_label(suggested), selected=link_type_label(link_type))}"
        )

    if not editable:
        st.warning(t("workspace.read_only"))
    else:
        with st.form(key=f"upload_form_{selected}", clear_on_submit=True):
            files = st.file_uploader(
                t("workspace.evidence_select_files"),
                accept_multiple_files=True,
                key=f"evidence_uploader_{selected}",
            )
            if not target_options.get(link_type):
                st.warning(t("workspace.evidence_no_targets", link_type=link_type_label(link_type)))
            link_id = _render_link_target_selector(
                selected,
                "upload_link_id",
                link_type,
                target_options,
                "",
            )
            submitted = st.form_submit_button(t("workspace.evidence_upload_button"))

        if submitted:
            if not files:
                st.error(t("workspace.evidence_select_files_error"))
            else:
                for f in files:
                    insert_evidence(
                        record_id=selected,
                        evidence_type=evidence_type,
                        original_name=f.name,
                        content_bytes=f.getvalue(),
                        link_type=link_type,
                        link_id=(link_id.strip() or None),
                    )
                st.success(t("workspace.evidence_uploaded"))
                _rerun_workspace(selected)


def render_validate_section(
    selected,
    u,
    rec,
    can_seal,
    list_evidences,
    list_txns,
    list_nodes,
    list_geos,
    validate_record_v1,
    compute_manifest_hash,
    submit_record,
    seal_record,
    downgrade_record,
    build_manifest_json,
    build_localized_manifest_json,
    build_full_package_zip,
):
    st.markdown("---")
    st.subheader(t("workspace.validate_title"))

    ev_rows = list_evidences(selected)
    txn_rows = list_txns(selected)
    node_rows = list_nodes(selected)
    geo_rows = list_geos(selected)

    errors, warnings = validate_record_v1(rec, ev_rows, txn_rows, node_rows, geo_rows)
    # Build structured issues (in-memory, per record)
    issues = []
    for msg in errors:
        it = _parse_issue(msg)
        it["severity"] = "error"
        issues.append(it)
    for msg in warnings:
        it = _parse_issue(msg)
        it["severity"] = "warning"
        issues.append(it)

    st.session_state[_issues_key(selected)] = issues

    # Persist last validation result per record so UI can show details
    vkey = f"validation_result_{selected}"
    if vkey not in st.session_state:
        st.session_state[vkey] = {"ran": False, "errors": [], "warnings": []}

    colv1, colv2, colv3 = st.columns([1, 1, 2])

    with colv1:
        if st.button(t("workspace.validate_button"), key=f"validate_{selected}"):
            st.session_state[vkey] = {"ran": True, "errors": errors, "warnings": warnings}
            if errors:
                st.error(t("workspace.validate_failed", count=len(errors)))
            else:
                st.success(t("workspace.validate_passed"))

    with colv2:
        locked = _record_is_finalized(rec)
        is_source_fact = rec["integrity_mode"] == "source_fact"
        action_label = t("workspace.action_seal") if is_source_fact else t("workspace.action_submit")
        action_disabled = locked or (not can_seal(u["role"])) or (is_source_fact and bool(errors))

        if u["role"] == "dds_viewer":
            st.info(t("workspace.read_only_submit"))

        if st.button(action_label, key=f"record_action_{selected}", disabled=action_disabled):
            mh = compute_manifest_hash(ev_rows)
            if is_source_fact:
                seal_record(rec["record_id"], u["org_id"], mh)
                st.success(t("workspace.record_sealed"))
            else:
                submit_record(rec["record_id"], u["org_id"], mh)
                st.success(t("workspace.record_submitted"))
            _rerun_workspace(selected)

    with colv3:
        vr = st.session_state[vkey]
        if not vr["ran"]:
            st.caption(t("workspace.validate_prompt"))
        else:
            if vr["errors"]:
                st.write(f"**{t('workspace.errors')}**")
                for msg in vr["errors"]:
                    st.write("-", msg)
            if vr["warnings"]:
                st.write(f"**{t('workspace.warnings')}**")
                for msg in vr["warnings"]:
                    st.write("-", msg)
            if (not vr["errors"]) and (not vr["warnings"]):
                st.write(t("workspace.no_validation_issues"))

    if rec["integrity_mode"] == "source_fact" and rec["status"] == "draft" and can_seal(u["role"]):
        with st.form(key=f"downgrade_form_{selected}"):
            reason = st.text_area(
                t("workspace.downgrade_reason"),
                help=t("workspace.downgrade_help"),
            )
            downgrade_submitted = st.form_submit_button(t("workspace.downgrade_button"))
        if downgrade_submitted:
            if not reason.strip():
                st.error(t("workspace.downgrade_missing"))
            else:
                downgrade_record(rec["record_id"], u["org_id"], u["email"], reason)
                st.success(t("workspace.downgraded"))
                _rerun_workspace(selected)

    # Export (only when submitted or sealed)
    if rec["status"] in {"submitted", "sealed"}:
        st.markdown(f"#### {t('workspace.export_title')}")

        export_lang = st.session_state.get("lang", "en")
        manifest_obj = build_manifest_json(rec, ev_rows, txn_rows, geo_rows)
        localized_manifest_obj = None
        localized_lang = None
        if export_lang and export_lang != "en":
            localized_manifest_obj = build_localized_manifest_json(rec, ev_rows, txn_rows, geo_rows, export_lang)
            localized_lang = export_lang
        zip_buf = build_full_package_zip(
            manifest_obj,
            ev_rows,
            txn_rows,
            geo_rows,
            localized_manifest_obj,
            localized_lang,
        )

        st.download_button(
            t("workspace.export_zip"),
            data=zip_buf,
            file_name=f"{rec['record_id']}.zip",
            mime="application/zip",
        )


def render_workspace_main(selected, u, rec, can_edit, list_txns, replace_txns, list_geos=None, list_nodes=None, update_nodes=None, resolve_nodes_for_record=None):
    st.markdown(f"### {t('workspace.txn_title')}")
    editable = can_edit(u["role"]) and not _record_is_finalized(rec)

    txn_rows = list_txns(selected)
    txn_dicts = [dict(t) for t in txn_rows] if txn_rows else []
    geo_rows = list_geos(selected) if list_geos else []
    geo_options = [("", t("workspace.txn_geo_empty"))]
    for geo in geo_rows:
        anchor_type = option_label("geo_anchor", (geo["anchor_type"] or "").strip()) if (geo["anchor_type"] or "").strip() else link_type_label("geo")
        file_name = (geo["file_name"] or "").strip() or t("workspace.file_fallback")
        geo_options.append((geo["geo_id"], f"{anchor_type} - {file_name}"))

    draft_key = f"txn_draft_{selected}"
    if draft_key not in st.session_state:
        st.session_state[draft_key] = txn_dicts

    draft = st.session_state[draft_key]

    # Add transaction button
    if editable:
        if st.button(f"➕ {t('workspace.txn_add')}", key=f"add_txn_{selected}"):
            draft.append(
                {
                    "txn_id": str(uuid.uuid4()),
                    # Row 1 (Sales / Output)
                    "product_name": "",
                    "output_node_name": "",
                    "reporting_node_name": "",
                    "species_common": "",
                    "species_latin": "",
                    "product_weight": None,
                    "product_volume": None,
                    "geo_id": "",
                    # Row 2 (Input / Production)
                    "input_node_name": "",
                    "quantity_unit": "",
                    "input_quantity": None,
                    "output_quantity": None,
                    "production_start_date": "",
                    "production_end_date": "",
                    "batch_label": "",
                    "assessment_risk_level": "",
                    "assessment_conclusion": "",
                }
            )
            st.session_state[draft_key] = draft
            _rerun_workspace(selected)
    else:
        st.info(t("workspace.read_only"))

    # Render transactions as three-row cards
    focus_txn = st.session_state.get("focus_txn_id")
    editing_txn = st.session_state.get("editing_txn_id")
    ordered_txns = list(enumerate(draft))
    if focus_txn:
        ordered_txns.sort(key=lambda pair: 0 if pair[1].get("txn_id") == focus_txn else 1)

    for i, txn in ordered_txns:
        product_name = (txn.get("product_name") or "").strip()
        output_node_name = (txn.get("output_node_name") or "").strip()
        display = f"{product_name or t('workspace.txn_product_fallback')} → {output_node_name or t('workspace.txn_to_fallback')}"

        focus_txn = st.session_state.get("focus_txn_id")
        with st.expander(
            f"Txn {i+1}: {display}",
            expanded=(focus_txn == txn.get("txn_id") or editing_txn == txn.get("txn_id")),
        ):
            # 如果是通过 issue 跳转来的，只展开一次
            if focus_txn == txn.get("txn_id"):
                st.info(t("workspace.txn_focus_hint_geo"))
                st.session_state["focus_txn_id"] = None

            # ----- Actions -----
            if editable:
                if not _record_is_finalized(rec):
                    col_del, col_sp = st.columns([1, 5])
                    with col_del:
                        if st.button(f"🗑 {t('workspace.txn_delete')}", key=f"del_txn_{selected}_{txn.get('txn_id','')}_{i}"):
                            draft.pop(i)
                            st.session_state[draft_key] = draft
                            _rerun_workspace(selected)
                else:
                    st.info(t("workspace.txn_finalized"))
            st.caption(f"{t('workspace.txn_id')}: {txn.get('txn_id', '')}")            
            
            # -----------------------------
            # Row 1 — Sales / Output
            # -----------------------------
            st.markdown(f"**{t('workspace.txn_row1')}**")
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

            with c1:
                txn["product_name"] = st.text_input(
                    t("field.txn_product_name"),
                    value=txn.get("product_name") or "",
                    key=f"txn_product_{selected}_{i}",
                    disabled=not editable,
                )
                # 👇 这一行：标记“当前正在编辑的 txn”
                st.session_state["editing_txn_id"] = txn.get("txn_id")
                txn["species_common"] = st.text_input(
                    t("field.txn_species_common"),
                    value=txn.get("species_common") or "",
                    key=f"txn_species_common_{selected}_{i}",
                    disabled=not editable,
                )

            with c2:
                txn["output_node_name"] = st.text_input(
                    t("field.txn_output_node_name"),
                    value=txn.get("output_node_name") or "",
                    key=f"txn_output_node_{selected}_{i}",
                    disabled=not editable,
                )
                txn["species_latin"] = st.text_input(
                    t("field.txn_species_latin"),
                    value=txn.get("species_latin") or "",
                    key=f"txn_species_latin_{selected}_{i}",
                    disabled=not editable,
                )

            with c3:
                # allow empty -> store None
                pw_val = txn.get("product_weight")
                pv_val = txn.get("product_volume")
                txn["product_weight"] = st.number_input(
                    t("field.txn_product_weight"),
                    value=float(pw_val) if pw_val not in (None, "", "None") else 0.0,
                    min_value=0.0,
                    key=f"txn_weight_{selected}_{i}",
                    disabled=not editable,
                )
                txn["product_volume"] = st.number_input(
                    t("field.txn_product_volume"),
                    value=float(pv_val) if pv_val not in (None, "", "None") else 0.0,
                    min_value=0.0,
                    key=f"txn_volume_{selected}_{i}",
                    disabled=not editable,
                )

            with c4:
                geo_option_ids = [opt_id for opt_id, _ in geo_options]
                current_geo_id = (txn.get("geo_id") or "").strip()
                if current_geo_id and current_geo_id not in geo_option_ids:
                    geo_options.append((current_geo_id, t("workspace.txn_geo_current", geo_id=current_geo_id)))
                    geo_option_ids.append(current_geo_id)
                geo_labels = {opt_id: label for opt_id, label in geo_options}

                txn["geo_id"] = st.selectbox(
                    t("field.txn_geo_id"),
                    geo_option_ids,
                    index=geo_option_ids.index(current_geo_id) if current_geo_id in geo_option_ids else 0,
                    format_func=lambda geo_id: geo_labels.get(geo_id, geo_id),
                    key=f"txn_geo_{selected}_{i}",
                    disabled=not editable,
                )
                st.caption(t("workspace.txn_geo_caption"))

            # -----------------------------
            # Row 2 — Procurement & Production
            # -----------------------------
            st.markdown(f"**{t('workspace.txn_row2')}**")
            d1, d2, d3, d4 = st.columns([2, 2, 2, 2])

            with d1:
                txn["input_node_name"] = st.text_input(
                    t("field.txn_input_node_name"),
                    value=txn.get("input_node_name") or "",
                    key=f"txn_input_node_{selected}_{i}",
                    disabled=not editable,
                )
                txn["reporting_node_name"] = st.text_input(
                    t("field.txn_reporting_node_name"),
                    value=txn.get("reporting_node_name") or "",
                    key=f"txn_reporting_node_{selected}_{i}",
                    disabled=not editable,
                )
                st.caption(t("workspace.txn_reporting_caption"))
                unit_options = ["", "m3", "kg", "ton"]
                current_unit = txn.get("quantity_unit") or ""
                if current_unit not in unit_options:
                    current_unit = ""
                txn["quantity_unit"] = st.selectbox(
                    t("field.txn_quantity_unit"),
                    unit_options,
                    index=unit_options.index(current_unit),
                    key=f"txn_unit_{selected}_{i}",
                    disabled=not editable,
                )

            with d2:
                iq_val = txn.get("input_quantity")
                oq_val = txn.get("output_quantity")
                txn["input_quantity"] = st.number_input(
                    t("field.txn_input_quantity"),
                    value=float(iq_val) if iq_val not in (None, "", "None") else 0.0,
                    min_value=0.0,
                    key=f"txn_in_qty_{selected}_{i}",
                    disabled=not editable,
                )
                txn["output_quantity"] = st.number_input(
                    t("field.txn_output_quantity"),
                    value=float(oq_val) if oq_val not in (None, "", "None") else 0.0,
                    min_value=0.0,
                    key=f"txn_out_qty_{selected}_{i}",
                    disabled=not editable,
                )

            with d3:
                txn["production_start_date"] = st.text_input(
                    t("field.txn_production_start_date"),
                    value=txn.get("production_start_date") or "",
                    key=f"txn_start_{selected}_{i}",
                    disabled=not editable,
                )
                txn["production_end_date"] = st.text_input(
                    t("field.txn_production_end_date"),
                    value=txn.get("production_end_date") or "",
                    key=f"txn_end_{selected}_{i}",
                    disabled=not editable,
                )

            with d4:
                txn["batch_label"] = st.text_input(
                    t("field.txn_batch_label"),
                    value=txn.get("batch_label") or "",
                    key=f"txn_batch_{selected}_{i}",
                    disabled=not editable,
                )
                st.caption(t("workspace.txn_batch_caption"))

            # Row 3 — Assessment
            st.markdown(f"**{t('workspace.txn_row3')}**")
            st.caption(t("workspace.txn_risk_scope_caption"))
            a1, a2 = st.columns([1, 3])

            with a1:
                risk_options = ["", "negligible", "low", "medium", "high"]
                current_risk = (txn.get("assessment_risk_level") or "").strip()
                if current_risk not in risk_options:
                    current_risk = ""

                txn["assessment_risk_level"] = st.selectbox(
                    t("field.txn_assessment_risk_level"),
                    risk_options,
                    index=risk_options.index(current_risk),
                    format_func=lambda value: option_label("risk", value) if value else "",
                    key=f"txn_risk_{selected}_{i}",
                    disabled=not editable,
                )

            with a2:
                txn["assessment_conclusion"] = st.text_area(
                    t("field.txn_assessment_conclusion"),
                    value=txn.get("assessment_conclusion") or "",
                    key=f"txn_concl_{selected}_{i}",
                    disabled=not editable,
                    height=100,
                )

            if rec["integrity_mode"] == "source_fact":
                st.caption(t("workspace.txn_source_fact_caption"))

            # persist row
            draft[i] = txn
            st.session_state[draft_key] = draft

    st.markdown(f"#### {t('workspace.txn_summary')}")

    # Build summary table from current draft
    summary_rows = []
    for txn in draft:
        product_name = (txn.get("product_name") or "").strip()
        output_node_name = (txn.get("output_node_name") or "").strip()
        txn_display = f"{product_name or t('workspace.txn_product_fallback')} → {output_node_name or t('workspace.txn_to_fallback')}"

        summary_rows.append(
            {
                "txn.id": txn.get("txn_id", ""),
                "txn.display": txn_display,
                # Row 1
                "txn.product_name": txn.get("product_name") or "",
                "txn.output_node_name": txn.get("output_node_name") or "",
                "txn.species_common": txn.get("species_common") or "",
                "txn.geo_id": txn.get("geo_id") or "",
                # Row 2 (key fields)
                "txn.input_node_name": txn.get("input_node_name") or "",
                "txn.reporting_node_name": txn.get("reporting_node_name") or "",
                "txn.quantity_unit": txn.get("quantity_unit") or "",
                "txn.input_quantity": txn.get("input_quantity") if txn.get("input_quantity") is not None else 0.0,
                "txn.output_quantity": txn.get("output_quantity") if txn.get("output_quantity") is not None else 0.0,
                "txn.production_start_date": txn.get("production_start_date") or "",
                "txn.production_end_date": txn.get("production_end_date") or "",
                "txn.batch_label": txn.get("batch_label") or "",
                # Row 3 (key fields)
                "txn.assessment_risk_level": txn.get("assessment_risk_level") or "",
                "txn.assessment_conclusion": txn.get("assessment_conclusion") or "",
                
            }
        )

    summary_df = pd.DataFrame(summary_rows)

    edited_summary = st.data_editor(
        summary_df,
        use_container_width=True,
        hide_index=True,
        disabled=True if not editable else ["txn.id", "txn.display"],
        column_config={
            "txn.product_name": st.column_config.TextColumn(t("field.txn_product_name")),
            "txn.display": st.column_config.TextColumn(t("field.txn_display")),
            "txn.output_node_name": st.column_config.TextColumn(t("field.txn_output_node_name")),
            "txn.species_common": st.column_config.TextColumn(t("field.txn_species_common")),
            "txn.geo_id": st.column_config.TextColumn(t("field.txn_geo_id")),
            "txn.input_node_name": st.column_config.TextColumn(t("field.txn_input_node_name")),
            "txn.reporting_node_name": st.column_config.TextColumn(t("field.txn_reporting_node_name")),
            "txn.quantity_unit": st.column_config.SelectboxColumn(
                t("field.txn_quantity_unit"),
                options=["", "m3", "kg", "ton"],
            ),
            "txn.input_quantity": st.column_config.NumberColumn(t("field.txn_input_quantity"), min_value=0.0),
            "txn.output_quantity": st.column_config.NumberColumn(t("field.txn_output_quantity"), min_value=0.0),
            "txn.production_start_date": st.column_config.TextColumn(t("field.txn_production_start_date")),
            "txn.production_end_date": st.column_config.TextColumn(t("field.txn_production_end_date")),
            "txn.batch_label": st.column_config.TextColumn(t("field.txn_batch_label")),
        },
        key=f"txn_summary_{selected}",
    )

    # Apply summary edits back into draft (in memory)
    if editable:
        if st.button(t("workspace.txn_apply_summary"), key=f"apply_txn_summary_{selected}"):
            # Map edited rows by txn.id
            edited_map = {
                row["txn.id"]: row
                for row in edited_summary.to_dict(orient="records")
            }

            for idx, txn in enumerate(draft):
                tid = txn.get("txn_id", "")
                row = edited_map.get(tid)
                if not row:
                    continue

                txn["product_name"] = row.get("txn.product_name", "")
                txn["output_node_name"] = row.get("txn.output_node_name", "")
                txn["species_common"] = row.get("txn.species_common", "")
                txn["geo_id"] = row.get("txn.geo_id", "")

                txn["input_node_name"] = row.get("txn.input_node_name", "")
                txn["reporting_node_name"] = row.get("txn.reporting_node_name", "")
                txn["quantity_unit"] = row.get("txn.quantity_unit", "")
                txn["input_quantity"] = row.get("txn.input_quantity", 0.0)
                txn["output_quantity"] = row.get("txn.output_quantity", 0.0)
                txn["production_start_date"] = row.get("txn.production_start_date", "")
                txn["production_end_date"] = row.get("txn.production_end_date", "")
                txn["batch_label"] = row.get("txn.batch_label", "")

                draft[idx] = txn

            st.session_state[draft_key] = draft
            st.success(t("workspace.txn_apply_summary_done"))
            _rerun_workspace(selected)
    else:
        st.info(t("workspace.read_only"))
    # Save all txns
    if editable:
        if st.button(f"💾 {t('workspace.txn_save_all')}", key=f"save_all_txns_{selected}"):
            replace_txns(selected, st.session_state[draft_key])
            st.success(t("workspace.txn_saved"))
            _rerun_workspace(selected)
    else:
        st.warning(t("workspace.read_only"))
