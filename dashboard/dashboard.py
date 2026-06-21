import math
import os
from html import escape
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Attribute AI Resolver", layout="wide", page_icon="🧩")

st.markdown(
    """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1600px;
}
.main-title {
    font-size: 2.05rem;
    font-weight: 900;
    margin: 0 0 .2rem 0;
    letter-spacing: -.02em;
}
.subtle {
    color: #667085;
    font-size: .9rem;
}
.panel-title {
    font-size: 1.15rem;
    font-weight: 850;
    margin: .2rem 0 .5rem 0;
}
.table-head {
    background: #f8fafc;
    border: 1px solid #e4e7ec;
    border-radius: .65rem .65rem 0 0;
    padding: .65rem .8rem;
    color: #344054;
    font-size: .82rem;
    font-weight: 850;
}
.table-row {
    border-left: 1px solid #e4e7ec;
    border-right: 1px solid #e4e7ec;
    border-bottom: 1px solid #e4e7ec;
    padding: .55rem .8rem;
    background: #ffffff;
}
.table-row:hover {
    background: #fcfcfd;
}
.row-title {
    font-weight: 850;
    font-size: .98rem;
    margin-bottom: .08rem;
}
.row-muted {
    color: #667085;
    font-size: .82rem;
    line-height: 1.45;
}
.small-muted {
    color: #667085;
    font-size: .78rem;
}
.chip {
    display: inline-block;
    border-radius: 999px;
    padding: .18rem .58rem;
    font-size: .76rem;
    font-weight: 800;
    border: 1px solid rgba(0,0,0,.06);
    white-space: nowrap;
}
.chip-active { background: #ecfdf3; color: #027a48; }
.chip-inactive { background: #f2f4f7; color: #344054; }
.chip-open { background: #eff8ff; color: #175cd3; }
.chip-approved { background: #ecfdf3; color: #027a48; }
.chip-ignored { background: #fff6ed; color: #c4320a; }
.inline-panel {
    background: #fcfcfd;
    border: 1px solid #d0d5dd;
    border-radius: .75rem;
    padding: .9rem .95rem .95rem .95rem;
    margin-top: .55rem;
}
.danger-box {
    background: #fff1f3;
    border: 1px solid #fecdca;
    border-radius: .75rem;
    padding: .85rem .95rem;
}
.alias-box {
    background: #ffffff;
    border: 1px solid #e4e7ec;
    border-radius: .65rem;
    padding: .55rem .7rem;
    margin-bottom: .35rem;
}
.stButton>button {
    border-radius: .55rem;
    min-height: 2.25rem;
}
hr { margin-top: .7rem; margin-bottom: .7rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">Attribute AI Resolver</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="subtle">Version: <b>v1.6.1-english-ui</b> | API: <code>{escape(API_BASE_URL)}</code> | Docs: <code>http://localhost:8000/docs</code></div>',
    unsafe_allow_html=True,
)


# -----------------------------
# API helpers
# -----------------------------
def api_get(path: str, **params: Any) -> Any:
    clean_params = {k: v for k, v in params.items() if v is not None}
    response = requests.get(f"{API_BASE_URL}{path}", params=clean_params, timeout=60)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict | None = None) -> Any:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=120)
    response.raise_for_status()
    return response.json()


def api_patch(path: str, payload: dict | None = None) -> Any:
    response = requests.patch(f"{API_BASE_URL}{path}", json=payload or {}, timeout=120)
    response.raise_for_status()
    return response.json()


def api_delete(path: str, **params: Any) -> Any:
    clean_params = {k: v for k, v in params.items() if v is not None}
    response = requests.delete(f"{API_BASE_URL}{path}", params=clean_params, timeout=120)
    response.raise_for_status()
    return response.json()


def show_error(exc: Exception) -> None:
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else "unknown"
        try:
            body = exc.response.json()
            detail = body.get("detail", body) if isinstance(body, dict) else body
            st.error(f"HTTP {status}: {detail}")
        except Exception:
            text = exc.response.text if exc.response is not None else str(exc)
            st.error(f"HTTP {status}: {text or exc}")
    else:
        st.error(str(exc))


# -----------------------------
# Small helpers
# -----------------------------
def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def join_values(values: list[Any] | None) -> str:
    return ", ".join(str(item) for item in (values or []) if str(item).strip())


def alias_summary(attr: dict, limit: int = 7) -> str:
    aliases = [a.get("alias_raw", "") for a in attr.get("aliases", []) if a.get("alias_raw")]
    if not aliases:
        return "-"
    visible = aliases[:limit]
    suffix = f" +{len(aliases) - limit}" if len(aliases) > limit else ""
    return ", ".join(visible) + suffix


def attr_option_label(attr: dict) -> str:
    aliases = alias_summary(attr, limit=4)
    active = "active" if attr.get("active", True) else "inactive"
    if aliases and aliases != "-":
        return f"#{attr['id']} | {attr['name']} | {active} | aliases: {aliases}"
    return f"#{attr['id']} | {attr['name']} | {active}"


def status_chip(label: str, kind: str) -> str:
    safe_label = escape(str(label))
    return f'<span class="chip chip-{kind}">{safe_label}</span>'


def reset_page_on_filter_change(page_key: str, signature: tuple[Any, ...]) -> None:
    sig_key = f"{page_key}_signature"
    if st.session_state.get(sig_key) != signature:
        st.session_state[sig_key] = signature
        st.session_state[page_key] = 1


def active_filter_to_params(value: str) -> dict[str, Any]:
    if value == "active":
        return {"active": True, "include_inactive": False}
    if value == "inactive":
        return {"active": False, "include_inactive": False}
    return {"active": None, "include_inactive": True}


def clamp_page(page: int, total_pages: int) -> int:
    return min(max(int(page or 1), 1), max(total_pages, 1))


def render_pager(page_key: str, total: int, page_size: int, prefix: str, compact: bool = False) -> int:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    page = clamp_page(st.session_state.get(page_key, 1), total_pages)
    st.session_state[page_key] = page
    input_key = f"{prefix}_page_input"
    if st.session_state.get(input_key) != page:
        st.session_state[input_key] = page
    start = 0 if total == 0 else (page - 1) * page_size + 1
    end = min(total, page * page_size)

    widths = [0.8, 0.9, 1.5, 2.2, 0.9, 0.8] if not compact else [1, 1, 2, 1, 1]
    if compact:
        c_prev, c_page, c_info, c_next, c_last = st.columns(widths)
    else:
        c_first, c_prev, c_page, c_info, c_next, c_last = st.columns(widths)
        with c_first:
            if st.button("First", key=f"{prefix}_first", disabled=page <= 1):
                st.session_state[page_key] = 1
                st.rerun()

    with c_prev:
        if st.button("Previous", key=f"{prefix}_prev", disabled=page <= 1):
            st.session_state[page_key] = page - 1
            st.rerun()
    with c_page:
        requested_page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=page,
            step=1,
            key=input_key,
        )
        if int(requested_page) != page:
            st.session_state[page_key] = int(requested_page)
            st.rerun()
    with c_info:
        st.markdown(
            f"<div class='row-muted' style='padding-top:1.75rem'>Showing <b>{start}</b> to <b>{end}</b> of <b>{total}</b> — page <b>{page}</b> of <b>{total_pages}</b></div>",
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("Next", key=f"{prefix}_next", disabled=page >= total_pages):
            st.session_state[page_key] = page + 1
            st.rerun()
    with c_last:
        if st.button("Last", key=f"{prefix}_last", disabled=page >= total_pages):
            st.session_state[page_key] = total_pages
            st.rerun()
    return page


def create_starter_attributes() -> tuple[int, list[str]]:
    starter_items = [
        {
            "name": "RAM",
            "slug": "ram",
            "category_hint": "laptop computer mobile",
            "aliases": ["ram", "RAM", "Ram", "computer ram", "ram memory", "RAM Memory", "RAM Capacity"],
            "sample_values": ["4GB", "8GB", "16GB", "32GB", "DDR4", "DDR5"],
        },
        {
            "name": "Processor",
            "slug": "cpu",
            "category_hint": "laptop computer mobile",
            "aliases": ["CPU", "cpu", "processor", "processor unit", "cpu", "processor model"],
            "sample_values": ["Core i3", "Core i5", "Core i7", "Ryzen 5", "Ryzen 7"],
        },
        {
            "name": "Description",
            "slug": "description",
            "category_hint": "content",
            "aliases": ["description", "desc", "more description", "extra description", "description text", "product description"],
            "sample_values": ["text", "HTML", "description"],
        },
        {
            "name": "Internal Storage",
            "slug": "storage",
            "category_hint": "laptop computer mobile",
            "aliases": ["storage", "internal storage", "hard drive", "ssd", "hard drive capacity", "storage space"],
            "sample_values": ["128GB", "256GB", "512GB", "1TB", "SSD", "HDD"],
        },
    ]

    created = 0
    messages: list[str] = []
    for item in starter_items:
        try:
            result = api_post("/canonical", item)
            created += 1
            messages.append(f"created #{result['id']} {result['name']}")
        except requests.HTTPError as exc:
            try:
                detail = exc.response.json()
            except Exception:
                detail = str(exc)
            messages.append(f"skipped {item['name']}: {detail}")
    return created, messages


# -----------------------------
# Data summary
# -----------------------------
try:
    stats = api_get("/stats")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Canonical", stats.get("canonical_count", 0))
    m2.metric("Aliases", stats.get("alias_count", 0))
    m3.metric("Embeddings", stats.get("embedding_count", 0))
    m4.metric("Open reviews", stats.get("open_review_count", 0))
    m5.metric("Approved", stats.get("approved_review_count", 0))
except Exception as exc:
    st.warning("API is not ready yet or the connection failed.")
    show_error(exc)
    stats = {}


# -----------------------------
# Attribute table/editor
# -----------------------------
def set_attr_action(attr_id: int | None, action: str | None) -> None:
    st.session_state.attr_action_id = attr_id
    st.session_state.attr_action = action
    st.session_state.editing_alias_id = None


def current_attr_action(attr_id: int) -> str | None:
    if st.session_state.get("attr_action_id") == attr_id:
        return st.session_state.get("attr_action")
    return None


def render_alias_editor(alias: dict) -> None:
    alias_id = alias["id"]
    st.markdown("<div class='inline-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Edit alias</div>", unsafe_allow_html=True)
    with st.form(f"edit_alias_form_{alias_id}"):
        c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1])
        with c1:
            alias_raw = st.text_input("Alias text", value=alias.get("alias_raw", ""), key=f"alias_raw_{alias_id}")
        with c2:
            source = st.text_input("Source", value=alias.get("source", "manual"), key=f"alias_source_{alias_id}")
        with c3:
            confidence = st.number_input(
                "Confidence",
                min_value=0.0,
                max_value=1.0,
                value=float(alias.get("confidence", 1.0)),
                step=0.01,
                key=f"alias_conf_{alias_id}",
            )
        with c4:
            approved = st.checkbox("Approved", value=bool(alias.get("approved", True)), key=f"alias_approved_{alias_id}")
        c_save, c_close = st.columns([1, 1])
        if c_save.form_submit_button("Save alias", type="primary"):
            try:
                api_patch(
                    f"/aliases/{alias_id}",
                    {
                        "alias_raw": alias_raw,
                        "source": source,
                        "confidence": confidence,
                        "approved": approved,
                        "reindex": True,
                    },
                )
                st.session_state.editing_alias_id = None
                st.success("Alias saved.")
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if c_close.form_submit_button("Close"):
            st.session_state.editing_alias_id = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_alias_manager(attr: dict) -> None:
    attr_id = attr["id"]
    st.markdown("<div class='panel-title'>Aliases</div>", unsafe_allow_html=True)

    with st.form(f"add_alias_form_{attr_id}", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([3, 1.35, 1, 1, 1.2])
        with c1:
            alias_raw = st.text_input("New alias", key=f"new_alias_raw_{attr_id}")
        with c2:
            source = st.text_input("Source", value="manual", key=f"new_alias_source_{attr_id}")
        with c3:
            confidence = st.number_input(
                "Confidence",
                min_value=0.0,
                max_value=1.0,
                value=1.0,
                step=0.01,
                key=f"new_alias_conf_{attr_id}",
            )
        with c4:
            approved = st.checkbox("Approved", value=True, key=f"new_alias_approved_{attr_id}")
        with c5:
            st.write("")
            add_alias = st.form_submit_button("Add", type="primary")
        if add_alias:
            try:
                api_post(
                    "/aliases",
                    {
                        "canonical_id": attr_id,
                        "alias_raw": alias_raw,
                        "source": source,
                        "confidence": confidence,
                        "approved": approved,
                        "reindex": True,
                    },
                )
                st.success("Alias added.")
                st.rerun()
            except Exception as exc:
                show_error(exc)

    aliases = attr.get("aliases", [])
    if not aliases:
        st.info("No aliases yet.")
        return

    h1, h2, h3, h4, h5 = st.columns([3.0, 2.1, 1.1, 1.2, 1.7])
    h1.markdown("<div class='small-muted'><b>Alias</b></div>", unsafe_allow_html=True)
    h2.markdown("<div class='small-muted'><b>Normalized</b></div>", unsafe_allow_html=True)
    h3.markdown("<div class='small-muted'><b>Confidence</b></div>", unsafe_allow_html=True)
    h4.markdown("<div class='small-muted'><b>Status</b></div>", unsafe_allow_html=True)
    h5.markdown("<div class='small-muted'><b>Actions</b></div>", unsafe_allow_html=True)

    for alias in aliases:
        alias_id = alias["id"]
        c1, c2, c3, c4, c5 = st.columns([3.0, 2.1, 1.1, 1.2, 1.7])
        with c1:
            st.markdown(f"<div class='alias-box'><b>{escape(alias.get('alias_raw', ''))}</b><br><span class='small-muted'>source: {escape(alias.get('source', ''))}</span></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='alias-box'>{escape(alias.get('alias_norm', '-'))}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='alias-box'>{float(alias.get('confidence', 0)):.2f}</div>", unsafe_allow_html=True)
        with c4:
            kind = "active" if alias.get("approved", True) else "inactive"
            label = "approved" if alias.get("approved", True) else "pending"
            st.markdown(f"<div class='alias-box'>{status_chip(label, kind)}</div>", unsafe_allow_html=True)
        with c5:
            b1, b2 = st.columns([1, 1])
            if b1.button("Edit", key=f"alias_edit_{alias_id}"):
                st.session_state.editing_alias_id = alias_id
                st.rerun()
            if b2.button("Delete", key=f"alias_delete_{alias_id}"):
                st.session_state.editing_alias_id = f"delete_{alias_id}"
                st.rerun()

        if st.session_state.get("editing_alias_id") == alias_id:
            render_alias_editor(alias)
        elif st.session_state.get("editing_alias_id") == f"delete_{alias_id}":
            st.markdown("<div class='danger-box'>", unsafe_allow_html=True)
            st.warning(f"Delete alias: {alias.get('alias_raw')}")
            confirm = st.checkbox("I confirm deleting this alias", key=f"confirm_alias_delete_{alias_id}")
            d1, d2 = st.columns([1, 1])
            if d1.button("Delete alias", key=f"do_alias_delete_{alias_id}", type="primary"):
                if not confirm:
                    st.warning("Check the delete confirmation box first.")
                else:
                    try:
                        api_delete(f"/aliases/{alias_id}", reindex=True)
                        st.session_state.editing_alias_id = None
                        st.success("Alias deleted.")
                        st.rerun()
                    except Exception as exc:
                        show_error(exc)
            if d2.button("Cancel", key=f"cancel_alias_delete_{alias_id}"):
                st.session_state.editing_alias_id = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


def render_attribute_edit_panel(attr: dict) -> None:
    attr_id = attr["id"]
    st.markdown("<div class='inline-panel'>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel-title'>Edit attribute #{attr_id}</div>", unsafe_allow_html=True)

    with st.form(f"edit_attr_form_{attr_id}"):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            name = st.text_input("Name", value=attr.get("name", ""), key=f"attr_name_{attr_id}")
            category_hint = st.text_input(
                "Category hint",
                value=attr.get("category_hint") or "",
                key=f"attr_category_{attr_id}",
            )
        with c2:
            slug = st.text_input("Slug", value=attr.get("slug", ""), key=f"attr_slug_{attr_id}")
            sample_values = st.text_input(
                "Sample values, comma separated",
                value=join_values(attr.get("sample_values", [])),
                key=f"attr_samples_{attr_id}",
            )
        with c3:
            active = st.checkbox("Active", value=bool(attr.get("active", True)), key=f"attr_active_{attr_id}")
            st.caption("Safe delete means deactivation; data and aliases are kept.")

        description = st.text_area(
            "Description",
            value=attr.get("description") or "",
            height=90,
            key=f"attr_description_{attr_id}",
        )

        save_col, close_col = st.columns([1, 1])
        if save_col.form_submit_button("Save changes", type="primary"):
            try:
                api_patch(
                    f"/canonical/{attr_id}",
                    {
                        "name": name,
                        "slug": slug,
                        "description": description,
                        "category_hint": category_hint,
                        "sample_values": split_csv(sample_values),
                        "active": active,
                    },
                )
                st.success("Changes saved.")
                st.rerun()
            except Exception as exc:
                show_error(exc)

        if close_col.form_submit_button("Close"):
            set_attr_action(None, None)
            st.rerun()

    a1, a2, a3 = st.columns([1, 1, 4])
    with a1:
        if st.button("Reindex", key=f"reindex_attr_{attr_id}"):
            try:
                result = api_post(f"/embeddings/reindex/{attr_id}")
                if result.get("warning"):
                    st.warning(result)
                else:
                    st.success(result)
            except Exception as exc:
                show_error(exc)
    with a2:
        label = "Deactivate" if attr.get("active", True) else "Activate"
        if st.button(label, key=f"toggle_active_{attr_id}"):
            try:
                if attr.get("active", True):
                    api_delete(f"/canonical/{attr_id}")
                else:
                    api_patch(f"/canonical/{attr_id}", {"active": True})
                st.success("Status updated.")
                st.rerun()
            except Exception as exc:
                show_error(exc)

    st.divider()
    render_alias_manager(attr)
    st.markdown("</div>", unsafe_allow_html=True)


def render_attribute_delete_panel(attr: dict) -> None:
    attr_id = attr["id"]
    st.markdown("<div class='danger-box'>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel-title'>Delete / deactivate attribute #{attr_id}</div>", unsafe_allow_html=True)
    if attr.get("active", True):
        st.warning(
            "To preserve logs and avoid breaking previous reviews, dashboard delete is handled as deactivation. "
            "After deactivation, this attribute will not be used in active matches."
        )
        confirm = st.checkbox(f"I confirm deactivating {attr.get('name')}", key=f"confirm_deactivate_{attr_id}")
        d1, d2 = st.columns([1, 1])
        if d1.button("Delete / deactivate", key=f"do_deactivate_{attr_id}", type="primary"):
            if not confirm:
                st.warning("Check the confirmation box first.")
            else:
                try:
                    api_delete(f"/canonical/{attr_id}")
                    set_attr_action(None, None)
                    st.success("Attribute deactivated.")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)
        if d2.button("Cancel", key=f"cancel_deactivate_{attr_id}"):
            set_attr_action(None, None)
            st.rerun()
    else:
        st.info("This attribute is already inactive.")
        r1, r2 = st.columns([1, 1])
        if r1.button("Reactivate", key=f"reactivate_from_delete_{attr_id}", type="primary"):
            try:
                api_patch(f"/canonical/{attr_id}", {"active": True})
                set_attr_action(None, None)
                st.success("Attribute reactivated.")
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if r2.button("Close", key=f"close_delete_{attr_id}"):
            set_attr_action(None, None)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_attribute_table_header() -> None:
    st.markdown("<div class='table-head'>", unsafe_allow_html=True)
    h1, h2, h3, h4, h5, h6 = st.columns([0.7, 2.1, 1.35, 3.0, 1.0, 1.8])
    h1.markdown("ID")
    h2.markdown("Name")
    h3.markdown("Slug")
    h4.markdown("Alias / Sample")
    h5.markdown("Status")
    h6.markdown("Actions")
    st.markdown("</div>", unsafe_allow_html=True)


def render_attribute_table_row(attr: dict) -> None:
    attr_id = attr["id"]
    action = current_attr_action(attr_id)

    st.markdown("<div class='table-row'>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns([0.7, 2.1, 1.35, 3.0, 1.0, 1.8])
    with c1:
        st.markdown(f"<div class='row-title'>#{attr_id}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='row-title'>{escape(attr.get('name', ''))}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='row-muted'>{escape(attr.get('category_hint') or '-')}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='row-muted'>{escape(attr.get('slug') or '-')}</div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='row-muted'><b>aliases:</b> {escape(alias_summary(attr, limit=6))}</div>", unsafe_allow_html=True)
        samples = join_values(attr.get("sample_values", [])) or "-"
        st.markdown(f"<div class='row-muted'><b>samples:</b> {escape(samples)}</div>", unsafe_allow_html=True)
    with c5:
        kind = "active" if attr.get("active", True) else "inactive"
        label = "active" if attr.get("active", True) else "inactive"
        st.markdown(status_chip(label, kind), unsafe_allow_html=True)
    with c6:
        e1, e2 = st.columns([1, 1])
        edit_label = "Close" if action == "edit" else "Edit"
        if e1.button(edit_label, key=f"table_edit_attr_{attr_id}", type="primary" if action == "edit" else "secondary"):
            if action == "edit":
                set_attr_action(None, None)
            else:
                set_attr_action(attr_id, "edit")
            st.rerun()
        delete_label = "Close" if action == "delete" else "Delete"
        if e2.button(delete_label, key=f"table_delete_attr_{attr_id}"):
            if action == "delete":
                set_attr_action(None, None)
            else:
                set_attr_action(attr_id, "delete")
            st.rerun()

    if action == "edit":
        render_attribute_edit_panel(attr)
    elif action == "delete":
        render_attribute_delete_panel(attr)
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# Review renderers
# -----------------------------
def render_review_panel(item: dict) -> None:
    review_id = item["id"]
    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.markdown("<div class='panel-title'>Input</div>", unsafe_allow_html=True)
        st.json(
            {
                "raw": item.get("input_raw"),
                "normalized": item.get("input_norm"),
                "category": item.get("category"),
                "sample_values": item.get("sample_values") or [],
            }
        )
    with right:
        candidates = item.get("candidates_snapshot") or []
        st.markdown("<div class='panel-title'>Semantic candidates</div>", unsafe_allow_html=True)
        if candidates:
            st.dataframe(pd.DataFrame(candidates), use_container_width=True, hide_index=True)
        else:
            st.info("No semantic candidates. A suitable canonical attribute may not exist yet, or the score was too low.")

    if item["status"] != "open":
        st.info(f"This item is already closed with status {item['status']}.")
        return

    st.markdown("<div class='panel-title'>Approve as existing attribute</div>", unsafe_allow_html=True)
    candidates = item.get("candidates_snapshot") or []
    if candidates:
        cols = st.columns(min(len(candidates), 4))
        for idx, cand in enumerate(candidates[:4]):
            with cols[idx % len(cols)]:
                label = f"Approve {cand['name']} ({cand['score']:.3f})"
                if st.button(label, key=f"approve_candidate_{review_id}_{cand['canonical_id']}"):
                    try:
                        api_post(
                            f"/review/{review_id}/approve",
                            {
                                "canonical_id": cand["canonical_id"],
                                "alias_raw": item["input_raw"],
                                "notes": "Approved suggested candidate from dashboard",
                            },
                        )
                        st.success("Approved.")
                        st.rerun()
                    except Exception as exc:
                        show_error(exc)
    else:
        st.caption("No suggested candidates. Use manual search below.")

    st.markdown("<div class='panel-title'>Manual search for an existing attribute</div>", unsafe_allow_html=True)
    manual_q = st.text_input(
        "Search existing canonical by name or alias",
        value=item.get("input_raw", ""),
        key=f"manual_search_{review_id}",
    )
    try:
        attrs = api_get("/canonical", q=manual_q or None, active=True, include_inactive=False, limit=30)
    except Exception as exc:
        attrs = []
        show_error(exc)

    if attrs:
        option_map = {attr_option_label(attr): attr for attr in attrs}
        selected_label = st.selectbox(
            "Select existing canonical attribute",
            list(option_map.keys()),
            key=f"manual_select_{review_id}",
        )
        alias_raw = st.text_input(
            "Alias to save for selected attribute",
            value=item.get("input_raw", ""),
            key=f"manual_alias_{review_id}",
        )
        selected_attr = option_map[selected_label]
        if st.button("Approve and save alias", key=f"approve_manual_{review_id}", type="primary"):
            try:
                api_post(
                    f"/review/{review_id}/approve",
                    {
                        "canonical_id": selected_attr["id"],
                        "alias_raw": alias_raw or item["input_raw"],
                        "notes": "Approved manually from dashboard search",
                    },
                )
                st.success("Approved and alias saved.")
                st.rerun()
            except Exception as exc:
                show_error(exc)
    else:
        st.info("No existing attribute found. If this is really new, create it below.")

    st.divider()
    st.markdown("<div class='panel-title'>Create a new canonical attribute from this review</div>", unsafe_allow_html=True)
    with st.form(f"create_new_from_review_{review_id}"):
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Name", value=item.get("input_raw", ""), key=f"new_name_{review_id}")
            new_slug = st.text_input("Slug optional", value="", key=f"new_slug_{review_id}")
        with c2:
            new_aliases = st.text_input("Extra aliases, comma separated", value="", key=f"new_aliases_{review_id}")
            category_hint = st.text_input("Category hint", value=item.get("category") or "", key=f"new_category_{review_id}")
        create_submitted = st.form_submit_button("Create new attribute", type="primary")
        if create_submitted:
            try:
                api_post(
                    f"/review/{review_id}/create-attribute",
                    {
                        "name": new_name,
                        "slug": new_slug or None,
                        "category_hint": category_hint or None,
                        "aliases": split_csv(new_aliases),
                        "notes": "Created from dashboard",
                    },
                )
                st.success("Created and review approved.")
                st.rerun()
            except Exception as exc:
                show_error(exc)

    st.divider()
    ignore_col, close_col = st.columns([1, 1])
    with ignore_col:
        if st.button("Ignore", key=f"ignore_{review_id}"):
            try:
                api_post(f"/review/{review_id}/ignore", {"notes": "Ignored from dashboard"})
                st.success("Ignored.")
                st.rerun()
            except Exception as exc:
                show_error(exc)
    with close_col:
        if st.button("Close Review", key=f"close_review_{review_id}"):
            st.session_state.open_review_id = None
            st.rerun()


def render_review_row(item: dict) -> None:
    review_id = item["id"]
    is_open = st.session_state.get("open_review_id") == review_id
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([0.8, 2.4, 1.8, 2.2, 1.2])
        with c1:
            st.markdown(f"<div class='row-muted'>ID</div><div class='row-title'>#{review_id}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='row-title'>{escape(item.get('input_raw', ''))}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='row-muted'>norm: {escape(item.get('input_norm', ''))}</div>", unsafe_allow_html=True)
        with c3:
            kind = item.get("status", "open")
            if kind not in {"open", "approved", "ignored"}:
                kind = "inactive"
            st.markdown(status_chip(item.get("status", "open"), kind), unsafe_allow_html=True)
            st.markdown(f"<div class='row-muted'>decision: {escape(item.get('decision', '-'))}</div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='row-muted'>category: {escape(item.get('category') or '-')}</div>", unsafe_allow_html=True)
            samples = join_values(item.get("sample_values", [])) or "-"
            st.markdown(f"<div class='row-muted'>samples: {escape(samples)}</div>", unsafe_allow_html=True)
        with c5:
            label = "Close" if is_open else "Review"
            if st.button(label, key=f"review_open_{review_id}", type="primary" if is_open else "secondary"):
                st.session_state.open_review_id = None if is_open else review_id
                st.rerun()

        if is_open:
            render_review_panel(item)


# -----------------------------
# Tabs
# -----------------------------
resolve_tab, review_tab, attributes_tab, tools_tab = st.tabs(["Resolve tester", "Review queue", "Attributes", "Tools"])

with resolve_tab:
    st.subheader("Resolve tester")
    st.caption("Quickly test which canonical attribute a raw attribute name resolves to.")

    with st.form("resolve_form"):
        c1, c2 = st.columns([2, 1])
        with c1:
            raw_name = st.text_input("Raw attribute name", value="Ram")
        with c2:
            category = st.text_input("Category", value="laptop")
        sample_values = st.text_input("Sample values, comma separated", value="8GB, 16GB, DDR4")
        create_review = st.checkbox("Create review when uncertain", value=True)
        submitted = st.form_submit_button("Resolve", type="primary")

    if submitted:
        try:
            st.session_state.last_resolve_result = api_post(
                "/resolve",
                {
                    "raw_name": raw_name,
                    "category": category,
                    "sample_values": split_csv(sample_values),
                    "create_review": create_review,
                },
            )
        except Exception as exc:
            show_error(exc)

    result = st.session_state.get("last_resolve_result")
    if result:
        st.markdown("<div class='panel-title'>Result</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Decision", result.get("decision", "-"))
        c2.metric("Method", result.get("method", "-"))
        c3.metric("Confidence", "-" if result.get("confidence") is None else f"{result['confidence']:.3f}")
        c4.metric("Review ID", result.get("review_id") or "-")
        if result.get("attribute"):
            st.success(f"Matched: #{result['attribute']['id']} | {result['attribute']['name']}")
        if result.get("candidates"):
            st.dataframe(pd.DataFrame(result["candidates"]), use_container_width=True, hide_index=True)
        with st.expander("Raw response", expanded=False):
            st.json(result)

with review_tab:
    st.subheader("Human review queue")

    f1, f2, f3 = st.columns([1.2, 1.2, 3])
    with f1:
        status = st.selectbox("Status", ["open", "approved", "ignored", "all"], index=0)
    with f2:
        review_page_size = int(st.selectbox("Items per page", [5, 10, 20, 50, 100], index=1, key="review_page_size"))
    with f3:
        if st.button("Refresh reviews"):
            st.rerun()

    reset_page_on_filter_change("review_page", (status, review_page_size))

    try:
        # Use the page endpoint when available.
        total_reviews = int(api_get("/review/count", status=status).get("total", 0))
        review_page = render_pager("review_page", total_reviews, review_page_size, "reviews")
        review_offset = (review_page - 1) * review_page_size
        reviews = api_get("/review", status=status, limit=review_page_size, offset=review_offset)

        if not reviews:
            st.info("No items to display.")
        else:
            for item in reviews:
                render_review_row(item)
    except Exception as exc:
        show_error(exc)

with attributes_tab:
    st.subheader("Canonical attributes")
    st.caption("Main attributes table. Use Edit or Delete on a row; the action panel opens inline under that row.")

    top_actions = st.columns([1.1, 1.1, 4])
    with top_actions[0]:
        if st.button("+ Create new attribute", type="primary"):
            if st.session_state.get("show_create_attr"):
                st.session_state.show_create_attr = False
            else:
                st.session_state.show_create_attr = True
                set_attr_action(None, None)
            st.rerun()
    with top_actions[1]:
        if st.button("Refresh list"):
            st.rerun()

    if st.session_state.get("show_create_attr"):
        st.markdown("<div class='inline-panel'>", unsafe_allow_html=True)
        st.markdown("<div class='panel-title'>Create new attribute</div>", unsafe_allow_html=True)
        with st.form("create_attribute_form"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name")
                slug = st.text_input("Slug optional")
                category_hint = st.text_input("Category hint optional")
            with c2:
                aliases = st.text_area("Aliases, comma/new-line separated", height=95)
                sample_values = st.text_input("Sample values, comma separated")
            create_c, close_c = st.columns([1, 1])
            create_attr = create_c.form_submit_button("Create attribute", type="primary")
            close_create = close_c.form_submit_button("Close")

        if create_attr:
            try:
                alias_text = aliases.replace("\n", ",")
                result = api_post(
                    "/canonical",
                    {
                        "name": name,
                        "slug": slug or None,
                        "category_hint": category_hint,
                        "aliases": split_csv(alias_text),
                        "sample_values": split_csv(sample_values),
                    },
                )
                st.session_state.show_create_attr = False
                st.success(f"Created canonical attribute #{result['id']}")
                st.rerun()
            except Exception as exc:
                show_error(exc)
        if close_create:
            st.session_state.show_create_attr = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    f1, f2, f3 = st.columns([2.4, 1.2, 1.2])
    with f1:
        q = st.text_input("Search name / slug / alias", value="", placeholder="e.g. ram or processor")
    with f2:
        active_filter = st.selectbox("Status", ["active", "inactive", "all"], index=0)
    with f3:
        attr_page_size = int(st.selectbox("Items per page", [10, 20, 50, 100], index=1, key="attr_page_size"))

    reset_page_on_filter_change("attr_page", (q, active_filter, attr_page_size))
    params = active_filter_to_params(active_filter)

    try:
        page = int(st.session_state.get("attr_page", 1) or 1)
        page_payload = api_get(
            "/canonical/page",
            q=q or None,
            page=page,
            page_size=attr_page_size,
            **params,
        )
        total_attrs = int(page_payload.get("total", 0))
        # The API clamps page. Keep session state in sync.
        st.session_state.attr_page = int(page_payload.get("page", 1))
        page = render_pager("attr_page", total_attrs, attr_page_size, "attrs")

        # Re-fetch when pager changed page in this run.
        if page != int(page_payload.get("page", 1)):
            page_payload = api_get(
                "/canonical/page",
                q=q or None,
                page=page,
                page_size=attr_page_size,
                **params,
            )
        attrs = page_payload.get("items", [])

        if not attrs:
            st.info("No attributes found.")
        else:
            render_attribute_table_header()
            for attr in attrs:
                render_attribute_table_row(attr)
            st.caption("Delete in this dashboard means safe deactivation, not physical deletion from the database.")
    except requests.HTTPError as exc:
        # Fallback for older backend versions that do not have /canonical/page.
        if exc.response is not None and exc.response.status_code == 404:
            try:
                total_attrs = int(api_get("/canonical/count", q=q or None, **params).get("total", 0))
                page = render_pager("attr_page", total_attrs, attr_page_size, "attrs")
                offset = (page - 1) * attr_page_size
                attrs = api_get("/canonical", q=q or None, limit=attr_page_size, offset=offset, **params)
                if not attrs:
                    st.info("No attributes found.")
                else:
                    render_attribute_table_header()
                    for attr in attrs:
                        render_attribute_table_row(attr)
            except Exception as fallback_exc:
                show_error(fallback_exc)
        else:
            show_error(exc)
    except Exception as exc:
        show_error(exc)

with tools_tab:
    st.subheader("Maintenance")

    with st.container(border=True):
        st.markdown("<div class='panel-title'>Starter data</div>", unsafe_allow_html=True)
        st.caption("Creates a few starter canonical attributes such as RAM, Processor, Description, and Internal Storage.")
        if st.button("Create starter attributes"):
            try:
                created, messages = create_starter_attributes()
                if created:
                    st.success(f"Created {created} starter attributes.")
                else:
                    st.info("No new starter attributes were created. They may already exist.")
                st.json(messages)
                st.rerun()
            except Exception as exc:
                show_error(exc)

    with st.container(border=True):
        st.markdown("<div class='panel-title'>Embeddings</div>", unsafe_allow_html=True)
        st.caption("Rebuild embeddings after bulk imports or model changes.")
        if st.button("Reindex all embeddings"):
            try:
                result = api_post("/embeddings/reindex")
                st.success(result)
            except Exception as exc:
                show_error(exc)

    with st.container(border=True):
        st.markdown("<div class='panel-title'>Health</div>", unsafe_allow_html=True)
        if st.button("Check API health"):
            try:
                st.json(api_get("/health"))
            except Exception as exc:
                show_error(exc)
