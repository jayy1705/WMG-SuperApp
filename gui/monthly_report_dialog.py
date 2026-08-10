"""
gui/monthly_report_dialog.py

Modal popup that asks the user to pick ONE outlet and ONE month before
generating the "Monthly Detailed Report" (Report 2). Used by
gui/step3_analyze.py.

Follows the same lightweight Toplevel-popup pattern as mapping_editor.py
("Manage Customer Names") — a blocking modal that returns its result to
the caller rather than using callbacks.
"""

import tkinter as tk
from tkinter import ttk


class MonthlyReportDialog(tk.Toplevel):
    """
    Usage:
        dialog = MonthlyReportDialog(parent, outlets, months)
        parent.wait_window(dialog)
        if dialog.result:
            outlet, month_period, month_label = dialog.result
    """

    def __init__(self, parent, outlets: list, months: list):
        """
        outlets: list[str] — from analysis_monthly.get_available_outlets()
        months: list[(Period, str)] — from analysis_monthly.get_available_months()
        """
        super().__init__(parent)
        self.title("Generate Detailed Monthly Report")
        self.resizable(False, False)
        self.result = None  # set to (outlet, month_period, month_label) on Generate

        self._months = months
        month_labels = [label for _, label in months]

        pad = {"padx": 15, "pady": 8}

        tk.Label(self, text="Choose an outlet and month to report on:", anchor="w").pack(
            fill="x", **pad
        )

        row1 = tk.Frame(self)
        row1.pack(fill="x", padx=15, pady=4)
        tk.Label(row1, text="Outlet:", width=10, anchor="w").pack(side="left")
        self.outlet_var = tk.StringVar(value=outlets[0] if outlets else "")
        outlet_combo = ttk.Combobox(
            row1, textvariable=self.outlet_var, values=outlets, state="readonly", width=40
        )
        outlet_combo.pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(self)
        row2.pack(fill="x", padx=15, pady=4)
        tk.Label(row2, text="Month:", width=10, anchor="w").pack(side="left")
        self.month_var = tk.StringVar(value=month_labels[0] if month_labels else "")
        month_combo = ttk.Combobox(
            row2, textvariable=self.month_var, values=month_labels, state="readonly", width=40
        )
        month_combo.pack(side="left", fill="x", expand=True)

        if not outlets or not month_labels:
            tk.Label(
                self,
                text="No outlet/month data available — run Steps 1 and 2 first.",
                fg="#B00020",
                anchor="w",
            ).pack(fill="x", padx=15, pady=(0, 8))

        nav = tk.Frame(self)
        nav.pack(fill="x", padx=15, pady=(10, 15))
        tk.Button(nav, text="Cancel", command=self._on_cancel).pack(side="right", padx=(8, 0))
        self.generate_btn = tk.Button(
            nav,
            text="Generate...",
            command=self._on_generate,
            bg="#4CAF50",
            fg="white",
            state="normal" if (outlets and month_labels) else "disabled",
        )
        self.generate_btn.pack(side="right")

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _on_generate(self):
        outlet = self.outlet_var.get()
        month_label = self.month_var.get()
        month_period = next((p for p, label in self._months if label == month_label), None)
        if outlet and month_period is not None:
            self.result = (outlet, month_period, month_label)
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def ask_outlet_and_month(parent, outlets: list, months: list):
    """
    Convenience wrapper: blocks until the dialog closes, returns
    (outlet, month_period, month_label) or None if cancelled.
    """
    dialog = MonthlyReportDialog(parent, outlets, months)
    parent.wait_window(dialog)
    return dialog.result
