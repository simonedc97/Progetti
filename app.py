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

# =========================
# HELPERS
# =========================
progress_values = ["Not started", "In progress", "Completed"]
progress_score = {"Not started": 0, "In progress": 0.5, "Completed": 1}

def save_csv(df, path):
    os.makedirs("data", exist_ok=True)
    df.to_csv(path, index=False)

def clean_eom_dataframe(df, month_cols):
    """Pulisce il DataFrame EOM assicurando i tipi corretti"""
    # Crea una copia per non modificare l'originale
    df = df.copy()
    
    # Assicura che le colonne boolean siano effettivamente boolean
    bool_cols = ["🗑️ Delete"] + month_cols
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False)
            df[col] = df[col].replace("", False)
            df[col] = df[col].apply(
                lambda x: True if x in [True, "True", "true", "1", 1] else False
            )
    
    # Assicura che le colonne di testo siano stringhe
    text_cols = ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    
    return df

def load_csv(path, columns, date_cols=None):
    if os.path.exists(path):
        if date_cols:
            return pd.read_csv(path, parse_dates=date_cols)
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)

def last_working_day(year, month):
    """Calcola l'ultimo giorno lavorativo del mese"""
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    while last_day.weekday() >= 5:  # 5=Saturday, 6=Sunday
        last_day -= timedelta(days=1)
    return last_day

def get_next_months(n=6, include_previous=True):
    """Genera i prossimi N mesi, includendo il mese precedente se richiesto"""
    today = date.today()
    months = []
    
    # Aggiungi il mese precedente come "mese corrente di lavoro"
    if include_previous:
        prev_month = today.month - 1
        prev_year = today.year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
        months.append((prev_year, prev_month))
    
    # Aggiungi i prossimi N mesi
    for i in range(n):
        month = today.month + i
        year = today.year
        while month > 12:
            month -= 12
            year += 1
        months.append((year, month))
    
    # Assicurati che dicembre 2025 sia incluso se non c'è già
    if (2025, 12) not in months:
        months.append((2025, 12))
    
    # Ordina e rimuovi duplicati
    months = sorted(list(set(months)))
    
    return months

# =========================
# LOAD DATA
# =========================
df = load_csv(DATA_PATH, PROJECT_COLUMNS, date_cols=["Release Date", "Due Date"])
if "Owner" in df.columns:
    df["Owner"] = df["Owner"].fillna("")

eom_df = load_csv(EOM_PATH, EOM_BASE_COLUMNS)

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
                last_update = pd.to_datetime(df["Release Date"]).max()
                st.caption(f"🕒 Last update: {last_update.strftime('%d/%m/%Y')}")
            except:
                pass

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

        if col2.button("Create project", type="primary"):
            if not area or not project:
                st.error("❌ Area and Project name are required!")
            elif not tasks:
                st.error("❌ Add at least one task!")
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
                save_csv(df, DATA_PATH)
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
                save_csv(df, DATA_PATH)
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
                    save_csv(df, DATA_PATH)
                    st.success(f"✅ Task '{task_name}' deleted")
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

            # HEADER PROGETTO
            header_text = f"📁 {project} ({area}) — {completion}%"
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

                # TASK VIEW (NON IN EDIT MODE)
                if not st.session_state.edit_mode:
                    for idx, r in proj_df.iterrows():
                        cols = st.columns([10, 1])
                        with cols[0]:
                            st.markdown(f"**{r['Task']}**")
                            st.write(f"👤 Owner: {r['Owner'] if r['Owner'] else '—'}")
                            st.write(f"🎯 Priority: {r['Priority']} | 📅 Due: {r['Due Date'].date()}")

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
                                save_csv(df, DATA_PATH)
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
                        df.loc[df["Project"] == project, "Area"] = new_area
                        df.loc[df["Project"] == project, "Project"] = new_name

                        for idx, t, o, p, pr, d in updated_rows:
                            df.loc[idx, "Task"] = t
                            df.loc[idx, "Owner"] = o
                            df.loc[idx, "Progress"] = p
                            df.loc[idx, "Priority"] = pr
                            df.loc[idx, "Due Date"] = pd.Timestamp(d)

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

                        save_csv(df, DATA_PATH)
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

    elif not st.session_state.add_project and len(df) == 0:
        st.info("📝 No projects yet. Click '➕ Project' to create your first project!")

    # FOOTER
    st.divider()
    if len(df) > 0:
        total_tasks = len(df)
        completed_tasks = len(df[df["Progress"] == "Completed"])
        st.caption(f"📊 Total projects: {df['Project'].nunique()} | Tasks: {completed_tasks}/{total_tasks} completed ({int(completed_tasks/total_tasks*100)}%)")

