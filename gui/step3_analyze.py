"""
gui/step3_analyze.py

Step 3 of the combined pipeline: AutoEDA. Takes the cleaned/grouped
DataFrame from Step 2 and offers two separate reports:

  - "Generate Yearly Overview Report" -> Report 1 (analysis.py):
    every outlet, whole period covered by the data.
  - "Generate Detailed Monthly Report" -> Report 2 (analysis_monthly.py):
    ONE outlet + ONE month, chosen via a popup (monthly_report_dialog.py),
    with branch-level detail.

Both run on a background thread so the GUI doesn't freeze while
matplotlib/ReportLab work.
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from analysis import generate_overall_sales_report
from analysis_monthly import get_available_outlets, get_available_months, generate_monthly_detail_report
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

        tk.Label(
            self,
            text=f"Received {len(input_df)} rows from Step 2.",
            anchor="w",
        ).pack(fill="x", padx=15)

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
    # Report 1: Yearly Overview
    # -------------------------------------------------------------
    def generate_yearly_report(self):
        if self.df is None or self.df.empty:
            messagebox.showerror("No data", "There is no data to generate a report from.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Save Yearly Overview Report",
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile="Yearly_Overview_Report.pdf",
        )
        if not output_path:
            return

        self._set_buttons_state("disabled")
        self.log(f"Generating Yearly Overview Report for {len(self.df)} rows...")

        thread = threading.Thread(target=self._run_yearly, args=(output_path,), daemon=True)
        thread.start()

    def _run_yearly(self, output_path):
        try:
            generate_overall_sales_report(self.df, output_path)
        except Exception as e:
            self.after(0, self._on_error, e)
            return
        self.after(0, self._on_success, output_path)

    # -------------------------------------------------------------
    # Report 2: Detailed Monthly Report
    # -------------------------------------------------------------
    def generate_monthly_report(self):
        if self.df is None or self.df.empty:
            messagebox.showerror("No data", "There is no data to generate a report from.")
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

        self._set_buttons_state("disabled")
        self.log(f"Generating Monthly Detailed Report for '{outlet}' ({month_label})...")

        thread = threading.Thread(
            target=self._run_monthly, args=(outlet, month_period, output_path), daemon=True
        )
        thread.start()

    def _run_monthly(self, outlet, month_period, output_path):
        try:
            generate_monthly_detail_report(self.df, outlet, month_period, output_path)
        except Exception as e:
            self.after(0, self._on_error, e)
            return
        self.after(0, self._on_success, output_path)

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
