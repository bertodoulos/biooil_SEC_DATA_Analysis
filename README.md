# biooil_SEC_DATA_Analysis
A program that uses size exclusion HPLC data to estimate molecular weight distributions and average MWs

# Bio-Oil SEC Analytical Suite

A modern, browser-based web application tailored for the automated processing, calibration, and relative abundance analysis of Size Exclusion Chromatography (SEC) data derived from bio-oil upgrading projects. 

This application bridges the gap between raw analytical instrument data and downstream engineering reports, removing the need for manual copy-pasting, tedious multi-step spreadsheet integrations, or local script execution.

---

## 🚀 Live Access
The application is deployed on the cloud and can be accessed directly by all team members here:
👉 **[INSERT YOUR STREAMLIT APP URL HERE (e.g., https://biooil-sec-suite.streamlit.app)]**

*Note: No Streamlit account or authentication login is required to run the app.*

---

## 🛠️ Key Features

- **Automated Mass Batch Builder (Tab 1):** Instantly builds run lists by fuzzy-matching raw sample file names against an R&D Master Database to pull exact oil and solvent weights (`oil_mass_mg` and `2meth_thf_mass_mg`).
- **Robust Multi-Format File Reader:** Seamlessly handles instrument-specific encoding types (such as UTF-16) and variable data delimiters (tabs or commas) without throwing encoding exceptions.
- **Power-Law Column Calibration (Tab 2):** Performs linear regressions on standard peak logs to live-calculate and map the power-law relation ($MW = a \cdot t^b$), featuring state file tracking via lightweight `.json` files.
- **Advanced Baseline Integration & Math (Tab 3):** Automatically handles timeline interpolations for accurate solvent background blank subtractions, applies line flattening baseline corrections, and integrations out $M_n$, $M_w$, and Polydispersity Index ($PDI$).
- **Report & View Filtering:** Multi-selection control panels let users cherry-pick specific active curves to dynamically render charts, hide processing anomalies, and slice relative abundances into custom Dalton buckets.
- **One-Click Multi-Page Vector PDF Reports:** Generates professional, scalable vector reports compiling run logs, calibration curves, analytical result tables, and fraction charts into a unified document.

---

## 📋 Repository Structure

```text
├── app.py                # Main Streamlit web application script
├── requirements.txt      # Automated cloud deployment dependency matrix
└── README.md             # Repository documentation (this file)
