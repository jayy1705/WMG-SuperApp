"""
mapping_editor.py

A Tkinter window that lets a non-technical user view, add, edit, and
delete customer name -> group mappings, without touching mapping.csv
or any source code directly.

Opened as a Toplevel window from gui/step2_clean.py's "Manage Customer
Names" button.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from mapping_store import load_mapping, save_mapping, get_mapping_path


class MappingEditor(tk.Toplevel):
    def __init__(self, parent, on_close=None):
        """
        parent: the main app window (Tk root).
        on_close: optional callback run after this window closes and the
                  mapping was saved — use it to call cleaning.reload_mapping()
                  and refresh the main window's status log.
        """
        super().__init__(parent)
        self.title("Manage Customer Names")
        self.geometry("700x480")
        self.on_close = on_close
        self.saved_since_open = False

        self.pairs = load_mapping()  # list of (raw_name, group_name)

        # --- Table ---
        columns = ("raw_name", "group_name")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("raw_name", text="Raw name (as it appears in your data)")
        self.tree.heading("group_name", text="Group (canonical customer)")
        self.tree.column("raw_name", width=400)
        self.tree.column("group_name", width=250)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, anchor="ne")

        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        self._refresh_tree()

        # --- Buttons ---
        button_frame = tk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(button_frame, text="Add New...", command=self.add_entry).pack(side="left")
        tk.Button(button_frame, text="Edit Selected...", command=self.edit_selected).pack(side="left", padx=5)
        tk.Button(button_frame, text="Delete Selected", command=self.delete_selected).pack(side="left")

        tk.Button(button_frame, text="Save & Close", command=self.save_and_close, bg="#4CAF50", fg="white").pack(
            side="right"
        )
        tk.Button(button_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)

        tk.Label(
            self,
            text=f"File: {get_mapping_path()}",
            fg="gray",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 5))

    # -------------------------------------------------------------
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, (raw, group) in enumerate(sorted(self.pairs, key=lambda p: p[1])):
            self.tree.insert("", "end", iid=str(i), values=(raw, group))

    # -------------------------------------------------------------
    def add_entry(self):
        raw = simpledialog.askstring(
            "Add New", "Raw name (exactly as it appears in your data file):", parent=self
        )
        if not raw or not raw.strip():
            return
        raw = raw.strip()

        group = simpledialog.askstring("Add New", f"Group name for '{raw}':", parent=self)
        if not group or not group.strip():
            return
        group = group.strip()

        # Warn on exact duplicate raw name (case-insensitive) already present
        existing = next((g for r, g in self.pairs if r.strip().upper() == raw.upper()), None)
        if existing is not None:
            if not messagebox.askyesno(
                "Already exists",
                f"'{raw}' is already mapped to '{existing}'.\nReplace it with '{group}'?",
                parent=self,
            ):
                return
            self.pairs = [(r, g) for r, g in self.pairs if r.strip().upper() != raw.upper()]

        self.pairs.append((raw, group))
        self._refresh_tree()

    # -------------------------------------------------------------
    def _selected_index(self):
        """Index into self.pairs of the currently selected tree row, or None."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No selection", "Select a row first.", parent=self)
            return None

        # The tree is displayed sorted, so match on the row's values
        # rather than trusting the iid to line up with self.pairs.
        row_values = self.tree.item(selection[0], "values")
        for idx, (raw, group) in enumerate(self.pairs):
            if raw == row_values[0] and group == row_values[1]:
                return idx
        return None

    def edit_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        raw, group = self.pairs[idx]

        new_raw = simpledialog.askstring("Edit", "Raw name:", initialvalue=raw, parent=self)
        if not new_raw:
            return
        new_group = simpledialog.askstring("Edit", "Group name:", initialvalue=group, parent=self)
        if not new_group:
            return

        self.pairs[idx] = (new_raw.strip(), new_group.strip())
        self._refresh_tree()

    def delete_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        raw = self.pairs[idx][0]
        if messagebox.askyesno("Confirm delete", f"Delete mapping for '{raw}'?", parent=self):
            del self.pairs[idx]
            self._refresh_tree()

    # -------------------------------------------------------------
    def save_and_close(self):
        try:
            save_mapping(self.pairs)
            self.saved_since_open = True
        except Exception as e:
            messagebox.showerror("Error saving", str(e), parent=self)
            return

        if self.on_close:
            self.on_close(saved=True)
        self.destroy()

    def destroy(self):
        if not self.saved_since_open and self.on_close:
            self.on_close(saved=False)
        super().destroy()
