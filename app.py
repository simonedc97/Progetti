import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import requests
import json

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="RM Insurance Planner", layout="wide")

# JSONBin Configuration
JSONBIN_API_KEY = "$2a$10$O1c.ADK9BgMXBYVzCnRe2eRnLiTVK4bd7Hqd7kRLMwIISia4UHBQa"
JSONBIN_BIN_ID_PROJECTS = "69628091d0ea881f40626147"  # ⚠️ DA MODIFICARE
JSONBIN_BIN_ID_EOM = "696280d9d0ea881f406261d7"  # ⚠️ DA MODIFICARE
JSONBIN_BIN_ID_ATTENDANCE = "696280f9d0ea881f40626222 "  # ⚠️ DA MODIFICARE

PROJECT_COLUMNS = [
    "Area", "Project", "Task", "Owner",
    "Progress", "Priority", "Release Date", "Due Date", "GR/Mail Object", "Notes", "Last Update", "Order"
]

EOM_BASE_COLUMNS = [
    "Area", "ID Macro", "ID Micro",
    "Activity", "Frequency", "Files", "🗑️ Delete", "Last Update", "Order"
]

TEAM_MEMBERS = ["Elena", "Giulia", "Simone", "Paolo"]
ATTENDANCE_TYPES = ["", "🏢 Office", "🏠 Smart Working", "🌴 Vacation", "⏰ Hourly Leave", "💰 Time Bank"]

# =========================
# JSONBIN FUNCTIONS
# =========================
def save_to_jsonbin(df, bin_id):
    url = f"https://api.jsonbin.io/v3/b/{bin_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_API_KEY
    }
    
    data_dict = df.copy()
    for col in data_dict.columns:
        if data_dict[col].dtype == 'datetime64[ns]':
            data_dict[col] = data_dict[col].astype(str)
        elif data_dict[col].dtype == 'bool':  # AGGIUNTO
            data_dict[col] = data_dict[col].astype(str)  # AGGIUNTO
    
    data_to_save = data_dict.to_dict('records')
    
    try:  # AGGIUNTO
        response = requests.put(url, json=data_to_save, headers=headers)
        return response.status_code == 200
    except Exception as e:  # AGGIUNTO
        st.error(f"Error saving: {e}")  # AGGIUNTO
        return False  # AGGIUNTO

def load_from_jsonbin(bin_id, columns, date_cols=None):
    """Carica DataFrame da JSONBin"""
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
    headers = {
        "X-Master-Key": JSONBIN_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()['record']
            if data:
                df = pd.DataFrame(data)
                
                # Converti stringhe in datetime
                if date_cols:
                    for col in date_cols:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors='coerce')
                
                return df
            return pd.DataFrame(columns=columns)
        else:
            return pd.DataFrame(columns=columns)
    except:
        return pd.DataFrame(columns=columns)

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
if "show_filters" not in st.session_state:
    st.session_state.show_filters = False
if "show_eom_filters" not in st.session_state:
    st.session_state.show_eom_filters = False
if "eom_bulk_delete" not in st.session_state:
    st.session_state.eom_bulk_delete = False
if "reset_filters_flag" not in st.session_state:
    st.session_state.reset_filters_flag = 0
if "reset_eom_filters_flag" not in st.session_state:
    st.session_state.reset_eom_filters_flag = 0
if "hidden_months" not in st.session_state:
    st.session_state.hidden_months = []
if "show_month_manager" not in st.session_state:
    st.session_state.show_month_manager = False
if "selected_attendance_month" not in st.session_state:
    st.session_state.selected_attendance_month = date.today().replace(day=1)

# =========================
# HELPERS
# =========================
progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

def clean_eom_dataframe(df, month_cols):
    """Pulisce il DataFrame EOM assicurando i tipi corretti"""
    df = df.copy()
    
    for col in month_cols:
        if col in df.columns:
            df[col] = df[col].fillna("⚪")
            df[col] = df[col].replace("", "⚪")
            df[col] = df[col].apply(lambda x: 
                "🟢" if x in [True, "True", "true", "Done", "🟢", "1", 1] 
                else "🔴" if x in [False, "False", "false", "Undone", "🔴", "0", 0]
                else "⚪"
            )
    
    if "🗑️ Delete" in df.columns:
        df["🗑️ Delete"] = df["🗑️ Delete"].fillna(False)
        df["🗑️ Delete"] = df["🗑️ Delete"].replace("", False)
        df["🗑️ Delete"] = df["🗑️ Delete"].apply(
            lambda x: True if x in [True, "True", "true", "1", 1] else False
        )
    
    text_cols = ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    
    return df

def last_working_day(year, month):
    """Calcola l'ultimo giorno lavorativo del mese"""
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    while last_day.weekday() >= 5:
        last_day -= timedelta(days=1)
    return last_day

def get_next_months(n=6, include_previous=True):
    """Genera i prossimi N mesi, includendo il mese precedente se richiesto"""
    today = date.today()
    months = []
    
    if include_previous:
        prev_month = today.month - 1
        prev_year = today.year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
        months.append((prev_year, prev_month))
    
    for i in range(n):
        month = today.month + i
        year = today.year
        while month > 12:
            month -= 12
            year += 1
        months.append((year, month))
    
    if (2025, 12) not in months:
        months.append((2025, 12))
    
    months = sorted(list(set(months)))
    
    return months

def get_month_dates(year, month):
    """Ritorna tutte le date di un mese"""
    _, num_days = calendar.monthrange(year, month)
    return [date(year, month, day) for day in range(1, num_days + 1)]

