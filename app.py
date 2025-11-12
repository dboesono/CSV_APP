import streamlit as st
import pandas as pd
import numpy as np
import re
from collections import Counter

# ─── 1) SESSION STATE FLAGS & RESET ────────────────────────────────────────────
for key in ('processed', 'device_idx', 'device_results', 'alarm_df', 'to_process', 'uploaded'):
    if key not in st.session_state:
        st.session_state[key] = False if key=='processed' else 0 if key=='device_idx' \
            else [] if key in ('device_results','to_process','uploaded') else pd.DataFrame()

# def reset_all():
#     for k in [
#         "processed", "device_idx",
#         "device_results", "alarm_df",
#         "uploaded", "to_process"
#     ]:
#         st.session_state.pop(k, None)
#     st.rerun()

def reset_state():
    """Use in on_change callbacks: no rerun here."""
    for k in ["processed", "device_idx", "device_results", "alarm_df", "uploaded", "to_process"]:
        st.session_state.pop(k, None)

def reset_and_rerun():
    """Use for the Reset button: safe to rerun outside callbacks."""
    reset_state()
    st.rerun()

# ─── 2) PAGE CONFIG & THEME ────────────────────────────────────────────────────
st.set_page_config(page_title="CSV/Excel Processor", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
  [data-testid="stSidebar"] { background-color: #262730 !important; }
  [data-testid="block-container"] { background-color: #0E1117 !important; color: #E5E7EB; }
  h1,h2,h3,h4,h5,h6 { color: #E5E7EB !important; }
</style>
""", unsafe_allow_html=True)

# ─── 3) HELPERS ────────────────────────────────────────────────────────────────
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

def parse_alarm_series(s: pd.Series, expected_month: int | None = None) -> pd.Series:
    """Robust parser for 'Alarm time' that handles:
       - strict YYYY/MM/DD HH:MM:SS
       - D/M/Y and M/D/Y inference
       - Excel serials
       Optionally fixes day↔month only if it lands in expected_month.
    """
    raw = s.astype(str).str.replace('\u00A0', ' ', regex=True).str.strip()

    # Try strict target first
    ymd = pd.to_datetime(raw, format="%Y/%m/%d %H:%M:%S", errors="coerce")
    # Then inference with day-first and month-first
    dmy = pd.to_datetime(raw, dayfirst=True, errors="coerce")
    mdy = pd.to_datetime(raw, dayfirst=False, errors="coerce")

    # Excel serials (numeric-looking leftovers)
    is_num = raw.str.fullmatch(r"\d+(\.\d+)?")
    excel = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    excel.loc[is_num] = pd.to_datetime(
        raw.loc[is_num].astype(float),
        unit="D", origin="1899-12-30", errors="coerce"
    )

    # Prefer strict -> dmy -> mdy -> excel
    base = ymd.fillna(dmy).fillna(mdy).fillna(excel)

    if expected_month is not None:
        wrong = base.notna() & (base.dt.month != expected_month)

        def swap(ts):
            try:
                return pd.Timestamp(
                    year=ts.year, month=ts.day, day=ts.month,
                    hour=ts.hour, minute=ts.minute, second=ts.second
                )
            except Exception:
                return pd.NaT

        swapped = base.where(~wrong, base.map(swap))
        # Only accept swap if it fixes the month
        base = swapped.where(swapped.dt.month == expected_month, base)

    return base

def process_files(uploaded, selection, mode, expected_month:int|None, show_diag:bool):
    if mode == "Device":
        devs = []
        for f in uploaded:
            if f.name in selection:
                raw = (pd.read_excel(f, engine='openpyxl', header=None, dtype=str)
                       if f.name.lower().endswith('.xlsx')
                       else pd.read_csv(f, header=None, dtype=str, encoding='utf-8', low_memory=False))
                devs.append((f.name, clean_device_df(raw)))
        st.session_state.device_results = devs
        return

    # Alarm mode
    dfs = []
    date_col = "Alarm time"
    exclude = ["Alarm Evidence","Evidence Status","Evidence Size",
               "Evidence generation time","Evidence completion time",
               "Alarm Status","Label","Processing Contents",
               "Operator","Process time"]

    for f in uploaded:
        if f.name not in selection:
            continue

        # DO NOT force dtype=str for Excel; keep real datetimes
        if f.name.lower().endswith('.xlsx'):
            df = pd.read_excel(f, engine='openpyxl')
        else:
            df = pd.read_csv(f, dtype=str, encoding='utf-8', low_memory=False)

        # Normalize headers
        df.columns = (pd.Index(df.columns)
                        .map(lambda x: str(x).replace('\u00A0',' ').strip()))

        if date_col in df.columns:
            col = df[date_col]
            if np.issubdtype(col.dtype, np.datetime64):
                parsed = pd.to_datetime(col, errors='coerce')
            else:
                parsed = parse_alarm_series(col, expected_month=expected_month)

            df[date_col] = parsed.dt.strftime('%Y/%m/%d %H:%M:%S')

        df = df.drop(columns=[c for c in exclude if c in df], errors='ignore')
        dfs.append(df)

        # Optional diagnostics
        if show_diag and date_col in df.columns:
            with st.expander(f"Diagnostics: {f.name}", expanded=False):
                s = df[date_col].astype(str).str.strip()
                st.write({"rows": len(s)})
                # Re-run inference over raw strings for comparison if source was text
                # (For display only)
                raw_src = col.astype(str).str.strip() if not np.issubdtype(col.dtype, np.datetime64) else s
                patt_dmy = raw_src.str.match(r"\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}").sum()
                patt_ymd = raw_src.str.match(r"\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2}").sum()
                patt_num = raw_src.str.match(r"\d+(\.\d+)?").sum()
                st.write({
                    "looks_dmy": int(patt_dmy),
                    "looks_ymd": int(patt_ymd),
                    "looks_excel_serial": int(patt_num),
                })
                dmy_months = pd.to_datetime(raw_src, dayfirst=True, errors='coerce').dt.month.value_counts().sort_index()
                mdy_months = pd.to_datetime(raw_src, dayfirst=False, errors='coerce').dt.month.value_counts().sort_index()
                st.write("Month distribution if day-first:", dmy_months.to_dict())
                st.write("Month distribution if month-first:", mdy_months.to_dict())

    st.session_state.alarm_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# ─── 4) SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📂 CSV/Excel Processor")
    mode = st.selectbox("Mode:", ["Device","Alarm"], key="mode", on_change=reset_state)

    exp_month = st.number_input("Expected month (0=disable)", min_value=0, max_value=12, value=0, step=1)
    expected_month = None if exp_month == 0 else int(exp_month)

    show_diag = st.checkbox("Show diagnostics per file", value=False)

    uploaded = st.file_uploader("Upload .xlsx/.csv", accept_multiple_files=True,
                                key="uploaded_files", on_change=reset_state)

    # Keep our own list of files
    if uploaded is not None:
        st.session_state.uploaded = uploaded
    names = [f.name for f in st.session_state.uploaded]

    # --- initialize/normalize 'to_process' ONLY via session_state (no widget default) ---
    # 1) initialize on first run or after reset/uploader change
    if "to_process" not in st.session_state:
        st.session_state.to_process = names.copy()

    # 2) if the available names changed (e.g., user added/removed files), keep only valid ones
    st.session_state.to_process = [n for n in st.session_state.to_process if n in names]

    # 3) if nothing selected but there are names, auto-select all
    if not st.session_state.to_process and names:
        st.session_state.to_process = names.copy()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Select All"):
            st.session_state.to_process = names.copy()
    with c2:
        if st.button("Clear All"):
            st.session_state.to_process = []

    # IMPORTANT: no `default=` here
    to_process = st.multiselect(
        "Files to process:",
        options=names,
        key="to_process",
    )

    if st.button("Process Selected"):
        st.session_state.processed = True
        process_files(st.session_state.uploaded, to_process, mode, expected_month, show_diag)
        st.session_state.device_idx = 0

    if st.button("Reset"):
        reset_and_rerun()

# ─── 5) MAIN AREA ──────────────────────────────────────────────────────────────
col1, col2 = st.columns([1,4], gap="medium")
with col1:
    st.write("Uploaded:", len(st.session_state.uploaded))
    st.write("Selected:", len(to_process))
    st.write("Mode:", mode)
    st.write("Expected month:", expected_month if expected_month is not None else "disabled")

with col2:
    if not st.session_state.processed:
        st.markdown("## How It Works")
        if mode=="Device":
            st.write("""
- Drop merged 1st row, use 2nd as headers  
- Remove memory-usage columns  
- Deduplicate headers `(_0, _1, _2, …)`  
- Reformat `time` columns to `YYYY/MM/DD HH:MM:SS` 
- Preview 100 rows; ← → to navigate
- `.csv` file ready to download   
            """)
        else:
            st.write("""
- Upload `.xlsx`/`.csv` files  
- Keep Excel native datetimes; safely parse text dates  
- (Optional) enforce expected month by safe day↔month swap  
- Drop unwanted columns & concatenate  
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
        else:
            st.info("Nothing to show yet. Make sure files are selected and processed.")


