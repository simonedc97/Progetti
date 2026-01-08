import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import os
import calendar

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="RM Insurance Planner", layout="wide")

DATA_PATH = "data/planner.csv"
EOM_PATH = "data/eom_activities.csv"

PROJECT_COLUMNS = [
    "Area", "Project", "Task", "Owner",
    "Progress", "Priority", "Release Date", "Due Date",
    "GR / Mail Object"
]

EOM_BASE_COLUMNS = [
    "Area", "ID Macro", "ID Micro",
    "Activity", "Frequency", "Files", "🗑️ Delete"
]

# =========================
# SESSION STATE
# =========================
if "section" not in st.session_state:
    st.session_state.section = "Projects"
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "add_project" not in st.session_state:
    st.session_state.add_project = False
if "task_boxes" not in st.session_state:
    st.session_state.task_boxes = 1
if "delete_mode" not in st.session_state:
    st.session_state.delete_mode = False
if "confirm_delete_project" not in st.session_state:
    st.session_state.confirm_delete_project = None
if "confirm_delete_task" not in st.session_state:
    st.session_state.confirm_delete_task = None
if "show_completed_months" not in st.session_state:
    st.session_state.show_completed_months = False
if "eom_edit_mode" not in st.session_state:
    st.session_state.eom_edit_mode = False
if "confirm_delete_eom" not in st.session_state:
    st.session_state.confirm_delete_eom = None

# =========================
# HELPERS
# =========================
progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

def save_csv(df, path):
    os.makedirs("data", exist_ok=True)
    df.to_csv(path, index=False)

def load_csv(path, columns, date_cols=None):
    if os.path.exists(path):
        if date_cols:
            return pd.read_csv(path, parse_dates=date_cols)
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)

# =========================
# LOAD DATA
# =========================
df = load_csv(
    DATA_PATH,
    PROJECT_COLUMNS,
    date_cols=["Release Date", "Due Date"]
)

for col in PROJECT_COLUMNS:
    if col not in df.columns:
        df[col] = ""

# =========================
# HEADER
# =========================
st.title("🗂️ RM Insurance Planner")

nav1, nav2 = st.columns(2)
with nav1:
    if st.button("📊 Projects Activities", use_container_width=True,
                 type="primary" if st.session_state.section == "Projects" else "secondary"):
        st.session_state.section = "Projects"
        st.rerun()
with nav2:
    if st.button("📅 End of Month Activities", use_container_width=True,
                 type="primary" if st.session_state.section == "EOM" else "secondary"):
        st.session_state.section = "EOM"
        st.rerun()

st.divider()

# ======================================================
# 📊 PROJECTS ACTIVITIES
# ======================================================
if st.session_state.section == "Projects":

    col_title, col_actions = st.columns([6, 4])
    with col_title:
        st.subheader("📊 Projects Activities")

    with col_actions:
        c1, c2, c3 = st.columns(3)
        if c1.button("✏️ Edit"):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()
        if c2.button("➕ Project"):
            st.session_state.add_project = True
            st.session_state.task_boxes = 1
            st.rerun()
        if c3.button("➖ Delete"):
            st.session_state.delete_mode = not st.session_state.delete_mode
            st.rerun()

    # ======================================================
    # ➕ ADD PROJECT
    # ======================================================
    if st.session_state.add_project:
        st.subheader("➕ New Project")

        area = st.text_input("Area")
        project = st.text_input("Project name")

        tasks = []
        for i in range(st.session_state.task_boxes):
            with st.container():
                st.markdown(f"**Task {i+1}**")
                t = st.text_input("Task", key=f"new_task_{i}")
                o = st.text_input("Owner", key=f"new_owner_{i}")
                gr = st.text_area("GR / Mail Object", key=f"new_gr_{i}")
                p = st.selectbox("Status", progress_values, key=f"new_prog_{i}")
                pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"new_prio_{i}")
                rd = st.date_input("Release Date", value=date.today(), key=f"new_rel_{i}")
                dd = st.date_input("Due Date", value=date.today(), key=f"new_due_{i}")
                if t:
                    tasks.append((t, o, gr, p, pr, rd, dd))
                st.divider()

        if st.button("Create project", type="primary"):
            rows = []
            for t, o, gr, p, pr, rd, dd in tasks:
                rows.append({
                    "Area": area,
                    "Project": project,
                    "Task": t,
                    "Owner": o,
                    "GR / Mail Object": gr,
                    "Progress": p,
                    "Priority": pr,
                    "Release Date": pd.Timestamp(rd),
                    "Due Date": pd.Timestamp(dd)
                })
            df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
            save_csv(df, DATA_PATH)
            st.session_state.add_project = False
            st.rerun()

    # ======================================================
    # 📁 PROJECT VIEW
    # ======================================================
    if len(df) > 0:
        for project, proj_df in df.groupby("Project"):
            completion = int(proj_df["Progress"].map(progress_score).mean() * 100)
            area = proj_df["Area"].iloc[0]

            expand = st.expander(f"📁 {project} ({area}) — {completion}%", expanded=True)

            with expand:
                st.progress(completion / 100)

                # VIEW MODE
                if not st.session_state.edit_mode:
                    for idx, r in proj_df.iterrows():
                        st.markdown(f"### {r['Task']}")
                        st.write(f"👤 Owner: {r['Owner'] or '—'}")
                        st.write(f"🗓️ Release: {r['Release Date'].date()} | Due: {r['Due Date'].date()}")
                        if r["GR / Mail Object"]:
                            st.info(f"📧 **GR / Mail Object**: {r['GR / Mail Object']}")

                        status = st.radio(
                            "Status",
                            progress_values,
                            index=progress_values.index(r["Progress"]),
                            key=f"status_{idx}",
                            horizontal=True
                        )
                        if status != r["Progress"]:
                            df.loc[idx, "Progress"] = status
                            save_csv(df, DATA_PATH)
                            st.rerun()
                        st.divider()

                # EDIT MODE
                if st.session_state.edit_mode:
                    for idx, r in proj_df.iterrows():
                        with st.container():
                            st.text_input("Task", r["Task"], key=f"t_{idx}")
                            st.text_input("Owner", r["Owner"], key=f"o_{idx}")
                            st.text_area("GR / Mail Object", r["GR / Mail Object"], key=f"gr_{idx}")
                            st.date_input("Release Date", r["Release Date"], key=f"rd_{idx}")
                            st.date_input("Due Date", r["Due Date"], key=f"dd_{idx}")
                            st.selectbox(
                                "Status", progress_values,
                                index=progress_values.index(r["Progress"]),
                                key=f"p_{idx}"
                            )
                            st.selectbox(
                                "Priority", ["Low", "Important", "Urgent"],
                                index=["Low", "Important", "Urgent"].index(r["Priority"]),
                                key=f"pr_{idx}"
                            )
                            st.divider()

    st.divider()
    st.caption(f"📊 Total projects: {df['Project'].nunique()} | Tasks: {len(df)}")