# =========================
# LOAD DATA
# =========================
df = load_from_jsonbin(JSONBIN_BIN_ID_PROJECTS, PROJECT_COLUMNS, date_cols=["Release Date", "Due Date"])
if "Owner" in df.columns:
    df["Owner"] = df["Owner"].fillna("")
if "GR/Mail Object" in df.columns:
    df["GR/Mail Object"] = df["GR/Mail Object"].fillna("")
if "Release Date" not in df.columns:
    df["Release Date"] = pd.NaT
if "GR/Mail Object" not in df.columns:
    df["GR/Mail Object"] = ""
if "Notes" not in df.columns:
    df["Notes"] = ""
if "Last Update" not in df.columns:
    df["Last Update"] = pd.Timestamp.now()
if "Order" not in df.columns:
    df["Order"] = range(len(df))

eom_df = load_from_jsonbin(JSONBIN_BIN_ID_EOM, EOM_BASE_COLUMNS)
if "Last Update" not in eom_df.columns:
    eom_df["Last Update"] = pd.Timestamp.now()
if "Order" not in eom_df.columns:
    eom_df["Order"] = range(len(eom_df))

# Load attendance data
attendance_df = load_from_jsonbin(JSONBIN_BIN_ID_ATTENDANCE, ["Date", "Member", "Type", "Notes"], date_cols=["Date"])
if len(attendance_df) == 0:
    attendance_df = pd.DataFrame(columns=["Date", "Member", "Type", "Notes"])
if "Date" in attendance_df.columns:
    attendance_df["Date"] = pd.to_datetime(attendance_df["Date"], errors='coerce')
if "Notes" in attendance_df.columns:  # AGGIUNTO
    attendance_df["Notes"] = attendance_df["Notes"].fillna("")  # AGGIUNTO

# =========================
# HEADER + NAVIGATION
# =========================
col_title, col_attendance = st.columns([8, 2])
with col_title:
    st.title("🗂️ RM Insurance Planner")
