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
st.session_state.setdefault("task_boxes", 1)
st.session_state.setdefault("delete_mode", False)
st.session_state.setdefault("confirm_delete_project", None)
st.session_state.setdefault("confirm_delete_task", None)

# ======================================================
# 🔐 LOGIN – BOX CLICK
# ======================================================
if st.session_state.user is None:
    st.markdown("<h1 style='text-align:center'>🔐 Login</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    cols = st.columns(4)
    for col, user in zip(cols, USERS):
        with col:
            if st.button(user, use_container_width=True):
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
progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

def area_color(area):
    h = int(hashlib.md5(area.encode()).hexdigest(), 16)
    return f"#{h % 0xFFFFFF:06x}"

# -------------------------
# HEADER
# -------------------------
col_title, col_actions = st.columns([6, 4])
with col_title:
    st.title("📊 Team Projects Planner")
    st.caption(f"Logged in as **{st.session_state.user}**")

with col_actions:
    if st.button("✏️ Edit"):
        st.session_state.edit_mode = not st.session_state.edit_mode
    if st.button("➕ Project"):
        st.session_state.add_project = True
        st.session_state.task_boxes = 1
    if st.button("➖ Delete"):
        st.session_state.delete_mode = not st.session_state.delete_mode

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
            t = st.text_input("Task", key=f"new_task_{i}")
            o = st.text_input("Owner (optional)", key=f"new_owner_{i}")
            p = st.selectbox("Status", progress_values, key=f"new_prog_{i}")
            pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"new_prio_{i}")
            d = st.date_input("Due Date", value=date.today(), key=f"new_due_{i}")
            if t:
                tasks.append((t, o, p, pr, d))

    col1, col2, col3 = st.columns(3)
    if col1.button("➕ Add task"):
        st.session_state.task_boxes += 1
        st.rerun()

    if col2.button("Create project"):
        for t, o, p, pr, d in tasks:
            df = pd.concat([df, pd.DataFrame([{
                "Area": area,
                "Project": project,
                "Task": t,
                "Owner": o,
                "Progress": p,
                "Priority": pr,
                "Release Date": date.today(),
                "Due Date": d
            }])], ignore_index=True)

        os.makedirs("data", exist_ok=True)
        df.to_csv(DATA_PATH, index=False)
        st.session_state.add_project = False
        st.rerun()

    if col3.button("Cancel"):
        st.session_state.add_project = False
        st.session_state.task_boxes = 1
        st.rerun()

