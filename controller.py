"""Application controller.

Sits between the GUI and the domain/data/report layers. The GUI calls single
high-level methods here; the controller orchestrates adapters, the analysis
engine, validation and report generation. This enforces separation of
responsibilities.
"""

import os
from datetime import datetime

import pandas as pd

from config import constants, settings as app_settings
from database import repositories as repos
from database.repositories import (MachineRepository, ParameterRepository,
                                   ProfileRepository, SqlConnectionRepository,
                                   SqlMappingRepository, SettingsRepository)
from data import data_validator, data_transformer
from data.demo_adapter import DemoDataAdapter
from data.excel_adapter import ExcelDataAdapter
from data.sql_adapter import SqlDataAdapter
from analysis import statistics as stat_engine
from reports import report_utils
from reports import excel_report as excel_report_mod
from reports import pdf_report as pdf_report_mod
from utils import logger, validators


class Controller:
    def __init__(self):
        self.machine_repo = MachineRepository()
        self.param_repo = ParameterRepository()
        self.profile_repo = ProfileRepository()
        self.sql_conn_repo = SqlConnectionRepository()
        self.sql_map_repo = SqlMappingRepository()
        self.settings_repo = SettingsRepository()

        self.current_df = None      # standardized DataFrame (cached)
        self.current_raw = None     # raw source DataFrame
        self.current_result = None  # AnalysisResult
        self.current_source_info = {}
        self.current_machine_id = None
        self.current_quality = None
        self.current_selection = None  # None = all rows; else list of positions

    # ------------------------------------------------------------------ #
    # Application settings
    # ------------------------------------------------------------------ #
    def load_settings(self):
        vals = self.settings_repo.load_all()
        app_settings.set_values(vals)

    def save_setting(self, key, value):
        self.settings_repo.set(key, value)
        self.load_settings()

    def save_settings(self, mapping):
        self.settings_repo.set_many(mapping)
        self.load_settings()

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def load_from_sql(self, machine_id, parameter_ids, date_from=None,
                      date_to=None, model=None, shift=None):
        machine = self.machine_repo.get(machine_id)
        if not machine:
            raise ValueError("Machine not found.")
        mapping = self.sql_map_repo.get_for_machine(machine_id)
        if not mapping or not mapping.get("table_name"):
            raise ValueError(
                "No SQL table configured for this machine.\n"
                "Configure it in Configuration > SQL.")
        conn_id = mapping.get("connection_id")
        if not conn_id:
            raise ValueError("No SQL connection configured for this machine.")
        conn = self.sql_conn_repo.get_decrypted(conn_id)

        params = self.param_repo.list_for_machine(machine_id)
        selected = [p for p in params if p["id"] in set(parameter_ids)]
        parameter_map = {}
        for p in selected:
            col = p.get("sql_column") or p.get("display_name") or p.get("name")
            parameter_map[p.get("display_name") or p.get("name")] = col

        # Build field map (standard key -> sql alias). The adapter returns
        # aliases Serial, Timestamp, Model, Shift, Operator.
        alias_field = {}
        if mapping.get("timestamp_column"):
            alias_field[constants.FIELD_TIMESTAMP] = "Timestamp"
        if mapping.get("serial_column"):
            alias_field[constants.FIELD_SERIAL] = "Serial"
        if mapping.get("model_column"):
            alias_field[constants.FIELD_MODEL] = "Model"
        if mapping.get("shift_column"):
            alias_field[constants.FIELD_SHIFT] = "Shift"
        if mapping.get("operator_column"):
            alias_field[constants.FIELD_OPERATOR] = "Operator"

        adapter = SqlDataAdapter(
            conn, mapping, parameter_map,
            date_from=date_from, date_to=date_to, model=model, shift=shift)
        raw = adapter.load()
        logger.info("SQL load complete: %d rows", len(raw))
        standard, warnings = data_transformer.build_standard_dataframe(
            raw, alias_field, parameter_map)

        self.current_raw = raw
        self.current_df = standard
        self.current_machine_id = machine_id
        self.current_selection = None  # default: all fetched rows selected
        desc = adapter.describe()
        self.current_source_info = {
            "source": "SQL Server",
            "machine": machine["name"],
            "detail": f"{desc.get('server','')}/{desc.get('database','')} "
                      f":: {desc.get('table','')}",
            "warnings": warnings,
        }
        self._compute_quality()
        return self._load_summary()

    def load_from_excel(self, filepath, machine_id, field_map, parameter_map,
                        sheet_name=None):
        adapter = ExcelDataAdapter(filepath)
        if not sheet_name:
            sheets = adapter.list_sheets()
            if not sheets:
                raise ValueError("Excel file has no readable sheets.")
            sheet_name = sheets[0]
        adapter.load_sheet(sheet_name, 0)
        standard, warnings = adapter.to_standard(field_map, parameter_map)
        machine = self.machine_repo.get(machine_id)
        self.current_machine_id = machine_id
        self.current_raw = adapter.get_raw()
        self.current_df = standard
        self.current_selection = None  # default: all fetched rows selected
        self.current_source_info = {
            "source": "Excel",
            "machine": machine["name"] if machine else "",
            "detail": f"{os.path.basename(filepath)} :: {sheet_name or adapter.sheet_name}",
            "warnings": warnings,
        }
        self._compute_quality()
        return self._load_summary()

    def load_from_demo(self, machine_id, parameter_ids):
        machine = self.machine_repo.get(machine_id)
        params = self.param_repo.list_for_machine(machine_id)
        selected = [p for p in params if p["id"] in set(parameter_ids)]
        # build generation specs with demo means around the configured targets
        demo_params = []
        for p in selected:
            mean = p.get("target") if p.get("target") is not None else 10.0
            span = 0
            if p.get("usl") is not None and p.get("lsl") is not None:
                span = (p["usl"] - p["lsl"])
            std = span / 8.0 if span else 0.5
            name = p.get("display_name") or p.get("name")
            demo_params.append({"name": name, "mean": mean, "std": std,
                                "lsl": p.get("lsl"), "usl": p.get("usl")})

        adapter = DemoDataAdapter(machine["name"], demo_params)
        raw = adapter.load()
        # Standardized Demo adapter already returns standard columns
        standard = raw.copy()
        parameter_map = {p.get("display_name") or p.get("name"): (p.get("display_name") or p.get("name")) for p in selected}
        # ensure column names match display names
        for p in selected:
            disp = p.get("display_name") or p.get("name")
            if disp in standard.columns:
                pass
        self.current_raw = raw
        self.current_df = standard
        self.current_machine_id = machine_id
        self.current_selection = None  # default: all fetched rows selected
        self.current_source_info = {
            "source": "Demo", "machine": machine["name"],
            "detail": "DEMO DATA (synthetic)", "warnings": [],
        }
        self._compute_quality()
        return self._load_summary()

    # ------------------------------------------------------------------ #
    # Row selection
    # ------------------------------------------------------------------ #
    def selected_df(self):
        """Return the cached df restricted to the rows chosen for analysis.

        ``current_selection`` is None when every fetched row is selected.
        """
        if self.current_df is None:
            return None
        if self.current_selection is None:
            return self.current_df
        return self.current_df.iloc[self.current_selection]

    def selected_positions(self):
        """Return positional indices of the rows chosen for analysis."""
        if self.current_df is None:
            return []
        if self.current_selection is None:
            return list(range(len(self.current_df)))
        return list(self.current_selection)

    def set_selection(self, positions):
        """Set the rows (positional indices) to include in the analysis.

        Passing None (or every row) restores the default 'all rows' selection.
        """
        if self.current_df is None:
            self.current_selection = None
        elif positions is None:
            self.current_selection = None
        else:
            total = len(self.current_df)
            sel = sorted({int(p) for p in positions if 0 <= int(p) < total})
            self.current_selection = None if len(sel) == total else sel
        self._compute_quality()

    # ------------------------------------------------------------------ #
    # Quality
    # ------------------------------------------------------------------ #
    def _compute_quality(self):
        df = self.selected_df()
        params = self.param_repo.list_for_machine(self.current_machine_id)
        cols = [p.get("display_name") or p.get("name") for p in params
                if (p.get("display_name") or p.get("name")) in
                (df.columns if df is not None else [])]
        if not cols and df is not None:
            cols = [c for c in df.columns
                    if c not in constants.STANDARD_COLUMNS]
        self.current_quality = data_validator.validate(df, cols)

    def _load_summary(self):
        q = self.current_quality
        return {
            "total": q.total_records,
            "valid": q.valid_records,
            "missing": q.missing_values,
            "invalid": q.invalid_values,
            "duplicates": q.duplicate_records,
            "source": self.current_source_info,
        }

    def clean_current(self):
        """Return a cleaned copy of the selected rows (invalid rows removed)."""
        df = self.selected_df()
        if df is None:
            return None
        params = self.param_repo.list_for_machine(self.current_machine_id)
        cols = [p.get("display_name") or p.get("name") for p in params
                if (p.get("display_name") or p.get("name")) in df.columns]
        return data_validator.clean_for_analysis(df, cols)

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #
    def run_analysis(self, parameter_ids, capability_method="BOTH",
                     primary_status="Cpk"):
        if self.current_df is None or self.current_df.empty:
            raise ValueError("No data loaded. Fetch/load data first.")
        if self.selected_df() is None or self.selected_df().empty:
            raise ValueError(
                "No rows are selected for analysis. Open the data preview and "
                "select at least one row.")
        machine = self.machine_repo.get(self.current_machine_id)
        params = self.param_repo.list_for_machine(self.current_machine_id)
        selected = [p for p in params if p["id"] in set(parameter_ids)]
        if not selected:
            raise ValueError("No parameters selected for analysis.")

        cleaned = self.clean_current()
        result = stat_engine.run_analysis(
            cleaned, selected, capability_method=capability_method,
            primary_status=primary_status)
        result.machine = machine["name"] if machine else ""
        result.profile = ""
        result.data_source = self.current_source_info.get("source", "")
        result.source_detail = self.current_source_info.get("detail", "")
        result.generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result.user = getattr(self, "_current_user", "")
        result.capability_method = capability_method
        result.primary_status = primary_status
        result.total_records = self.current_quality.total_records
        result.valid_records = self.current_quality.valid_records
        result.missing_values = self.current_quality.missing_values
        result.invalid_values = self.current_quality.invalid_values
        result.duplicate_records = self.current_quality.duplicate_records

        # analysis period from timestamps if present
        ts = cleaned.get(constants.COL_TIMESTAMP)
        if ts is not None and ts.notna().any():
            result.period_from = ts.min().strftime("%Y-%m-%d %H:%M")
            result.period_to = ts.max().strftime("%Y-%m-%d %H:%M")
        else:
            result.period_from = ""
            result.period_to = ""

        result.report_number = report_utils.get_report_number()
        self.current_result = result
        logger.info("Analysis complete: %d parameters", len(selected))
        return result

    def set_result_meta(self, user=""):
        if self.current_result:
            self.current_result.user = user

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #
    def export_excel(self, filepath, include_raw=False, my_cleaned=None):
        if not self.current_result:
            raise ValueError("No analysis result to export.")
        cleaned = my_cleaned if my_cleaned is not None else self.clean_current()
        return excel_report_mod.generate_excel_report(
            self.current_result, filepath, include_raw=include_raw,
            raw_df=cleaned)

    def export_pdf(self, filepath, bins=20, include_raw=False):
        if not self.current_result:
            raise ValueError("No analysis result to export.")
        # PDF reports contain summaries/charts only; raw data is
        # available via the Excel report / Export Raw Data.
        return pdf_report_mod.generate_pdf_report(
            self.current_result, filepath, bins=bins)

    def export_raw_data(self, filepath):
        cleaned = self.clean_current()
        if cleaned is None or cleaned.empty:
            raise ValueError("No data to export.")
        cleaned.to_excel(filepath, index=False)
        return filepath

    # ------------------------------------------------------------------ #
    # Cache
    # ------------------------------------------------------------------ #
    def clear_data(self):
        self.current_df = None
        self.current_raw = None
        self.current_result = None
        self.current_source_info = {}
        self.current_quality = None
        self.current_selection = None
