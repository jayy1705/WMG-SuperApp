"""
gui/step3_analyze.py

Step 3 of the combined pipeline: AutoEDA. Takes the cleaned/grouped
DataFrame from Step 2 and offers two separate reports:

  - "Generate Yearly Overview Report" -> Report 1 (analysis.py):
    every outlet, whole period covered by the data.
  - "Generate Detailed Monthly Report" -> Report 2 (analysis_monthly.py):
    ONE outlet + ONE month, chosen via a popup (monthly_report_dialog.py),
    with branch-level detail.

Also allows importing an external .csv/.xlsx file to analyze INSTEAD of
the data handed over from Step 2 — e.g. re-opening a file previously
exported via Step 2's "Export Cleaned & Grouped Data" button, in a later
session without re-running Steps 1-2. Imported files must already have
(or be automatically cleaned into) the columns Report 1/2 need.

Both report-generation actions run on a background thread so the GUI
doesn't freeze while matplotlib/ReportLab work.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd

from analysis import generate_overall_sales_report, validate_columns
from analysis_monthly import get_available_outlets, get_available_months, generate_monthly_detail_report
from cleaning import process as clean_process
from gui.monthly_report_dialog import ask_outlet_and_month


class AnalyzeFrame(tk.Frame):
    def __init__(self, parent, input_df, on_back=None):
        super().__init__(parent)
        self.df = input_df
        self.on_back = on_back

        pad = {"padx": 15, "pady": 6}

        tk.Label(
            self,
            text="Step 3: Analyze",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", **pad)

        self.source_label = tk.Label(
            self,
            text=f"Analyzing {len(input_df)} rows from Step 2.",
            anchor="w",
        )
        self.source_label.pack(fill="x", padx=15)

        tk.Button(
            self,
            text="Import External File to Analyze...",
            command=self.import_external_file,
            bg="#00A8F6",
            fg="white",
        ).pack(fill="x", padx=15, pady=(8, 4))

        self.yearly_btn = tk.Button(
            self,
            text="Generate Yearly Overview Report...",
            command=self.generate_yearly_report,
            height=2,
            bg="#4CAF50",
            fg="white",
        )
        self.yearly_btn.pack(fill="x", padx=15, pady=(10, 4))

        self.monthly_btn = tk.Button(
            self,
            text="Generate Detailed Monthly Report...",
            command=self.generate_monthly_report,
            height=2,
            bg="#4CAF50",
            fg="white",
        )
        self.monthly_btn.pack(fill="x", padx=15, pady=(4, 10))

        tk.Label(self, text="Status", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", **pad)
        self.status_text = tk.Text(self, height=12, state="disabled", bg="#f5f5f5")
        self.status_text.pack(fill="both", expand=True, padx=15)

        nav = tk.Frame(self)
        nav.pack(fill="x", padx=15, pady=10)
        if self.on_back:
            tk.Button(nav, text="<- Back", command=self.on_back).pack(side="left")

    def log(self, message):
        self.status_text.config(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.config(state="disabled")

    def _set_buttons_state(self, state):
        self.yearly_btn.config(state=state)
        self.monthly_btn.config(state=state)

    # -------------------------------------------------------------
    # Import an external file to analyze instead of Step 2's output
    # -------------------------------------------------------------
    def import_external_file(self):
        path = filedialog.askopenfilename(
            title="Import file to analyze",
            filetypes=[
                ("CSV or Excel files", "*.csv *.xlsx *.xls"),
                ("CSV file", "*.csv"),
                ("Excel file", "*.xlsx *.xls"),
            ],
        )
        if not path:
            return

        try:
            if path.lower().endswith(".csv"):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            self.log(f"ERROR reading imported file: {e}")
            return

        try:
            if "group" not in df.columns:
                # Not yet cleaned/grouped (e.g. a raw Step 1-style export)
                # — auto-run cleaning if it at least has a Name column to
                # group from, same logic Step 2 uses.
                if "Name" in df.columns:
                    self.log("Imported file has no 'group' column — running cleaning & grouping automatically...")
                    df = clean_process(df, name_col="Name", group_col="group")
                else:
                    raise ValueError(
                        "Imported file has neither a 'group' nor a 'Name' column, so it can't be "
                        "grouped by outlet. Import a file that already has these columns (e.g. one "
                        "exported from Step 2), or a raw listing with a 'Name' column."
                    )

            validate_columns(df)  # checks DocDate / group / Description / LineAmount are present
        except Exception as e:
            messagebox.showerror("Invalid file", str(e))
            self.log(f"ERROR: imported file is not usable: {e}")
            return

        self.df = df
        self.source_label.config(
            text=f"Analyzing {len(df)} rows from IMPORTED file: {os.path.basename(path)}"
        )
        self.log(f"Imported {len(df)} rows from:\n{path}")

        if "Name" not in df.columns:
            self.log(
                "WARNING: no 'Name' (branch) column in this file — Detailed Monthly Report "
                "needs branch-level data and will be unavailable until a compatible file is loaded."
            )
            self.monthly_btn.config(state="disabled")
        else:
            self.monthly_btn.config(state="normal")

    # -------------------------------------------------------------
    # Shared report runner
    # -------------------------------------------------------------
    def _has_data(self) -> bool:
        if self.df is None or self.df.empty:
            messagebox.showerror("No data", "There is no data to generate a report from.")
            return False
        return True

    def _run_in_background(self, report_func, *args):
        """
        Run a generate_*_report() function off the main thread (so the GUI
        stays responsive) and report success/failure back on it. Both
        report functions return the output path, so one runner covers both.
        """
        self._set_buttons_state("disabled")

        def worker():
            try:
                output_path = report_func(*args)
            except Exception as e:
                self.after(0, self._on_error, e)
                return
            self.after(0, self._on_success, output_path)

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------
    # Report 1: Yearly Overview
    # -------------------------------------------------------------
    def generate_yearly_report(self):
        if not self._has_data():
            return

        output_path = filedialog.asksaveasfilename(
            title="Save Yearly Overview Report",
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile="Yearly_Overview_Report.pdf",
        )
        if not output_path:
            return

        self.log(f"Generating Yearly Overview Report for {len(self.df)} rows...")
        self._run_in_background(generate_overall_sales_report, self.df, output_path)

    # -------------------------------------------------------------
    # Report 2: Detailed Monthly Report
    # -------------------------------------------------------------
    def generate_monthly_report(self):
        if not self._has_data():
            return

        outlets = get_available_outlets(self.df)
        months = get_available_months(self.df)
        if not outlets or not months:
            messagebox.showerror("No data", "No outlet/month data available to choose from.")
            return

        selection = ask_outlet_and_month(self.winfo_toplevel(), outlets, months)
        if not selection:
            return  # user cancelled
        outlet, month_period, month_label = selection

        default_name = f"Monthly_Report_{outlet}_{month_label}.pdf".replace(" ", "_").replace("/", "-")
        output_path = filedialog.asksaveasfilename(
            title="Save Monthly Detailed Report",
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile=default_name,
        )
        if not output_path:
            return

        self.log(f"Generating Monthly Detailed Report for '{outlet}' ({month_label})...")
        self._run_in_background(
            generate_monthly_detail_report, self.df, outlet, month_period, output_path
        )

    # -------------------------------------------------------------
    # Shared callbacks
    # -------------------------------------------------------------
    def _on_success(self, output_path):
        self.log(f"Report saved successfully:\n{output_path}")
        messagebox.showinfo("Report generated", f"Report saved:\n{output_path}")
        self._set_buttons_state("normal")

    def _on_error(self, error):
        self.log(f"ERROR: {error}")
        messagebox.showerror("Error while generating report", str(error))
        self._set_buttons_state("normal")
