import os
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Attribute AI Resolver", layout="wide")
st.title("Attribute AI Resolver")
st.caption(f"API: {API_BASE_URL}")


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


def split_values(value: str) -> list[str]:
    """Split comma/newline/pipe separated input values."""
    return [item.strip() for item in re.split(r"[,\n|]+", value or "") if item.strip()]


def join_values(values: list[Any]) -> str:
    return "\n".join(str(v) for v in values or [])


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


def alias_summary(attr: dict, limit: int = 6) -> str:
    aliases = [a.get("alias_raw", "") for a in attr.get("aliases", []) if a.get("alias_raw")]
    aliases = aliases[:limit]
    return ", ".join(aliases)


def attr_option_label(attr: dict) -> str:
    aliases = alias_summary(attr, limit=4)
    if aliases:
        return f"#{attr['id']} | {attr['name']} | aliases: {aliases}"
    return f"#{attr['id']} | {attr['name']}"


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


try:
    stats = api_get("/stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Canonical", stats["canonical_count"])
    c2.metric("Aliases", stats["alias_count"])
    c3.metric("Embeddings", stats["embedding_count"])
    c4.metric("Open reviews", stats["open_review_count"])

    if stats["canonical_count"] == 0:
        st.warning(
            "No canonical attributes exist yet. Review items cannot show existing-match buttons until you create at least one canonical attribute. "
            "Use 'Create new attribute' inside a review item, create attributes in the Attributes tab, or use Tools -> Create starter attributes."
        )
except Exception as exc:
    stats = None
    show_error(exc)

resolve_tab, review_tab, attributes_tab, tools_tab = st.tabs(
    ["Resolve tester", "Review queue", "Attributes", "Tools"]
)

with resolve_tab:
    st.subheader("Test resolver")
    with st.form("resolve_form"):
        raw_name = st.text_input("Raw attribute name", value="Ram")
        category = st.text_input("Category/context", value="laptop")
        sample_values_raw = st.text_input("Sample values, comma/newline separated", value="8GB, 16GB, DDR4")
        create_review = st.checkbox("Create review item for uncertain results", value=True)
        submitted = st.form_submit_button("Resolve")

    if submitted:
        try:
            result = api_post(
                "/resolve",
                {
                    "raw_name": raw_name,
                    "category": category,
                    "sample_values": split_values(sample_values_raw),
                    "create_review": create_review,
                },
            )
            st.json(result)
            candidates = result.get("candidates") or []
            if candidates:
                st.dataframe(pd.DataFrame(candidates), use_container_width=True)
        except Exception as exc:
            show_error(exc)