with col_attendance:
    if st.button("📅 Attendance", use_container_width=True, 
                 type="primary" if st.session_state.section == "Attendance" else "secondary"):
        st.session_state.section = "Attendance"
        st.rerun()

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
        if len(df) > 0:
            try:
                if "Last Update" in df.columns and pd.notna(df["Last Update"].iloc[0]):
                    last_update = pd.to_datetime(df["Last Update"]).max()
                else:
                    last_update = pd.Timestamp.now()
                st.caption(f"🕒 Last update: {last_update.strftime('%d/%m/%Y %H:%M')}")
            except:
                st.caption(f"🕒 Last update: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")

    with col_actions:
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("🔍 Filters"):
            st.session_state.show_filters = not st.session_state.show_filters
            st.rerun()
        if c2.button("✏️ Edit"):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()
        if c3.button("➕ Project"):
            st.session_state.add_project = True
            st.session_state.task_boxes = 1
            st.rerun()
        if c4.button("➖ Delete"):
            st.session_state.delete_mode = not st.session_state.delete_mode
            st.rerun()

    # ======================================================
    # FILTERS SECTION
    # ======================================================
    if st.session_state.show_filters and len(df) > 0:
        with st.expander("🔍 Filters", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                areas = ["All"] + sorted(df["Area"].dropna().unique().tolist())
                selected_area = st.selectbox("Area", areas, 
                                            index=0,
                                            key=f"filter_area_{st.session_state.reset_filters_flag}")
            
            with col2:
                owners = ["All"] + sorted(df["Owner"].dropna().unique().tolist())
                selected_owner = st.selectbox("Owner", owners, 
                                             index=0,
                                             key=f"filter_owner_{st.session_state.reset_filters_flag}")
            
            with col3:
                statuses = ["All"] + progress_values
                selected_status = st.selectbox("Status", statuses, 
                                              index=0,
                                              key=f"filter_status_{st.session_state.reset_filters_flag}")
            
            with col4:
                priorities = ["All", "Low", "Important", "Urgent"]
                selected_priority = st.selectbox("Priority", priorities, 
                                                index=0,
                                                key=f"filter_priority_{st.session_state.reset_filters_flag}")
            
            col5, col6, col7 = st.columns(3)
            
            with col5:
                due_filter = st.selectbox("Due Date", 
                                         ["All", "Overdue", "This Week", "This Month", "No Date"], 
                                         index=0,
                                         key=f"filter_due_{st.session_state.reset_filters_flag}")
            
            with col6:
                projects = ["All"] + sorted(df["Project"].dropna().unique().tolist())
                selected_project = st.selectbox("Project", projects, 
                                               index=0,
                                               key=f"filter_project_{st.session_state.reset_filters_flag}")
            
            with col7:
                if st.button("🔄 Reset Filters", use_container_width=True):
                    st.session_state.reset_filters_flag += 1
                    st.rerun()
        
        # Apply filters
        filtered_df = df.copy()
        
        if selected_area != "All":
            filtered_df = filtered_df[filtered_df["Area"] == selected_area]
        
        if selected_owner != "All":
            filtered_df = filtered_df[filtered_df["Owner"] == selected_owner]
        
        if selected_status != "All":
            filtered_df = filtered_df[filtered_df["Progress"] == selected_status]
        
        if selected_priority != "All":
            filtered_df = filtered_df[filtered_df["Priority"] == selected_priority]
        
        if selected_project != "All":
            filtered_df = filtered_df[filtered_df["Project"] == selected_project]
        
        if due_filter != "All":
            today = pd.Timestamp(date.today())
            if due_filter == "Overdue":
                filtered_df = filtered_df[filtered_df["Due Date"] < today]
            elif due_filter == "This Week":
                week_end = today + pd.Timedelta(days=7)
                filtered_df = filtered_df[(filtered_df["Due Date"] >= today) & (filtered_df["Due Date"] <= week_end)]
            elif due_filter == "This Month":
                month_end = today + pd.offsets.MonthEnd(0)
                filtered_df = filtered_df[(filtered_df["Due Date"] >= today) & (filtered_df["Due Date"] <= month_end)]
            elif due_filter == "No Date":
                filtered_df = filtered_df[filtered_df["Due Date"].isna()]
        
        df = filtered_df
        
        original_df = load_from_jsonbin(JSONBIN_BIN_ID_PROJECTS, PROJECT_COLUMNS, date_cols=['Release Date', 'Due Date'])
        st.info(f"📊 Showing {len(df)} of {len(original_df)} tasks")
        st.divider()

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
                
                col_a, col_b = st.columns(2)
                with col_a:
                    p = st.selectbox("Status", progress_values, key=f"new_prog_{i}")
                with col_b:
                    pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"new_prio_{i}")
                
                col_c, col_d = st.columns(2)
                with col_c:
                    r = st.date_input("Release Date (optional)", value=None, key=f"new_rel_{i}")
                with col_d:
                    d = st.date_input("Due Date (optional)", value=None, key=f"new_due_{i}")
                
                col_gr, col_mail = st.columns(2)
                with col_gr:
                    gr = st.text_area("📋 GR Number (optional)", key=f"new_gr_{i}", height=80)
                with col_mail:
                    mail = st.text_area("📧 Mail Object (optional)", key=f"new_mail_{i}", height=80)
                
                gr_combined = f"{gr}\n{mail}" if gr or mail else ""
                
                notes = st.text_area("Notes (optional)", key=f"new_notes_{i}", height=60)
                
                if t:
                    tasks.append((t, o, p, pr, r, d, gr_combined, notes))
                st.divider()

        col1, col2, col3 = st.columns(3)
        if col1.button("➕ Add task"):
            st.session_state.task_boxes += 1
            st.rerun()

        if col2.button("Create project", type="primary"):
            if not area or not project:
                st.error("❌ Area and Project name are required!")
            elif not tasks:
                st.error("❌ Add at least one task!")
            else:
                new_rows = []
                next_order = df["Order"].max() + 1 if len(df) > 0 else 0
                for t, o, p, pr, r, d, gr, notes in tasks:
                    new_rows.append({
                        "Area": area,
                        "Project": project,
                        "Task": t,
                        "Owner": o,
                        "Progress": p,
                        "Priority": pr,
                        "Release Date": pd.Timestamp(r) if r else pd.NaT,
                        "Due Date": pd.Timestamp(d) if d else pd.NaT,
                        "GR/Mail Object": gr,
                        "Notes": notes,
                        "Last Update": pd.Timestamp.now() + pd.Timedelta(hours=1),
                        "Order": next_order
                    })
                    next_order += 1
                
                df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                save_to_jsonbin(df, JSONBIN_BIN_ID_PROJECTS)
                st.session_state.add_project = False
                st.session_state.task_boxes = 1
                st.success(f"✅ Project '{project}' created successfully!")
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
                save_to_jsonbin(df, JSONBIN_BIN_ID_PROJECTS)
                st.success(f"✅ Project '{project}' deleted")
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
        project_name, task_name = task_id
        mask = (df["Project"] == project_name) & (df["Task"] == task_name)
        
        if mask.any():
            st.warning(f"⚠️ Are you sure you want to delete the task **{task_name}**? This cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, delete task", key=f"confirm_del_task_{task_name}", type="primary"):
                    df = df[~mask].reset_index(drop=True)
                    save_to_jsonbin(df, JSONBIN_BIN_ID_PROJECTS)
                    st.success(f"✅ Task '{task_name}' deleted")
                    st.session_state.confirm_delete_task = None
                    st.rerun()
            with col2:
                if st.button("❌ Cancel", key=f"cancel_del_task_{task_name}"):
                    st.session_state.confirm_delete_task = None
                    st.rerun()
            st.stop()

    # ======================================================
    # 📁 PROJECT VIEW (parte non edit mode)
    # ======================================================
    if not st.session_state.add_project and len(df) > 0:
    if "Project" not in df.columns or len(df) == 0:  # AGGIUNTO
        st.warning("⚠️ No projects found")  # AGGIUNTO
    else:  # AGGIUNTO
        in_progress_projects = []
        in_progress_projects = []
        completed_projects = []
        
        for project in df["Project"].unique():
            proj_df = df[df["Project"] == project]
            completion = proj_df["Progress"].map(progress_score).mean()
            
            if completion == 1.0:
                completed_projects.append(project)
            else:
                in_progress_projects.append(project)
        
        in_progress_projects.sort()
        completed_projects.sort()
        
        # ===== IN PROGRESS SECTION =====
        if in_progress_projects:
            st.markdown("### 📂 In Progress")
            
            in_progress_by_area = {}
            for project in in_progress_projects:
                area = df[df["Project"] == project]["Area"].iloc[0]
                if area not in in_progress_by_area:
                    in_progress_by_area[area] = []
                in_progress_by_area[area].append(project)
            
            for area in sorted(in_progress_by_area.keys()):
                st.markdown(f"#### 🏢 {area}")
                
                for project in sorted(in_progress_by_area[area]):
                    proj_df = df[df["Project"] == project]
                    completion = int(proj_df["Progress"].map(progress_score).mean() * 100)
                    
                    header_text = f"📁 {project} — {completion}%"
                    
                    if st.session_state.delete_mode:
                        cols = st.columns([8, 1])
                        with cols[0]:
                            expand = st.expander(header_text, expanded=False)
                        with cols[1]:
                            if st.button("🗑️", key=f"delete_proj_{project}"):
                                st.session_state.confirm_delete_project = project
                                st.rerun()
                    else:
                        expand = st.expander(header_text, expanded=False)
                    
                    with expand:
                        st.progress(completion / 100)

                        if not st.session_state.edit_mode:
                            for idx, r in proj_df.iterrows():
                                cols = st.columns([10, 1])
                                with cols[0]:
                                    st.markdown(f"**{r['Task']}**")
                                    st.write(f"👤 Owner: {r['Owner'] if r['Owner'] else '—'}")
                                    
                                    release_str = r['Release Date'].strftime('%d/%m/%Y') if pd.notna(r['Release Date']) else '—'
                                    due_str = r['Due Date'].strftime('%d/%m/%Y') if pd.notna(r['Due Date']) else '—'
                                    st.write(f"🎯 Priority: {r['Priority']} | 📅 Release: {release_str} | Due: {due_str}")
                                    
                                    gr_text = r.get('GR/Mail Object', '')
                                    if gr_text:
                                        parts = gr_text.split('\n', 1) if '\n' in gr_text else [gr_text, '']
                                        
                                        if parts[0].strip():
                                            with st.expander("📋 GR Number"):
                                                st.text(parts[0].strip())
                                        
                                        if len(parts) > 1 and parts[1].strip():
                                            with st.expander("📧 Mail Object"):
                                                st.text(parts[1].strip())
                                    
                                    current_notes = r.get('Notes', '')
                                    if pd.isna(current_notes):
                                        current_notes = ''
                                    notes = st.text_area(
                                        "📝 Notes",
                                        value=current_notes,
                                        key=f"notes_{project}_{r['Task']}_{idx}",
                                        height=80,
                                        placeholder="Add your notes here..."
                                    )
                                    
                                    if notes != current_notes:
                                        df.loc[idx, "Notes"] = notes
                                        df.loc[idx, "Last Update"] = pd.Timestamp.now() + pd.Timedelta(hours=1)
                                        save_to_jsonbin(df, JSONBIN_BIN_ID_PROJECTS)

                                    current_status = r["Progress"]
                                    status = st.radio(
                                        "Status",
                                        options=progress_values,
                                        index=progress_values.index(current_status),
                                        key=f"status_radio_{project}_{r['Task']}_{idx}",
                                        horizontal=True
                                    )
                                    
                                    if status != current_status:
                                        df.loc[idx, "Progress"] = status
                                        df.loc[idx, "Last Update"] = pd.Timestamp.now() + pd.Timedelta(hours=1)
                                        save_to_jsonbin(df, JSONBIN_BIN_ID_PROJECTS)
                                        st.rerun()

                                with cols[1]:
                                    if st.button("🗑️", key=f"delete_task_{project}_{r['Task']}"):
                                        st.session_state.confirm_delete_task = (project, r['Task'])
                                        st.rerun()
                                
                                st.divider()

