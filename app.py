import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import time
import socket
import re
import hashlib

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
# ✅ NEW: EOM STATUS DOTS (white default + gray/green/red)
# =========================
EOM_WHITE = "⚪"   # default / not answered
EOM_GRAY  = "⚫"   # not to do (excluded from denominator)
EOM_GREEN = "🟢"   # done
EOM_RED   = "🔴"   # not done
EOM_STATUS_OPTIONS = [EOM_WHITE, EOM_GRAY, EOM_GREEN, EOM_RED]

# =========================
# GOOGLE SHEETS FUNCTIONS - VERSIONE OTTIMIZZATA
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

            # Imposta timeout
            socket.setdefaulttimeout(15)

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
            time.sleep(0.3)

            # Poi scrivi i nuovi dati
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                body={'values': values}
            ).execute()

            # Invalida cache dopo salvataggio
            st.cache_data.clear()

            return True

        except socket.timeout:
            retry_count += 1
            if retry_count < max_retries:
                st.warning(f"⏱️ Timeout - tentativo {retry_count}/{max_retries}...")
                time.sleep(2)
                continue
            else:
                st.error("❌ Timeout: impossibile connettersi a Google Sheets")
                return False
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
                continue
            else:
                st.error(f"❌ Errore nel salvataggio dopo {max_retries} tentativi: {e}")
                return False

    return False

def load_from_gsheet(sheet_name, columns, date_cols=None):
    """Carica DataFrame da Google Sheets - VERSIONE OTTIMIZZATA"""
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            service = get_gsheet_service()
            spreadsheet_id = st.secrets["spreadsheet_id"]

            # Imposta timeout
            socket.setdefaulttimeout(15)

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

        except socket.timeout:
            retry_count += 1
            if retry_count < max_retries:
                st.warning(f"⏱️ Timeout caricamento - tentativo {retry_count}/{max_retries}...")
                time.sleep(2)
                continue
            else:
                st.error("❌ Timeout: impossibile caricare i dati da Google Sheets")
                return pd.DataFrame(columns=columns)
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
# LOAD DATA CON CACHE
# =========================
@st.cache_data(ttl=30)  # Cache per 30 secondi
def load_projects_data():
    """Carica dati Projects con cache"""
    df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
    df["Owner"] = df["Owner"].fillna("")
    df["GR/Mail Object"] = df["GR/Mail Object"].fillna("")
    df["Notes"] = df["Notes"].fillna("")
    return df

@st.cache_data(ttl=30)  # Cache per 30 secondi
def load_eom_data():
    """Carica dati EOM con cache"""
    eom_df = load_from_gsheet("EOM", EOM_BASE_COLUMNS)
    if "Last Update" not in eom_df.columns:
        eom_df["Last Update"] = pd.Timestamp.now()
    if "Order" not in eom_df.columns:
        eom_df["Order"] = range(len(eom_df))
    return eom_df

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
if "eom_last_saved_state" not in st.session_state:
    st.session_state.eom_last_saved_state = None
if "show_old_months" not in st.session_state:
    st.session_state.show_old_months = False
if "selected_old_months" not in st.session_state:
    st.session_state.selected_old_months = []

# =========================
# HELPERS
# =========================
progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

def parse_id(id_str):
    """Estrae macro e micro ID da una stringa come '1.2' o '1'"""
    if not id_str or pd.isna(id_str):
        return None, None

    id_str = str(id_str).strip()
    if '.' in id_str:
        parts = id_str.split('.')
        try:
            macro = int(parts[0])
            micro = int(parts[1]) if len(parts) > 1 else None
            return macro, micro
        except:
            return None, None
    else:
        try:
            return int(id_str), None
        except:
            return None, None

