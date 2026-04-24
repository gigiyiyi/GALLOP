from ui.dashboard import render_dashboard
from ui.admin import render_admin_page
import re
from ui.workspace import (
    _parse_issue,
    render_workspace_header,
    render_transactions_section,
    render_nodes_section,
    render_geo_section,
    render_source_page_section,
    render_evidence_section,
    render_validate_section,
    source_page_applies,
)
from constants import (
    INTEGRITY_MODE_LABELS,
    RECORD_STATUS_LABELS,
)
from i18n import SUPPORTED_LANGUAGES, link_type_label, mode_label, option_label, status_label, t
from rules import validate_record_v1
from export_pack import (
    compute_manifest_hash,
    build_manifest_json,
    build_localized_manifest_json,
    build_full_package_zip,
)
from db import (
    admin_exists,
    init_db,
    seed_demo_data,
    ensure_org,
    get_user_by_email,
    list_orgs,
    list_users,
    list_records_for_org,
    get_record_for_org,
    create_record,
    create_user as db_create_user,
    list_txns,
    replace_txns,
    list_nodes,
    update_nodes,
    resolve_nodes_for_record,
    list_geos,
    insert_geo,
    list_evidences,
    insert_evidence,
    update_evidence_link,
    update_record_contact,
    update_user_status,
    update_user_password,
    submit_record,
    seal_record,
    downgrade_record,
)

import bcrypt
import streamlit as st

# -------------------------------------------------
# App config
# -------------------------------------------------
st.set_page_config(page_title="GALLOP MVP", layout="wide")


# -------------------------------------------------
# Auth helpers
# -------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, pw_hash: str) -> bool:
    return bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("utf-8"))


def bootstrap_admin_from_secrets():
    try:
        secret_email = st.secrets.get("ADMIN_EMAIL")
        secret_password = st.secrets.get("ADMIN_PASSWORD")
        secret_name = st.secrets.get("ADMIN_NAME", "GALLOP Admin")
        secret_org_id = st.secrets.get("ADMIN_ORG_ID", "ORG_ADMIN")
        secret_org_name = st.secrets.get("ADMIN_ORG_NAME", "GALLOP Admin Org")
    except Exception:
        return

    if not secret_email or not secret_password:
        return

    if admin_exists():
        return

    ensure_org(secret_org_id, secret_org_name)
    db_create_user(
        secret_email,
        secret_name,
        hash_password(secret_password),
        secret_org_id,
        "admin",
        "active",
    )

# -------------------------------------------------
# Permissions
# -------------------------------------------------
def can_create(role: str) -> bool:
    return role in ("admin", "participant")


def can_edit(role: str) -> bool:
    return role in ("admin", "participant")


def can_seal(role: str) -> bool:
    return role in ("admin", "participant")


def can_admin(role: str) -> bool:
    return role == "admin"


# -------------------------------------------------
# App start
# -------------------------------------------------
init_db()
seed_demo_data(hash_password)
bootstrap_admin_from_secrets()


# Login
if "user" not in st.session_state:
    if "lang" not in st.session_state:
        st.session_state["lang"] = "en"
    lang_options = list(SUPPORTED_LANGUAGES.keys())
    st.selectbox(
        t("sidebar.language"),
        lang_options,
        format_func=lambda code: SUPPORTED_LANGUAGES[code],
        key="lang",
    )
    st.title(t("auth.login_title"))
    st.caption(t("auth.demo_users"))
    email = st.text_input(t("auth.email"))
    pw = st.text_input(t("auth.password"), type="password")
    if st.button(t("auth.login_button")):
        user = get_user_by_email(email)
        if user and verify_password(pw, user["password_hash"]) and user["status"] == "active":
            st.session_state.user = dict(user)
            st.rerun()
        else:
            st.error(t("auth.invalid"))
    st.stop()

u = st.session_state.user
org_lookup = {row["org_id"]: row["org_name"] for row in list_orgs()}
org_name = (org_lookup.get(u["org_id"]) or "").strip()
org_display = f"{org_name} ({u['org_id']})" if org_name else u["org_id"]

# Sidebar
if "lang" not in st.session_state:
    st.session_state["lang"] = "en"