with review_tab:
    st.subheader("Human review queue")
    status = st.selectbox("Status", ["open", "approved", "ignored"], index=0)
    if st.button("Refresh reviews"):
        st.rerun()

    try:
        reviews = api_get("/review", status=status, limit=100)
        st.write(f"Items: {len(reviews)}")
        for item in reviews:
            title = f"#{item['id']} | {item['input_raw']} | {item['decision']}"
            with st.expander(title, expanded=False):
                left, right = st.columns([2, 3])
                with left:
                    st.write("Input")
                    st.json(
                        {
                            "raw": item["input_raw"],
                            "normalized": item["input_norm"],
                            "category": item.get("category"),
                            "sample_values": item.get("sample_values"),
                        }
                    )
                with right:
                    candidates = item.get("candidates_snapshot") or []
                    if candidates:
                        st.write("Semantic candidates")
                        st.dataframe(pd.DataFrame(candidates), use_container_width=True)
                    else:
                        st.info("No semantic candidates. This usually means there are no canonical attributes yet, or scores were below the review threshold.")

                if item["status"] == "open":
                    candidates = item.get("candidates_snapshot") or []

                    st.divider()
                    st.write("### 1) Approve as existing attribute")
                    if candidates:
                        st.write("Suggested candidates")
                        cols = st.columns(min(len(candidates), 4))
                        for idx, cand in enumerate(candidates[:4]):
                            with cols[idx % len(cols)]:
                                label = f"Approve {cand['name']} ({cand['score']:.3f})"
                                if st.button(label, key=f"approve_candidate_{item['id']}_{cand['canonical_id']}"):
                                    try:
                                        api_post(
                                            f"/review/{item['id']}/approve",
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
                        st.caption("No suggested candidates for this item.")

                    st.write("Search and approve manually")
                    manual_q = st.text_input(
                        "Search existing canonical by name or alias",
                        value=item["input_raw"],
                        key=f"manual_search_{item['id']}",
                    )
                    attrs = api_get("/canonical", q=manual_q or None, active=True, limit=50)
                    if attrs:
                        option_map = {attr_option_label(attr): attr for attr in attrs}
                        selected_label = st.selectbox(
                            "Select existing canonical attribute",
                            list(option_map.keys()),
                            key=f"manual_select_{item['id']}",
                        )
                        alias_raw = st.text_input(
                            "Alias to save for selected attribute",
                            value=item["input_raw"],
                            key=f"manual_alias_{item['id']}",
                        )
                        selected_attr = option_map[selected_label]
                        if st.button("Approve selected existing attribute", key=f"approve_manual_{item['id']}"):
                            try:
                                api_post(
                                    f"/review/{item['id']}/approve",
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
                        st.info("No existing canonical attribute found. Create one below, or create attributes in the Attributes tab.")

                    st.divider()
                    st.write("### 2) Create new canonical attribute")
                    with st.form(f"create_new_{item['id']}"):
                        new_name = st.text_input("Name", value=item["input_raw"], key=f"new_name_{item['id']}")
                        new_slug = st.text_input("Slug optional", value="", key=f"new_slug_{item['id']}")
                        new_aliases = st.text_input("Extra aliases, comma/newline separated", value="", key=f"new_aliases_{item['id']}")
                        create_submitted = st.form_submit_button("Create new attribute")
                        if create_submitted:
                            try:
                                api_post(
                                    f"/review/{item['id']}/create-attribute",
                                    {
                                        "name": new_name,
                                        "slug": new_slug or None,
                                        "aliases": split_values(new_aliases),
                                        "notes": "Created from dashboard",
                                    },
                                )
                                st.success("Created and review approved.")
                                st.rerun()
                            except Exception as exc:
                                show_error(exc)

                    st.divider()
                    st.write("### 3) Ignore")
                    if st.button("Ignore", key=f"ignore_{item['id']}"):
                        try:
                            api_post(f"/review/{item['id']}/ignore", {"notes": "Ignored from dashboard"})
                            st.success("Ignored.")
                            st.rerun()
                        except Exception as exc:
                            show_error(exc)
                else:
                    st.info(f"This review item is already {item['status']}.")
    except Exception as exc:
        show_error(exc)

with attributes_tab:
    st.subheader("Canonical attributes")
    st.caption("Create, edit, deactivate/reactivate canonical attributes, and manage aliases from here.")

    with st.form("create_attribute_form"):
        name = st.text_input("Name")
        slug = st.text_input("Slug optional")
        description = st.text_area("Description optional", height=80)
        category_hint = st.text_input("Category hint optional")
        aliases = st.text_area("Aliases, comma/newline separated", height=80)
        sample_values = st.text_area("Sample values, comma/newline separated", height=80)
        create_attr = st.form_submit_button("Create attribute")

    if create_attr:
        try:
            result = api_post(
                "/canonical",
                {
                    "name": name,
                    "slug": slug or None,
                    "description": description or None,
                    "category_hint": category_hint,
                    "aliases": split_values(aliases),
                    "sample_values": split_values(sample_values),
                },
            )
            st.success(f"Created canonical attribute #{result['id']}")
            st.rerun()
        except Exception as exc:
            show_error(exc)

    st.divider()
    st.write("### Search and edit")
    col_q, col_status, col_limit = st.columns([3, 1, 1])
    with col_q:
        q = st.text_input("Search canonical attributes", value="")
    with col_status:
        active_filter = st.selectbox("Active filter", ["active", "inactive", "all"], index=0)
    with col_limit:
        limit = st.number_input("Limit", min_value=10, max_value=1000, value=200, step=10)

    active_param: bool | None
    if active_filter == "active":
        active_param = True
    elif active_filter == "inactive":
        active_param = False
    else:
        active_param = None

    try:
        attrs = api_get("/canonical", q=q or None, active=active_param, limit=int(limit))
        rows = []
        for attr in attrs:
            rows.append(
                {
                    "id": attr["id"],
                    "active": attr["active"],
                    "name": attr["name"],
                    "slug": attr["slug"],
                    "category": attr.get("category_hint") or "",
                    "aliases": ", ".join(a["alias_raw"] for a in attr.get("aliases", [])),
                    "samples": ", ".join(str(v) for v in attr.get("sample_values", [])),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        for attr in attrs:
            aliases_list = attr.get("aliases", []) or []
            title = f"#{attr['id']} | {attr['name']} | {len(aliases_list)} aliases | {'active' if attr['active'] else 'inactive'}"
            with st.expander(title, expanded=False):
                st.write("#### Edit canonical")
                with st.form(f"edit_attr_{attr['id']}"):
                    edit_name = st.text_input("Name", value=attr.get("name") or "", key=f"edit_name_{attr['id']}")
                    edit_slug = st.text_input("Slug", value=attr.get("slug") or "", key=f"edit_slug_{attr['id']}")
                    edit_description = st.text_area(
                        "Description",
                        value=attr.get("description") or "",
                        height=90,
                        key=f"edit_description_{attr['id']}",
                    )
                    edit_category = st.text_input(
                        "Category hint",
                        value=attr.get("category_hint") or "",
                        key=f"edit_category_{attr['id']}",
                    )
                    edit_samples = st.text_area(
                        "Sample values, one per line or comma separated",
                        value=join_values(attr.get("sample_values", [])),
                        height=100,
                        key=f"edit_samples_{attr['id']}",
                    )
                    edit_active = st.checkbox("Active", value=bool(attr.get("active")), key=f"edit_active_{attr['id']}")
                    save_attr = st.form_submit_button("Save canonical changes")

                if save_attr:
                    try:
                        api_patch(
                            f"/canonical/{attr['id']}",
                            {
                                "name": edit_name,
                                "slug": edit_slug or None,
                                "description": edit_description or None,
                                "category_hint": edit_category,
                                "sample_values": split_values(edit_samples),
                                "active": edit_active,
                            },
                        )
                        st.success("Canonical attribute updated.")
                        st.rerun()
                    except Exception as exc:
                        show_error(exc)

                col_add, col_manage = st.columns([1, 2])
                with col_add:
                    st.write("#### Add alias")
                    with st.form(f"add_alias_{attr['id']}"):
                        add_alias_raw = st.text_input("New alias", key=f"add_alias_raw_{attr['id']}")
                        add_alias_source = st.text_input("Source", value="manual", key=f"add_alias_source_{attr['id']}")
                        add_alias_confidence = st.number_input(
                            "Confidence",
                            min_value=0.0,
                            max_value=1.0,
                            value=1.0,
                            step=0.01,
                            key=f"add_alias_confidence_{attr['id']}",
                        )
                        add_alias_approved = st.checkbox("Approved", value=True, key=f"add_alias_approved_{attr['id']}")
                        add_alias_submit = st.form_submit_button("Add alias")
                    if add_alias_submit:
                        try:
                            api_post(
                                "/aliases",
                                {
                                    "canonical_id": attr["id"],
                                    "alias_raw": add_alias_raw,
                                    "source": add_alias_source or "manual",
                                    "confidence": add_alias_confidence,
                                    "approved": add_alias_approved,
                                },
                            )
                            st.success("Alias added.")
                            st.rerun()
                        except Exception as exc:
                            show_error(exc)

                with col_manage:
                    st.write("#### Edit / delete alias")
                    if aliases_list:
                        alias_options = {
                            f"#{a['id']} | {a['alias_raw']} | norm: {a['alias_norm']}": a
                            for a in aliases_list
                        }
                        selected_alias_label = st.selectbox(
                            "Select alias",
                            list(alias_options.keys()),
                            key=f"select_alias_{attr['id']}",
                        )
                        selected_alias = alias_options[selected_alias_label]

                        with st.form(f"edit_alias_{selected_alias['id']}"):
                            alias_raw = st.text_input(
                                "Alias raw",
                                value=selected_alias.get("alias_raw") or "",
                                key=f"alias_raw_{selected_alias['id']}",
                            )
                            alias_source = st.text_input(
                                "Source",
                                value=selected_alias.get("source") or "manual",
                                key=f"alias_source_{selected_alias['id']}",
                            )
                            alias_confidence = st.number_input(
                                "Confidence",
                                min_value=0.0,
                                max_value=1.0,
                                value=float(selected_alias.get("confidence", 1.0)),
                                step=0.01,
                                key=f"alias_confidence_{selected_alias['id']}",
                            )
                            alias_approved = st.checkbox(
                                "Approved",
                                value=bool(selected_alias.get("approved")),
                                key=f"alias_approved_{selected_alias['id']}",
                            )
                            save_alias = st.form_submit_button("Save alias changes")
                        if save_alias:
                            try:
                                api_patch(
                                    f"/aliases/{selected_alias['id']}",
                                    {
                                        "alias_raw": alias_raw,
                                        "source": alias_source or "manual",
                                        "confidence": alias_confidence,
                                        "approved": alias_approved,
                                    },
                                )
                                st.success("Alias updated.")
                                st.rerun()
                            except Exception as exc:
                                show_error(exc)

                        st.warning("Delete removes this alias permanently. Exact matching for that alias will stop working.")
                        if st.button("Delete selected alias", key=f"delete_alias_{selected_alias['id']}"):
                            try:
                                api_delete(f"/aliases/{selected_alias['id']}", reindex=True)
                                st.success("Alias deleted.")
                                st.rerun()
                            except Exception as exc:
                                show_error(exc)
                    else:
                        st.info("No aliases yet. Add one from the left side.")

                st.divider()
                st.write("#### Deactivate")
                st.caption("Deactivate hides this canonical from normal matching when active=True filters are used. It does not delete historical reviews/logs.")
                if attr.get("active"):
                    if st.button("Deactivate this canonical", key=f"deactivate_{attr['id']}"):
                        try:
                            api_delete(f"/canonical/{attr['id']}")
                            st.success("Canonical deactivated.")
                            st.rerun()
                        except Exception as exc:
                            show_error(exc)
                else:
                    st.info("This canonical is inactive. Turn on the Active checkbox and save to reactivate it.")

    except Exception as exc:
        show_error(exc)

with tools_tab:
    st.subheader("Maintenance")

    st.write("Starter data")
    st.caption("Creates a few initial canonical attributes such as رم, پردازنده, توضیحات, and حافظه داخلی.")
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

    st.divider()
    st.write("Rebuild embeddings after bulk imports, alias edits, or config/model changes.")
    if st.button("Reindex all embeddings"):
        try:
            result = api_post("/embeddings/reindex")
            st.success(result)
        except Exception as exc:
            show_error(exc)

    st.divider()
    st.write("Health")
    if st.button("Check API health"):
        try:
            st.json(api_get("/health"))
        except Exception as exc:
            show_error(exc)
