"""
================================================================================
SEC Analytical Suite - Streamlit Web Edition
================================================================================
Description:
This web application automates the processing, calibration, and reporting of SEC data.
================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from matplotlib.backends.backend_pdf import PdfPages
import os
import json
import io
import warnings

# Suppress pandas warnings for cleaner background execution
warnings.filterwarnings('ignore')

# Set page configuration to wide mode to fit laptop screens beautifully
st.set_page_config(page_title="SEC Analytical Suite", layout="wide")

# ==========================================
# INITIALIZE SESSION STATE (App Memory)
# ==========================================
if "calib_multiplier" not in st.session_state:
    st.session_state["calib_multiplier"] = 3.04850e15
if "calib_exponent" not in st.session_state:
    st.session_state["calib_exponent"] = -9.63581
if "loaded_calib_name" not in st.session_state:
    st.session_state["loaded_calib_name"] = "Default Constants"
if "current_std_data" not in st.session_state:
    st.session_state["current_std_data"] = []

if "master_results" not in st.session_state:
    st.session_state["master_results"] = []
if "master_all_curves" not in st.session_state:
    st.session_state["master_all_curves"] = {}
if "master_raw_curves" not in st.session_state:
    st.session_state["master_raw_curves"] = []

if "results_df" not in st.session_state:
    st.session_state["results_df"] = None
if "all_curves" not in st.session_state:
    st.session_state["all_curves"] = {}
if "raw_curves" not in st.session_state:
    st.session_state["raw_curves"] = []
if "fractions_df" not in st.session_state:
    st.session_state["fractions_df"] = None

# ==========================================
# APP NAVIGATION
# ==========================================
st.sidebar.title("SEC Analytical Suite")
page = st.sidebar.radio(
    "Go to Workflow Step:",
    [
        "1. File upload",
        "2. Calibration Curve",
        "3. MW Fractions",
        "4. Quick Screening Overlay",
        "5. Theory & Mathematics"
    ]
)

# ==========================================
# CORE UTILITY FUNCTIONS
# ==========================================
def parse_csv_file(uploaded_file):
    """Robust text file loader handling UTF-8, UTF-16, commas, and tabs safely."""
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)  # Reset buffer pointer
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), header=None, sep=None, engine='python', on_bad_lines='skip')
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(file_bytes), header=None, sep=None, engine='python', on_bad_lines='skip', encoding='utf-16')
        return df
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {e}")
        return None

def draw_pdf_table(df, title):
    """Generates a matplotlib figure containing a table for compilation into the PDF report."""
    fig_height = max(5, len(df) * 0.4)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    ax.axis('off')
    ax.set_title(title, fontweight='bold', fontsize=14, pad=20)
    df_disp = df.copy()
    for col in df_disp.columns:
        if pd.api.types.is_float_dtype(df_disp[col]):
            df_disp[col] = df_disp[col].round(2)
    table = ax.table(cellText=df_disp.values, colLabels=df_disp.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    fig.tight_layout()
    return fig

# ==========================================
# STEP 1: FILE UPLOAD & ANALYTICS
# ==========================================
if page == "1. File upload":
    st.header("Step 1: File upload & Analytics")
    st.info("Upload your Oil Concentration file along with your sample and solvent CSVs together once to run the math.")

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Data Uploads")
        oil_conc_file = st.file_uploader("1. Upload Oil Concentration File", type=["xlsx"])
        uploaded_csvs = st.file_uploader("2. Upload ALL Sample + Solvent CSVs together", type=["csv"], accept_multiple_files=True)
        
        st.markdown("---")
        st.subheader("Calculation Constraints")
        t_start = st.number_input("Integration Start Time (min)", value=12.0)
        t_end = st.number_input("Integration End Time (min)", value=35.0)
        
        run_calc = st.button("▶ Process Batch & Calculate MW", type="primary")
        
        if run_calc:
            if not oil_conc_file:
                st.error("Missing Oil Concentration file.")
            elif not uploaded_csvs:
                st.error("Please upload your sample and solvent CSV tracks.")
            else:
                try:
                    # Parse Oil Concentration File
                    all_sheets = pd.read_excel(oil_conc_file, sheet_name=None, header=0, skiprows=[1])
                    valid_sheets = [df for name, df in all_sheets.items() if not df.empty and "sample_id" in df.columns]
                    if not valid_sheets:
                        st.error("No valid metrics found containing 'sample_id' inside the Oil Concentration file.")
                    else:
                        master_df = pd.concat(valid_sheets, ignore_index=True).dropna(subset=["sample_id"])
                        
                        # Deduplicate file pool map by filename to prevent duplicates
                        file_map = {}
                        for f in uploaded_csvs:
                            file_map[f.name] = f
                        
                        # Identify solvent files automatically via naming conventions
                        sol_lookup = [f for f in file_map.keys() if "solvent" in f.lower() or "blank" in f.lower() or "thf" in f.lower()]
                        sol_file_key = sol_lookup[0] if sol_lookup else None
                        
                        if not sol_file_key:
                            st.error("Could not find a solvent blank file in the uploaded pool. Ensure the filename contains 'solvent', 'blank', or 'thf'.")
                        else:
                            st.session_state["master_results"] = []
                            st.session_state["master_all_curves"] = {}
                            st.session_state["master_raw_curves"] = []
                            
                            mult = st.session_state["calib_multiplier"]
                            exp = st.session_state["calib_exponent"]
                            
                            # Scan only files that are NOT solvents
                            sample_keys = [k for k in file_map.keys() if k != sol_file_key]
                            
                            # Keep track of unique short names processed to stop name duplication collision
                            seen_short_names = set()
                            
                            for s_key in sample_keys:
                                clean_name = s_key.lower().replace(" ", "")
                                match = master_df[master_df["sample_id"].apply(lambda x: str(x).lower().replace(" ", "") in clean_name if pd.notnull(x) else False)]
                                
                                if match.empty:
                                    st.warning(f"Skipping file {s_key}: Not found in Oil Concentration file.")
                                    continue
                                    
                                sam_short_id = s_key.split('.')[0]
                                if sam_short_id in seen_short_names:
                                    continue
                                seen_short_names.add(sam_short_id)
                                    
                                bio_mg = match.iloc[0]["oil_mass_mg"]
                                sol_mg = match.iloc[0]["2meth_thf_mass_mg"]
                                
                                df_sam = parse_csv_file(file_map[s_key])
                                df_sol = parse_csv_file(file_map[sol_file_key])
                                
                                if df_sam is not None and df_sol is not None:
                                    t_sam = pd.to_numeric(df_sam.iloc[:,0], errors='coerce').values
                                    sig_sam = pd.to_numeric(df_sam.iloc[:,1], errors='coerce').values
                                    t_sol = pd.to_numeric(df_sol.iloc[:,0], errors='coerce').values
                                    sig_sol = pd.to_numeric(df_sol.iloc[:,1], errors='coerce').values
                                    
                                    # Core Analytics Calculations
                                    sig_sol_aligned = np.interp(t_sam, t_sol, sig_sol)
                                    norm_sig = (sig_sam - sig_sol_aligned) / (bio_mg / (bio_mg + sol_mg))
                                    
                                    idx_start = np.argmin(np.abs(t_sam - t_start))
                                    idx_end = np.argmin(np.abs(t_sam - t_end))
                                    m = (norm_sig[idx_end] - norm_sig[idx_start]) / (t_sam[idx_end] - t_sam[idx_start])
                                    corr_sig = norm_sig - (m * t_sam + norm_sig[idx_start] - m * t_sam[idx_start])
                                    
                                    mask = (t_sam >= t_start) & (t_sam <= t_end)
                                    t_peak, W_i = t_sam[mask], corr_sig[mask]
                                    W_i[W_i < 0] = 0
                                    MW_i = mult * (t_peak ** exp)
                                    
                                    if np.sum(W_i) > 0:
                                        Mn = np.sum(W_i) / np.sum(W_i / MW_i)
                                        Mw = np.sum(W_i * MW_i) / np.sum(W_i)
                                        PDI = Mw / Mn
                                    else:
                                        Mn, Mw, PDI = 0, 0, 0
                                        
                                    st.session_state["master_results"].append({'Sample': sam_short_id, 'Mn': round(Mn), 'Mw': round(Mw), 'PDI': round(PDI, 2)})
                                    st.session_state["master_all_curves"][sam_short_id] = {'MW': MW_i, 'W': W_i}
                                    st.session_state["master_raw_curves"].append((sam_short_id, t_peak, W_i))
                            
                            st.success(f"Successfully processed {len(st.session_state['master_results'])} analytical runs!")
                except Exception as e:
                    st.error(f"Error executing combined analysis: {e}")

    with col2:
        st.subheader("Active Display Control")
        if not st.session_state["master_results"]:
            st.info("Upload your data dependencies on the left and click Process to generate tables and curves.")
        else:
            st.write("Select records to plot or integrate into reporting arrays:")
            selected_samples = []
            
            # FIXED: Guaranteed unique key generation using loop index tracking
            for idx, res in enumerate(st.session_state["master_results"]):
                if st.checkbox(res['Sample'], value=True, key=f"cb_main_{res['Sample']}_{idx}"):
                    selected_samples.append(res['Sample'])
            
            # Apply Filter Arrays
            st.session_state["results_df"] = pd.DataFrame([r for r in st.session_state["master_results"] if r['Sample'] in selected_samples])
            st.session_state["all_curves"] = {k: v for k, v in st.session_state["master_all_curves"].items() if k in selected_samples}
            st.session_state["raw_curves"] = [c for c in st.session_state["master_raw_curves"] if c[0] in selected_samples]
            
            # Distribution Plotting
            fig, ax = plt.subplots(figsize=(6, 4))
            for name, data in st.session_state["all_curves"].items():
                ax.plot(data['MW'], data['W'], label=name)
            ax.axhline(0, color='black', linestyle='--', linewidth=1)
            ax.set_xscale('log')
            if not ax.xaxis_inverted(): ax.invert_xaxis()
            ax.set_title("Molecular Weight Distribution Profiles", fontweight='bold')
            ax.set_xlabel("Molecular Weight (Da)", fontweight='bold')
            ax.set_ylabel("Normalized Abundance", fontweight='bold')
            ax.grid(True, which="both", linestyle=':', alpha=0.5)
            if selected_samples: ax.legend(frameon=False)
            st.pyplot(fig)
            
            st.write("#### Quantified Metrics Summary")
            st.dataframe(st.session_state["results_df"])
            
            if not st.session_state["results_df"].empty:
                pdf_buffer = io.BytesIO()
                with PdfPages(pdf_buffer) as pdf:
                    f_run = draw_pdf_table(st.session_state["results_df"], "SEC Target Averages Summary")
                    pdf.savefig(f_run); plt.close(f_run)
                    fig.tight_layout()
                    pdf.savefig(fig)
                pdf_buffer.seek(0)
                st.download_button("📄 Download Document PDF Report", data=pdf_buffer, file_name="SEC_Comprehensive_Report.pdf", mime="application/pdf")

# ==========================================
# STEP 2: CALIBRATION CURVE
# ==========================================
elif page == "2. Calibration Curve":
    st.header("Step 2: Column Calibration Engine")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Calibration Targets")
        mult_input = st.number_input("Multiplier (a)", value=st.session_state["calib_multiplier"], format="%.5e")
        exp_input = st.number_input("Exponent (b)", value=st.session_state["calib_exponent"], format="%.5f")
        st.session_state["calib_multiplier"] = mult_input
        st.session_state["calib_exponent"] = exp_input
        
        st.markdown("---")
        st.subheader("Manage Saved States")
        
        calib_dict = {
            "multiplier": st.session_state["calib_multiplier"],
            "exponent": st.session_state["calib_exponent"],
            "standards_table": st.session_state["current_std_data"]
        }
        st.download_button(
            "Export Configuration (JSON)",
            data=json.dumps(calib_dict, indent=4),
            file_name="SEC_Calibration.json",
            mime="application/json"
        )
        
        imported_json = st.file_uploader("Import Config File (JSON)", type=["json"])
        if imported_json:
            try:
                data = json.load(imported_json)
                st.session_state["calib_multiplier"] = data["multiplier"]
                st.session_state["calib_exponent"] = data["exponent"]
                st.session_state["current_std_data"] = data.get("standards_table", [])
                st.session_state["loaded_calib_name"] = imported_json.name
                st.success("Calibration data loaded successfully!")
            except Exception as e:
                st.error(f"Malformed config: {e}")

        st.markdown("---")
        st.subheader("Auto-Calculate from Standards")
        std_uploads = st.file_uploader("Upload known standard CSV runs", type=["csv"], accept_multiple_files=True)
        
        if std_uploads:
            calculated_stds = []
            with st.form("std_form"):
                st.write("Provide Molecular weights for uploaded standard files:")
                inputs = {}
                for idx, file in enumerate(std_uploads):
                    inputs[file.name] = st.number_input(f"MW for {file.name}", value=1000, key=f"std_mw_{idx}")
                submit_stds = st.form_submit_button("Run Regression Math")
                
                if submit_stds:
                    for file in std_uploads:
                        df = parse_csv_file(file)
                        if df is not None:
                            t = pd.to_numeric(df.iloc[:,0], errors='coerce').values
                            sig = pd.to_numeric(df.iloc[:,1], errors='coerce').values
                            t_peak = t[np.nanargmax(sig)]
                            calculated_stds.append({'Standard': file.name, 'MW': inputs[file.name], 't_peak': t_peak})
                    
                    if len(calculated_stds) >= 2:
                        df_std = pd.DataFrame(calculated_stds)
                        log_t, log_MW = np.log10(df_std['t_peak']), np.log10(df_std['MW'])
                        slope, intercept = np.polyfit(log_t, log_MW, 1)
                        
                        st.session_state["calib_multiplier"] = 10 ** intercept
                        st.session_state["calib_exponent"] = slope
                        st.session_state["current_std_data"] = calculated_stds
                        st.session_state["loaded_calib_name"] = "Fresh Matrix Calculation"
                        st.success("Recalculation complete!")
                    else:
                        st.error("Matrix generation requires at least 2 valid standards.")

    with col2:
        st.subheader("Calibration Graph View")
        fig, ax = plt.subplots(figsize=(6, 4))
        
        if st.session_state["current_std_data"]:
            df_points = pd.DataFrame(st.session_state["current_std_data"])
            ax.scatter(df_points['t_peak'], df_points['MW'], color='red', label='Standard Peaks', zorder=5)
            t_min, t_max = df_points['t_peak'].min() * 0.9, df_points['t_peak'].max() * 1.1
        else:
            t_min, t_max = 10, 40
            
        t_fit = np.linspace(t_min, t_max, 100)
        mw_fit = st.session_state["calib_multiplier"] * (t_fit ** st.session_state["calib_exponent"])
        ax.plot(t_fit, mw_fit, 'b--', label='Power-Law Fit')
        
        eq_text = f"MW = {st.session_state['calib_multiplier']:.3e} * t^({st.session_state['calib_exponent']:.4f})"
        ax.set_title(f"SEC Calibration: {st.session_state['loaded_calib_name']}\n{eq_text}", fontweight='bold')
        ax.set_xlabel("Retention Time (min)", fontweight='bold')
        ax.set_ylabel("Molecular Weight (Da)", fontweight='bold')
        ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(frameon=False)
        st.pyplot(fig)

# ==========================================
# STEP 3: MW FRACTIONS
# ==========================================
elif page == "3. MW Fractions":
    st.header("Step 3: Integration of Sliced Fractions")
    
    if not st.session_state["all_curves"]:
        st.warning("Please compute operational run profiles under Step 1 first.")
    else:
        mw_ranges = [("100-15 Da", 100, 15), ("250-100 Da", 250, 100), ("850-250 Da", 850, 250), ("3500-850 Da", 3500, 850), ("16000-3500 Da", 16000, 3500)]
        
        fraction_results = []
        for sam_name, data in st.session_state["all_curves"].items():
            MW, W = data['MW'], data['W']
            total_area = np.sum(W)
            sample_fractions = {'Sample': sam_name}
            for label, high, low in mw_ranges:
                rel_abundance = (np.sum(W[(MW <= high) & (MW > low)]) / total_area) * 100 if total_area > 0 else 0.0
                sample_fractions[label] = round(rel_abundance, 2)
            fraction_results.append(sample_fractions)
            
        st.session_state["fractions_df"] = pd.DataFrame(fraction_results)
        
        st.subheader("Relative Abundance Grid Metric (%)")
        st.dataframe(st.session_state["fractions_df"])
        
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = ['#4472c4', '#ffc000', '#00b050', '#ed7d31', '#5b9bd5']
        labels = [r[0] for r in mw_ranges]
        x, width = np.arange(len(st.session_state["fractions_df"])), 0.15
        offsets = [-2*width, -width, 0, width, 2*width]
        
        for i, col in enumerate(labels):
            ax.bar(x + offsets[i], st.session_state["fractions_df"][col], width, label=col, color=colors[i], edgecolor='white', linewidth=0.5)
            
        ax.set_ylabel('Relative Abundance (%)', fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(st.session_state["fractions_df"]['Sample'].tolist(), rotation=45, ha='right', fontweight='bold')
        ax.grid(axis='y', linestyle='-', color='gray', alpha=0.3)
        bottom, top = ax.get_ylim()
        ax.set_ylim(bottom=0, top=top * 1.15)
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.02), ncol=5, frameon=False)
        st.pyplot(fig)

# ==========================================
# STEP 4: QUICK SCREENING OVERLAY
# ==========================================
elif page == "4. Quick Screening Overlay":
    st.header("Step 4: Visual Overlay Screening Matrix")
    
    if not st.session_state["master_raw_curves"]:
        st.warning("Please execute analytics computations inside Step 1 to view comparative records.")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Filter Matrix")
            overlay_selected = []
            
            # FIXED: Guaranteed unique key generation using loop index tracking
            for idx, res in enumerate(st.session_state["master_results"]):
                if st.checkbox(res['Sample'], value=True, key=f"cb_over_{res['Sample']}_{idx}"):
                    overlay_selected.append(res['Sample'])
                    
        with col2:
            st.subheader("Max-Normalized Relative Output Profiles")
            fig, ax = plt.subplots(figsize=(6, 4))
            for sam_name, t_peak, W_i in st.session_state["master_raw_curves"]:
                if sam_name in overlay_selected:
                    peak_max = np.max(W_i)
                    if peak_max > 0:
                        ax.plot(t_peak, W_i / peak_max, label=sam_name, linewidth=2)
                        
            ax.set_xlabel("Retention Time (min)", fontweight='bold')
            ax.set_ylabel("Normalized Signal (Peak Max = 1.0)", fontweight='bold')
            ax.grid(True, linestyle='--', alpha=0.6)
            if overlay_selected: ax.legend(frameon=False)
            st.pyplot(fig)
            
            if overlay_selected:
                pdf_over_buf = io.BytesIO()
                fig.savefig(pdf_over_buf, format='pdf')
                pdf_over_buf.seek(0)
                st.download_button("📄 Save Standalone Overlay Plot PDF", data=pdf_over_buf, file_name="SEC_Screening_Overlay.pdf", mime="application/pdf")

# ==========================================
# STEP 5: THEORY & MATHEMATICS
# ==========================================
elif page == "5. Theory & Mathematics":
    st.header("Step 5: Mathematical Computation Logic Core")
    
    st.markdown("""
    ### 1. Mass Correlation Indexing Architecture
    The engine pairs uploaded file names (e.g., `PILOT_7_2.csv`) directly with rows in the Oil Concentration file, automatically extracting `oil_mass_mg` and `2meth_thf_mass_mg` metrics to establish proper dilution equations.
    
    ### 2. Standard Regression Fit Polynomial
    Peak positions are evaluated using maximum array indicators ($np.nanargmax$). Logarithmic coordinates track calibration targets through standard line fitting mechanics:
    $$\\log_{10}(MW) = m \\cdot \\log_{10}(t_{peak}) + b$$
    
    Which converts back to exponential format profiles:
    $$MW = a \\cdot t^b \\quad \\text{where } a = 10^b \\text{ and } b = m$$
    
    ### 3. Molecular Distribution Analytics Calculations
    * **Baseline Level Alignments:** Aligns timelines via 1D array linear coordinate data interpolation arrays ($np.interp$).
    * **Concentration Vector Calibration:** $$Signal_{Corrected} = \\frac{Sample - Solvent}{\\frac{Mass_{Oil}}{Mass_{Oil} + Mass_{Solvent}}}$$
    * **Integral Averages Estimations:** Fits standard numerical Riemann summations:
        * Number Average ($M_n$): $$M_n = \\frac{\\sum W_i}{\\sum \\left(\\frac{W_i}{MW_i}\\right)}$$
        * Weight Average ($M_w$): $$M_w = \\frac{\\sum (W_i \\cdot MW_i)}{\\sum W_i}$$
        * Dispersity Calculation Metrics ($PDI$): $$PDI = \\frac{M_w}{M_n}$$
    """)
