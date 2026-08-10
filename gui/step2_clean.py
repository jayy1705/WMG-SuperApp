"""
gui/step2_clean.py

Step 2 of the combined pipeline: takes the DataFrame produced by Step 1
(InvoiceConverter) and runs it through AutoCleaner's cleaning/grouping
logic (cleaning.py). Includes the "Manage Customer Names" editor.
On Next, hands the cleaned DataFrame to on_next().
"""

import tkinter as tk
from tkinter import messagebox

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
            if missed:
                self.log(f"{len(missed)} name(s) not in the mapping (grouped as 'Other'):")
                for name in missed[:10]:
                    self.log(f"   - {name}")
                if len(missed) > 10:
                    self.log(f"   ...and {len(missed) - 10} more.")
            else:
                self.log("All names matched the mapping.")

            self.next_btn.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error while cleaning", str(e))
            self.log(f"ERROR: {e}")

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
