import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import time

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="RM Insurance Planner", layout="wide")

PROJECT_COLUMNS = [
    "Area", "Project", "Task", "Owner",
    "Progress", "Priority", "Release Date", "Due Date", "GR/Mail Object", "Notes", "Last Update", "Order"
]

EOM_BASE_COLUMNS = [
    "Area", "ID Macro", "ID Micro",
    "Activity", "Frequency", "Files", "🗑️ Delete", "Last Update", "Order"
]

# =========================
# GOOGLE SHEETS FUNCTIONS - VERSIONE STABILE
# =========================
@st.cache_resource
def get_gsheet_service():
    """Crea connessione a Google Sheets"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build('sheets', 'v4', credentials=credentials)

def save_to_gsheet(df, sheet_name):
    """Salva DataFrame su Google Sheets - VERSIONE STABILE"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            service = get_gsheet_service()
            spreadsheet_id = st.secrets["spreadsheet_id"]
            
            # Prepara i dati in modo sicuro
            df_copy = df.copy()
            
            # Converti TUTTI i tipi in stringhe in modo sicuro
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].apply(
                        lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else ''
                    )
                elif df_copy[col].dtype == 'bool':
                    df_copy[col] = df_copy[col].apply(lambda x: 'True' if x else 'False')
                else:
                    df_copy[col] = df_copy[col].apply(
                        lambda x: '' if pd.isna(x) else str(x)
                    )
            
            # Converti in lista (header + dati)
            values = [df_copy.columns.tolist()] + df_copy.values.tolist()
            
            # Prima cancella tutto il foglio
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1:ZZ10000"
            ).execute()
            
            # Aspetta un momento per assicurare che la cancellazione sia completata
            time.sleep(0.5)
            
            # Poi scrivi i nuovi dati
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            return True
            
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)  # Aspetta prima di riprovare
                continue
            else:
                st.error(f"❌ Errore nel salvataggio dopo {max_retries} tentativi: {e}")
                return False
    
    return False

