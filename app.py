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
    "Progress", "Priority", "Release Date", "Due Date"
]

# =========================
# SESSION STATE
# =========================
st.session_state.setdefault("section", "Projects")
st.session_state.setdefault("edit_mode", False)
st.session_state.setdefault("add_project", False)
st.session_state.setdefault("task_boxes", 1)
st.session_state.setdefault("delete_mode", False)
st.session_state.setdefault("confirm_delete_project", None)
st.session_state.setdefault("confirm_delete_task", None)

# =========================
# HELPERS
# =========================
progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

def save_csv(df, path):
    os.makedirs("data", exist_ok=True)
    df.to_csv(path, index=False)

def load_csv(path, columns):
    if os.path.exists(path):
        return pd.read_csv(path, parse_dates=True)
    return pd.DataFrame(columns=columns)

def last_working_day(year, month):
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    while last_day.weekday() >= 5:  # 5=Sat, 6=Sun
        last_day -= timedelta(days=1)
    return last_day

# =========================
# LOAD DATA
# =========================
df = load_csv(DATA_PATH, PROJECT_COLUMNS)
df["Owner"] = df.get("Owner", "").fillna("")

eom_df = load_csv(EOM_PATH, [])

# =========================
# HEADER + NAVIGATION
# =========================
st.title("🗂️ RM Insurance Planner")

nav1, nav2 = st.columns(2)
with nav1:
    if st.button("📊 Projects Activities", use_container_width=True):
        st.session_state.section = "Projects"
with nav2:
    if st.button("📅 End of Month Activities", use_container_width=True):
        st.session_state.section = "EOM"

st.divider()

# ======================================================
# 📊 Projects Activities (SEZIONE 1)
# ======================================================
if st.session_state.section == "Projects":

    col_title, col_actions = st.columns([6, 4])
    with col_title:
        st.subheader("📊 Projects Activities")
        if len(df) > 0 and "Release Date" in df:
            last_update = pd.to_datetime(df["Release Date"]).max()
            st.caption(f"🕒 Last update: {last_update.strftime('%d/%m/%Y %H:%M')}")

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

    # ➕ ADD PROJECT
    if st.session_state.add_project:
        st.subheader("➕ New Project")
        area = st.text_input("Area")
        project = st.text_input("Project name")

        tasks = []
        for i in range(st.session_state.task_boxes):
            st.markdown(f"**Task {i+1}**")
            t = st.text_input("Task", key=f"t{i}")
            o = st.text_input("Owner", key=f"o{i}")
            p = st.selectbox("Status", progress_values, key=f"p{i}")
            pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"pr{i}")
            d = st.date_input("Due Date", key=f"d{i}")
            if t:
                tasks.append((t, o, p, pr, d))
            st.divider()

        c1, c2, c3 = st.columns(3)
        if c1.button("➕ Add task"):
            st.session_state.task_boxes += 1
            st.rerun()

        if c2.button("Create project"):
            for t, o, p, pr, d in tasks:
                df.loc[len(df)] = [
                    area, project, t, o, p, pr,
                    datetime.now(), d
                ]
            save_csv(df, DATA_PATH)
            st.session_state.add_project = False
            st.rerun()

        if c3.button("Cancel"):
            st.session_state.add_project = False
            st.rerun()

    # 📁 PROJECT VIEW
    for project, proj_df in df.groupby("Project"):
        completion = int(proj_df["Progress"].map(progress_score).mean() * 100)

        cols = st.columns([9, 1]) if st.session_state.delete_mode else [st.container()]
        with cols[0]:
            exp = st.expander(f"📁 {project} — {completion}%", expanded=True)

        if st.session_state.delete_mode:
            with cols[1]:
                if st.button("🗑️", key=f"del_proj_{project}"):
                    st.session_state.confirm_delete_project = project
                    st.rerun()

        with exp:
            st.progress(completion / 100)

            for idx, r in proj_df.iterrows():
                c_task, c_del = st.columns([10, 1])
                with c_task:
                    st.markdown(f"**{r['Task']}**")
                    st.write(f"👤 {r['Owner'] or '—'} | 🎯 {r['Priority']} | 📅 {r['Due Date']}")
                    status = st.radio(
                        "Status",
                        progress_values,
                        index=progress_values.index(r["Progress"]),
                        horizontal=True,
                        key=f"s_{idx}"
                    )
                    if status != r["Progress"]:
                        df.loc[idx, "Progress"] = status
                        df.loc[idx, "Release Date"] = datetime.now()
                        save_csv(df, DATA_PATH)
                        st.rerun()

                with c_del:
                    if st.button("🗑️", key=f"del_task_{idx}"):
                        st.session_state.confirm_delete_task = idx
                        st.rerun()
                st.divider()

    # CONFIRM DELETE
    if st.session_state.confirm_delete_project:
        p = st.session_state.confirm_delete_project
        st.warning(f"Delete project **{p}**?")
        if st.button("✅ Confirm"):
            df = df[df["Project"] != p]
            save_csv(df, DATA_PATH)
            st.session_state.confirm_delete_project = None
            st.session_state.delete_mode = False
            st.rerun()
        if st.button("❌ Cancel"):
            st.session_state.confirm_delete_project = None

    if st.session_state.confirm_delete_task is not None:
        st.warning("Delete task?")
        if st.button("✅ Confirm"):
            df = df.drop(st.session_state.confirm_delete_task)
            save_csv(df, DATA_PATH)
            st.session_state.confirm_delete_task = None
            st.rerun()
        if st.button("❌ Cancel"):
            st.session_state.confirm_delete_task = None

# ======================================================
# 📅 END OF MONTH ACTIVITIES (SEZIONE 2)
# ======================================================
if st.session_state.section == "EOM":

    st.subheader("📅 End of Month Activities")

    # Calcolo colonne (fine mese lavorativo)
    today = date.today()
    months = [(today.year, today.month + i) for i in range(0, 6)]
    months = [(y, m if m <= 12 else m - 12) for y, m in months]

    eom_dates = [last_working_day(y, m) for y, m in months]
    col_names = [d.strftime("%d %B %Y") for d in eom_dates]

    # Init dataframe
    if eom_df.empty:
        eom_df["Activity"] = []

    for c in col_names:
        if c not in eom_df.columns:
            eom_df[c] = False

    # ADD ACTIVITY
    new_act = st.text_input("➕ New activity")
    if st.button("Add activity") and new_act:
        row = {"Activity": new_act}
        for c in col_names:
            row[c] = False
        eom_df = pd.concat([eom_df, pd.DataFrame([row])], ignore_index=True)
        save_csv(eom_df, EOM_PATH)
        st.rerun()

    # TABLE
    edited = st.data_editor(
        eom_df,
        use_container_width=True,
        num_rows="fixed"
    )

    save_csv(edited, EOM_PATH)
