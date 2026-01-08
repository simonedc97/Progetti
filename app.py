import streamlit as st
import pandas as pd
from datetime import date
import os
import hashlib

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Team Projects Planner", layout="wide")

DATA_PATH = "data/planner.csv"
USERS = ["Elena", "Giulia", "Simone", "Paolo"]

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
# SESSION STATE
# -------------------------
st.session_state.setdefault("user", None)
st.session_state.setdefault("edit_mode", False)
st.session_state.setdefault("add_project", False)

# -------------------------
# LOGIN
# -------------------------
if st.session_state.user is None:
    st.title("🔐 Login")

    user = st.selectbox("Select user", USERS)

    if st.button("Login"):
        st.session_state.user = user
        st.rerun()

    st.stop()

# -------------------------
# LOAD DATA
# -------------------------
if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH, parse_dates=["Release Date", "Due Date"])
else:
    df = pd.DataFrame(columns=COLUMNS)

# -------------------------
# HELPERS
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

def split_tasks(text):
    return [t.strip() for t in text.split("\n") if t.strip()]

# -------------------------
# HEADER
# -------------------------
col_title, col_actions = st.columns([8, 2])

with col_title:
    st.title("📊 Team Projects Planner")
    st.caption(f"Logged in as **{st.session_state.user}**")

with col_actions:
    if st.button("✏️ Edit"):
        st.session_state.edit_mode = not st.session_state.edit_mode
    if st.button("➕ Project"):
        st.session_state.add_project = True

# -------------------------
# ADD PROJECT (MULTI-TASK)
# -------------------------
if st.session_state.add_project:
    with st.form("add_project"):
        st.subheader("➕ New Project")

        area = st.text_input("Area")
        project = st.text_input("Project name")

        tasks_text = st.text_area(
            "Tasks (one per line)",
            placeholder="Task 1\nTask 2\nTask 3"
        )

        owner = st.text_input("Owner", value=st.session_state.user)
        priority = st.selectbox("Priority", ["Low", "Important", "Urgent"])
        due = st.date_input("Due Date", value=date.today())

        if st.form_submit_button("Create project"):
            tasks = split_tasks(tasks_text)

            for task in tasks:
                df = pd.concat([df, pd.DataFrame([{
                    "Area": area,
                    "Project": project,
                    "Task": task,
                    "Owner": owner,
                    "Progress": "Not started",
                    "Priority": priority,
                    "Release Date": date.today(),
                    "Due Date": due
                }])], ignore_index=True)

            os.makedirs("data", exist_ok=True)
            df.to_csv(DATA_PATH, index=False)
            st.session_state.add_project = False
            st.success("Project created!")
            st.rerun()

# -------------------------
# PROJECT VIEW
# -------------------------
if df.empty:
    st.info("No projects yet.")
else:
    for project, proj_df in df.groupby("Project"):

        scores = proj_df["Progress"].map(progress_score).fillna(0)
        completion = int(scores.mean() * 100) if not scores.empty else 0

        area = proj_df["Area"].iloc[0]
        color = area_color(area)

        with st.expander(f"📁 {project} — {completion}% completed"):

            st.markdown(
                f"""
                <div style="padding:10px;border-radius:8px;background-color:{color}20">
                    <b>Area:</b> {area}<br>
                    <b>Completion:</b> {completion}%
                </div>
                """,
                unsafe_allow_html=True
            )

            st.progress(completion / 100)

            # TASK LIST
            for _, row in proj_df.iterrows():
                col1, col2, col3, col4, col5 = st.columns([3,2,2,2,1])
                col1.markdown(f"**{row['Task']}**")
                col2.write(row["Owner"])
                col3.write(row["Priority"])
                col4.write(f"{status_icon[row['Progress']]} {row['Progress']}")
                col5.write(row["Due Date"].date())

            # -------------------------
            # ADD TASK (MULTILINE)
            # -------------------------
            with st.form(f"add_task_{project}"):
                st.markdown("### ➕ Add tasks")

                tasks_text = st.text_area(
                    "Tasks (one per line)",
                    placeholder="New task 1\nNew task 2"
                )

                owner = st.text_input("Owner", value=st.session_state.user)
                priority = st.selectbox("Priority", ["Low", "Important", "Urgent"])
                progress = st.selectbox("Status", ["Not started", "In progress", "Completed"])
                due = st.date_input("Due Date", value=date.today())

                if st.form_submit_button("Add"):
                    tasks = split_tasks(tasks_text)

                    for task in tasks:
                        df = pd.concat([df, pd.DataFrame([{
                            "Area": area,
                            "Project": project,
                            "Task": task,
                            "Owner": owner,
                            "Progress": progress,
                            "Priority": priority,
                            "Release Date": date.today(),
                            "Due Date": due
                        }])], ignore_index=True)

                    df.to_csv(DATA_PATH, index=False)
                    st.rerun()

            # -------------------------
            # EDIT PROJECT (MULTI-TASK)
            # -------------------------
            if st.session_state.edit_mode:
                st.markdown("### ✏️ Edit project")

                new_area = st.text_input("Area", area, key=f"area_{project}")
                new_name = st.text_input("Project name", project, key=f"name_{project}")

                new_tasks = st.text_area(
                    "Add new tasks (one per line)",
                    placeholder="Extra task 1\nExtra task 2",
                    key=f"tasks_{project}"
                )

                if st.button("Save changes", key=f"save_{project}"):
                    df.loc[df["Project"] == project, "Area"] = new_area
                    df.loc[df["Project"] == project, "Project"] = new_name

                    for task in split_tasks(new_tasks):
                        df = pd.concat([df, pd.DataFrame([{
                            "Area": new_area,
                            "Project": new_name,
                            "Task": task,
                            "Owner": st.session_state.user,
                            "Progress": "Not started",
                            "Priority": "Low",
                            "Release Date": date.today(),
                            "Due Date": date.today()
                        }])], ignore_index=True)

                    df.to_csv(DATA_PATH, index=False)
                    st.success("Project updated")
                    st.rerun()
