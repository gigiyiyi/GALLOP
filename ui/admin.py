import sqlite3

import streamlit as st

from i18n import t


ROLE_OPTIONS = ["admin", "participant", "dds_viewer"]
STATUS_OPTIONS = ["active", "disabled"]


def render_admin_page(
    u,
    list_users,
    list_orgs,
    create_user,
    update_user_status,
    update_user_password,
    delete_user,
    hash_password,
):
    st.subheader(t("admin.title"))
    st.caption(t("admin.caption"))
    st.info(t("admin.recovery_help"))

    org_rows = list_orgs()
    org_ids = [row["org_id"] for row in org_rows]
    org_labels = {row["org_id"]: f"{row['org_name']} ({row['org_id']})" for row in org_rows}

    st.markdown(f"#### {t('admin.create_title')}")
    with st.form(key="admin_create_user_form", clear_on_submit=True):
        name = st.text_input(t("admin.name"))
        email = st.text_input(t("admin.email"))
        password = st.text_input(t("admin.password"), type="password")
        org_id = st.selectbox(
            t("admin.org"),
            org_ids,
            format_func=lambda value: org_labels.get(value, value),
        )
        role = st.selectbox(t("admin.role"), ROLE_OPTIONS, format_func=lambda value: t(f"admin.role_{value}"))
        status = st.selectbox(t("admin.status"), STATUS_OPTIONS, format_func=lambda value: t(f"admin.status_{value}"))
        submitted = st.form_submit_button(t("admin.create_button"))

    if submitted:
        if not name.strip() or not email.strip() or not password.strip():
            st.error(t("admin.create_missing"))
        else:
            try:
                create_user(email, name, hash_password(password), org_id, role, status)
                st.success(t("admin.create_success", email=email.strip().lower()))
                st.rerun()
            except sqlite3.IntegrityError:
                st.error(t("admin.create_duplicate"))

    st.markdown("---")
    st.markdown(f"#### {t('admin.manage_title')}")
    user_rows = list_users()
    if not user_rows:
        st.info(t("admin.no_users"))
        return

    search_query = st.text_input(t("admin.search"), value="").strip().lower()
    if search_query:
        user_rows = [
            row for row in user_rows
            if search_query in (row["name"] or "").lower()
            or search_query in (row["email"] or "").lower()
            or search_query in ((row["org_name"] or row["org_id"] or "").lower())
        ]
        if not user_rows:
            st.warning(t("admin.search_empty"))
            return

    st.dataframe(
        [
            {
                t("admin.col_name"): row["name"],
                t("admin.col_email"): row["email"],
                t("admin.col_org"): row["org_name"] or row["org_id"],
                t("admin.col_role"): t(f"admin.role_{row['role']}"),
                t("admin.col_status"): t(f"admin.status_{row['status']}"),
                t("admin.col_created"): row["created_at"],
            }
            for row in user_rows
        ],
        use_container_width=True,
    )

    user_ids = [row["user_id"] for row in user_rows]
    user_map = {row["user_id"]: row for row in user_rows}

    selected_user_id = st.selectbox(
        t("admin.select_user"),
        user_ids,
        format_func=lambda user_id: f"{user_map[user_id]['name']} · {user_map[user_id]['email']}",
    )
    selected_user = user_map[selected_user_id]

    st.caption(
        t(
            "admin.selected_user_help",
            email=selected_user["email"],
            status=t(f"admin.status_{selected_user['status']}"),
        )
    )

    admin_count = sum(1 for row in user_rows if row["role"] == "admin")
    can_delete_selected = True
    delete_block_reason = ""
    if selected_user_id == u["user_id"]:
        can_delete_selected = False
        delete_block_reason = t("admin.delete_self_blocked")
    elif selected_user["role"] == "admin" and admin_count <= 1:
        can_delete_selected = False
        delete_block_reason = t("admin.delete_last_admin_blocked")

    with st.form(key="admin_manage_user_form"):
        new_status = st.selectbox(
            t("admin.status"),
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(selected_user["status"]) if selected_user["status"] in STATUS_OPTIONS else 0,
            format_func=lambda value: t(f"admin.status_{value}"),
        )
        new_password = st.text_input(t("admin.reset_password"), type="password", help=t("admin.reset_password_help"))
        save = st.form_submit_button(t("admin.save_changes"))

    if save:
        update_user_status(selected_user_id, new_status)
        if new_password.strip():
            update_user_password(selected_user_id, hash_password(new_password))
        st.success(t("admin.saved"))
        st.rerun()

    st.markdown(f"##### {t('admin.delete_title')}")
    if delete_block_reason:
        st.info(delete_block_reason)

    with st.form(key="admin_delete_user_form"):
        confirm_email = st.text_input(
            t("admin.delete_confirm"),
            help=t("admin.delete_confirm_help", email=selected_user["email"]),
            disabled=not can_delete_selected,
        )
        delete_submitted = st.form_submit_button(
            t("admin.delete_button"),
            disabled=not can_delete_selected,
        )

    if delete_submitted:
        if confirm_email.strip().lower() != (selected_user["email"] or "").strip().lower():
            st.error(t("admin.delete_mismatch"))
        else:
            delete_user(selected_user_id)
            st.success(t("admin.delete_success", email=selected_user["email"]))
            st.rerun()