# ✏️ EDIT MODE
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
                                    
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        p = st.selectbox(
                                            "Status",
                                            progress_values,
                                            index=progress_values.index(row["Progress"]),
                                            key=f"p_{idx}"
                                        )
                                    with col_b:
                                        pr = st.selectbox(
                                            "Priority",
                                            ["Low", "Important", "Urgent"],
                                            index=["Low", "Important", "Urgent"].index(row["Priority"]),
                                            key=f"pr_{idx}"
                                        )
                                    
                                    col_c, col_d = st.columns(2)
                                    with col_c:
                                        r = st.date_input("Release Date", 
                                                         row["Release Date"] if pd.notna(row["Release Date"]) else None, 
                                                         key=f"r_{idx}")
                                    with col_d:
                                        d = st.date_input("Due Date", 
                                                         row["Due Date"] if pd.notna(row["Due Date"]) else None, 
                                                         key=f"d_{idx}")
                                    
                                    gr_combined = row.get("GR/Mail Object", "")
                                    parts = gr_combined.split('\n', 1) if '\n' in gr_combined else [gr_combined, '']
                                    
                                    col_gr, col_mail = st.columns(2)
                                    with col_gr:
                                        gr = st.text_area("📋 GR Number (optional)", 
                                                        parts[0] if parts[0] else "", 
                                                        key=f"gr_{idx}", 
                                                        height=80)
                                    with col_mail:
                                        mail = st.text_area("📧 Mail Object (optional)", 
                                                           parts[1] if len(parts) > 1 else "", 
                                                           key=f"mail_{idx}", 
                                                           height=80)
                                    
                                    gr_combined_save = f"{gr}\n{mail}" if gr or mail else ""
                                    
                                    notes = st.text_area("Notes (optional)", 
                                                        row.get("Notes", ""), 
                                                        key=f"notes_{idx}", 
                                                        height=60)

                                    updated_rows.append((idx, t, o, p, pr, r, d, gr_combined_save, notes))
                                    st.divider()

                            st.markdown("### ➕ Add new tasks to this project")
                            add_key = f"add_boxes_{project}"
                            if add_key not in st.session_state:
                                st.session_state[add_key] = 1
                                
                            new_tasks = []

                            for i in range(st.session_state[add_key]):
                                with st.container():
                                    st.markdown(f"**New Task {i+1}**")
                                    t = st.text_input("Task", key=f"nt_{project}_{i}")
                                    o = st.text_input("Owner (optional)", key=f"no_{project}_{i}")
                                    
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        p = st.selectbox("Status", progress_values, key=f"np_{project}_{i}")
                                    with col_b:
                                        pr = st.selectbox("Priority", ["Low", "Important", "Urgent"], key=f"npr_{project}_{i}")
                                    
                                    col_c, col_d = st.columns(2)
                                    with col_c:
                                        r = st.date_input("Release Date (optional)", value=None, key=f"nr_{project}_{i}")
                                    with col_d:
                                        d = st.date_input("Due Date (optional)", value=None, key=f"nd_{project}_{i}")
                                    
                                    col_gr, col_mail = st.columns(2)
                                    with col_gr:
                                        gr = st.text_area("📋 GR Number (optional)", key=f"ngr_{project}_{i}", height=80)
                                    with col_mail:
                                        mail = st.text_area("📧 Mail Object (optional)", key=f"nmail_{project}_{i}", height=80)
                                    
                                    gr_combined = f"{gr}\n{mail}" if gr or mail else ""
                                    
                                    notes = st.text_area("Notes (optional)", key=f"nnotes_{project}_{i}", height=60)
                                    
                                    if t:
                                        new_tasks.append((t, o, p, pr, r, d, gr_combined, notes))
                                    st.divider()

                            col1, col2, col3 = st.columns(3)
                            if col1.button("➕ Add task", key=f"add_{project}"):
                                st.session_state[add_key] += 1
                                st.rerun()

                            if col2.button("💾 Save changes", key=f"save_{project}", type="primary"):
                                df.loc[df["Project"] == project, "Area"] = new_area
                                df.loc[df["Project"] == project, "Project"] = new_name
                                df.loc[df["Project"] == project, "Last Update"] = pd.Timestamp.now() + pd.Timedelta(hours=1)

                                for idx, t, o, p, pr, r, d, gr, notes in updated_rows:
                                    df.loc[idx, "Task"] = t
                                    df.loc[idx, "Owner"] = o
                                    df.loc[idx, "Progress"] = p
                                    df.loc[idx, "Priority"] = pr
                                    df.loc[idx, "Release Date"] = pd.Timestamp(r) if r else pd.NaT
                                    df.loc[idx, "Due Date"] = pd.Timestamp(d) if d else pd.NaT
                                    df.loc[idx, "GR/Mail Object"] = gr
                                    df.loc[idx, "Notes"] = notes
                                    df.loc[idx, "Last Update"] = pd.Timestamp.now() + pd.Timedelta(hours=1)

                                new_rows = []
                                for t, o, p, pr, r, d, gr, notes in new_tasks:
                                    new_rows.append({
                                        "Area": new_area,
                                        "Project": new_name,
                                        "Task": t,
                                        "Owner": o,
                                        "Progress": p,
                                        "Priority": pr,
                                        "Release Date": pd.Timestamp(r) if r else pd.NaT,
                                        "Due Date": pd.Timestamp(d) if d else pd.NaT,
                                        "GR/Mail Object": gr,
                                        "Notes": notes,
                                        "Last Update": pd.Timestamp.now() + pd.Timedelta(hours=1),
                                        "Order": df["Order"].max() + 1
                                    })
                                
                                if new_rows:
                                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

                                save_to_jsonbin(df, JSONBIN_BIN_ID_PROJECTS)
                                st.session_state.edit_mode = False
                                if add_key in st.session_state:
                                    st.session_state[add_key] = 1
                                st.success("✅ Changes saved successfully!")
                                st.rerun()

                            if col3.button("❌ Cancel", key=f"cancel_{project}"):
                                st.session_state.edit_mode = False
                                if add_key in st.session_state:
                                    st.session_state[add_key] = 1
                                st.rerun()
            
            st.divider()
        
        # ===== COMPLETED SECTION (identico alla sezione In Progress ma per progetti completati) =====
        if completed_projects:
            st.markdown("### ✅ Completed")
            
            completed_by_area = {}
            for project in completed_projects:
                area = df[df["Project"] == project]["Area"].iloc[0]
                if area not in completed_by_area:
                    completed_by_area[area] = []
                completed_by_area[area].append(project)
            
            for area in sorted(completed_by_area.keys()):
                st.markdown(f"#### 🏢 {area}")
                
                for project in sorted(completed_by_area[area]):
                    proj_df = df[df["Project"] == project]
                    completion = int(proj_df["Progress"].map(progress_score).mean() * 100)
                    
                    header_text = f"📁 {project} — {completion}%"
                    
                    if st.session_state.delete_mode:
                        cols = st.columns([8, 1])
                        with cols[0]:
                            expand = st.expander(header_text, expanded=False)
                        with cols[1]:
                            if st.button("🗑️", key=f"delete_proj_comp_{project}"):
                                st.session_state.confirm_delete_project = project
                                st.rerun()
                    else:
                        expand = st.expander(header_text, expanded=False)
                    
                    with expand:
                        st.progress(completion / 100)
                        
                        if not st.session_state.edit_mode:
                            for idx, r in proj_df.iterrows():
                                st.markdown(f"**{r['Task']}**")
                                st.write(f"👤 Owner: {r['Owner'] if r['Owner'] else '—'}")
                                release_str = r['Release Date'].strftime('%d/%m/%Y') if pd.notna(r['Release Date']) else '—'
                                due_str = r['Due Date'].strftime('%d/%m/%Y') if pd.notna(r['Due Date']) else '—'
                                st.write(f"🎯 Priority: {r['Priority']} | 📅 Release: {release_str} | Due: {due_str}")
                                
                                gr_text = r.get('GR/Mail Object', '')
                                if gr_text:
                                    parts = gr_text.split('\n', 1) if '\n' in gr_text else [gr_text, '']
                                    
                                    if parts[0].strip():
                                        with st.expander("📋 GR Number"):
                                            st.text(parts[0].strip())
                                    
                                    if len(parts) > 1 and parts[1].strip():
                                        with st.expander("📧 Mail Object"):
                                            st.text(parts[1].strip())
                                
                                if r.get('Notes') and r['Notes']:
                                    with st.expander("📝 Notes"):
                                        st.text(r['Notes'])
                                
                                st.write(f"✅ Status: {r['Progress']}")
                                st.divider()

    elif not st.session_state.add_project and len(df) == 0:
        st.info("📝 No projects yet. Click '➕ Project' to create your first project!")

    # FOOTER
    st.divider()
    if len(df) > 0:
        total_tasks = len(df)
        completed_tasks = len(df[df["Progress"] == "Completed"])
        st.caption(f"📊 Total projects: {df['Project'].nunique()} | Tasks: {completed_tasks}/{total_tasks} completed ({int(completed_tasks/total_tasks*100)}%)")

