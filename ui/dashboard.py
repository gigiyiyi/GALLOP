# ui/dashboard.py

import streamlit as st
from i18n import mode_label, status_label, t


def _package_label(row) -> str:
    package_name = (row["case_title"] or "").strip() or t("dashboard.default_package_name")
    return f"{package_name} · {mode_label(row['integrity_mode'])} · {status_label(row['status'])}"


def render_dashboard(u, can_create, create_record, list_records_for_org, list_txns, list_nodes, list_geos, list_evidences, validate_record_v1):
    """
    Page 1: Records Dashboard
    - list records
    - open workspace (via nav_target + selected_record_override)
    - create record (and jump to workspace)
    """
    st.subheader(t("dashboard.title"))

    rows = list_records_for_org(u["org_id"])
    if not rows:
        st.info(t("dashboard.no_records"))
    else:
        dashboard_rows = []
        for r in rows:
            # quick validate for dashboard badge
            try:
                ev_rows = list_evidences(r["record_id"])
                txn_rows = list_txns(r["record_id"])
                node_rows = list_nodes(r["record_id"])
                geo_rows = list_geos(r["record_id"])
                # quick validate for dashboard badge (non-persistent)
                errors, warnings = validate_record_v1(r, ev_rows, txn_rows, node_rows, geo_rows)
                issues_badge = f"{len(errors)}E / {len(warnings)}W"
            except Exception:
                issues_badge = "-"
                
            ui_status = status_label(r["status"])

            # supersedes_record_id may be missing in older DBs; handle safely
            supersedes = ""
            try:
                supersedes = r["supersedes_record_id"] or ""
            except Exception:
                supersedes = ""

            dashboard_rows.append(
                {
                    t("dashboard.case_title"): (r["case_title"] or "").strip() or t("dashboard.default_package_name"),
                    t("dashboard.record_id"): r["record_id"],
                    t("dashboard.mode"): mode_label(r["integrity_mode"]),
                    t("dashboard.status"): ui_status,
                    t("dashboard.issues"): issues_badge,
                    t("dashboard.created_at"): r["created_at"],
                    t("dashboard.supersedes"): supersedes,
                }
            )

        st.dataframe(dashboard_rows, use_container_width=True)

        st.markdown(f"#### {t('dashboard.open_record')}")
        rec_ids = [r["record_id"] for r in rows]

        override = st.session_state.get("workspace_selected_record")
        if override and override in rec_ids:
            default_index = rec_ids.index(override)
        else:
            default_index = 0

        selected = st.selectbox(
            t("dashboard.open_record"),
            rec_ids,
            index=default_index,
            format_func=lambda rec_id: _package_label(next(r for r in rows if r["record_id"] == rec_id)),
            key="dashboard_selected_record",
        )
        st.caption(f"{t('dashboard.record_id')}: {selected}")

        col_open, col_hint = st.columns([1, 3])
        with col_open:
            if st.button(t("dashboard.open_workspace"), key="open_workspace_btn"):
                st.session_state["workspace_selected_record"] = selected
                st.session_state["nav_target"] = t("nav.workspace")
                st.rerun()
                st.stop()

        with col_hint:
            st.caption(t("dashboard.tip"))

    st.markdown("---")
    st.subheader(t("dashboard.create_title"))
    st.markdown(f"#### {t('dashboard.mode_help_title')}")
    st.info(
        "\n\n".join(
            [
                t("dashboard.mode_help_intro"),
                t("dashboard.mode_help_source_fact"),
                t("dashboard.mode_help_narrative"),
                t("dashboard.mode_help_downgrade"),
            ]
        )
    )

    with st.form(key="create_record_form", clear_on_submit=True):
        case_title = st.text_input(
            t("label.case_title"),
            value=t("dashboard.default_package_name"),
            help=t("dashboard.package_name_help"),
        )
        integrity_mode = st.selectbox(
            t("label.integrity_mode"),
            ["source_fact", "narrative"],
            format_func=mode_label,
        )
        submitted = st.form_submit_button(t("dashboard.create_button"))

    if submitted:
        if not can_create(u["role"]):
            st.error(t("dashboard.create_denied"))
        else:
            rid = create_record(case_title.strip(), integrity_mode, u["org_id"])
            st.success(t("dashboard.created", record_id=rid))
            st.session_state["workspace_selected_record"] = rid
            st.session_state["nav_target"] = t("nav.workspace")
            st.rerun()
            st.stop()
