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
    padding-top: 1.25rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}
.main-title {
    font-size: 2rem;
    font-weight: 800;
    margin: 0 0 .2rem 0;
}
.subtle {
    color: #667085;
    font-size: .9rem;
}
.chip {
    display: inline-block;
    border-radius: 999px;
    padding: .18rem .55rem;
    font-size: .78rem;
    font-weight: 700;
    border: 1px solid rgba(0,0,0,.08);
}
.chip-active { background: #ecfdf3; color: #027a48; }
.chip-inactive { background: #f2f4f7; color: #344054; }
.chip-open { background: #eff8ff; color: #175cd3; }
.chip-approved { background: #ecfdf3; color: #027a48; }
.chip-ignored { background: #fff6ed; color: #c4320a; }
.row-title {
    font-weight: 750;
    font-size: 1.03rem;
    margin-bottom: .1rem;
}
.row-muted {
    color: #667085;
    font-size: .84rem;
    line-height: 1.5;
}
.section-title {
    font-weight: 800;
    font-size: 1.08rem;
    margin: .25rem 0 .5rem 0;
}
hr { margin-top: .8rem; margin-bottom: .8rem; }
.stButton>button {
    border-radius: .55rem;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">Attribute AI Resolver</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="subtle">API connection: <code>{escape(API_BASE_URL)}</code> | Browser docs: <code>http://localhost:8000/docs</code></div>',
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


def alias_summary(attr: dict, limit: int = 6) -> str:
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


def get_current_page(page_key: str, total: int, page_size: int) -> tuple[int, int]:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    page = int(st.session_state.get(page_key, 1) or 1)
    page = min(max(page, 1), total_pages)
    st.session_state[page_key] = page
    return page, total_pages


def render_pagination(page_key: str, total: int, page_size: int, prefix: str) -> tuple[int, int]:
    page, total_pages = get_current_page(page_key, total, page_size)
    start = 0 if total == 0 else (page - 1) * page_size + 1
    end = min(total, page * page_size)

    col_first, col_prev, col_info, col_next, col_last = st.columns([1, 1, 2.5, 1, 1])
    with col_first:
        if st.button("اول", key=f"{prefix}_first", disabled=page <= 1):
            st.session_state[page_key] = 1
            st.rerun()
    with col_prev:
        if st.button("قبلی", key=f"{prefix}_prev", disabled=page <= 1):
            st.session_state[page_key] = page - 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<div class='row-muted' style='text-align:center;padding-top:.45rem'>صفحه <b>{page}</b> از <b>{total_pages}</b> — نمایش {start} تا {end} از {total}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("بعدی", key=f"{prefix}_next", disabled=page >= total_pages):
            st.session_state[page_key] = page + 1
            st.rerun()
    with col_last:
        if st.button("آخر", key=f"{prefix}_last", disabled=page >= total_pages):
            st.session_state[page_key] = total_pages
            st.rerun()

    return page, total_pages


def active_filter_to_params(value: str) -> dict[str, Any]:
    if value == "active":
        return {"active": True, "include_inactive": False}
    if value == "inactive":
        return {"active": False, "include_inactive": False}
    return {"active": None, "include_inactive": True}


def create_starter_attributes() -> tuple[int, list[str]]:
    starter_items = [
        {
            "name": "رم",
            "slug": "ram",
            "category_hint": "laptop computer mobile",
            "aliases": ["ram", "RAM", "Ram", "رم کامپیوتر", "حافظه رم", "RAM Memory", "RAM Capacity"],
            "sample_values": ["4GB", "8GB", "16GB", "32GB", "DDR4", "DDR5"],
        },
        {
            "name": "پردازنده",
            "slug": "cpu",
            "category_hint": "laptop computer mobile",
            "aliases": ["CPU", "cpu", "processor", "پردازشگر", "سی پی یو", "مدل پردازنده"],
            "sample_values": ["Core i3", "Core i5", "Core i7", "Ryzen 5", "Ryzen 7"],
        },
        {
            "name": "توضیحات",
            "slug": "description",
            "category_hint": "content",
            "aliases": ["description", "desc", "توضیحات بیشتر", "توضیحات اضافی", "توضیح", "شرح محصول"],
            "sample_values": ["text", "HTML", "description"],
        },
        {
            "name": "حافظه داخلی",
            "slug": "storage",
            "category_hint": "laptop computer mobile",
            "aliases": ["storage", "internal storage", "hard drive", "ssd", "ظرفیت هارد", "فضای ذخیره سازی"],
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
    st.warning("API هنوز آماده نیست یا اتصال برقرار نشد.")
    show_error(exc)
    stats = {}


# -----------------------------
# Renderers
# -----------------------------
def render_alias_inline_editor(alias: dict) -> None:
    alias_id = alias["id"]
    st.markdown("<div class='section-title'>ویرایش alias</div>", unsafe_allow_html=True)
    with st.form(f"edit_alias_form_{alias_id}"):
        c1, c2, c3, c4 = st.columns([3, 1.4, 1, 1])
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

        confirm_delete = st.checkbox("حذف این alias را تأیید می‌کنم", key=f"confirm_delete_alias_{alias_id}")
        save_col, cancel_col, delete_col = st.columns([1.2, 1.2, 1.2])
        save_alias = save_col.form_submit_button("ذخیره alias", type="primary")
        close_alias = cancel_col.form_submit_button("بستن")
        delete_alias = delete_col.form_submit_button("حذف alias")

        if save_alias:
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
                st.success("Alias updated.")
                st.rerun()
            except Exception as exc:
                show_error(exc)

        if close_alias:
            st.session_state.editing_alias_id = None
            st.rerun()

        if delete_alias:
            if not confirm_delete:
                st.warning("برای حذف، اول checkbox تأیید حذف را فعال کن.")
            else:
                try:
                    api_delete(f"/aliases/{alias_id}", reindex=True)
                    st.session_state.editing_alias_id = None
                    st.success("Alias deleted.")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)


def render_attribute_edit_panel(attr: dict) -> None:
    attr_id = attr["id"]
    st.divider()
    st.markdown(f"<div class='section-title'>ویرایش اتریبیوت #{attr_id}</div>", unsafe_allow_html=True)

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

        description = st.text_area(
            "Description",
            value=attr.get("description") or "",
            height=90,
            key=f"attr_description_{attr_id}",
        )

        save_col, close_col = st.columns([1, 1])
        save_attr = save_col.form_submit_button("ذخیره تغییرات", type="primary")
        close_attr = close_col.form_submit_button("بستن ویرایش")

        if save_attr:
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
                st.success("Attribute updated.")
                st.rerun()
            except Exception as exc:
                show_error(exc)

        if close_attr:
            st.session_state.editing_attr_id = None
            st.session_state.editing_alias_id = None
            st.rerun()

    action_col1, action_col2, action_col3 = st.columns([1.3, 1.3, 3])
    with action_col1:
        if st.button("Reindex", key=f"reindex_attr_{attr_id}"):
            try:
                result = api_post(f"/embeddings/reindex/{attr_id}")
                if result.get("warning"):
                    st.warning(result)
                else:
                    st.success(result)
            except Exception as exc:
                show_error(exc)
    with action_col2:
        if attr.get("active", True):
            if st.button("غیرفعال‌سازی", key=f"deactivate_attr_{attr_id}"):
                try:
                    api_delete(f"/canonical/{attr_id}")
                    st.session_state.editing_attr_id = None
                    st.success("Attribute deactivated.")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)
        else:
            if st.button("فعال‌سازی", key=f"reactivate_attr_{attr_id}"):
                try:
                    api_patch(f"/canonical/{attr_id}", {"active": True})
                    st.success("Attribute reactivated.")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)

    st.divider()
    st.markdown("<div class='section-title'>Aliasها</div>", unsafe_allow_html=True)

    with st.form(f"add_alias_form_{attr_id}", clear_on_submit=True):
        a1, a2, a3, a4 = st.columns([3, 1.4, 1, 1])
        with a1:
            alias_raw = st.text_input("Alias جدید", key=f"new_alias_raw_{attr_id}")
        with a2:
            source = st.text_input("Source", value="manual", key=f"new_alias_source_{attr_id}")
        with a3:
            confidence = st.number_input(
                "Confidence",
                min_value=0.0,
                max_value=1.0,
                value=1.0,
                step=0.01,
                key=f"new_alias_conf_{attr_id}",
            )
        with a4:
            approved = st.checkbox("Approved", value=True, key=f"new_alias_approved_{attr_id}")
        add_alias = st.form_submit_button("افزودن alias", type="primary")
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
        st.info("هنوز alias ندارد.")
    else:
        for alias in aliases:
            alias_id = alias["id"]
            is_editing_alias = st.session_state.get("editing_alias_id") == alias_id
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3, 2.4, 1.4, 1.2, 1])
                with c1:
                    st.markdown(f"<div class='row-title'>{escape(alias.get('alias_raw', ''))}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='row-muted'>norm: {escape(alias.get('alias_norm', ''))}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='row-muted'>source: {escape(alias.get('source', ''))}</div>", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"<div class='row-muted'>confidence: {float(alias.get('confidence', 0)):.2f}</div>", unsafe_allow_html=True)
                with c4:
                    kind = "active" if alias.get("approved", True) else "inactive"
                    label = "approved" if alias.get("approved", True) else "not approved"
                    st.markdown(status_chip(label, kind), unsafe_allow_html=True)
                with c5:
                    button_label = "بستن" if is_editing_alias else "ویرایش"
                    if st.button(button_label, key=f"edit_alias_btn_{alias_id}", type="primary" if is_editing_alias else "secondary"):
                        st.session_state.editing_alias_id = None if is_editing_alias else alias_id
                        st.rerun()

                if is_editing_alias:
                    render_alias_inline_editor(alias)


def render_attribute_row(attr: dict) -> None:
    attr_id = attr["id"]
    is_editing = st.session_state.get("editing_attr_id") == attr_id

    with st.container(border=True):
        c1, c2, c3, c4, c5, c6 = st.columns([0.7, 2.4, 1.5, 1.1, 3.2, 1.2])
        with c1:
            st.markdown(f"<div class='row-muted'>ID</div><div class='row-title'>#{attr_id}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='row-title'>{escape(attr.get('name', ''))}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='row-muted'>category: {escape(attr.get('category_hint') or '-')}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='row-muted'>slug</div><div>{escape(attr.get('slug', '-'))}</div>", unsafe_allow_html=True)
        with c4:
            kind = "active" if attr.get("active", True) else "inactive"
            label = "active" if attr.get("active", True) else "inactive"
            st.markdown(status_chip(label, kind), unsafe_allow_html=True)
        with c5:
            st.markdown(f"<div class='row-muted'>aliases</div><div>{escape(alias_summary(attr, limit=8))}</div>", unsafe_allow_html=True)
            sample = join_values(attr.get("sample_values", [])) or "-"
            st.markdown(f"<div class='row-muted'>samples: {escape(sample)}</div>", unsafe_allow_html=True)
        with c6:
            label = "بستن" if is_editing else "ویرایش"
            if st.button(label, key=f"edit_attr_btn_{attr_id}", type="primary" if is_editing else "secondary"):
                st.session_state.editing_attr_id = None if is_editing else attr_id
                st.session_state.editing_alias_id = None
                st.rerun()

        if is_editing:
            render_attribute_edit_panel(attr)


def render_review_panel(item: dict) -> None:
    review_id = item["id"]
    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.markdown("<div class='section-title'>Input</div>", unsafe_allow_html=True)
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
        st.markdown("<div class='section-title'>Semantic candidates</div>", unsafe_allow_html=True)
        if candidates:
            st.dataframe(pd.DataFrame(candidates), use_container_width=True, hide_index=True)
        else:
            st.info("کاندید semantic ندارد. احتمالاً هنوز canonical مناسب ساخته نشده یا score پایین بوده.")

    if item["status"] != "open":
        st.info(f"این آیتم قبلاً با وضعیت {item['status']} بسته شده است.")
        return

    st.markdown("<div class='section-title'>تأیید به عنوان اتریبیوت موجود</div>", unsafe_allow_html=True)
    candidates = item.get("candidates_snapshot") or []
    if candidates:
        cols = st.columns(min(len(candidates), 4))
        for idx, cand in enumerate(candidates[:4]):
            with cols[idx % len(cols)]:
                label = f"تأیید {cand['name']} ({cand['score']:.3f})"
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
        st.caption("کاندید پیشنهادی وجود ندارد؛ از جستجوی دستی استفاده کن.")

    st.markdown("<div class='section-title'>جستجوی دستی attribute موجود</div>", unsafe_allow_html=True)
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
        if st.button("تأیید و ذخیره alias", key=f"approve_manual_{review_id}", type="primary"):
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
        st.info("attribute موجودی پیدا نشد. اگر واقعاً جدید است، از بخش زیر بساز.")

    st.divider()
    st.markdown("<div class='section-title'>ساخت canonical جدید از این review</div>", unsafe_allow_html=True)
    with st.form(f"create_new_from_review_{review_id}"):
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Name", value=item.get("input_raw", ""), key=f"new_name_{review_id}")
            new_slug = st.text_input("Slug optional", value="", key=f"new_slug_{review_id}")
        with c2:
            new_aliases = st.text_input("Extra aliases, comma separated", value="", key=f"new_aliases_{review_id}")
            category_hint = st.text_input("Category hint", value=item.get("category") or "", key=f"new_category_{review_id}")
        create_submitted = st.form_submit_button("ساخت attribute جدید", type="primary")
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
        if st.button("بستن بررسی", key=f"close_review_{review_id}"):
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
            label = "بستن" if is_open else "بررسی"
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
    st.caption("برای تست سریع اینکه یک نام attribute به چه چیزی match می‌شود.")

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
        st.markdown("<div class='section-title'>Result</div>", unsafe_allow_html=True)
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
        status = st.selectbox("Status", ["open", "approved", "ignored"], index=0)
    with f2:
        review_page_size = int(st.selectbox("Items per page", [5, 10, 20, 50, 100], index=1, key="review_page_size"))
    with f3:
        if st.button("Refresh reviews"):
            st.rerun()

    reset_page_on_filter_change("review_page", (status, review_page_size))

    try:
        total_reviews = int(api_get("/review/count", status=status).get("total", 0))
        review_page, _ = render_pagination("review_page", total_reviews, review_page_size, "reviews")
        review_offset = (review_page - 1) * review_page_size
        reviews = api_get("/review", status=status, limit=review_page_size, offset=review_offset)

        if not reviews:
            st.info("آیتمی برای نمایش وجود ندارد.")
        else:
            for item in reviews:
                render_review_row(item)
    except Exception as exc:
        show_error(exc)

with attributes_tab:
    st.subheader("Canonical attributes")
    st.caption("لیست صفحه‌بندی‌شده، ویرایش inline، مدیریت aliasها و فعال/غیرفعال‌سازی.")

    with st.expander("ساخت attribute جدید", expanded=False):
        with st.form("create_attribute_form"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name")
                slug = st.text_input("Slug optional")
            with c2:
                category_hint = st.text_input("Category hint optional")
                sample_values = st.text_input("Sample values, comma separated")
            aliases = st.text_input("Aliases, comma separated")
            create_attr = st.form_submit_button("Create attribute", type="primary")

        if create_attr:
            try:
                result = api_post(
                    "/canonical",
                    {
                        "name": name,
                        "slug": slug or None,
                        "category_hint": category_hint,
                        "aliases": split_csv(aliases),
                        "sample_values": split_csv(sample_values),
                    },
                )
                st.success(f"Created canonical attribute #{result['id']}")
                st.rerun()
            except Exception as exc:
                show_error(exc)

    f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.2, 1])
    with f1:
        q = st.text_input("جستجو در name / slug / alias", value="")
    with f2:
        active_filter = st.selectbox("وضعیت", ["active", "inactive", "all"], index=0)
    with f3:
        attr_page_size = int(st.selectbox("تعداد در صفحه", [10, 20, 50, 100], index=1, key="attr_page_size"))
    with f4:
        if st.button("Refresh"):
            st.rerun()

    reset_page_on_filter_change("attr_page", (q, active_filter, attr_page_size))
    params = active_filter_to_params(active_filter)

    try:
        total_attrs = int(api_get("/canonical/count", q=q or None, **params).get("total", 0))
        attr_page, _ = render_pagination("attr_page", total_attrs, attr_page_size, "attrs")
        attr_offset = (attr_page - 1) * attr_page_size
        attrs = api_get("/canonical", q=q or None, limit=attr_page_size, offset=attr_offset, **params)

        if not attrs:
            st.info("هیچ attributeای پیدا نشد.")
        else:
            for attr in attrs:
                render_attribute_row(attr)
    except Exception as exc:
        show_error(exc)

with tools_tab:
    st.subheader("Maintenance")

    with st.container(border=True):
        st.markdown("<div class='section-title'>Starter data</div>", unsafe_allow_html=True)
        st.caption("چند canonical اولیه مثل رم، پردازنده، توضیحات و حافظه داخلی می‌سازد.")
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
        st.markdown("<div class='section-title'>Embeddings</div>", unsafe_allow_html=True)
        st.caption("بعد از import گروهی یا تغییر مدل، embeddingها را بازسازی کن.")
        if st.button("Reindex all embeddings"):
            try:
                result = api_post("/embeddings/reindex")
                st.success(result)
            except Exception as exc:
                show_error(exc)

    with st.container(border=True):
        st.markdown("<div class='section-title'>Health</div>", unsafe_allow_html=True)
        if st.button("Check API health"):
            try:
                st.json(api_get("/health"))
            except Exception as exc:
                show_error(exc)
