"""
main.py

Combined pipeline app: InvoiceConverter -> AutoCleaner -> AutoEDA.
One process, one window, one .exe. Each stage is a Frame in gui/ that
hands its output DataFrame to the next stage in memory — no saving and
reopening files between steps.

This is the file to run directly, and the file to point PyInstaller at
when packaging.
"""

import tkinter as tk

from gui.step1_convert import ConvertFrame
from gui.step2_clean import CleanFrame
from gui.step3_analyze import AnalyzeFrame


class MainApp:
    def __init__(self, root):
        self.root = root
        root.title("WMG Data Pipeline")
        root.geometry("650x560")
        root.resizable(False, False)

        # Shared pipeline state — each stage reads/writes this via callbacks
        self.converted_df = None
        self.cleaned_df = None

        self.step_label = tk.Label(root, text="", font=("Segoe UI", 12, "bold"))
        self.step_label.pack(pady=(12, 0))

        self.container = tk.Frame(root)
        self.container.pack(fill="both", expand=True)

        self.show_step1()

    def _clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    #Step 1: Convert
    def show_step1(self):
        self._clear_container()
        self.step_label.config(text="Step 1 of 3 — Convert Invoice")
        ConvertFrame(self.container, on_next=self._go_to_step2).pack(fill="both", expand=True)

    def _go_to_step2(self, df):
        self.converted_df = df
        self.show_step2()

    #Step 2: Clean & group
    def show_step2(self):
        self._clear_container()
        self.step_label.config(text="Step 2 of 3 — Clean & Group Names")
        CleanFrame(
            self.container,
            input_df=self.converted_df,
            on_next=self._go_to_step3,
            on_back=self.show_step1,
        ).pack(fill="both", expand=True)

    def _go_to_step3(self, df):
        self.cleaned_df = df
        self.show_step3()

    #Step 3: Analyze (placeholder until AutoEDA is ready) 
    def show_step3(self):
        self._clear_container()
        self.step_label.config(text="Step 3 of 3 — Analyze")
        AnalyzeFrame(
            self.container,
            input_df=self.cleaned_df,
            on_back=self.show_step2,
        ).pack(fill="both", expand=True)


def main():
    root = tk.Tk()
    MainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
