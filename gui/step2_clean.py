"""
gui/step2_clean.py

Step 2 of the combined pipeline: takes the DataFrame produced by Step 1
(InvoiceConverter) and runs it through AutoCleaner's cleaning/grouping
logic (cleaning.py). Includes the "Manage Customer Names" editor.
On Next, hands the cleaned DataFrame to on_next().
"""

import tkinter as tk
from tkinter import filedialog, messagebox

from cleaning import process, unmatched_names, reload_mapping
from mapping_editor import MappingEditor


class CleanFrame(tk.Frame):
    def __init__(self, parent, input_df, on_next, on_back=None):
        """
        input_df: the DataFrame handed over from Step 1.
        on_next(df): called when the user clicks Next, with the cleaned DataFrame.
        on_back(): called when the user clicks Back (optional).
        """
        super().__init__(parent)
        self.input_df = input_df
        self.on_next = on_next
        self.on_back = on_back
        self.cleaned_df = None

        pad = {"padx": 15, "pady": 6}

        tk.Label(
            self,
            text=f"Received {len(input_df)} rows from Step 1.",
            anchor="w",
        ).pack(fill="x", **pad)

        tk.Button(self, text="Run Cleaning & Grouping", command=self.run_cleaning, height=2).pack(
            fill="x", padx=15, pady=5
        )

        tk.Button(self, text="Manage Customer Names...", command=self.open_mapping_editor).pack(
            fill="x", padx=15, pady=5
        )

        self.export_btn = tk.Button(
            self,
            text="Export Cleaned & Grouped Data...",
            command=self.export_data,
            state="disabled",
        )
        self.export_btn.pack(fill="x", padx=15, pady=5)

        tk.Label(self, text="Status", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", **pad)
        self.status_text = tk.Text(self, height=10, state="disabled", bg="#f5f5f5")
        self.status_text.pack(fill="both", expand=True, padx=15)

        nav = tk.Frame(self)
        nav.pack(fill="x", padx=15, pady=10)
        self.next_btn = tk.Button(
            nav, text="Next: Analyze ->", command=self.go_next, state="disabled", bg="#4CAF50", fg="white"
        )
        self.next_btn.pack(side="right")
        if self.on_back:
            tk.Button(nav, text="<- Back", command=self.on_back).pack(side="left")

    def log(self, message):
        self.status_text.config(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.config(state="disabled")

    def run_cleaning(self):
        if "Name" not in self.input_df.columns:
            messagebox.showerror("Missing column", "This data has no 'Name' column.")
            self.log("ERROR: 'Name' column not found.")
            return

        try:
            self.cleaned_df = process(self.input_df, name_col="Name", group_col="group")
            missed = unmatched_names(self.cleaned_df, name_col="Name")

            self.log(f"Cleaning complete. {len(self.cleaned_df)} rows processed.")

            self._log_data_quality_summary()

            if missed:
                self.log(f"{len(missed)} name(s) not in the mapping (grouped as 'Other'):")
                for name in missed[:10]:
                    self.log(f"   - {name}")
                if len(missed) > 10:
                    self.log(f"   ...and {len(missed) - 10} more.")
            else:
                self.log("All names matched the mapping.")

            self.next_btn.config(state="normal")
            self.export_btn.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error while cleaning", str(e))
            self.log(f"ERROR: {e}")

    def _log_data_quality_summary(self):
        """
        Logs a quick data-quality snapshot of the cleaned/grouped data:
        total missing values (with a per-column breakdown if any exist)
        and count of fully duplicated rows. Purely informational — does
        not block or alter cleaning in any way.
        """
        df = self.cleaned_df

        total_missing = int(df.isna().sum().sum())
        self.log(f"Missing values: {total_missing} total")
        if total_missing > 0:
            per_col = df.isna().sum()
            per_col = per_col[per_col > 0].sort_values(ascending=False)
            for col, count in per_col.items():
                self.log(f"   - {col}: {count} missing")

        dup_count = int(df.duplicated().sum())
        self.log(f"Duplicate rows (fully identical): {dup_count}")

    def export_data(self):
        if self.cleaned_df is None:
            messagebox.showerror("No data", "Run cleaning first before exporting.")
            return

        path = filedialog.asksaveasfilename(
            title="Export cleaned & grouped data",
            defaultextension=".xlsx",
            filetypes=[("Excel file", "*.xlsx"), ("CSV file", "*.csv")],
            initialfile="Cleaned_Grouped_Data.xlsx",
        )
        if not path:
            return

        try:
            if path.lower().endswith(".csv"):
                self.cleaned_df.to_csv(path, index=False)
            else:
                self.cleaned_df.to_excel(path, index=False)
            self.log(f"Cleaned & grouped data exported to:\n{path}")
            messagebox.showinfo("Exported", f"File saved successfully:\n{path}")
        except Exception as e:
            messagebox.showerror("Error while exporting", str(e))
            self.log(f"ERROR exporting file: {e}")

    def open_mapping_editor(self):
        def on_close(saved):
            if saved:
                reload_mapping()
                self.log("Customer mapping updated and reloaded.")
                if self.cleaned_df is not None:
                    self.log("Note: re-run cleaning to apply the updated mapping.")

        MappingEditor(self.winfo_toplevel(), on_close=on_close)

    def go_next(self):
        if self.cleaned_df is not None:
            self.on_next(self.cleaned_df)