lang_options = list(SUPPORTED_LANGUAGES.keys())
st.sidebar.selectbox(
    t("sidebar.language"),
    lang_options,
    format_func=lambda code: SUPPORTED_LANGUAGES[code],
    key="lang",
)
st.sidebar.write(f"**{t('sidebar.user')}:** {u['name']} ({u['email']})")
st.sidebar.write(f"**{t('sidebar.org')}:** {org_display}")
st.sidebar.write(f"**{t('sidebar.role')}:** {u['role']}")
st.sidebar.caption(
    t("sidebar.temp_notice")
)
st.sidebar.caption(t("sidebar.invite_notice"))
if st.sidebar.button(t("sidebar.logout")):
    st.session_state.clear()
    st.rerun()

st.title(t("app.title"))

NAV_PAGES = [t("nav.dashboard"), t("nav.workspace")]
if can_admin(u["role"]):
    NAV_PAGES.append(t("nav.admin"))

if st.session_state.get("nav_page") not in NAV_PAGES:
    st.session_state["nav_page"] = NAV_PAGES[0]

# Apply nav_target (button-driven navigation)
target = st.session_state.pop("nav_target", None)
if target in NAV_PAGES:
    st.session_state["nav_page"] = target
    st.session_state["nav_page_widget"] = target

page = st.sidebar.radio(
    t("nav.label"),
    NAV_PAGES,
    key="nav_page_widget",
)
st.session_state["nav_page"] = page


def _package_label(rec) -> str:
    package_name = (rec["case_title"] or "").strip() or t("dashboard.default_package_name")
    return f"{package_name} · {mode_label(rec['integrity_mode'])} · {status_label(rec['status'])}"


