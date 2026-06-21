import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Attribute AI Resolver", layout="wide")
st.title("Attribute AI Resolver")
st.caption(f"API: {API_BASE_URL}")


def api_get(path: str, **params: Any) -> Any:
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict | None = None) -> Any:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=120)
    response.raise_for_status()
    return response.json()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def show_error(exc: Exception) -> None:
    if isinstance(exc, requests.HTTPError):
        try:
            st.error(exc.response.json())
        except Exception:
            st.error(str(exc))
    else:
        st.error(str(exc))


try:
    stats = api_get("/stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Canonical", stats["canonical_count"])
    c2.metric("Aliases", stats["alias_count"])
    c3.metric("Embeddings", stats["embedding_count"])
    c4.metric("Open reviews", stats["open_review_count"])
except Exception as exc:
    show_error(exc)

resolve_tab, review_tab, attributes_tab, tools_tab = st.tabs(
    ["Resolve tester", "Review queue", "Attributes", "Tools"]
)

with resolve_tab:
    st.subheader("Test resolver")
    with st.form("resolve_form"):
        raw_name = st.text_input("Raw attribute name", value="Ram")
        category = st.text_input("Category/context", value="laptop")
        sample_values_raw = st.text_input("Sample values, comma separated", value="8GB, 16GB, DDR4")
        create_review = st.checkbox("Create review item for uncertain results", value=True)
        submitted = st.form_submit_button("Resolve")

    if submitted:
        try:
            result = api_post(
                "/resolve",
                {
                    "raw_name": raw_name,
                    "category": category,
                    "sample_values": split_csv(sample_values_raw),
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
    refresh = st.button("Refresh reviews")

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
                        st.write("Candidates")
                        st.dataframe(pd.DataFrame(candidates), use_container_width=True)
                    else:
                        st.info("No semantic candidates.")

                if item["status"] == "open":
                    candidates = item.get("candidates_snapshot") or []
                    if candidates:
                        st.write("Approve as existing attribute")
                        cols = st.columns(min(len(candidates), 4))
                        for idx, cand in enumerate(candidates[:4]):
                            with cols[idx % len(cols)]:
                                label = f"Approve {cand['name']} ({cand['score']:.3f})"
                                if st.button(label, key=f"approve_{item['id']}_{cand['canonical_id']}"):
                                    try:
                                        api_post(
                                            f"/review/{item['id']}/approve",
                                            {
                                                "canonical_id": cand["canonical_id"],
                                                "alias_raw": item["input_raw"],
                                                "notes": "Approved from dashboard",
                                            },
                                        )
                                        st.success("Approved.")
                                        st.rerun()
                                    except Exception as exc:
                                        show_error(exc)

                    with st.form(f"create_new_{item['id']}"):
                        st.write("Create new canonical attribute")
                        new_name = st.text_input("Name", value=item["input_raw"], key=f"new_name_{item['id']}")
                        new_slug = st.text_input("Slug optional", value="", key=f"new_slug_{item['id']}")
                        new_aliases = st.text_input("Extra aliases, comma separated", value="", key=f"new_aliases_{item['id']}")
                        create_submitted = st.form_submit_button("Create new attribute")
                        if create_submitted:
                            try:
                                api_post(
                                    f"/review/{item['id']}/create-attribute",
                                    {
                                        "name": new_name,
                                        "slug": new_slug or None,
                                        "aliases": split_csv(new_aliases),
                                        "notes": "Created from dashboard",
                                    },
                                )
                                st.success("Created.")
                                st.rerun()
                            except Exception as exc:
                                show_error(exc)

                    if st.button("Ignore", key=f"ignore_{item['id']}"):
                        try:
                            api_post(f"/review/{item['id']}/ignore", {"notes": "Ignored from dashboard"})
                            st.success("Ignored.")
                            st.rerun()
                        except Exception as exc:
                            show_error(exc)
    except Exception as exc:
        show_error(exc)

with attributes_tab:
    st.subheader("Canonical attributes")
    with st.form("create_attribute_form"):
        name = st.text_input("Name")
        slug = st.text_input("Slug optional")
        category_hint = st.text_input("Category hint optional")
        aliases = st.text_input("Aliases, comma separated")
        sample_values = st.text_input("Sample values, comma separated")
        create_attr = st.form_submit_button("Create attribute")

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
        except Exception as exc:
            show_error(exc)

    q = st.text_input("Search canonical attributes", value="")
    try:
        attrs = api_get("/canonical", q=q or None, active=True, limit=200)
        rows = []
        for attr in attrs:
            rows.append(
                {
                    "id": attr["id"],
                    "name": attr["name"],
                    "slug": attr["slug"],
                    "aliases": ", ".join(a["alias_raw"] for a in attr.get("aliases", [])),
                    "samples": ", ".join(str(v) for v in attr.get("sample_values", [])),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    except Exception as exc:
        show_error(exc)

with tools_tab:
    st.subheader("Maintenance")
    st.write("Rebuild embeddings after bulk imports or config/model changes.")
    if st.button("Reindex all embeddings"):
        try:
            result = api_post("/embeddings/reindex")
            st.success(result)
        except Exception as exc:
            show_error(exc)

    st.write("Health")
    if st.button("Check API health"):
        try:
            st.json(api_get("/health"))
        except Exception as exc:
            show_error(exc)