# ======================================================
# 📅 END OF MONTH ACTIVITIES
# ======================================================
if st.session_state.section == "EOM":

    st.subheader("📅 End of Month Activities")

    # Calcola i mesi (include mese precedente come corrente)
    months = get_next_months(6, include_previous=True)
    eom_dates = [last_working_day(y, m) for y, m in months]
    month_cols = [d.strftime("%d %B %Y") for d in eom_dates]
    current_month_col = month_cols[0]  # Il primo è quello precedente (corrente di lavoro)

    # INIT COLUMNS - Assicurati che tutti i campi base esistano
    for col in EOM_BASE_COLUMNS:
        if col not in eom_df.columns:
            if col == "🗑️ Delete":
                eom_df[col] = False
            else:
                eom_df[col] = ""

    # Aggiungi colonne mesi se non esistono
    for c in month_cols:
        if c not in eom_df.columns:
            eom_df[c] = False

    # Pulisci il DataFrame per assicurare tipi corretti
    eom_df = clean_eom_dataframe(eom_df, month_cols)

    # Determina quali colonne sono completate al 100%
    completed_cols = []
    if len(eom_df) > 0:
        for col in month_cols:
            if col in eom_df.columns:
                if eom_df[col].all():  # Tutte le attività completate
                    completed_cols.append(col)

    # HEADER WITH ACTIONS
    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        st.caption(f"🎯 **Current working month**: {current_month_col}")
    with col2:
        if st.button("✏️ Edit Mode" if not st.session_state.eom_edit_mode else "✅ View Mode", 
                     use_container_width=True):
            st.session_state.eom_edit_mode = not st.session_state.eom_edit_mode
            st.rerun()
    with col3:
        if completed_cols:
            show_text = f"👁️ Show Completed ({len(completed_cols)})" if not st.session_state.show_completed_months else f"🔒 Hide Completed ({len(completed_cols)})"
            if st.button(show_text, use_container_width=True):
                st.session_state.show_completed_months = not st.session_state.show_completed_months
                st.rerun()

    st.divider()

    # ======================================================
    # CONFIRM DELETE EOM ACTIVITY
    # ======================================================
    if st.session_state.confirm_delete_eom is not None:
        idx = st.session_state.confirm_delete_eom
        if idx in eom_df.index:
            activity_name = eom_df.loc[idx, "Activity"]
            st.warning(f"⚠️ Are you sure you want to delete the activity **{activity_name}**? This cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, delete activity", key=f"confirm_del_eom_{idx}", type="primary"):
                    eom_df = eom_df.drop(idx).reset_index(drop=True)
                    save_csv(eom_df, EOM_PATH)
                    st.success(f"✅ Activity '{activity_name}' deleted")
                    st.session_state.confirm_delete_eom = None
                    st.rerun()
            with col2:
                if st.button("❌ Cancel", key=f"cancel_del_eom_{idx}"):
                    st.session_state.confirm_delete_eom = None
                    st.rerun()
        st.stop()

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
                st.success(f"✅ Activity '{activity}' added!")
                st.rerun()

    st.divider()

    # ======================================================
    # EDIT MODE - LIST VIEW
    # ======================================================
    if st.session_state.eom_edit_mode and len(eom_df) > 0:
        st.subheader("✏️ Edit Activities")
        
        for idx, row in eom_df.iterrows():
            with st.expander(f"📝 {row['Activity']}", expanded=False):
                col1, col2 = st.columns([10, 1])
                
                with col1:
                    c1, c2, c3 = st.columns(3)
                    new_area = c1.text_input("Area", row["Area"], key=f"edit_area_{idx}")
                    new_macro = c2.text_input("ID Macro", row["ID Macro"], key=f"edit_macro_{idx}")
                    new_micro = c3.text_input("ID Micro", row["ID Micro"], key=f"edit_micro_{idx}")
                    
                    new_activity = st.text_input("Activity", row["Activity"], key=f"edit_activity_{idx}")
                    
                    c4, c5 = st.columns(2)
                    new_freq = c4.text_input("Frequency", row["Frequency"], key=f"edit_freq_{idx}")
                    new_files = c5.text_input("Files", row["Files"], key=f"edit_files_{idx}")
                    
                    if st.button("💾 Save changes", key=f"save_eom_{idx}", type="primary"):
                        eom_df.loc[idx, "Area"] = new_area
                        eom_df.loc[idx, "ID Macro"] = new_macro
                        eom_df.loc[idx, "ID Micro"] = new_micro
                        eom_df.loc[idx, "Activity"] = new_activity
                        eom_df.loc[idx, "Frequency"] = new_freq
                        eom_df.loc[idx, "Files"] = new_files
                        save_csv(eom_df, EOM_PATH)
                        st.success(f"✅ Activity updated!")
                        st.rerun()
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"delete_eom_{idx}"):
                        st.session_state.confirm_delete_eom = idx
                        st.rerun()

        st.divider()

    # ======================================================
    # TABLE VIEW (NON EDIT MODE)
    # ======================================================
    if not st.session_state.eom_edit_mode and len(eom_df) > 0:
        # Determina quali colonne mostrare
        visible_cols = month_cols.copy()
        
        if not st.session_state.show_completed_months:
            # Nascondi colonne completate
            visible_cols = [col for col in month_cols if col not in completed_cols]
        
        # Crea subset del dataframe con solo colonne visibili
        display_cols = ["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"] + visible_cols
        display_df = eom_df[display_cols].copy()
        
        # Configura solo le colonne essenziali per evitare conflitti di tipo
        column_config = {}
        
        # Aggiungi configurazione per le colonne dei mesi visibili
        for i, col in enumerate(visible_cols):
            is_current = (col == current_month_col)
            column_config[col] = st.column_config.CheckboxColumn(
                col,
                help="🎯 **Current working month**" if is_current else "Future month",
                default=False,
                width="medium"
            )

        # Info su colonne nascoste
        if not st.session_state.show_completed_months and completed_cols:
            st.info(f"✅ **{len(completed_cols)} completed month(s) hidden**: {', '.join([c.split()[1] for c in completed_cols])}. Click 'Show Completed' to view them.")

        edited = st.data_editor(
            display_df,
            use_container_width=True,
            num_rows="fixed",
            column_config=column_config,
            hide_index=True,
            key="eom_editor",
            disabled=["Area", "ID Macro", "ID Micro", "Activity", "Frequency", "Files"]
        )

        # Aggiorna solo le colonne dei mesi nel dataframe originale
        for col in visible_cols:
            if col in edited.columns:
                eom_df[col] = edited[col]

        # Salva automaticamente le modifiche
        save_csv(eom_df, EOM_PATH)

        st.divider()
        
        # STATISTICS
        total_activities = len(eom_df)
        completed_current = eom_df[current_month_col].sum() if current_month_col in eom_df.columns else 0
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

        # Mostra stato delle altre colonne
        st.caption("**Month Overview:**")
        cols = st.columns(min(len(visible_cols), 4))
        for i, col in enumerate(visible_cols[:4]):
            with cols[i]:
                completed = eom_df[col].sum()
                pct = int((completed / total_activities * 100)) if total_activities > 0 else 0
                month_name = col.split()[1]  # Estrae il nome del mese
                
                if pct == 100:
                    st.success(f"✅ {month_name}: {pct}%")
                elif pct > 0:
                    st.info(f"⏳ {month_name}: {pct}%")
                else:
                    st.caption(f"⚪ {month_name}: {pct}%")

    elif not st.session_state.eom_edit_mode and len(eom_df) == 0:
        st.info("📝 No End-of-Month activities yet. Add your first activity above!")

    # Footer con info
    st.divider()
    if len(eom_df) > 0:
        st.caption(f"📊 Total activities: {len(eom_df)} | Completed months: {len(completed_cols)}/{len(month_cols)}")