def render_record_workspace(selected, u):
    rec = get_record_for_org(selected, u["org_id"])
    if not rec:
        st.error("Access denied or record not found.")
        st.stop()

    # =========================
    # Workspace Meta Header
    # =========================
    col_title, col_meta = st.columns([7, 3])

    with col_title:
        st.markdown(f"## {t('workspace.title')}")
        st.caption(f"{t('dashboard.case_title')}: {(rec['case_title'] or '').strip() or t('dashboard.default_package_name')}  |  {t('dashboard.record_id')}: {rec['record_id']}")

    with col_meta:
        mode_text = mode_label(rec["integrity_mode"])
        status_text = status_label(rec["status"])
        st.caption(
            f"**{t('workspace.meta_mode')}:** {mode_text}  \n"
            f"**{t('workspace.meta_status')}:** {status_text}  \n"
            f"**{t('workspace.meta_role')}:** {u['role']}"
        )

    origin_text = mode_label(rec["mode_origin"])
    mode_note = (
        t("workspace.mode_note_source_fact")
        if rec["integrity_mode"] == "source_fact"
        else t("workspace.mode_note_narrative")
    )
    if rec["mode_origin"] == "source_fact" and rec["integrity_mode"] == "narrative":
        mode_note = t(
            "workspace.mode_note_downgraded",
            reason=rec["downgrade_reason"] or t("workspace.no_reason"),
        )

    st.info(
        f"**{t('workspace.current_mode')}:** {mode_text}\n\n"
        f"**{t('workspace.origin')}:** {origin_text}\n\n"
        f"**{t('workspace.mode_note')}:** {mode_note}"
    )

    with st.expander(
        t("workspace.review_contact_title"),
        expanded=bool(rec["review_coordinator_name"] or rec["review_coordinator_email"] or rec["review_coordinator_note"]),
    ):
        st.caption(t("workspace.review_contact_caption"))
        if rec["review_coordinator_name"] or rec["review_coordinator_email"] or rec["review_coordinator_note"]:
            st.info(
                f"**{t('workspace.review_contact_name')}:** {rec['review_coordinator_name'] or t('workspace.review_contact_missing')}\n\n"
                f"**{t('workspace.review_contact_email')}:** {rec['review_coordinator_email'] or t('workspace.review_contact_missing')}\n\n"
                f"**{t('workspace.review_contact_note')}:** {rec['review_coordinator_note'] or t('workspace.review_contact_missing')}"
            )
        if can_edit(u["role"]) and rec["status"] == "draft":
            with st.form(key=f"review_contact_form_{selected}"):
                coordinator_name = st.text_input(t("workspace.review_contact_name"), value=rec["review_coordinator_name"] or "")
                coordinator_email = st.text_input(t("workspace.review_contact_email"), value=rec["review_coordinator_email"] or "")
                coordinator_note = st.text_area(
                    t("workspace.review_contact_note"),
                    value=rec["review_coordinator_note"] or "",
                    height=80,
                )
                contact_submitted = st.form_submit_button(t("workspace.review_contact_save"))
            if contact_submitted:
                update_record_contact(selected, u["org_id"], coordinator_name, coordinator_email, coordinator_note)
                st.success(t("workspace.review_contact_saved"))
                st.rerun()

    st.markdown(f"### {t('workspace.guide_title')}")
    st.markdown(
        "\n".join(
            [
                t("workspace.guide_intro"),
                t("workspace.guide_1"),
                t("workspace.guide_2"),
                t("workspace.guide_3"),
                t("workspace.guide_4"),
                t("workspace.guide_5"),
                t("workspace.guide_6"),
            ]
        )
    )
    st.caption(t("workspace.guide_caption"))

    def format_issue_message(message: str) -> str:
        if st.session_state.get("lang", "en") != "zh":
            return message

        patterns = [
            (r"^R005: missing link_id for (?P<evidence_id>.+)$", lambda m: t("rule.R005", evidence_id=m["evidence_id"])),
            (r"^R006: invalid link_type for (?P<evidence_id>.+): (?P<link_type>.+)$", lambda m: t("rule.R006", evidence_id=m["evidence_id"], link_type=link_type_label(m["link_type"]))),
            (r"^R007(?:\(warn\))?: evidence (?P<evidence_id>.+) links to non-existing txn\.id: (?P<link_id>.+)$", lambda m: t("rule.R007", evidence_id=m["evidence_id"], link_id=m["link_id"])),
            (r"^R008(?:\(warn\))?: evidence (?P<evidence_id>.+) links to non-existing node\.id: (?P<link_id>.+)$", lambda m: t("rule.R008", evidence_id=m["evidence_id"], link_id=m["link_id"])),
            (r"^R009: evidence (?P<evidence_id>.+) links to non-existing geo\.id: (?P<link_id>.+)$", lambda m: t("rule.R009", evidence_id=m["evidence_id"], link_id=m["link_id"])),
            (r"^R010(?:\(warn\))?: evidence (?P<evidence_id>.+) links to non-existing node\.id: (?P<link_id>.+)$", lambda m: t("rule.R010", evidence_id=m["evidence_id"], link_id=m["link_id"])),
            (r"^R021: missing txn\.assessment_risk_level for txn\.id (?P<txn_id>.+)$", lambda m: t("rule.R021", txn_id=m["txn_id"])),
            (r"^R022: missing txn\.assessment_conclusion for txn\.id (?P<txn_id>.+)$", lambda m: t("rule.R022", txn_id=m["txn_id"])),
            (r"^R023: invalid txn\.assessment_risk_level for txn\.id (?P<txn_id>.+): (?P<risk>.+)$", lambda m: t("rule.R023", txn_id=m["txn_id"], risk=option_label("risk", m["risk"]))),
            (r"^R025: txn assessment fields must be paired for txn\.id (?P<txn_id>.+)$", lambda m: t("rule.R025", txn_id=m["txn_id"])),
            (r"^R026: .+$", lambda m: t("rule.R026")),
            (r"^R027: .+$", lambda m: t("rule.R027")),
            (r"^R029: txn (?P<txn_id>.+) references non-existing geo\.id: (?P<geo_id>.+)$", lambda m: t("rule.R029", txn_id=m["txn_id"], geo_id=m["geo_id"])),
            (r"^R030: reporting forest/farm transaction requires txn\.geo_id for txn (?P<txn_id>.+)$", lambda m: t("rule.R030", txn_id=m["txn_id"])),
            (r"^R031: reporting forest/farm areas should include at least one legality or land-right document$", lambda m: t("rule.R031")),
            (r"^R032: reporting forest/farm areas should include at least one map or boundary document$", lambda m: t("rule.R032")),
            (r"^R033: reporting forest/farm areas should include at least one site photo or field assessment$", lambda m: t("rule.R033")),
            (r"^R034: reporting entity is recommended for txn (?P<txn_id>.+)$", lambda m: t("rule.R034", txn_id=m["txn_id"])),
        ]

        for pattern, formatter in patterns:
            match = re.match(pattern, message)
            if match:
                rule_id = message.split(":", 1)[0].replace("(warn)", "")
                return f"{rule_id}: {formatter(match.groupdict())}"
        return message

    # ---- Issue summary (fresh validation) ----
    ev_rows = list_evidences(selected)
    txn_rows = list_txns(selected)
    node_rows = list_nodes(selected)
    geo_rows = list_geos(selected)
    errors, warnings = validate_record_v1(rec, ev_rows, txn_rows, node_rows, geo_rows)
    issues = []
    for msg in errors:
        it = _parse_issue(msg)
        it["severity"] = "error"
        issues.append(it)
    for msg in warnings:
        it = _parse_issue(msg)
        it["severity"] = "warning"
        issues.append(it)
    st.session_state[f"issues_{selected}"] = issues

    if issues:
        st.markdown(f"### {t('workspace.warnings_title')}")
        st.caption(t("workspace.warnings_caption"))

        for i, it in enumerate(issues[:8]):  # 先只显示前8条
            cols = st.columns([6, 1])
            with cols[0]:
                severity_label = t("workspace.severity_error") if it["severity"] == "error" else t("workspace.severity_warning")
                st.write(f"- [{severity_label}] {format_issue_message(it['message'])}")
            with cols[1]:
                if it["scope"] in {"txn", "evidence"} and it["target_id"]:
                    if st.button(t("workspace.go"), key=f"issue_go_{selected}_{i}"):
                        if it["scope"] == "txn":
                            st.session_state["focus_txn_id"] = it["target_id"]
                        elif it["scope"] == "evidence":
                            st.session_state["focus_evidence_id"] = it["target_id"]
                        st.session_state["workspace_selected_record"] = selected
                        st.session_state["nav_target"] = t("nav.workspace")
                        st.rerun()
    else:
        st.markdown(f"### {t('workspace.warnings_title')}")
        st.success(t("workspace.no_warnings"))

    sections = {
        "transactions": lambda: render_transactions_section(selected, u, rec, list_txns, replace_txns, can_edit, list_geos),
        "nodes": lambda: render_nodes_section(
            selected, u, rec, can_edit,
            list_nodes, update_nodes, resolve_nodes_for_record
        ),
        "geo": lambda: render_geo_section(selected, u, rec, can_edit, list_geos, insert_geo),
        "source_page": lambda: render_source_page_section(
            selected, u, rec, can_edit,
            list_nodes, list_txns, list_geos, list_evidences, insert_evidence
        ),
        "evidence": lambda: render_evidence_section(
            selected, u, rec, can_edit,
            list_evidences, insert_evidence, update_evidence_link,
            list_txns, list_nodes,
            list_geos,
        ),
    }

    show_source_page = source_page_applies(list_nodes(selected), list_txns(selected))

    section_order = ["transactions", "nodes", "geo", "source_page", "evidence"]
    if st.session_state.get("focus_evidence_id"):
        section_order = ["evidence", "transactions", "nodes", "geo", "source_page"]
    elif st.session_state.get("focus_txn_id"):
        section_order = ["transactions", "nodes", "geo", "source_page", "evidence"]

    for section_name in section_order:
        if section_name == "source_page" and not show_source_page:
            continue
        sections[section_name]()

    render_validate_section(
        selected, u, rec,
        can_seal,
        list_evidences, list_txns, list_nodes, list_geos,
        validate_record_v1,
        compute_manifest_hash,
        submit_record,
        seal_record,
        downgrade_record,
        build_manifest_json,
        build_localized_manifest_json,
        build_full_package_zip,
    )