def load_from_gsheet(sheet_name, columns, date_cols=None):
    """Carica DataFrame da Google Sheets - VERSIONE STABILE"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            service = get_gsheet_service()
            spreadsheet_id = st.secrets["spreadsheet_id"]
            
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:ZZ"
            ).execute()
            
            values = result.get('values', [])
            
            # Se non ci sono dati, ritorna DataFrame vuoto
            if not values or len(values) < 2:
                df = pd.DataFrame(columns=columns)
                if "Order" in columns:
                    df["Order"] = []
                return df
            
            # Crea DataFrame (prima riga = header)
            df = pd.DataFrame(values[1:], columns=values[0])
            
            # Gestisci colonne mancanti
            for col in columns:
                if col not in df.columns:
                    if col in ["Release Date", "Due Date", "Last Update"]:
                        df[col] = pd.NaT
                    elif col == "Order":
                        df[col] = range(len(df))
                    elif col == "🗑️ Delete":
                        df[col] = False
                    else:
                        df[col] = ""
            
            # Converti date
            if date_cols:
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Converti Order in int
            if "Order" in df.columns:
                df["Order"] = pd.to_numeric(df["Order"], errors='coerce').fillna(0).astype(int)
            
            # Converti booleani
            if "🗑️ Delete" in df.columns:
                df["🗑️ Delete"] = df["🗑️ Delete"].apply(
                    lambda x: True if str(x).lower() in ['true', '1', 'yes'] else False
                )
            
            return df
            
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
                continue
            else:
                st.error(f"❌ Errore nel caricamento dopo {max_retries} tentativi: {e}")
                return pd.DataFrame(columns=columns)
    
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
                "🟢" if str(x) in ["True", "true", "Done", "🟢", "1"] 
                else "🔴" if str(x) in ["False", "false", "Undone", "🔴", "0"]
                else "⚪"
            )
    
    if "🗑️ Delete" in df.columns:
        df["🗑️ Delete"] = df["🗑️ Delete"].apply(
            lambda x: True if str(x).lower() in ['true', '1', 'yes'] else False
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
    """Genera i prossimi N mesi"""
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

# =========================
# LOAD DATA
# =========================
df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
df["Owner"] = df["Owner"].fillna("")
df["GR/Mail Object"] = df["GR/Mail Object"].fillna("")
df["Notes"] = df["Notes"].fillna("")

eom_df = load_from_gsheet("EOM", EOM_BASE_COLUMNS)
if "Last Update" not in eom_df.columns:
    eom_df["Last Update"] = pd.Timestamp.now()
if "Order" not in eom_df.columns:
    eom_df["Order"] = range(len(eom_df))

# =========================
# HEADER + NAVIGATION
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
        
        original_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=['Release Date', 'Due Date'])
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
                # Ricarica i dati freschi prima di aggiungere
                fresh_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
                
                new_rows = []
                next_order = fresh_df["Order"].max() + 1 if len(fresh_df) > 0 else 0
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
                        "Last Update": pd.Timestamp.now(),
                        "Order": next_order
                    })
                    next_order += 1
                
                fresh_df = pd.concat([fresh_df, pd.DataFrame(new_rows)], ignore_index=True)
                
                if save_to_gsheet(fresh_df, "Projects"):
                    st.session_state.add_project = False
                    st.session_state.task_boxes = 1
                    st.success(f"✅ Project '{project}' created successfully!")
                    time.sleep(1)
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
                # Ricarica dati freschi prima di cancellare
                fresh_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
                fresh_df = fresh_df[fresh_df["Project"] != project].reset_index(drop=True)
                
                if save_to_gsheet(fresh_df, "Projects"):
                    st.success(f"✅ Project '{project}' deleted")
                    st.session_state.confirm_delete_project = None
                    st.session_state.delete_mode = False
                    time.sleep(1)
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
        
        # Ricarica dati freschi
        fresh_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
        mask = (fresh_df["Project"] == project_name) & (fresh_df["Task"] == task_name)
        
        if mask.any():
            st.warning(f"⚠️ Are you sure you want to delete the task **{task_name}**? This cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, delete task", key=f"confirm_del_task_{task_name}", type="primary"):
                    fresh_df = fresh_df[~mask].reset_index(drop=True)
                    if save_to_gsheet(fresh_df, "Projects"):
                        st.success(f"✅ Task '{task_name}' deleted")
                        st.session_state.confirm_delete_task = None
                        time.sleep(1)
                        st.rerun()
            with col2:
                if st.button("❌ Cancel", key=f"cancel_del_task_{task_name}"):
                    st.session_state.confirm_delete_task = None
                    st.rerun()
            st.stop()

    # ======================================================
    # 📁 PROJECT VIEW (SIMPLIFIED - Continue with existing logic)
    # ======================================================
    if not st.session_state.add_project and len(df) > 0:
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
        
        # Display projects (keeping existing display logic but improving save operations)
        if in_progress_projects:
            st.markdown("### 📂 In Progress")
            
            for project in in_progress_projects:
                proj_df = df[df["Project"] == project]
                area = proj_df["Area"].iloc[0]
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
                                    # Ricarica e salva
                                    fresh_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
                                    fresh_df.loc[idx, "Notes"] = notes
                                    fresh_df.loc[idx, "Last Update"] = pd.Timestamp.now()
                                    save_to_gsheet(fresh_df, "Projects")

                                current_status = r["Progress"]
                                status = st.radio(
                                    "Status",
                                    options=progress_values,
                                    index=progress_values.index(current_status),
                                    key=f"status_radio_{project}_{r['Task']}_{idx}",
                                    horizontal=True
                                )
                                
                                if status != current_status:
                                    # Ricarica e salva
                                    fresh_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
                                    fresh_df.loc[idx, "Progress"] = status
                                    fresh_df.loc[idx, "Last Update"] = pd.Timestamp.now()
                                    if save_to_gsheet(fresh_df, "Projects"):
                                        time.sleep(0.5)
                                        st.rerun()

                            with cols[1]:
                                if st.button("🗑️", key=f"delete_task_{project}_{r['Task']}"):
                                    st.session_state.confirm_delete_task = (project, r['Task'])
                                    st.rerun()
                            
                            st.divider()
        
        if completed_projects:
            st.markdown("### ✅ Completed")
            for project in completed_projects:
                proj_df = df[df["Project"] == project]
                completion = int(proj_df["Progress"].map(progress_score).mean() * 100)
                
                header_text = f"📁 {project} — {completion}%"
                expand = st.expander(header_text, expanded=False)
                
                with expand:
                    st.progress(completion / 100)
                    for idx, r in proj_df.iterrows():
                        st.markdown(f"**{r['Task']}**")
                        st.write(f"👤 Owner: {r['Owner'] if r['Owner'] else '—'}")
                        st.write(f"✅ Status: {r['Progress']}")
                        st.divider()

    elif not st.session_state.add_project and len(df) == 0:
        st.info("📝 No projects yet. Click '➕ Project' to create your first project!")

    st.divider()
    if len(df) > 0:
        total_tasks = len(df)
        completed_tasks = len(df[df["Progress"] == "Completed"])
        st.caption(f"📊 Total projects: {df['Project'].nunique()} | Tasks: {completed_tasks}/{total_tasks} completed ({int(completed_tasks/total_tasks*100) if total_tasks > 0 else 0}%)")

# ======================================================
# 📅 END OF MONTH ACTIVITIES
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

    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        st.caption(f"🎯 **Current working month**: {current_month_col}")
    with col2:
        if st.button("🔍 Filters" if not st.session_state.show_eom_filters else "🔍 Hide", 
                     use_container_width=True):
            st.session_state.show_eom_filters = not st.session_state.show_eom_filters
            st.rerun()
    with col3:
    if st.button("✏️ Edit" if not st.session_state.eom_edit_mode else "✅ View", 
                     use_container_width=True):
            st.session_state.eom_edit_mode = not st.session_state.eom_edit_mode
            st.rerun()
    with col4:
        if st.button("🗑️ Delete" if not st.session_state.eom_bulk_delete else "❌ Cancel", 
                     use_container_width=True):
            st.session_state.eom_bulk_delete = not st.session_state.eom_bulk_delete
            st.rerun()

    st.divider()

    # ======================================================
    # BULK DELETE MODE
    # ======================================================
    if st.session_state.eom_bulk_delete and len(eom_df) > 0:
        st.warning("🗑️ **Delete Mode**: Select activities to delete")
        
        selected_to_delete = []
        for idx, row in eom_df.iterrows():
            col1, col2 = st.columns([1, 10])
            with col1:
                if st.checkbox("", key=f"bulk_select_{idx}"):
                    selected_to_delete.append(idx)
            with col2:
                st.write(f"**{row['Activity']}** ({row['Area']} - {row['ID Macro']}/{row['ID Micro']})")
        
        st.divider()
        
        if selected_to_delete:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button(f"🗑️ Delete {len(selected_to_delete)} selected", type="primary", key="confirm_bulk_delete"):
                    # Ricarica dati freschi
                    fresh_eom = load_from_gsheet("EOM", EOM_BASE_COLUMNS)
                    fresh_eom = fresh_eom.drop(selected_to_delete).reset_index(drop=True)
                    
                    if save_to_gsheet(fresh_eom, "EOM"):
                        st.success(f"✅ {len(selected_to_delete)} activities deleted!")
                        st.session_state.eom_bulk_delete = False
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("👆 Select activities above to delete them")
        
        st.divider()

    with st.expander("➕ Add new End-of-Month Activity", expanded=False):
        c1, c2, c3 = st.columns(3)
        area = c1.text_input("Area", key="eom_area")
        id_macro = c2.text_input("ID Macro", key="eom_macro")
        id_micro = c3.text_input("ID Micro", key="eom_micro")

        activity = st.text_input("Activity", key="eom_activity")
        c4, c5 = st.columns(2)
        frequency = c4.text_input("Frequency", key="eom_freq")
        files = c5.text_input("Files", key="eom_files")

        if st.button("➕ Add activity", type="primary", key="eom_add_btn"):
            if not activity:
                st.error("❌ Activity name is required!")
            else:
                # Ricarica dati freschi
                fresh_eom = load_from_gsheet("EOM", EOM_BASE_COLUMNS)
                
                next_order = fresh_eom["Order"].max() + 1 if len(fresh_eom) > 0 else 0
                row = {
                    "Area": area,
                    "ID Macro": id_macro,
                    "ID Micro": id_micro,
                    "Activity": activity,
                    "Frequency": frequency,
                    "Files": files,
                    "🗑️ Delete": False,
                    "Last Update": pd.Timestamp.now(),
                    "Order": next_order
                }
                for c in month_cols:
                    row[c] = "⚪"

                fresh_eom = pd.concat([fresh_eom, pd.DataFrame([row])], ignore_index=True)
                if save_to_gsheet(fresh_eom, "EOM"):
                    st.success(f"✅ Activity '{activity}' added!")
                    time.sleep(1)
                    st.rerun()

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

        edited = st.data_editor(
            display_df,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            hide_index=True,
            key="eom_editor",
            disabled=["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]
        )

        # Salva solo se ci sono modifiche
        has_changes = False
        for col in visible_cols:
            if col in edited.columns:
                if not edited[col].equals(eom_df[col]):
                    has_changes = True
                    eom_df[col] = edited[col]
                    eom_df["Last Update"] = pd.Timestamp.now()

        if has_changes:
            save_to_gsheet(eom_df, "EOM")

        st.divider()
        
        total_activities = len(eom_df)
        completed_current = (eom_df[current_month_col] == "🟢").sum() if current_month_col in eom_df.columns else 0
        progress_pct = int((completed_current / total_activities * 100)) if total_activities > 0 else 0
        
        st.metric(
            label="Current Month Progress",
            value=f"{completed_current}/{total_activities}",
            delta=f"{progress_pct}%"
        )

    elif not st.session_state.eom_edit_mode and not st.session_state.eom_bulk_delete and len(eom_df) == 0:
        st.info("📝 No End-of-Month activities yet. Add your first activity above!")

    st.divider()
    if len(eom_df) > 0:
        total_activities = len(eom_df)
        completed_current_month = (eom_df[current_month_col] == "🟢").sum() if current_month_col in eom_df.columns else 0
        st.caption(f"📊 Total activities: {total_activities} | Current month completed: {completed_current_month}/{total_activities}")
