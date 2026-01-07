import streamlit as st
import pandas as pd
from datetime import date
import os
import hashlib

st.set_page_config(page_title="Team Projects Planner", layout="wide")

DATA_PATH = "data/planner.csv"

COLUMNS = [
    "Area",
    "Project",
    "Task",
    "Owner",
    "Progress",
    "Priority",
    "Release Date",
    "Due Date"
]

# -------------------------
# Load data
# -------------------------
if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH, parse_dates=["Release Date", "Due Date"])
else:
    df = pd.DataFrame(columns=COLUMNS)

# -------------------------
# Sidebar – Filters
# -------------------------
st.sidebar.title("🔎 Filters")

area_filter = st.sidebar.multiselect(
    "Area",
    sorted(df["Area"].dropna().unique())
)

project_filter = st.sidebar.multiselect(
    "Project",
    sorted(df["Project"].dropna().unique())
)

task_status_filter = st.sidebar.multiselect(
    "Task status",
    ["Not started", "In progress", "Completed"]
)

filtered_df = df.copy()

if area_filter:
    filtered_df = filtered_df[filtered_df["Area"].isin(area_filter)]
if project_filter:
    filtered_df = filtered_df[filtered_df["Project"].isin(project_filter)]
if task_status_filter:
    filtered_df = filtered_df[filtered_df["Progress"].isin(task_status_filter)]

# -------------------------
# Helper functions
# -------------------------
progress_score = {
    "Not started": 0,
    "In progress": 0.5,
    "Completed": 1
}

status_icon = {
    "Completed": "🟢",
    "In progress": "🟡",
    "Not started": "🔴"
}

def area_color(area):
    h = int(hashlib.md5(area.encode()).hexdigest(), 16)
    return f"#{h % 0xFFFFFF:06x}"

# -------------------------
# Title
# -------------------------
st.title("📊 Team Projects Planner")
st.caption("Project-based task tracking with visual progress")

# -------------------------
# PROJECT VIEW (COLLAPSIBLE)
# -------------------------
if not filtered_df.empty:

    for project, proj_df in filtered_df.groupby("Project"):

        scores = proj_df["Progress"].map(progress_score).fillna(0)
        completion = int(scores.mean() * 100) if not scores.empty else 0

        area = proj_df["Area"].iloc[0]
        color = area_color(area)

        with st.expander(f"📁 {project} — {completion}% completed", expanded=False):

            st.markdown(
                f"""
                <div style="padding:10px; border-radius:8px; background-color:{color}20;">
                    <b>Area:</b> {area}<br>
                    <b>Completion:</b> {completion}%
                </div>
                """,
                unsafe_allow_html=True
            )

            st.progress(completion / 100)

            # Task table inside project
            display_df = proj_df.copy()
            display_df["Status"] = (
                display_df["Progress"].map(status_icon)
                + " "
                + display_df["Progress"]
            )

            display_df = display_df[
                ["Status", "Task", "Owner", "Priority", "Due Date"]
            ]

            st.dataframe(display_df, use_container_width=True)

else:
    st.info("No data to display with current filters.")

# -------------------------
# EDIT MODE
# -------------------------
st.subheader("✏️ Edit tasks")

edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Progress": st.column_config.SelectboxColumn(
            options=["Not started", "In progress", "Completed"]
        ),
        "Priority": st.column_config.SelectboxColumn(
            options=["Low", "Important", "Urgent"]
        ),
        "Release Date": st.column_config.DateColumn(),
        "Due Date": st.column_config.DateColumn()
    }
)

if st.button("💾 Save changes"):
    os.makedirs("data", exist_ok=True)
    edited_df.to_csv(DATA_PATH, index=False)
    st.success("Saved successfully!")