if page == t("nav.dashboard"):
    render_dashboard(
        u, can_create, create_record, list_records_for_org,
        list_txns, list_nodes, list_geos, list_evidences,
        validate_record_v1
    )
elif can_admin(u["role"]) and page == t("nav.admin"):
    render_admin_page(
        u,
        list_users,
        list_orgs,
        db_create_user,
        update_user_status,
        update_user_password,
        hash_password,
    )
elif page == t("nav.workspace"):

    # 1) 列出当前组织可访问的 records
    rows = list_records_for_org(u["org_id"])
    if not rows:
        st.info(t("workspace.no_records"))
        st.stop()

    record_ids = [r["record_id"] for r in rows]
    record_map = {r["record_id"]: r for r in rows}


    # 2) 支持从 Dashboard 跳转时带入 selected_record
    selected = st.session_state.get("workspace_selected_record")
    if selected not in record_ids:
        selected = record_ids[0]

    selected = st.selectbox(
        t("workspace.select_record"),
        record_ids,
        index=record_ids.index(selected),
        format_func=lambda rec_id: _package_label(record_map[rec_id]),
        key="workspace_record_selector",
    )
    st.session_state["workspace_selected_record"] = selected

    # 3) 渲染 Workspace 主体
    render_record_workspace(selected, u)              
