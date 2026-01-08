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
# SESSION STATE INIT
# -------------------------
st.session_state.setdefault("user", None)
st.session_state.setdefault("edit_mode", False)
st.session_state.setdefault("add_project", False)
st.session_state.setdefault("task_boxes", 1)

# ======================================================
# 🔐 LOGIN (BOX STYLE)
# ======================================================
if st.session_state.user is None:
    st.markdown("<h1 style='text-align:center'>🔐 Login</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    cols = st.columns(4)

    for col, user in zip(cols, USERS):
        with col:
            with st.container(border=True):
                st.markdown(
                    f"<h3 style='text-align:center'>{user}</h3>",
                    unsafe_allow_html=True
                )
                if st.button("Login", key=f"login_{user}", use_container_width=True):
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
        st.session_state.task_boxes = 1

# ======================================================
# ➕ ADD PROJECT
# ======================================================
if st.session_state.add_project:
    st.subheader("➕ New Project")

    area = st.text_input("Area")
    project = st.text_input("Project name")

    st.markdown("### Tasks")

    tasks_data = []

    for i in range(st.session_state.task_boxes):
        with st.container(border=True):
            task = st.text_input("Task name", key=f"new_task_{i}")
            owner = st.text_input("Owner (optional)", key=f"new_owner_{i}")
            progress = st.selectbox(
                "Status", ["Not started", "In progress", "Completed"],
                key=f"new_progress_{i}"
            )
            priority = st.selectbox(
                "Priority", ["Low", "Important", "Urgent"],
                key=f"new_priority_{i}"
            )
            due = st.date_input("Due Date", value=date.today(), key=f"new_due_{i}")

            if task:
                tasks_data.append({
                    "Task": task,
                    "Owner": owner,
                    "Progress": progress,
                    "Priority": priority,
                    "Due Date": due
                })

    col_add, col_create, col_cancel = st.columns(3)

    with col_add:
        if st.button("➕ Add task"):
            st.session_state.task_boxes += 1
            st.rerun()

    with col_create:
        if st.button("Create project"):
            for t in tasks_data:
                df = pd.concat([df, pd.DataFrame([{
                    "Area": area,
                    "Project": project,
                    "Task": t["Task"],
                    "Owner": t["Owner"],
                    "Progress": t["Progress"],
                    "Priority": t["Priority"],
                    "Release Date": date.today(),
                    "Due Date": t["Due Date"]
                }])], ignore_index=True)

            os.makedirs("data", exist_ok=True)
            df.to_csv(DATA_PATH, index=False)
            st.session_state.add_project = False
            st.success("Project created!")
            st.rerun()

    with col_cancel:
        if st.button("Cancel"):
            st.session_state.add_project = False
            st.session_state.task_boxes = 1
            st.rerun()

# ======================================================
# 📁 PROJECT VIEW
# ======================================================
if not st.session_state.add_project:
    if df.empty:
        st.info("No projects yet.")
    else:
        for project, proj_df in df.groupby("Project"):

            scores = proj_df["Progress"].map(progress_score).fillna(0)
            completion = int(scores.mean() * 100)

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

                for _, row in proj_df.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['Task']}**")
                        st.write(f"Owner: {row['Owner'] or '—'}")
                        st.write(f"Priority: {row['Priority']}")
                        st.write(f"{status_icon[row['Progress']]} {row['Progress']}")
                        st.write(f"Due: {row['Due Date'].date()}")

                # ✏️ EDIT PROJECT
                if st.session_state.edit_mode:
                    st.markdown("### ✏️ Edit project")

                    new_area = st.text_input("Area", area, key=f"area_{project}")
                    new_name = st.text_input("Project name", project, key=f"name_{project}")

                    key_boxes = f"edit_boxes_{project}"
                    st.session_state.setdefault(key_boxes, 1)
                    new_tasks = []

                    for i in range(st.session_state[key_boxes]):
                        with st.container(border=True):
                            task = st.text_input("Task name", key=f"edit_task_{project}_{i}")
                            owner = st.text_input("Owner (optional)", key=f"edit_owner_{project}_{i}")
                            progress = st.selectbox(
                                "Status", ["Not started", "In progress", "Completed"],
                                key=f"edit_progress_{project}_{i}"
                            )
                            priority = st.selectbox(
                                "Priority", ["Low", "Important", "Urgent"],
                                key=f"edit_priority_{project}_{i}"
                            )
                            due = st.date_input(
                                "Due Date", value=date.today(),
                                key=f"edit_due_{project}_{i}"
                            )

                            if task:
                                new_tasks.append({
                                    "Task": task,
                                    "Owner": owner,
                                    "Progress": progress,
                                    "Priority": priority,
                                    "Due Date": due
                                })

                    col_add, col_save, col_cancel = st.columns(3)

                    with col_add:
                        if st.button("➕ Add task", key=f"add_task_{project}"):
                            st.session_state[key_boxes] += 1
                            st.rerun()

                    with col_save:
                        if st.button("Save changes", key=f"save_{project}"):
                            df.loc[df["Project"] == project, ["Area", "Project"]] = [new_area, new_name]

                            for t in new_tasks:
                                df = pd.concat([df, pd.DataFrame([{
                                    "Area": new_area,
                                    "Project": new_name,
                                    "Task": t["Task"],
                                    "Owner": t["Owner"],
                                    "Progress": t["Progress"],
                                    "Priority": t["Priority"],
                                    "Release Date": date.today(),
                                    "Due Date": t["Due Date"]
                                }])], ignore_index=True)

                            df.to_csv(DATA_PATH, index=False)
                            st.session_state.edit_mode = False
                            st.success("Project updated")
                            st.rerun()

                    with col_cancel:
                        if st.button("Cancel", key=f"cancel_{project}"):
                            st.session_state.edit_mode = False
                            st.session_state[key_boxes] = 1
                            st.rerun()
