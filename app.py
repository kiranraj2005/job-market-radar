"""
app.py

Job Market Radar - Streamlit front end.

Step 3 (this version): two pages now - Browse Jobs (EL-1 filter, from
step 2) and CV Gap Analysis, which wires up analyze_cv() (RAG-4b)
behind a text box so the citation-grounded gap analysis has an actual
UI instead of only living in a terminal.

Run with:
    streamlit run app.py
"""

import pandas as pd
import streamlit as st

from pipeline.browse import list_jobs, distinct_role_types
from pipeline.analyze import analyze_cv
from pipeline.trends import get_trend_history

st.set_page_config(page_title="Job Market Radar", page_icon="\U0001F4CA", layout="wide")

st.title("Job Market Radar")
st.caption("Live German tech job postings, RAG-powered CV matching, and a genuine entry-level detector.")

page = st.sidebar.radio("Page", ["Browse Jobs", "CV Gap Analysis", "Trends"])
st.sidebar.divider()


def render_browse_jobs():
    st.sidebar.header("Filters")
    entry_level_only = st.sidebar.checkbox(
        "Genuinely entry-level only",
        help="Keeps only postings EL-1 did NOT flag as secretly demanding prior experience.",
    )
    remote_only = st.sidebar.checkbox("Remote only")

    role_types = ["All"] + distinct_role_types()
    selected_role = st.sidebar.selectbox("Role type", role_types)
    role_filter = None if selected_role == "All" else selected_role

    jobs = list_jobs(
        entry_level_only=entry_level_only,
        role_type=role_filter,
        remote_only=remote_only,
    )

    st.subheader("Browse postings")
    st.caption(f"{len(jobs)} posting(s) match the current filters.")

    if not jobs:
        st.info("No postings match these filters. Try loosening them.")
        return

    table_rows = [
        {
            "Title": j["title"],
            "Company": j["company"],
            "City": j["city"],
            "Remote": "Yes" if j["remote"] else "No",
            "Role type": j["role_type"],
            "Posted": j["posted_at"],
            "Min. years (detected)": str(j["min_years_required"]) if j["min_years_required"] is not None else "-",
            "Mismatch flagged": "⚠️ Yes" if j["experience_mismatch"] else "No",
            "Posting": j["posting_url"],
        }
        for j in jobs
    ]
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Posting": st.column_config.LinkColumn("Posting", display_text="Open ↗"),
        },
    )


def render_cv_analysis():
    st.subheader("CV gap analysis")
    st.caption(
        "Paste your CV text below. This retrieves the 5 most relevant real postings "
        "from the database and asks Gemini to name specific skill gaps, citing exactly "
        "which posting(s) support each claim."
    )

    cv_text = st.text_area("Your CV (plain text)", height=250, placeholder="Paste your CV content here...")
    k = st.slider("Number of postings to compare against", min_value=3, max_value=10, value=5)

    if st.button("Analyze", type="primary", disabled=not cv_text.strip()):
        with st.spinner("Retrieving matching postings and generating analysis..."):
            try:
                answer, citations = analyze_cv(cv_text, k=k)
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                return

        st.markdown("### Gap analysis")
        st.markdown(answer)

        st.markdown("### Sources")
        for i, c in enumerate(citations, start=1):
            st.markdown(f"**[{i}]** [{c['title']} @ {c['company']}]({c['url']}) — posted {c['posted_at']}")


def render_trends():
    st.subheader("Market trends")
    st.caption(
        "Each pipeline run captures one snapshot of the dataset. These charts need a few "
        "runs spread over time to become meaningful \u2014 with only one or two snapshots so "
        "far, expect a short, flat line rather than a real trend yet."
    )

    history = get_trend_history()
    if not history:
        st.info("No snapshots yet. Run the pipeline at least once to capture the first one.")
        return

    df = pd.DataFrame(history).set_index("captured_at")

    # A line chart needs at least 2 points to draw a line between - with just
    # one snapshot, Vega-Lite (what st.line_chart uses under the hood) can't
    # infer a sensible axis range and renders an ugly, confusing artifact
    # instead of nothing. Below that threshold, show the one real number
    # plainly with st.metric() instead; switch to the real line chart once
    # there's an actual trend to show.
    enough_history = len(history) >= 2

    st.markdown("**Genuine entry-level mismatch rate over time (%)**")
    if enough_history:
        st.line_chart(df["entry_level_mismatch_rate"])
    else:
        st.metric("Latest snapshot", f"{history[-1]['entry_level_mismatch_rate']}%")
        st.caption("Only one snapshot so far - run the pipeline again later to start a real trend line.")

    st.markdown("**Average detected minimum years required, over time**")
    if enough_history:
        st.line_chart(df["avg_min_years_required"])
    else:
        st.metric("Latest snapshot", f"{history[-1]['avg_min_years_required']} years")
        st.caption("Only one snapshot so far - run the pipeline again later to start a real trend line.")

    latest = history[-1]
    st.markdown(f"**Skill demand \u2014 latest snapshot ({latest['captured_at']})**")
    skill_df = pd.DataFrame(
        sorted(latest["skill_counts"].items(), key=lambda x: -x[1]),
        columns=["Skill", "Postings"],
    ).set_index("Skill")
    st.bar_chart(skill_df)

    st.markdown(f"**Role-type distribution \u2014 latest snapshot ({latest['captured_at']})**")
    role_df = pd.DataFrame(
        sorted(latest["role_type_counts"].items(), key=lambda x: -x[1]),
        columns=["Role type", "Postings"],
    ).set_index("Role type")
    st.bar_chart(role_df)


if page == "Browse Jobs":
    render_browse_jobs()
elif page == "CV Gap Analysis":
    render_cv_analysis()
else:
    render_trends()
