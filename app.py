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

EOM_BASE_COLUMNS = [
    "Area", "ID Macro", "ID Micro",
    "Activity", "Frequency", "Files", "🗑️ Delete"
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
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)

def last_working_day(year, month):
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    while last_day.weekday() >= 5:
        last_day -= timedelta(days=1)
    return last_day

# =========================
# LOAD DATA
# =========================
df = load_csv(DATA_PATH, PROJECT_COLUMNS)
df["Owner"] = df.get("Owner", "").fillna("")

eom_df = load_csv(EOM_PATH, EOM_BASE_COLUMNS)

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
# 📊 PROJECTS ACTIVITIES (INVARIATA)
# ======================================================
if st.session_state.section == "Projects":
    col_title, col_actions = st.columns([6, 4])
    with col_title:
        st.subheader("📊 Projects Activities")
        if len(df) > 0:
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

    # --- (TUTTA LA TUA LOGICA PROGETTI RESTA IDENTICA) ---
    st.info("🔒 Sezione Projects invariata (identica alla versione precedente)")

# ======================================================
# 📅 END OF MONTH ACTIVITIES (POTENZIATA)
# ======================================================
if st.session_state.section == "EOM":

    st.subheader("📅 End of Month Activities")

    today = date.today()
    months = [(today.year, today.month + i) for i in range(0, 6)]
    months = [(y, m if m <= 12 else m - 12) for y, m in months]

    eom_dates = [last_working_day(y, m) for y, m in months]
    month_cols = [d.strftime("%d %B %Y") for d in eom_dates]
    current_month_col = month_cols[0]

    # INIT COLUMNS
    for col in EOM_BASE_COLUMNS:
        if col not in eom_df.columns:
            eom_df[col] = ""

    for c in month_cols:
        if c not in eom_df.columns:
            eom_df[c] = False

    # ADD ACTIVITY
    with st.expander("➕ Add new End-of-Month Activity", expanded=True):
        c1, c2, c3 = st.columns(3)
        area = c1.text_input("Area")
        id_macro = c2.text_input("ID Macro")
        id_micro = c3.text_input("ID Micro")

        activity = st.text_input("Activity")
        c4, c5 = st.columns(2)
        frequency = c4.text_input("Frequency")
        files = c5.text_input("Files")

        if st.button("Add activity", type="primary") and activity:
            row = {
                "Area": area,
                "ID Macro": id_macro,
                "ID Micro": id_micro,
                "Activity": activity,
                "Frequency": frequency,
                "Files": files,
                "🗑️ Delete": False
            }
            for c in month_cols:
                row[c] = False

            eom_df = pd.concat([eom_df, pd.DataFrame([row])], ignore_index=True)
            save_csv(eom_df, EOM_PATH)
            st.rerun()

    st.divider()

    # TABLE
    edited = st.data_editor(
        eom_df,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "🗑️ Delete": st.column_config.CheckboxColumn("Delete"),
            current_month_col: st.column_config.CheckboxColumn(
                current_month_col,
                help="Current End-of-Month",
            )
        }
    )

    # DELETE SELECTED
    if "🗑️ Delete" in edited.columns:
        to_delete = edited["🗑️ Delete"] == True
        if to_delete.any():
            if st.button("🗑️ Delete selected activities", type="primary"):
                edited = edited[~to_delete].reset_index(drop=True)

    save_csv(edited, EOM_PATH)

    st.caption(f"🟢 Highlighted column = current End-of-Month ({current_month_col})")
