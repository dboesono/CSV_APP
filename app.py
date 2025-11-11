import streamlit as st
import pandas as pd
import re
from collections import Counter

# ─── 1) SESSION STATE FLAGS & RESET ON MODE/UPLOAD ────────────────────────────
for key in ('processed', 'device_idx', 'device_results', 'alarm_df', 'to_process'):
    if key not in st.session_state:
        st.session_state[key] = False if key=='processed' else 0 if key=='device_idx' else [] if key in ('device_results','to_process') else pd.DataFrame()

def reset_all():
    # remove keys so their widgets get recreated next run
    for key in [
        "processed", "device_idx",
        "device_results", "alarm_df",
        "uploaded_files", "to_process"
    ]:
        st.session_state.pop(key, None)
    st.rerun()

# ─── 2) PAGE CONFIG & THEME ────────────────────────────────────────────────────
st.set_page_config(page_title="CSV Processor", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
  [data-testid="stSidebar"] { background-color: #262730 !important; }
  [data-testid="block-container"] { background-color: #0E1117 !important; }
</style>
""", unsafe_allow_html=True)

# ─── 3) CLEANING LOGIC ─────────────────────────────────────────────────────────
def clean_device_df(raw: pd.DataFrame) -> pd.DataFrame:
    # 1) Drop merged first row, set second row as header
    header = raw.iloc[1].astype(str).str.strip().tolist()
    df = raw.iloc[2:].reset_index(drop=True)
    df.columns = header

    # 2) Drop unwanted memory-usage columns
    drop_phrases = [
        'Remaining usage time of memory',
        'Power on duration of memory'
    ]
    df = df.drop(columns=[c for c in df.columns if any(p in c for p in drop_phrases)],
                 errors='ignore')

    # 3) Make every column name unique by appending _0, _1, _2… for duplicates
    bases = [re.sub(r'\.\d+$', '', str(col)) for col in df.columns]
    freq  = Counter(bases)
    counts = {b: 0 for b in bases}
    new_cols = []
    for b in bases:
        if freq[b] > 1:
            # always append a suffix, starting from 0
            new_cols.append(f"{b}_{counts[b]}")
            counts[b] += 1
        else:
            new_cols.append(b)
    df.columns = new_cols

    # 4) Reformat any “time” columns …
    for c in df.columns:
        if 'time' in c.lower():
            df[c] = (pd.to_datetime(df[c], errors='coerce')
                         .dt.strftime('%Y/%m/%d %H:%M:%S'))
    return df


def process_files(uploaded, selection, mode):
    if mode=="Device":
        devs = []
        for f in uploaded:
            if f.name in selection:
                raw = (pd.read_excel(f, engine='openpyxl', header=None, dtype=str)
                       if f.name.lower().endswith('.xlsx')
                       else pd.read_csv(f, header=None, dtype=str))
                devs.append((f.name, clean_device_df(raw)))
        st.session_state.device_results = devs

    else:
        dfs = []
        date_col = "Alarm time"
        exclude = ["Alarm Evidence","Evidence Status","Evidence Size",
                   "Evidence generation time","Evidence completion time",
                   "Alarm Status","Label","Processing Contents",
                   "Operator","Process time"]
        for f in uploaded:
            if f.name in selection:
                df = (pd.read_excel(f, engine='openpyxl', dtype=str)
                      if f.name.lower().endswith('.xlsx')
                      else pd.read_csv(f, dtype=str, encoding='utf-8'))
                if date_col in df:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')\
                                     .dt.strftime('%Y/%m/%d %H:%M:%S')
                dfs.append(df.drop(columns=[c for c in exclude if c in df], errors='ignore'))
        st.session_state.alarm_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# ─── 4) SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📂 CSV Processor")
    mode = st.selectbox("Mode:", ["Device","Alarm"], key="mode", on_change=reset_all)
    uploaded = st.file_uploader("Upload .xlsx/.csv", accept_multiple_files=True,
                                key="uploaded", on_change=reset_all)
    names = [f.name for f in st.session_state.uploaded]
    
    # select/clear all
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Select All"):
            st.session_state.to_process = names.copy()
    with c2:
        if st.button("Clear All"):
            st.session_state.to_process = []

    to_process = st.multiselect(
        "Files to process:", 
        options=names,
        default=names, 
        key="to_process")
    
    if st.button("Process Selected"):
        st.session_state.processed = True
        process_files(st.session_state.uploaded, to_process, mode)
        st.session_state.device_idx = 0

    if st.button("Reset"):
        reset_all()

# ─── 5) MAIN AREA ──────────────────────────────────────────────────────────────
col1, col2 = st.columns([1,4], gap="medium")
with col1:
    st.write("Uploaded:", len(st.session_state.uploaded))
    st.write("Selected:", len(to_process))
    st.write("Mode:", mode)

with col2:
    if not st.session_state.processed:
        st.markdown("## How It Works")
        if mode=="Device":
            st.write("""
- Drop merged 1st row, use 2nd as headers  
- Remove memory-usage columns  
- Deduplicate headers `(_0, _1, _2, …)  
- Reformat `time` columns to `YYYY/MM/DD HH:MM:SS` 
- Preview 100 rows; ← → to navigate
- `.csv` file ready to download   
            """)
        else:
            st.write("""
- Upload `.xlsx`/`.csv` files  
- Reformat `Alarm time` to `YYYY/MM/DD HH:MM:SS`  
- Drop unwanted columns  
- Concatenate all into one DataFrame  
- Preview first 100 rows
- `.csv` file ready to download 
            """)
    else:
        if mode=="Device" and st.session_state.device_results:
            idx = st.session_state.device_idx
            name, df = st.session_state.device_results[idx]
            st.subheader(name)
            st.write(f"Rows: {df.shape[0]}  Cols: {df.shape[1]}")
            st.dataframe(df.head(100), use_container_width=True, height=500)

            p,_,n = st.columns([1,6,1])
            with p:
                if st.button("←", key="prev"):
                    st.session_state.device_idx = (idx-1)%len(st.session_state.device_results)
            with n:
                if st.button("→", key="next"):
                    st.session_state.device_idx = (idx+1)%len(st.session_state.device_results)
            
            st.download_button("Download", df.to_csv(index=False), file_name=f"{name}_out.csv")

        elif mode=="Alarm" and not st.session_state.alarm_df.empty:
            df = st.session_state.alarm_df
            st.subheader("Combined Alarm")
            st.write(f"Rows: {df.shape[0]}  Cols: {df.shape[1]}")
            st.dataframe(df.head(100), use_container_width=True, height=500)
            st.download_button("Download Combined", df.to_csv(index=False), file_name="alarm_combined.csv")











