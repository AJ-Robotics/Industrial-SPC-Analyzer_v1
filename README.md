# Industrial SPC Analyzer

**Box-Whisker & Process Capability Analysis System**

A lightweight, offline-capable Windows desktop application for industrial
Statistical Process Control (SPC), box-and-whisker analysis, process
capability studies, and professional report generation.

The application reads production data from either **SQL Server** or **Excel**,
normalizes both into one internal data model, and runs the **same** analysis
engine on both sources.

---

## Features

- SQL Server data acquisition (Windows / SQL Server authentication)
- Excel import (`.xlsx`, `.xls`, `.csv`) with automatic & manual column mapping
- Box-and-whisker analysis with mean / median / LSL / Target / USL
- Process capability study: **Cp, Cpk, Pp, Ppk**
- Configurable capability status thresholds
- Optional normality assessment (Shapiro-Wilk / D'Agostino-Pearson)
- Trend / run charts and histograms
- Industrial dashboard with worst-parameter navigation
- Professional Excel and PDF reports
- Machine-wise, parameter-wise & model-wise configuration
- Analysis profiles / recipes
- User login (ADMIN / USER roles), role-based access
- Demo mode (no SQL Server or Excel required)
- 100% offline capable, no internet or cloud needed

---

## Requirements

- Windows 10/11 (industrial PCs and laptops)
- Python 3.10+
- [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
  (only needed if you connect to SQL Server; not required for Excel/Demo mode)

---

## Installation (development)

```bat
git clone <this-repo>
cd <project-root>

REM create a virtual environment (recommended)
python -m venv .venv
call .venv\Scripts\activate.bat

REM install dependencies
pip install -r requirements.txt
```

Run the application:

```bat
python app.py
```

> Default login: **admin / admin** (change it after first login, in
> Configuration > Users).

---

## Project Structure

```
<project-root>/
├── app.py                  # entry point
├── controller.py           # application controller (GUI <-> domain)
├── config/                 # constants + settings
├── database/
│   ├── sqlite_db.py        # local configuration store (SQLite)
│   ├── sql_server.py       # SQL Server connection (pyodbc)
│   ├── repositories.py     # CRUD for all configuration entities
│   └── demo_seed.py        # first-run demo machines/parameters
├── data/                   # source-independent data layer
│   ├── base_adapter.py
│   ├── sql_adapter.py
│   ├── excel_adapter.py
│   ├── demo_adapter.py
│   ├── data_validator.py
│   └── data_transformer.py # common data model
├── analysis/               # statistical engine (source-independent)
│   ├── statistics.py
│   ├── capability.py
│   └── normality.py
├── models/                 # analysis result model
├── charts/                 # matplotlib chart generation
├── reports/                # Excel (openpyxl) + PDF (reportlab)
├── ui/                     # PySide6 screens
├── utils/                  # logging, security, validation
├── assets/                 # logo / icon
├── samples/                # sample SQL schema + Excel file
└── build/                  # PyInstaller build scripts
```

---

## How the data sources work

Regardless of input, every row is converted into a **standardized DataFrame**:

```
SerialNumber, Timestamp, Model, Shift, Operator,
Parameter_1, Parameter_2, ...      (one column per parameter)
```

**SQL Server** and **Excel are only data sources.** There is no separate
statistical implementation for either. Analysis, box plots, capability,
trend, and reports are computed on the standardized data only.

```
SQL / Excel / Demo  ->  Standardized DataFrame  ->  Analysis Engine
                                                        |-> Box Plot
                                                        |-> Capability
                                                        |-> Trend
                                                        v
                                          Excel Report / PDF Report
```

---

## SQL Server configuration

1. Go to **Configuration ▸ SQL Server**.
2. **Connections** tab: add a connection (server, database, authentication).
   Use **TEST CONNECTION** to verify. Passwords are stored obfuscated in the
   local config database, never in plain text.
3. **Machine SQL Mapping** tab:
   - Choose the machine.
   - Select the connection.
   - Set schema (default `dbo`), table/view and the metadata columns
     (timestamp, serial, model, shift, operator — all optional).
   - In the **Parameter → SQL Column** table, map each parameter to its
     SQL column. Click **SAVE PARAMETER SQL COLUMNS**.
4. Back on the main screen, select **SQL Server** as the data source, then
   **FETCH / LOAD DATA**.

Queries are built **parameterized** (no string concatenation of input) and
only request the selected columns. Filters (date range, model, shift)
are pushed down to SQL.

---

## Excel import

1. On the main screen select **Excel**, or open **Configuration ▸ Excel Mapping**.
2. Choose the machine, **SELECT EXCEL FILE**, choose a sheet.
3. The app auto-suggests the column mapping (matching names closely).
   Correct any mappings manually.
4. Save the mapping as a **profile** for reuse, or click **IMPORT DATA**.

Excel-only filters (model, shift, date) operate on the imported dataset.

For `.xls` support, install the optional `xlrd` package (see
`requirements_extras.txt`).

---

## Machine configuration

In **Configuration ▸ Machines**: add machines. Each machine can have its own
SQL mapping, Excel mapping, parameters, limits and profiles.

## Parameter configuration

In **Configuration ▸ Parameters**: select a machine and add parameters.

Fields: name, display name, unit, SQL column, Excel column, **LSL**, **Target**,
**USL**, decimal places, enabled, analysis enabled, sequence.

- Limits are validated (LSL must be < USL; target within limits).
- Parameters with no limits are allowed; capability is shown as *unavailable*
  for them.
- A machine can have any number of parameters (tested up to 50+).

## Analysis profiles / recipes

In **Configuration ▸ Profiles**: create named recipes that bind a machine,
model, parameter set, capability method, and primary status metric.

Selecting a profile on the main screen automatically fills the parameter
selection.

---

## Capability & statistics

- **Cp**   = (USL − LSL) / (6·σ_within)
- **Cpk**  = min((USL−Mean)/(3·σ_within), (Mean−LSL)/(3·σ_within))
- **Pp**   = (USL − LSL) / (6·σ_overall)
- **Ppk**  = min((USL−Mean)/(3·σ_overall), (Mean−LSL)/(3·σ_overall))

When genuine within-subgroup data is unavailable, within indices are only
estimated from overall variation and a clear note is shown — the application
never fabricates subgroup capability.

Capability status thresholds are configurable (defaults: CAPABLE ≥ 1.33,
REVIEW ≥ 1.00, else NOT CAPABLE). The primary status metric is configurable
(Cp / Cpk / Pp / Ppk).

Special cases handled without misleading output:
- missing LSL / USL, only one-sided limits
- LSL ≥ USL (rejected at configuration)
- zero / non-positive standard deviation (identical values)
- insufficient samples
- non-finite (NaN / Inf) values
- non-normal data (shown as a warning, not invalidating results)

---

## Reports

Reports are generated from the **same** AnalysisResult object used by the GUI,
so all numbers are consistent.

- **Excel** (`.xlsx`): Report Summary, Capability Summary, one detailed sheet
  per parameter (statistics, specification, capability, embedded box plot,
  histogram, trend), Data Quality, and optional Raw Data sheet.
- **PDF**: cover/header, Executive Summary, Capability Summary, per-parameter
  statistics/specification/capability with embedded box plot, histogram and
  trend, page numbers, and footer.

Report metadata (company, plant, line, prefix, revision, prepared/reviewed/
approved, logo) is configured in **Configuration ▸ Settings**.

---

## Packaging (Windows executable)

Use the provided `build.py` to produce a **portable, runtime executable** that
runs on another PC with **no Python or installation required**:

```bat
python build.py            REM single .exe (default)  -> dist\IndustrialSPCAnalyzer.exe
python build.py --onedir   REM folder-based deployment (faster startup)
```

Options:
- `--onefile` / `--onedir` — single `.exe` or folder-based deployment.
- `--name NAME` — custom executable name.
- `--console` — include a console window (debugging only).
- `--no-venv` — build with the current Python environment instead of the
  isolated build venv.

By default `build.py` creates an isolated build virtual environment
(`.build-venv`) containing only the runtime dependencies, so the build is fast
and the executable stays small. A PyInstaller spec and batch script are also
available under `build/` for advanced/CI use:

```bat
build\build_windows.bat
```

The app stores its local config database and logs **next to the executable**
when running as a packaged build, making it fully portable — copy the `.exe`
to any target PC and run it directly.

---

## Demo mode

On the main screen select **Demo Data**. Demo mode generates labelled
**DEMO DATA** (synthetic) for the configured machines and parameters — no SQL
Server or Excel file required. Demo data is always clearly labelled and never
presented as production data.

---

## Sample data

- `samples/sample_sql_schema.sql` — example SQL schema + test data.
- `samples/Sample_Data_Machine1.xlsx` — example Excel file the app can import.
- `samples/generate_sample_excel.py` — regenerate/alter the sample Excel file.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| SQL Connection Failed | Check server address, database, network, authentication; confirm "ODBC Driver 17 for SQL Server" is installed. |
| Excel import failed | Ensure the file is not corrupted, the sheet exists, and required columns are mapped (or mapped automatically). |
| Analysis failed / no data | Fetch/load data first, then run analysis; ensure at least one parameter is selected. |
| Capability N/A | The parameter has no limits, insufficient data, or invalid configuration; the note explains why. |
| Logs | See `logs/application.log` (rotated, credentials are never logged). |

---

## Security

- Passwords are hashed (PBKDF2).
- SQL credentials are stored obfuscated, not plain text, and never logged.
- All SQL uses parameterized queries.
- Role-based access: non-admin users cannot open configuration or users pages.