# ======================================================
# 📁 PROJECT VIEW
# ======================================================
if not st.session_state.add_project:
    for project, proj_df in df.groupby("Project"):
        completion = int(proj_df["Progress"].map(progress_score).mean() * 100)
        area = proj_df["Area"].iloc[0]

        # HEADER PROGETTO CON DELETE MODE
        header_text = f"📁 {project} — {completion}%"
        if st.session_state.delete_mode:
            cols = st.columns([8, 1])
            with cols[0]:
                expand = st.expander(header_text, expanded=True)
            with cols[1]:
                if st.button("🗑️", key=f"delete_proj_{project}"):
                    st.session_state.confirm_delete_project = project
        else:
            expand = st.expander(header_text)

        with expand:
            st.progress(completion / 100)

            # TASK VIEW
            for idx, r in proj_df.iterrows():
                cols = st.columns([10, 1])
                with cols[0]:
                    st.markdown(f"**{r['Task']}**")
                    st.write(f"Owner: {r['Owner'] or '—'}")
                    st.write(f"Priority: {r['Priority']} | Due: {r['Due Date'].date()}")

                    # Radio per selezionare lo stato
                    status = st.radio(
                        "Status",
                        options=progress_values,
                        index=progress_values.index(r["Progress"]),
                        key=f"status_radio_{idx}",
                        horizontal=True
                    )
                    df.loc[idx, "Progress"] = status

                if not st.session_state.edit_mode:
                    # Delete task icon
                    with cols[1]:
                        if st.button("🗑️", key=f"delete_task_{idx}"):
                            st.session_state.confirm_delete_task = idx

            # ==================================================
            # ✏️ EDIT PROJECT
            # ==================================================
            if st.session_state.edit_mode:
                st.markdown("### ✏️ Edit project")
                new_area = st.text_input("Area", area, key=f"ea_{project}")
                new_name = st.text_input("Project name", project, key=f"ep_{project}")

                st.markdown("### Edit existing tasks")
                updated_rows = []

                for idx, row in proj_df.iterrows():
                    with st.container():
                        t = st.text_input("Task", row["Task"], key=f"t_{idx}")
                        o = st.text_input("Owner (optional)", row["Owner"], key=f"o_{idx}")
                        p = st.selectbox(
                            "Status",
                            progress_values,
                            index=progress_values.index(row["Progress"]),
                            key=f"p_{idx}"
                        )
                        pr = st.selectbox(
                            "Priority",
                            ["Low", "Important", "Urgent"],
                            index=["Low", "Important", "Urgent"].index(row["Priority"]),
                            key=f"pr_{idx}"
                        )
                        d = st.date_input("Due Date", row["Due Date"], key=f"d_{idx}")

                        updated_rows.append((idx, t, o, p, pr, d))

                st.markdown("### ➕ Add new tasks")
                add_key = f"add_boxes_{project}"
                st.session_state.setdefault(add_key, 1)
                new_tasks = []

                for i in range(st.session_state[add_key]):
                    with st.container():
                        t = st.text_input("Task", key=f"nt_{project}_{i}")
                        o = st.text_input("Owner (optional)", key=f"no_{project}_{i}")
                        p = st.selectbox("Status", progress_values, key=f"np_{project}_{i}")
                        pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"npr_{project}_{i}")
                        d = st.date_input("Due Date", value=date.today(), key=f"nd_{project}_{i}")
                        if t:
                            new_tasks.append((t, o, p, pr, d))

                col1, col2, col3 = st.columns(3)
                if col1.button("➕ Add task", key=f"add_{project}"):
                    st.session_state[add_key] += 1
                    st.rerun()

                if col2.button("Save changes", key=f"save_{project}"):
                    df.loc[df["Project"] == project, ["Area", "Project"]] = [new_area, new_name]

                    for idx, t, o, p, pr, d in updated_rows:
                        df.loc[idx, ["Task", "Owner", "Progress", "Priority", "Due Date"]] = [t, o, p, pr, d]

                    for t, o, p, pr, d in new_tasks:
                        df = pd.concat([df, pd.DataFrame([{
                            "Area": new_area,
                            "Project": new_name,
                            "Task": t,
                            "Owner": o,
                            "Progress": p,
                            "Priority": pr,
                            "Release Date": date.today(),
                            "Due Date": d
                        }])], ignore_index=True)

                    df.to_csv(DATA_PATH, index=False)
                    st.session_state.edit_mode = False
                    st.rerun()

                if col3.button("Cancel", key=f"cancel_{project}"):
                    st.session_state.edit_mode = False
                    st.session_state[add_key] = 1
                    st.rerun()

# ======================================================
# CONFIRM DELETE PROJECT
# ======================================================
if st.session_state.confirm_delete_project:
    project = st.session_state.confirm_delete_project
    st.warning(f"Are you sure you want to delete the project **{project}**? This cannot be undone!")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, delete project"):
            df = df[df["Project"] != project]
            df.to_csv(DATA_PATH, index=False)
            st.success(f"Project '{project}' deleted")
            st.session_state.confirm_delete_project = None
            st.experimental_rerun()
    with col2:
        if st.button("Cancel"):
            st.session_state.confirm_delete_project = None
            st.experimental_rerun()

# ======================================================
# CONFIRM DELETE TASK
# ======================================================
if st.session_state.confirm_delete_task is not None:
    idx = st.session_state.confirm_delete_task
    task_name = df.loc[idx, "Task"]
    st.warning(f"Are you sure you want to delete the task **{task_name}**? This cannot be undone!")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, delete task"):
            df = df.drop(idx).reset_index(drop=True)
            df.to_csv(DATA_PATH, index=False)
            st.success(f"Task '{task_name}' deleted")
            st.session_state.confirm_delete_task = None
            st.experimental_rerun()
    with col2:
        if st.button("Cancel"):
            st.session_state.confirm_delete_task = None
            st.experimental_rerun()
