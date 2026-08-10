"""
gui/step1_convert.py

Step 1 of the combined pipeline: pick a raw WMG invoice listing .xlsx
file and convert it into a flat DataFrame using invoice_converter.py.
On success, hands the DataFrame to on_next() so main.py can move to
Step 2 (AutoCleaner) without the user saving/reopening any file.
"""

import os
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from InvoiceConverter import convert_to_dataframe


class ConvertFrame(tk.Frame):
    def __init__(self, parent, on_next):
        """on_next(df): called when the user clicks Next, with the converted DataFrame."""
        super().__init__(parent)
        self.on_next = on_next
        self.input_path = None
        self.df = None

        pad = {"padx": 15, "pady": 6}

        tk.Label(self, text="1. Choose the invoice listing .xlsx file:", anchor="w").pack(fill="x", **pad)
        row1 = tk.Frame(self)
        row1.pack(fill="x", padx=15)
        tk.Button(row1, text="Choose File...", command=self.choose_file, width=16).pack(side="left")
        self.file_label = tk.Label(row1, text="No file selected", anchor="w", fg="#555")
        self.file_label.pack(side="left", padx=(10, 0))

        tk.Label(self, text="2. Run the conversion:", anchor="w").pack(fill="x", **pad)
        self.run_btn = tk.Button(self, text="Run Conversion", command=self.run_conversion, state="disabled")
        self.run_btn.pack(anchor="w", padx=15)

        tk.Label(self, text="Status:", anchor="w").pack(fill="x", **pad)
        self.log = scrolledtext.ScrolledText(self, height=10, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=15)

        nav = tk.Frame(self)
        nav.pack(fill="x", padx=15, pady=10)
        self.next_btn = tk.Button(
            nav, text="Next: Clean & Group Names ->", command=self.go_next, state="disabled",
            bg="#4CAF50", fg="white",
        )
        self.next_btn.pack(side="right")

    def log_msg(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose invoice listing file",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        self.input_path = path
        self.df = None
        self.file_label.config(text=os.path.basename(path), fg="#000")
        self.run_btn.config(state="normal")
        self.next_btn.config(state="disabled")
        self.log_msg(f"Selected: {path}")

    def run_conversion(self):
        if not self.input_path:
            return
        self.run_btn.config(state="disabled")
        self.log_msg("Running conversion...")
        self.update_idletasks()
        try:
            df, unrecognized, mismatches, invoice_count = convert_to_dataframe(self.input_path)
        except Exception as e:
            self.log_msg(f"ERROR: {e}")
            self.log_msg(traceback.format_exc())
            messagebox.showerror("Conversion failed", str(e))
            self.run_btn.config(state="normal")
            return

        self.df = df
        self.log_msg(f"Done. {len(df)} line items across {invoice_count} invoices.")

        if unrecognized:
            self.log_msg(f"WARNING: {len(unrecognized)} rows were not recognized and were skipped.")
            for i, row in unrecognized[:10]:
                self.log_msg(f"  row {i}: {row}")
        if mismatches:
            self.log_msg(f"WARNING: {len(mismatches)} invoices' totals don't reconcile:")
            for docno, total, inv_amt in mismatches[:10]:
                self.log_msg(f"  {docno}: lines sum to {total}, header says {inv_amt}")
        if not unrecognized and not mismatches:
            self.log_msg("All rows recognized, all invoice totals reconciled. Looks clean.")

        self.run_btn.config(state="normal")
        self.next_btn.config(state="normal")

    def go_next(self):
        if self.df is not None:
            self.on_next(self.df)