# ======================================================
# 📅 END OF MONTH ACTIVITIES (Mantieni identico al codice originale)
# ======================================================
if st.session_state.section == "EOM":

    st.subheader("📅 End of Month Activities")
    
    if len(eom_df) > 0 and "Last Update" in eom_df.columns:
        try:
            last_update_eom = pd.to_datetime(eom_df["Last Update"]).max()
            st.caption(f"🕒 Last update: {last_update_eom.strftime('%d/%m/%Y %H:%M')}")
        except:
            st.caption(f"🕒 Last update: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")

    months = get_next_months(6, include_previous=True)
    eom_dates = [last_working_day(y, m) for y, m in months]
    month_cols = [d.strftime("%d %B %Y") for d in eom_dates]
    current_month_col = month_cols[0]

    for col in EOM_BASE_COLUMNS:
        if col not in eom_df.columns:
            if col == "🗑️ Delete":
                eom_df[col] = False
            else:
                eom_df[col] = ""

    for c in month_cols:
        if c not in eom_df.columns:
            eom_df[c] = "⚪"

    eom_df = clean_eom_dataframe(eom_df, month_cols)

    completed_cols = []
    if len(eom_df) > 0:
        for col in month_cols:
            if col in eom_df.columns:
                values = eom_df[col].unique()
                if all(v in ["🟢", "⚪"] for v in values):
                    completed_cols.append(col)

    col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1, 1, 1])
    with col1:
        st.caption(f"🎯 **Current working month**: {current_month_col}")
    with col2:
        if st.button("📅 Months", use_container_width=True):
            st.session_state.show_month_manager = not st.session_state.show_month_manager
            st.rerun()
    with col3:
        if st.button("🔍 Filters" if not st.session_state.show_eom_filters else "🔍 Hide", 
                     use_container_width=True):
            st.session_state.show_eom_filters = not st.session_state.show_eom_filters
            st.rerun()
    with col4:
        if st.button("✏️ Edit" if not st.session_state.eom_edit_mode else "✅ View", 
                     use_container_width=True):
            st.session_state.eom_edit_mode = not st.session_state.eom_edit_mode
            st.rerun()
    with col5:
        if st.button("🗑️ Delete" if not st.session_state.eom_bulk_delete else "❌ Cancel", 
                     use_container_width=True):
            st.session_state.eom_bulk_delete = not st.session_state.eom_bulk_delete
            st.rerun()

    # Month Manager (uguale al codice originale)
    if st.session_state.show_month_manager:
        with st.expander("📅 Month Visibility Manager", expanded=True):
            st.markdown("**Manage which months to display in the table**")
            
            num_cols = 3
            cols = st.columns(num_cols)
            
            for i, col in enumerate(month_cols):
                with cols[i % num_cols]:
                    month_name = col.split()[1]
                    year = col.split()[2]
                    
                    is_hidden = col in st.session_state.hidden_months
                    is_completed = col in completed_cols
                    is_current = col == current_month_col
                    
                    label = f"{month_name} {year}"
                    if is_current:
                        label = f"🎯 {label} (Current)"
                    elif is_completed:
                        label = f"✅ {label}"
                    
                    visible = st.checkbox(
                        label,
                        value=not is_hidden,
                        key=f"month_visibility_{col}",
                        help=f"{'Completed' if is_completed else 'In progress'}"
                    )
                    
                    if not visible and col not in st.session_state.hidden_months:
                        st.session_state.hidden_months.append(col)
                    elif visible and col in st.session_state.hidden_months:
                        st.session_state.hidden_months.remove(col)
            
            st.divider()
            col_reset, col_hide_completed, col_show_all = st.columns(3)
            
            with col_reset:
                if st.button("🔄 Reset to Default", use_container_width=True):
                    st.session_state.hidden_months = []
                    st.session_state.show_completed_months = False
                    st.rerun()
            
            with col_hide_completed:
                if st.button("🔒 Hide All Completed", use_container_width=True):
                    st.session_state.hidden_months = completed_cols.copy()
                    st.rerun()
            
            with col_show_all:
                if st.button("👁️ Show All Months", use_container_width=True):
                    st.session_state.hidden_months = []
                    st.rerun()

    # ADD ACTIVITY
    with st.expander("➕ Add new End-of-Month Activity", expanded=st.session_state.eom_edit_mode):
        c1, c2, c3 = st.columns(3)
        area = c1.text_input("Area", key="eom_area")
        id_macro = c2.text_input("ID Macro", key="eom_macro")
        id_micro = c3.text_input("ID Micro", key="eom_micro")

        activity = st.text_input("Activity", key="eom_activity")
        c4, c5 = st.columns(2)
        frequency = c4.text_input("Frequency (e.g., Monthly, Quarterly)", key="eom_freq")
        files = c5.text_input("Files", key="eom_files")

        if st.button("➕ Add activity", type="primary", key="eom_add_btn"):
            if not activity:
                st.error("❌ Activity name is required!")
            else:
                next_order = eom_df["Order"].max() + 1 if len(eom_df) > 0 else 0
                row = {
                    "Area": area,
                    "ID Macro": id_macro,
                    "ID Micro": id_micro,
                    "Activity": activity,
                    "Frequency": frequency,
                    "Files": files,
                    "🗑️ Delete": False,
                    "Last Update": pd.Timestamp.now() + pd.Timedelta(hours=1),
                    "Order": next_order
                }
                for c in month_cols:
                    row[c] = "⚪"

                eom_df = pd.concat([eom_df, pd.DataFrame([row])], ignore_index=True)
                save_to_jsonbin(eom_df, JSONBIN_BIN_ID_EOM)
                st.success(f"✅ Activity '{activity}' added!")
                st.rerun()

    st.divider()

    # TABLE VIEW (come nel codice originale ma con save_to_jsonbin)
    if not st.session_state.eom_edit_mode and not st.session_state.eom_bulk_delete and len(eom_df) > 0:
        eom_df = eom_df.sort_values('Order').reset_index(drop=True)
        
        visible_cols = [col for col in month_cols if col not in st.session_state.hidden_months]
        
        display_cols = ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"] + visible_cols
        display_df = eom_df[display_cols].copy()
        
        column_config = {}
        
        for i, col in enumerate(visible_cols):
            is_current = (col == current_month_col)
            column_config[col] = st.column_config.SelectboxColumn(
                col,
                help="🎯 **Current working month**" if is_current else "Future month",
                options=["⚪", "🟢", "🔴"],
                default="⚪",
                width="small"
            )

        hidden_count = len(st.session_state.hidden_months)
        if hidden_count > 0:
            hidden_month_names = [c.split()[1] for c in st.session_state.hidden_months]
            st.info(f"📅 **{hidden_count} month(s) hidden**: {', '.join(hidden_month_names)}. Click '📅 Months' to manage visibility.")

        edited = st.data_editor(
            display_df,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            hide_index=True,
            key="eom_editor",
            disabled=["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]
        )

        for col in visible_cols:
            if col in edited.columns:
                if not edited[col].equals(eom_df[col]):
                    eom_df[col] = edited[col]
                    eom_df["Last Update"] = pd.Timestamp.now() + pd.Timedelta(hours=1)

        save_to_jsonbin(eom_df, JSONBIN_BIN_ID_EOM)

        st.divider()
        
        total_activities = len(eom_df)
        completed_current = (eom_df[current_month_col] == "🟢").sum() if current_month_col in eom_df.columns else 0
        progress_pct = int((completed_current / total_activities * 100)) if total_activities > 0 else 0
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.metric(
                label="Current Month Progress",
                value=f"{completed_current}/{total_activities}",
                delta=f"{progress_pct}%"
            )
        with col2:
            if progress_pct == 100:
                st.success("🎉 All activities completed!")
            elif progress_pct >= 50:
                st.info(f"💪 Keep going! {total_activities - completed_current} left")
            else:
                st.warning(f"🚀 Let's get started!")

    elif not st.session_state.eom_edit_mode and not st.session_state.eom_bulk_delete and len(eom_df) == 0:
        st.info("📝 No End-of-Month activities yet. Add your first activity above!")

    st.divider()
    if len(eom_df) > 0:
        total_activities = len(eom_df)
        completed_current_month = (eom_df[current_month_col] == "🟢").sum() if current_month_col in eom_df.columns else 0
        st.caption(f"📊 Total activities: {total_activities} | Current month completed: {completed_current_month}/{total_activities}")
# ======================================================
# 📅 ATTENDANCE SECTION
# ======================================================
if st.session_state.section == "Attendance":
    st.subheader("📅 Team Attendance Tracker")
    
    # Month navigation
    col1, col2, col3, col4, col5 = st.columns([2, 1, 2, 1, 2])
    
    with col2:
        if st.button("◀️ Previous", use_container_width=True):
            current = st.session_state.selected_attendance_month
            if current.month == 1:
                st.session_state.selected_attendance_month = date(current.year - 1, 12, 1)
            else:
                st.session_state.selected_attendance_month = date(current.year, current.month - 1, 1)
            st.rerun()
    
    with col3:
        selected_month = st.session_state.selected_attendance_month
        st.markdown(f"### {selected_month.strftime('%B %Y')}")
    
    with col4:
        if st.button("Next ▶️", use_container_width=True):
            current = st.session_state.selected_attendance_month
            if current.month == 12:
                st.session_state.selected_attendance_month = date(current.year + 1, 1, 1)
            else:
                st.session_state.selected_attendance_month = date(current.year, current.month + 1, 1)
            st.rerun()
    
    with col5:
        if st.button("📅 Today", use_container_width=True):
            st.session_state.selected_attendance_month = date.today().replace(day=1)
            st.rerun()
    
    st.divider()
    
    # Get all dates for selected month
    year = selected_month.year
    month = selected_month.month
    month_dates = get_month_dates(year, month)
    
    # Create calendar view for each team member
    for member in TEAM_MEMBERS:
        with st.expander(f"👤 {member}", expanded=True):
            
            # Create a grid for the calendar
            # Get day names
            days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            
            # Get first day of month and calculate offset
            first_day = month_dates[0]
            first_weekday = first_day.weekday()  # 0 = Monday
            
            # Create header
            header_cols = st.columns(7)
            for i, day_name in enumerate(days_header):
                with header_cols[i]:
                    st.markdown(f"**{day_name}**")
            
            st.divider()
            
            # Create calendar grid
            week_dates = []
            current_week = [None] * first_weekday  # Empty cells before first day
            
            for day_date in month_dates:
                current_week.append(day_date)
                
                if len(current_week) == 7:
                    week_dates.append(current_week)
                    current_week = []
            
            # Add last week if not complete
            if current_week:
                while len(current_week) < 7:
                    current_week.append(None)
                week_dates.append(current_week)
            
            # Display calendar weeks
            for week in week_dates:
                week_cols = st.columns(7)
                
                for i, day_date in enumerate(week):
                    with week_cols[i]:
                        if day_date is None:
                            st.write("")
                        else:
                            # Get attendance for this day and member
                            day_str = day_date.strftime('%Y-%m-%d')
                            mask = (attendance_df["Date"].dt.strftime('%Y-%m-%d') == day_str) & (attendance_df["Member"] == member)
                            
                            current_type = ""
                            current_notes = ""
                            
                            if mask.any():
                                current_type = attendance_df[mask]["Type"].iloc[0]
                                current_notes = attendance_df[mask]["Notes"].iloc[0]
                            
                            # Display day number
                            is_weekend = day_date.weekday() >= 5
                            is_today = day_date == date.today()
                            
                            day_label = f"**{day_date.day}**"
                            if is_today:
                                day_label = f"🔵 **{day_date.day}**"
                            elif is_weekend:
                                day_label = f"⚪ {day_date.day}"
                            
                            st.markdown(day_label)
                            
                            # Attendance type selector
                            att_type = st.selectbox(
                                "Type",
                                options=ATTENDANCE_TYPES,
                                index=ATTENDANCE_TYPES.index(current_type) if current_type in ATTENDANCE_TYPES else 0,
                                key=f"att_{member}_{day_str}",
                                label_visibility="collapsed"
                            )
                            
                            # Notes
                            notes = st.text_input(
                                "Notes",
                                value=current_notes,
                                key=f"notes_{member}_{day_str}",
                                placeholder="Notes...",
                                label_visibility="collapsed"
                            )
                            
                            # Save changes
                            if att_type != current_type or notes != current_notes:
                                # Remove old entry if exists
                                attendance_df = attendance_df[~mask]
                                
                                # Add new entry if type is not empty
                                if att_type:
                                    new_entry = pd.DataFrame([{
                                        "Date": pd.Timestamp(day_date),
                                        "Member": member,
                                        "Type": att_type,
                                        "Notes": notes
                                    }])
                                    attendance_df = pd.concat([attendance_df, new_entry], ignore_index=True)
                                
                                save_to_jsonbin(attendance_df, JSONBIN_BIN_ID_ATTENDANCE)
            
            st.divider()
            
            # Monthly summary for this member
            member_month_data = attendance_df[
                (attendance_df["Member"] == member) & 
                (attendance_df["Date"].dt.year == year) & 
                (attendance_df["Date"].dt.month == month)
            ]
            
            if len(member_month_data) > 0:
                summary_cols = st.columns(5)
                
                for i, att_type in enumerate(["🏢 Office", "🏠 Smart Working", "🌴 Vacation", "⏰ Hourly Leave", "💰 Time Bank"]):
                    count = len(member_month_data[member_month_data["Type"] == att_type])
                    with summary_cols[i]:
                        st.metric(att_type.split()[1], count)
    
    st.divider()
    
    # Overall team statistics for the month
    st.subheader("📊 Team Summary")
    
    team_month_data = attendance_df[
        (attendance_df["Date"].dt.year == year) & 
        (attendance_df["Date"].dt.month == month)
    ]
    
    if len(team_month_data) > 0:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            office_count = len(team_month_data[team_month_data["Type"] == "🏢 Office"])
            st.metric("🏢 Total Office Days", office_count)
        
        with col2:
            smart_count = len(team_month_data[team_month_data["Type"] == "🏠 Smart Working"])
            st.metric("🏠 Total Smart Working", smart_count)
        
        with col3:
            vacation_count = len(team_month_data[team_month_data["Type"] == "🌴 Vacation"])
            st.metric("🌴 Total Vacations", vacation_count)
        
        with col4:
            hourly_count = len(team_month_data[team_month_data["Type"] == "⏰ Hourly Leave"])
            st.metric("⏰ Total Hourly Leaves", hourly_count)
        
        with col5:
            bank_count = len(team_month_data[team_month_data["Type"] == "💰 Time Bank"])
            st.metric("💰 Total Time Bank", bank_count)
        
        st.divider()
        
        # Team presence chart
        st.markdown("### 📈 Daily Team Presence")
        
        daily_presence = []
        for day_date in month_dates:
            day_str = day_date.strftime('%Y-%m-%d')
            day_data = team_month_data[team_month_data["Date"].dt.strftime('%Y-%m-%d') == day_str]
            
            office = len(day_data[day_data["Type"] == "🏢 Office"])
            smart = len(day_data[day_data["Type"] == "🏠 Smart Working"])
            
            daily_presence.append({
                "Date": day_date.strftime('%d/%m'),
                "Office": office,
                "Smart Working": smart,
                "Total Present": office + smart
            })
        
        if daily_presence:
            presence_df = pd.DataFrame(daily_presence)
            st.line_chart(presence_df.set_index("Date")[["Office", "Smart Working", "Total Present"]])
    else:
        st.info("📝 No attendance data for this month yet. Start marking attendance above!")
    
    st.divider()
    st.caption(f"📅 Attendance tracking for {selected_month.strftime('%B %Y')} | Team: {', '.join(TEAM_MEMBERS)}")
