import streamlit as st
import pandas as pd
from datetime import date, timedelta
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

progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

# =========================
# HELPERS
# =========================
def save_csv(df, path):
    os.makedirs("data", exist_ok=True)
    df.to_csv(path, index=False)

def load_csv(path, columns, date_cols=None):
    if os.path.exists(path):
        if date_cols:
            return pd.read_csv(path, parse_dates=date_cols)
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)

def last_working_day(year, month):
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    while last_day.weekday() >= 5:
        last_day -= timedelta(days=1)
    return last_day

def get_next_months(n=6):
    today = date.today()
    months = []

    for i in range(n):
        m = today.month + i
        y = today.year
        while m > 12:
            m -= 12
            y += 1
        months.append((y, m))

    # Sempre includi dicembre 2025
    if (2025, 12) not in months:
        months.append((2025, 12))

    return sorted(months)

def clean_eom_dataframe(df, month_cols):
    df = df.copy()
    for c in ["🗑️ Delete"] + month_cols:
        if c in df.columns:
            df[c] = df[c].fillna(False).astype(bool)
    for c in ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)
    return df

# =========================
# LOAD DATA
# =========================
df = load_csv(DATA_PATH, PROJECT_COLUMNS, ["Release Date", "Due Date"])
eom_df = load_csv(EOM_PATH, EOM_BASE_COLUMNS)

# =========================
# NAVIGATION
# =========================
if "section" not in st.session_state:
    st.session_state.section = "Projects"
if "eom_delete_row" not in st.session_state:
    st.session_state.eom_delete_row = None

st.title("🗂️ RM Insurance Planner")

c1, c2 = st.columns(2)
if c1.button("📊 Projects Activities", use_container_width=True):
    st.session_state.section = "Projects"
if c2.button("📅 End of Month Activities", use_container_width=True):
    st.session_state.section = "EOM"

st.divider()

# ======================================================
# 📅 END OF MONTH ACTIVITIES
# ======================================================
if st.session_state.section == "EOM":

    st.subheader("📅 End of Month Activities")

    # MONTH LOGIC
    months = get_next_months(6)
    eom_dates = [last_working_day(y, m) for y, m in months]
    month_cols = [d.strftime("%d %B %Y") for d in eom_dates]

    today = date.today()
    prev_month = today.month - 1 or 12
    prev_year = today.year if today.month > 1 else today.year - 1
    current_eom = last_working_day(prev_year, prev_month).strftime("%d %B %Y")

    # INIT COLUMNS
    for col in EOM_BASE_COLUMNS:
        if col not in eom_df.columns:
            eom_df[col] = False if col == "🗑️ Delete" else ""

    for c in month_cols:
        if c not in eom_df.columns:
            eom_df[c] = False

    eom_df = clean_eom_dataframe(eom_df, month_cols)

    # ADD ACTIVITY
    with st.expander("➕ Add new End-of-Month Activity"):
        a1, a2, a3 = st.columns(3)
        area = a1.text_input("Area")
        id_macro = a2.text_input("ID Macro")
        id_micro = a3.text_input("ID Micro")
        activity = st.text_input("Activity")
        b1, b2 = st.columns(2)
        freq = b1.text_input("Frequency")
        files = b2.text_input("Files")

        if st.button("Add activity", type="primary"):
            if activity:
                row = {
                    "Area": area,
                    "ID Macro": id_macro,
                    "ID Micro": id_micro,
                    "Activity": activity,
                    "Frequency": freq,
                    "Files": files,
                    "🗑️ Delete": False
                }
                for c in month_cols:
                    row[c] = False

                eom_df = pd.concat([eom_df, pd.DataFrame([row])], ignore_index=True)
                save_csv(eom_df, EOM_PATH)
                st.success("✅ Activity added")
                st.rerun()

    st.divider()

    # NASCONDI MESI COMPLETATI
    completed_months = [
        c for c in month_cols
        if c in eom_df.columns and len(eom_df) > 0 and eom_df[c].all()
    ]

    show_completed = st.checkbox("👁️ Show completed months", value=False)

    visible_cols = [
        c for c in eom_df.columns
        if c not in completed_months or show_completed
    ]

    edited = st.data_editor(
        eom_df[visible_cols],
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="eom_editor"
    )

    # DELETE MULTI
    if "🗑️ Delete" in edited.columns:
        to_delete = edited["🗑️ Delete"]
        if to_delete.any():
            if st.button("🗑️ Delete selected", type="primary"):
                edited = edited[~to_delete].reset_index(drop=True)
                save_csv(edited, EOM_PATH)
                st.success("✅ Deleted")
                st.rerun()

    # SAVE EDITS
    save_csv(edited, EOM_PATH)
    eom_df = edited

    # DELETE SINGLE
    st.markdown("### 🗑️ Delete single activity")
    for i, r in eom_df.iterrows():
        col1, col2 = st.columns([10, 1])
        with col1:
            st.write(r["Activity"])
        with col2:
            if st.button("🗑️", key=f"del_{i}"):
                st.session_state.eom_delete_row = i
                st.rerun()

    if st.session_state.eom_delete_row is not None:
        idx = st.session_state.eom_delete_row
        st.warning("⚠️ Confirm delete activity?")
        c1, c2 = st.columns(2)
        if c1.button("Yes", type="primary"):
            eom_df = eom_df.drop(index=idx).reset_index(drop=True)
            save_csv(eom_df, EOM_PATH)
            st.session_state.eom_delete_row = None
            st.rerun()
        if c2.button("Cancel"):
            st.session_state.eom_delete_row = None

    st.divider()
    st.info(f"✅ **Current End-of-Month:** {current_eom}")

    total = len(eom_df)
    completed = eom_df[current_eom].sum() if current_eom in eom_df.columns else 0
    st.caption(f"📊 Activities: {completed}/{total} completed")
