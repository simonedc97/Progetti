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

# -------------------------
# LOAD DATA
# -------------------------
def load_data():
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH, parse_dates=["Release Date", "Due Date"])
        # Gestisci i NaN nei campi Owner
        df["Owner"] = df["Owner"].fillna("")
        return df
    else:
        return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    os.makedirs("data", exist_ok=True)
    df.to_csv(DATA_PATH, index=False)

df = load_data()

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

with col_actions:
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✏️ Edit"):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()
    with col2:
        if st.button("➕ Project"):
            st.session_state.add_project = True
            st.session_state.task_boxes = 1
            st.rerun()
    with col3:
        if st.button("➖ Delete"):
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
            o = st.text_input("Owner (optional)", key=f"new_owner_{i}")
            p = st.selectbox("Status", progress_values, key=f"new_prog_{i}")
            pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"new_prio_{i}")
            d = st.date_input("Due Date", value=date.today(), key=f"new_due_{i}")
            if t:
                tasks.append((t, o, p, pr, d))
            st.divider()

    col1, col2, col3 = st.columns(3)
    if col1.button("➕ Add task"):
        st.session_state.task_boxes += 1
        st.rerun()

    if col2.button("Create project"):
        if not area or not project:
            st.error("Area and Project name are required!")
        elif not tasks:
            st.error("Add at least one task!")
        else:
            new_rows = []
            for t, o, p, pr, d in tasks:
                new_rows.append({
                    "Area": area,
                    "Project": project,
                    "Task": t,
                    "Owner": o,
                    "Progress": p,
                    "Priority": pr,
                    "Release Date": pd.Timestamp(date.today()),
                    "Due Date": pd.Timestamp(d)
                })
            
            df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
            save_data(df)
            st.session_state.add_project = False
            st.session_state.task_boxes = 1
            st.success(f"Project '{project}' created successfully!")
            st.rerun()

    if col3.button("Cancel"):
        st.session_state.add_project = False
        st.session_state.task_boxes = 1
        st.rerun()

# ======================================================
# CONFIRM DELETE PROJECT
# ======================================================
if st.session_state.confirm_delete_project is not None:
    project = st.session_state.confirm_delete_project
    st.warning(f"⚠️ Are you sure you want to delete the project **{project}**? This cannot be undone!")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, delete project", key=f"confirm_del_proj_{project}", type="primary"):
            df = df[df["Project"] != project].reset_index(drop=True)
            save_data(df)
            st.success(f"Project '{project}' deleted")
            st.session_state.confirm_delete_project = None
            st.session_state.delete_mode = False
            st.rerun()
    with col2:
        if st.button("❌ Cancel", key=f"cancel_del_proj_{project}"):
            st.session_state.confirm_delete_project = None
            st.rerun()
    st.stop()

# ======================================================
# CONFIRM DELETE TASK
# ======================================================
if st.session_state.confirm_delete_task is not None:
    task_id = st.session_state.confirm_delete_task
    # Usa un ID univoco basato su Project + Task name invece dell'indice
    project_name, task_name = task_id
    mask = (df["Project"] == project_name) & (df["Task"] == task_name)
    
    if mask.any():
        st.warning(f"⚠️ Are you sure you want to delete the task **{task_name}**? This cannot be undone!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, delete task", key=f"confirm_del_task_{task_name}", type="primary"):
                df = df[~mask].reset_index(drop=True)
                save_data(df)
                st.success(f"Task '{task_name}' deleted")
                st.session_state.confirm_delete_task = None
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key=f"cancel_del_task_{task_name}"):
                st.session_state.confirm_delete_task = None
                st.rerun()
        st.stop()