def renumber_eom_ids(df):
    """Rinumera automaticamente gli ID Macro e Micro del DataFrame EOM"""
    if len(df) == 0:
        return df

    df = df.copy()

    # Parsing degli ID esistenti
    df['parsed_macro'] = df['ID Macro'].apply(lambda x: parse_id(x)[0])
    df['parsed_micro'] = df['ID Micro'].apply(lambda x: parse_id(x)[1])

    # Ordina per macro e micro ID
    df = df.sort_values(['parsed_macro', 'parsed_micro'], na_position='last').reset_index(drop=True)

    # Rinumerazione
    new_macro_counter = 1
    macro_mapping = {}

    for idx, row in df.iterrows():
        old_macro = row['parsed_macro']

        if pd.isna(old_macro):
            continue

        # Se questo macro ID non è ancora stato mappato
        if old_macro not in macro_mapping:
            macro_mapping[old_macro] = new_macro_counter
            new_macro_counter += 1

        new_macro = macro_mapping[old_macro]

        # Aggiorna ID Macro
        df.loc[idx, 'ID Macro'] = str(new_macro)

    # Rinumerazione Micro ID per ciascun gruppo Macro
    for macro_id in df['ID Macro'].unique():
        if not macro_id or pd.isna(macro_id):
            continue

        mask = df['ID Macro'] == macro_id
        micro_rows = df[mask & df['parsed_micro'].notna()]

        if len(micro_rows) > 0:
            new_micro_counter = 1
            for idx in micro_rows.index:
                df.loc[idx, 'ID Micro'] = f"{macro_id}.{new_micro_counter}"
                new_micro_counter += 1

    # Rimuovi colonne temporanee
    df = df.drop(['parsed_macro', 'parsed_micro'], axis=1)

    return df

def clean_eom_dataframe(df, month_cols):
    """Pulisce il DataFrame EOM assicurando i tipi corretti"""
    df = df.copy()

    for col in month_cols:
        if col in df.columns:
            df[col] = df[col].fillna(EOM_WHITE)
            df[col] = df[col].replace("", EOM_WHITE)

            # ✅ NEW: include GRAY, and normalize legacy values
            def _norm_status(x):
                s = str(x).strip()

                # Keep if already one of our dots
                if s in EOM_STATUS_OPTIONS:
                    return s

                # legacy / boolean-like -> map
                if s in ["True", "true", "Done", "1"]:
                    return EOM_GREEN
                if s in ["False", "false", "Undone", "0"]:
                    return EOM_RED

                # gray / n-a like strings
                if s.lower() in ["na", "n/a", "not applicable", "not to do", "skip", "skipped", "excluded", "no"]:
                    return EOM_GRAY

                # default
                return EOM_WHITE

            df[col] = df[col].apply(_norm_status)

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
    """Genera TUTTI i mesi (anche quelli vecchi per mantenere i dati)"""
    today = date.today()
    all_months = []
    
    # Il "current working month" è il mese precedente a quello attuale
    current_year = today.year
    current_month = today.month - 1
    if current_month < 1:
        current_month = 12
        current_year -= 1
    
    # Genera mesi partendo da 12 mesi fa (per mantenere storico)
    for i in range(12, -2, -1):  # Da -12 a +1 mese
        month = current_month - i
        year = current_year
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        all_months.append((year, month))
    
    # Rimuovi duplicati e ordina
    all_months = sorted(list(set(all_months)))
    
    return all_months

def get_visible_months():
    """Restituisce solo i mesi da visualizzare: 4 precedenti + current + 1 successivo"""
    today = date.today()
    visible_months = []
    
    # Current working month
    current_year = today.year
    current_month = today.month - 1
    if current_month < 1:
        current_month = 12
        current_year -= 1
    
    # 4 mesi precedenti
    for i in range(4, 0, -1):
        month = current_month - i
        year = current_year
        while month < 1:
            month += 12
            year -= 1
        visible_months.append((year, month))
    
    # Current month
    visible_months.append((current_year, current_month))
    
    # 1 mese successivo
    month = current_month + 1
    year = current_year
    if month > 12:
        month = 1
        year += 1
    visible_months.append((year, month))
    
    return visible_months

