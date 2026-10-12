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

import streamlit as st

from pipeline.browse import list_jobs, distinct_role_types
from pipeline.analyze import analyze_cv

st.set_page_config(page_title="Job Market Radar", page_icon="\U0001F4CA", layout="wide")

st.title("Job Market Radar")
st.caption("Live German tech job postings, RAG-powered CV matching, and a genuine entry-level detector.")

page = st.sidebar.radio("Page", ["Browse Jobs", "CV Gap Analysis"])
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
            "Min. years (detected)": j["min_years_required"] if j["min_years_required"] is not None else "-",
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


if page == "Browse Jobs":
    render_browse_jobs()
else:
    render_cv_analysis()