# ======================================================
# 📁 PROJECT VIEW
# ======================================================
if not st.session_state.add_project and len(df) > 0:
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
                    st.rerun()
        else:
            expand = st.expander(header_text, expanded=True)

        with expand:
            st.progress(completion / 100)

            # TASK VIEW
            if not st.session_state.edit_mode:
                for idx, r in proj_df.iterrows():
                    cols = st.columns([10, 1])
                    with cols[0]:
                        st.markdown(f"**{r['Task']}**")
                        st.write(f"👤 Owner: {r['Owner'] if r['Owner'] else '—'}")
                        st.write(f"🎯 Priority: {r['Priority']} | 📅 Due: {r['Due Date'].date()}")

                        # Radio per selezionare lo stato
                        current_status = r["Progress"]
                        status = st.radio(
                            "Status",
                            options=progress_values,
                            index=progress_values.index(current_status),
                            key=f"status_radio_{project}_{r['Task']}_{idx}",
                            horizontal=True
                        )
                        
                        # Aggiorna lo stato se cambiato
                        if status != current_status:
                            df.loc[idx, "Progress"] = status
                            save_data(df)
                            st.rerun()

                    # Delete task icon
                    with cols[1]:
                        if st.button("🗑️", key=f"delete_task_{project}_{r['Task']}"):
                            st.session_state.confirm_delete_task = (project, r['Task'])
                            st.rerun()
                    
                    st.divider()

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
                        st.markdown(f"**Task #{idx}**")
                        t = st.text_input("Task", row["Task"], key=f"t_{idx}")
                        o = st.text_input("Owner (optional)", row["Owner"] if row["Owner"] else "", key=f"o_{idx}")
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
                        st.divider()

                st.markdown("### ➕ Add new tasks")
                add_key = f"add_boxes_{project}"
                if add_key not in st.session_state:
                    st.session_state[add_key] = 1
                    
                new_tasks = []

                for i in range(st.session_state[add_key]):
                    with st.container():
                        st.markdown(f"**New Task {i+1}**")
                        t = st.text_input("Task", key=f"nt_{project}_{i}")
                        o = st.text_input("Owner (optional)", key=f"no_{project}_{i}")
                        p = st.selectbox("Status", progress_values, key=f"np_{project}_{i}")
                        pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"npr_{project}_{i}")
                        d = st.date_input("Due Date", value=date.today(), key=f"nd_{project}_{i}")
                        if t:
                            new_tasks.append((t, o, p, pr, d))
                        st.divider()

                col1, col2, col3 = st.columns(3)
                if col1.button("➕ Add task", key=f"add_{project}"):
                    st.session_state[add_key] += 1
                    st.rerun()

                if col2.button("💾 Save changes", key=f"save_{project}", type="primary"):
                    # Aggiorna area e nome progetto
                    df.loc[df["Project"] == project, "Area"] = new_area
                    df.loc[df["Project"] == project, "Project"] = new_name

                    # Aggiorna task esistenti
                    for idx, t, o, p, pr, d in updated_rows:
                        df.loc[idx, "Task"] = t
                        df.loc[idx, "Owner"] = o
                        df.loc[idx, "Progress"] = p
                        df.loc[idx, "Priority"] = pr
                        df.loc[idx, "Due Date"] = pd.Timestamp(d)

                    # Aggiungi nuovi task
                    new_rows = []
                    for t, o, p, pr, d in new_tasks:
                        new_rows.append({
                            "Area": new_area,
                            "Project": new_name,
                            "Task": t,
                            "Owner": o,
                            "Progress": p,
                            "Priority": pr,
                            "Release Date": pd.Timestamp(date.today()),
                            "Due Date": pd.Timestamp(d)
                        })
                    
                    if new_rows:
                        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

                    save_data(df)
                    st.session_state.edit_mode = False
                    if add_key in st.session_state:
                        st.session_state[add_key] = 1
                    st.success("Changes saved successfully!")
                    st.rerun()

                if col3.button("❌ Cancel", key=f"cancel_{project}"):
                    st.session_state.edit_mode = False
                    if add_key in st.session_state:
                        st.session_state[add_key] = 1
                    st.rerun()

elif not st.session_state.add_project and len(df) == 0:
    st.info("📝 No projects yet. Click '➕ Project' to create your first project!")

# -------------------------
# FOOTER
# -------------------------
st.divider()
st.caption(f"Total projects: {df['Project'].nunique() if len(df) > 0 else 0} | Total tasks: {len(df)}")