# =========================
# CARICA DATI (CON CACHE)
# =========================
df = load_projects_data()
eom_df = load_eom_data()

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

        original_df = load_projects_data()
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
    # 📁 PROJECT VIEW - ORGANIZZATO PER STATUS E AREA
    # ======================================================
    if not st.session_state.add_project and len(df) > 0:
        # Dividi progetti in In Progress e Completed
        in_progress_projects = {}
        completed_projects = {}

        for project in df["Project"].unique():
            proj_df = df[df["Project"] == project]
            area = proj_df["Area"].iloc[0]
            completion = proj_df["Progress"].map(progress_score).mean()

            if completion == 1.0:
                if area not in completed_projects:
                    completed_projects[area] = []
                completed_projects[area].append(project)
            else:
                if area not in in_progress_projects:
                    in_progress_projects[area] = []
                in_progress_projects[area].append(project)

        # Ordina le aree alfabeticamente
        in_progress_areas = sorted(in_progress_projects.keys())
        completed_areas = sorted(completed_projects.keys())

        # ======================================================
        # IN PROGRESS SECTION
        # ======================================================
        if in_progress_areas:
            st.markdown("### 📂 In Progress")

            for area in in_progress_areas:
                st.markdown(f"#### 📍 {area}")

                for project in sorted(in_progress_projects[area]):
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

                        for idx, r in proj_df.iterrows():
                            cols = st.columns([10, 1])
                            with cols[0]:
                                if st.session_state.edit_mode:
                                    # EDIT MODE - Mostra campi editabili
                                    st.markdown(f"**Edit Task: {r['Task']}**")

                                    new_task = st.text_input("Task Name", value=r['Task'], key=f"edit_task_{idx}")
                                    new_owner = st.text_input("Owner", value=r['Owner'], key=f"edit_owner_{idx}")

                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        new_priority = st.selectbox(
                                            "Priority", ["Low", "Important", "Urgent"],
                                            index=["Low", "Important", "Urgent"].index(r['Priority']) if r['Priority'] in ["Low", "Important", "Urgent"] else 0,
                                            key=f"edit_priority_{idx}"
                                        )
                                    with col_b:
                                        new_progress = st.selectbox(
                                            "Status", progress_values,
                                            index=progress_values.index(r['Progress']) if r['Progress'] in progress_values else 0,
                                            key=f"edit_progress_{idx}"
                                        )

                                    col_c, col_d = st.columns(2)
                                    with col_c:
                                        current_release = r['Release Date'].date() if pd.notna(r['Release Date']) else None
                                        new_release = st.date_input("Release Date", value=current_release, key=f"edit_release_{idx}")
                                    with col_d:
                                        current_due = r['Due Date'].date() if pd.notna(r['Due Date']) else None
                                        new_due = st.date_input("Due Date", value=current_due, key=f"edit_due_{idx}")

                                    gr_text = r.get('GR/Mail Object', '')
                                    if '\n' in gr_text:
                                        parts = gr_text.split('\n', 1)
                                        current_gr = parts[0].strip()
                                        current_mail = parts[1].strip() if len(parts) > 1 else ''
                                    else:
                                        current_gr = gr_text
                                        current_mail = ''

                                    col_gr, col_mail = st.columns(2)
                                    with col_gr:
                                        new_gr = st.text_area("📋 GR Number", value=current_gr, key=f"edit_gr_{idx}", height=80)
                                    with col_mail:
                                        new_mail = st.text_area("📧 Mail Object", value=current_mail, key=f"edit_mail_{idx}", height=80)

                                    new_notes = st.text_area("📝 Notes", value=r.get('Notes', ''), key=f"edit_notes_{idx}", height=80)

                                    if st.button("💾 Save Changes", key=f"save_edit_{idx}", type="primary"):
                                        fresh_df = load_from_gsheet("Projects", PROJECT_COLUMNS, date_cols=["Release Date", "Due Date", "Last Update"])
                                        fresh_df.loc[idx, "Task"] = new_task
                                        fresh_df.loc[idx, "Owner"] = new_owner
                                        fresh_df.loc[idx, "Priority"] = new_priority
                                        fresh_df.loc[idx, "Progress"] = new_progress
                                        fresh_df.loc[idx, "Release Date"] = pd.Timestamp(new_release) if new_release else pd.NaT
                                        fresh_df.loc[idx, "Due Date"] = pd.Timestamp(new_due) if new_due else pd.NaT
                                        fresh_df.loc[idx, "GR/Mail Object"] = f"{new_gr}\n{new_mail}" if new_gr or new_mail else ""
                                        fresh_df.loc[idx, "Notes"] = new_notes
                                        fresh_df.loc[idx, "Last Update"] = pd.Timestamp.now()

                                        if save_to_gsheet(fresh_df, "Projects"):
                                            st.success("✅ Changes saved!")
                                            time.sleep(1)
                                            st.rerun()

                                else:
                                    # VIEW MODE - Mostra dati come prima
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

                                    # OTTIMIZZATO: Salva notes senza rerun
                                    if notes != current_notes:
                                        df.loc[idx, "Notes"] = notes
                                        df.loc[idx, "Last Update"] = pd.Timestamp.now()
                                        save_to_gsheet(df, "Projects")
                                        st.success("💾 Notes saved", icon="✅")

                                    current_status = r["Progress"]
                                    status = st.radio(
                                        "Status",
                                        options=progress_values,
                                        index=progress_values.index(current_status),
                                        key=f"status_radio_{project}_{r['Task']}_{idx}",
                                        horizontal=True
                                    )

                                    if status != current_status:
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

                st.divider()

        # ======================================================
        # COMPLETED SECTION
        # ======================================================
        if completed_areas:
            st.markdown("### ✅ Completed")

            for area in completed_areas:
                st.markdown(f"#### 📍 {area}")

                for project in sorted(completed_projects[area]):
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

    # ✅ TUTTI I MESI (per mantenere i dati su Google Sheets)
    all_months = get_next_months()
    all_eom_dates = [last_working_day(y, m) for y, m in all_months]
    all_month_cols = [d.strftime("%d %B %Y") for d in all_eom_dates]
    
    # ✅ MESI VISIBILI (4 precedenti + current + 1 successivo)
    visible_months = get_visible_months()
    visible_eom_dates = [last_working_day(y, m) for y, m in visible_months]
    visible_month_cols = [d.strftime("%d %B %Y") for d in visible_eom_dates]
    
    # Il current working month è il 5° nella lista dei visibili (indice 4)
    current_month_col = visible_month_cols[4]
    
    # ✅ Mesi vecchi (non visibili di default)
    old_month_cols = [col for col in all_month_cols if col not in visible_month_cols]

    for col in EOM_BASE_COLUMNS:
        if col not in eom_df.columns:
            if col == "🗑️ Delete":
                eom_df[col] = False
            else:
                eom_df[col] = ""

    # ✅ Crea colonne per TUTTI i mesi (anche quelli vecchi)
    for c in all_month_cols:
        if c not in eom_df.columns:
            eom_df[c] = EOM_WHITE  # ✅ default white

    eom_df = clean_eom_dataframe(eom_df, all_month_cols)

    # ======================================================
    # ✅ FIX: EOM FILTERS + SAFE VIEW/EDIT DATAFRAMES
    # ======================================================
    eom_full_df = eom_df.copy()   # SEMPRE completo -> è quello che si salva
    eom_view_df = eom_df.copy()   # quello che si mostra (eventualmente filtrato)

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
    # ✅ EOM FILTERS
    # ======================================================
    if st.session_state.show_eom_filters and len(eom_full_df) > 0:
        with st.expander("🔍 Filters (EOM)", expanded=True):
            f1, f2, f3, f4 = st.columns(4)

            with f1:
                eom_areas = ["All"] + sorted(eom_full_df["Area"].dropna().unique().tolist())
                eom_selected_area = st.selectbox(
                    "Area",
                    eom_areas,
                    index=0,
                    key=f"eom_filter_area_{st.session_state.reset_eom_filters_flag}"
                )

            with f2:
                macro_vals = ["All"] + sorted([x for x in eom_full_df["ID Macro"].dropna().unique().tolist() if str(x).strip() != ""])
                eom_selected_macro = st.selectbox(
                    "ID Macro",
                    macro_vals,
                    index=0,
                    key=f"eom_filter_macro_{st.session_state.reset_eom_filters_flag}"
                )

            with f3:
                freq_vals = ["All"] + sorted([x for x in eom_full_df["Frequency"].dropna().unique().tolist() if str(x).strip() != ""])
                eom_selected_freq = st.selectbox(
                    "Frequency",
                    freq_vals,
                    index=0,
                    key=f"eom_filter_freq_{st.session_state.reset_eom_filters_flag}"
                )

            with f4:
                # ✅ include gray in filter options
                status_vals = ["All"] + EOM_STATUS_OPTIONS
                eom_selected_status = st.selectbox(
                    f"Status ({current_month_col})",
                    status_vals,
                    index=0,
                    key=f"eom_filter_status_{st.session_state.reset_eom_filters_flag}"
                )

            s1, s2, s3 = st.columns([2, 2, 1])
            with s1:
                eom_search = st.text_input(
                    "Search in Activity / Files",
                    value="",
                    key=f"eom_filter_search_{st.session_state.reset_eom_filters_flag}"
                )
            with s2:
                # ✅ NUOVO: Multiselect per scegliere mesi vecchi da mostrare
                if len(old_month_cols) > 0:
                    selected_old = st.multiselect(
                        "📅 Show old months",
                        options=old_month_cols,
                        default=st.session_state.selected_old_months,
                        key=f"old_months_select_{st.session_state.reset_eom_filters_flag}",
                        help="Select which old months to display"
                    )
                    if selected_old != st.session_state.selected_old_months:
                        st.session_state.selected_old_months = selected_old
                        st.rerun()
                else:
                    st.caption("No old months available")
            with s3:
                if st.button("🔄 Reset Filters", use_container_width=True):
                    st.session_state.reset_eom_filters_flag += 1
                    st.session_state.show_old_months = False
                    st.session_state.selected_old_months = []
                    st.rerun()

        # Apply filters
        eom_view_df = eom_full_df.copy()

        if eom_selected_area != "All":
            eom_view_df = eom_view_df[eom_view_df["Area"] == eom_selected_area]

        if eom_selected_macro != "All":
            eom_view_df = eom_view_df[eom_view_df["ID Macro"] == eom_selected_macro]

        if eom_selected_freq != "All":
            eom_view_df = eom_view_df[eom_view_df["Frequency"] == eom_selected_freq]

        if eom_selected_status != "All" and current_month_col in eom_view_df.columns:
            eom_view_df = eom_view_df[eom_view_df[current_month_col] == eom_selected_status]

        if eom_search and eom_search.strip():
            pattern = re.escape(eom_search.strip())
            eom_view_df = eom_view_df[
                eom_view_df["Activity"].astype(str).str.contains(pattern, case=False, na=False) |
                eom_view_df["Files"].astype(str).str.contains(pattern, case=False, na=False)
            ]

        st.info(f"📊 Showing {len(eom_view_df)} of {len(eom_full_df)} activities")
        st.divider()

    # ======================================================
    # BULK DELETE MODE CON RINUMERAZIONE AUTOMATICA
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
                    fresh_eom = load_from_gsheet("EOM", EOM_BASE_COLUMNS)

                    # Elimina le righe selezionate
                    fresh_eom = fresh_eom.drop(selected_to_delete).reset_index(drop=True)

                    # Rinumera automaticamente gli ID
                    fresh_eom = renumber_eom_ids(fresh_eom)

                    if save_to_gsheet(fresh_eom, "EOM"):
                        st.success(f"✅ {len(selected_to_delete)} activities deleted and IDs renumbered!")
                        st.session_state.eom_bulk_delete = False
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("👆 Select activities above to delete them")

        st.divider()

    with st.expander("➕ Add new End-of-Month Activity", expanded=False):
        c1, c2, c3 = st.columns(3)
        area = c1.text_input("Area", key="eom_area")
        id_macro = c2.text_input("ID Macro (e.g., 1, 2, 3)", key="eom_macro")
        id_micro = c3.text_input("ID Micro (e.g., 1.1, 1.2, 2.1)", key="eom_micro")

        activity = st.text_input("Activity", key="eom_activity")
        c4, c5 = st.columns(2)
        frequency = c4.text_input("Frequency", key="eom_freq")
        files = c5.text_input("Files", key="eom_files")

        if st.button("➕ Add activity", type="primary", key="eom_add_btn"):
            if not activity:
                st.error("❌ Activity name is required!")
            else:
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
                # ✅ Aggiungi TUTTI i mesi (anche quelli vecchi)
                for c in all_month_cols:
                    row[c] = EOM_WHITE  # ✅ default white

                fresh_eom = pd.concat([fresh_eom, pd.DataFrame([row])], ignore_index=True)

                # Rinumera automaticamente dopo l'aggiunta
                fresh_eom = renumber_eom_ids(fresh_eom)

                if save_to_gsheet(fresh_eom, "EOM"):
                    st.success(f"✅ Activity '{activity}' added!")
                    time.sleep(1)
                    st.rerun()

    # ======================================================
    # ✅ EOM EDIT MODE CON FIX SALVATAGGIO
    # ======================================================
    if st.session_state.eom_edit_mode and not st.session_state.eom_bulk_delete and len(eom_view_df) > 0:
        eom_view_df = eom_view_df.sort_values('Order').reset_index(drop=True)

        # ✅ Mostra mesi visibili + mesi vecchi selezionati
        display_month_cols = visible_month_cols.copy()
        if st.session_state.selected_old_months:
            # Aggiungi i mesi vecchi selezionati PRIMA dei mesi visibili (in ordine cronologico)
            selected_sorted = sorted(st.session_state.selected_old_months, 
                                    key=lambda x: all_month_cols.index(x))
            display_month_cols = selected_sorted + display_month_cols
            st.info(f"📅 Showing {len(selected_sorted)} old month(s) + {len(visible_month_cols)} current months")

        edit_cols = ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"] + display_month_cols + ["Order"]

        edit_df = eom_view_df[edit_cols].copy()

        # ✅ INDICATORE VISIVO: Rinomina current month con emoji blu
        current_month_display = f"🔵 {current_month_col}"
        if current_month_col in edit_df.columns:
            edit_df = edit_df.rename(columns={current_month_col: current_month_display})
            display_month_cols_renamed = [current_month_display if c == current_month_col else c for c in display_month_cols]
        else:
            display_month_cols_renamed = display_month_cols

        col_cfg = {}
        for c in display_month_cols_renamed:
            is_current = (c == current_month_display)
            
            # Trova il nome originale per verificare se è old
            original_col = current_month_col if is_current else c
            is_old = original_col in old_month_cols
            
            col_cfg[c] = st.column_config.SelectboxColumn(
                c,
                help="🎯 **Current working month**" if is_current else ("📦 Old month" if is_old else "Future month"),
                options=EOM_STATUS_OPTIONS,
                default=EOM_WHITE,
                width="medium" if is_current else "small"
            )

        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            num_rows="fixed",
            hide_index=True,
            column_config=col_cfg,
            disabled=["Order"],
            key="eom_edit_editor"
        )

        # ✅ FIX: Salvataggio robusto senza messaggi e senza bug
        # Rinomina indietro per il salvataggio
        current_month_display = f"🔵 {current_month_col}"
        edited_original_names = edited.copy()
        if current_month_display in edited_original_names.columns:
            edited_original_names = edited_original_names.rename(columns={current_month_display: current_month_col})
        
        def df_to_comparable_dict(df):
            """Converte DataFrame in dict comparabile per rilevare modifiche"""
            return df.to_dict('records')

        current_state = df_to_comparable_dict(edited)
        
        # Inizializza lo stato salvato alla prima esecuzione
        if st.session_state.eom_last_saved_state is None:
            st.session_state.eom_last_saved_state = df_to_comparable_dict(edit_df)
        
        # Rileva modifiche confrontando con lo stato salvato
        if current_state != st.session_state.eom_last_saved_state:
            fresh_full = load_from_gsheet("EOM", EOM_BASE_COLUMNS)
            
            # Aggiungi tutte le colonne mesi che potrebbero esistere (anche quelle nascoste)
            for c in all_month_cols:
                if c not in fresh_full.columns:
                    fresh_full[c] = EOM_WHITE

            if "Order" not in fresh_full.columns:
                fresh_full["Order"] = range(len(fresh_full))
            fresh_full["Order"] = pd.to_numeric(fresh_full["Order"], errors='coerce').fillna(0).astype(int)

            # Applica modifiche riga per riga usando Order come chiave (usa nomi originali)
            for _, r in edited_original_names.iterrows():
                o = int(r["Order"])
                mask = fresh_full["Order"] == o
                if mask.any():
                    for c in ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"] + display_month_cols:
                        if c in fresh_full.columns and c in edited_original_names.columns:
                            fresh_full.loc[mask, c] = r[c]

            fresh_full["Last Update"] = pd.Timestamp.now()
            fresh_full = renumber_eom_ids(fresh_full)
            fresh_full = clean_eom_dataframe(fresh_full, all_month_cols)

            if save_to_gsheet(fresh_full, "EOM"):
                # ✅ Aggiorna lo stato salvato IMMEDIATAMENTE dopo il salvataggio
                st.session_state.eom_last_saved_state = current_state
                # ✅ NO messaggio di salvataggio

        st.divider()

    # ======================================================
    # ✅ VIEW MODE - SISTEMA SALVATAGGIO DEFINITIVO
    # ======================================================
    if not st.session_state.eom_edit_mode and not st.session_state.eom_bulk_delete and len(eom_view_df) > 0:
        eom_view_df = eom_view_df.sort_values('Order').reset_index(drop=True)

        # ✅ Mostra mesi visibili + mesi vecchi selezionati
        display_month_cols = visible_month_cols.copy()
        if st.session_state.selected_old_months:
            selected_sorted = sorted(st.session_state.selected_old_months, 
                                    key=lambda x: all_month_cols.index(x))
            display_month_cols = selected_sorted + display_month_cols
            st.info(f"📅 Showing {len(selected_sorted)} old month(s) + {len(visible_month_cols)} current months")

        display_cols = ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"] + display_month_cols
        display_df = eom_view_df[display_cols].copy()

        # ✅ INDICATORE VISIVO: Rinomina current month con emoji azzurro
        column_config = {}
        display_df_renamed = display_df.copy()
        
        current_month_display = f"🔵 {current_month_col}"
        if current_month_col in display_df_renamed.columns:
            display_df_renamed = display_df_renamed.rename(columns={current_month_col: current_month_display})
            display_month_cols_renamed = [current_month_display if c == current_month_col else c for c in display_month_cols]
        else:
            display_month_cols_renamed = display_month_cols

        for i, col in enumerate(display_month_cols_renamed):
            is_current = (col == current_month_display)
            
            # Trova il nome originale per verificare se è old
            original_col = current_month_col if is_current else col
            is_old = original_col in old_month_cols
            
            column_config[col] = st.column_config.SelectboxColumn(
                col,
                help="🎯 **Current working month**" if is_current else ("📦 Old month" if is_old else "Future month"),
                options=EOM_STATUS_OPTIONS,
                default=EOM_WHITE,
                width="medium" if is_current else "small"
            )

        # Inizializza stato di confronto se non esiste
        if 'eom_view_snapshot' not in st.session_state:
            st.session_state.eom_view_snapshot = display_df_renamed.copy()

        edited = st.data_editor(
            display_df_renamed,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            hide_index=True,
            key="eom_editor",
            disabled=["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]
        )

        # ✅ SALVATAGGIO SEMPLIFICATO - Confronta solo se veramente diverso
        changes_detected = False
        
        # Rinomina indietro per confronto
        edited_original_names = edited.rename(columns={current_month_display: current_month_col})
        
        for month_col in display_month_cols:
            if month_col in eom_view_df.columns and month_col in edited_original_names.columns:
                if not edited_original_names[month_col].equals(eom_view_df[month_col]):
                    changes_detected = True
                    break
        
        if changes_detected:
            # Salva immediatamente
            fresh_full = load_from_gsheet("EOM", EOM_BASE_COLUMNS)
            
            for c in all_month_cols:
                if c not in fresh_full.columns:
                    fresh_full[c] = EOM_WHITE

            if "Order" not in fresh_full.columns:
                fresh_full["Order"] = range(len(fresh_full))
            fresh_full["Order"] = pd.to_numeric(fresh_full["Order"], errors='coerce').fillna(0).astype(int)

            # Applica modifiche
            if "Order" in eom_view_df.columns:
                for idx, r in edited_original_names.iterrows():
                    o = int(eom_view_df.iloc[idx]["Order"])
                    mask = fresh_full["Order"] == o
                    if mask.any():
                        for c in display_month_cols:
                            if c in fresh_full.columns and c in edited_original_names.columns:
                                fresh_full.loc[mask, c] = r[c]

            fresh_full["Last Update"] = pd.Timestamp.now()
            fresh_full = clean_eom_dataframe(fresh_full, all_month_cols)
            
            if save_to_gsheet(fresh_full, "EOM"):
                # Aggiorna snapshot dopo salvataggio
                st.session_state.eom_view_snapshot = edited.copy()
                time.sleep(0.3)
                st.rerun()

        st.divider()

        # ======================================================
        # ✅ NEW: metrics exclude GRAY from denominator
        # ======================================================
        total_activities = len(eom_df)
        if current_month_col in eom_df.columns:
            todo_mask = eom_df[current_month_col] != EOM_GRAY
            total_todo = int(todo_mask.sum())
            completed_current = int(((eom_df[current_month_col] == EOM_GREEN) & todo_mask).sum())
        else:
            total_todo = total_activities
            completed_current = 0

        progress_pct = int((completed_current / total_todo * 100)) if total_todo > 0 else 0

        st.metric(
            label="Current Month Progress",
            value=f"{completed_current}/{total_todo}",
            delta=f"{progress_pct}%"
        )

    elif not st.session_state.eom_edit_mode and not st.session_state.eom_bulk_delete and len(eom_df) == 0:
        st.info("📝 No End-of-Month activities yet. Add your first activity above!")

    st.divider()
    if len(eom_df) > 0:
        if current_month_col in eom_df.columns:
            todo_mask = eom_df[current_month_col] != EOM_GRAY
            total_todo = int(todo_mask.sum())
            completed_current_month = int(((eom_df[current_month_col] == EOM_GREEN) & todo_mask).sum())
        else:
            total_todo = len(eom_df)
            completed_current_month = 0

        st.caption(f"📊 Total activities: {len(eom_df)} | Current month completed: {completed_current_month}/{total_todo}")
