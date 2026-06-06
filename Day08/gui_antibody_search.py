"""Tkinter GUI for the Day06 antibody target search."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from antibody_processing import (
    OUTPUT_COLUMNS,
    SPECIES_OPTIONS,
    write_excel_results,
    write_results,
)
from antibody_search import safe_count_pubmed_references, safe_fetch_gene_aliases
from data_sources import load_antibody_table
from multi_source_search import search_all_sources


class AntibodySearchApp:
    """Small GUI wrapper around the antibody search workflow."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Cancer Target Antibody Search")
        self.rows: list[dict[str, str | int]] = []
        self.raw_rows: list[dict[str, str]] | None = None

        self.target_var = tk.StringVar(value="PD1")
        self.limit_var = tk.IntVar(value=10)
        self.status_var = tk.StringVar(value="Ready")
        self.other_species_var = tk.StringVar()
        self.species_vars = {
            species: tk.BooleanVar(value=False)
            for species in SPECIES_OPTIONS
            if species != "Other"
        }

        self.build_widgets()

    def build_widgets(self) -> None:
        controls = ttk.Frame(self.root, padding=10)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Target").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(controls, textvariable=self.target_var, width=24).grid(row=0, column=1, padx=5)

        ttk.Label(controls, text="Limit").grid(row=0, column=2, sticky=tk.W)
        ttk.Spinbox(controls, from_=1, to=100, textvariable=self.limit_var, width=8).grid(
            row=0, column=3, padx=5
        )

        ttk.Button(controls, text="Search", command=self.start_search).grid(row=0, column=4, padx=5)
        ttk.Button(controls, text="Load File", command=self.load_input_file).grid(
            row=0, column=5, padx=5
        )
        ttk.Button(controls, text="Save CSV", command=self.save_csv_results).grid(
            row=0, column=6, padx=5
        )
        ttk.Button(controls, text="Save Excel", command=self.save_excel_results).grid(
            row=0, column=7, padx=5
        )

        species_frame = ttk.LabelFrame(self.root, text="Species / antibody type", padding=10)
        species_frame.pack(fill=tk.X, padx=10, pady=5)
        for index, (species, variable) in enumerate(self.species_vars.items()):
            ttk.Checkbutton(species_frame, text=species, variable=variable).grid(
                row=0, column=index, sticky=tk.W, padx=4
            )
        ttk.Label(species_frame, text="Other").grid(row=0, column=len(self.species_vars), padx=4)
        ttk.Entry(species_frame, textvariable=self.other_species_var, width=18).grid(
            row=0, column=len(self.species_vars) + 1, padx=4
        )

        self.table = ttk.Treeview(self.root, columns=OUTPUT_COLUMNS, show="headings", height=15)
        for column in OUTPUT_COLUMNS:
            self.table.heading(column, text=column)
            self.table.column(column, width=160, stretch=True)
        self.table.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ttk.Label(self.root, textvariable=self.status_var, padding=10).pack(fill=tk.X)

    def selected_species_filters(self) -> list[str]:
        """Return selected species/type filters from the GUI."""
        filters = [
            species
            for species, variable in self.species_vars.items()
            if variable.get()
        ]
        other_species = self.other_species_var.get().strip()
        if other_species:
            filters.append(other_species)
        return filters

    def load_input_file(self) -> None:
        """Load antibody data from a user-selected CSV or Excel file."""
        file_name = filedialog.askopenfilename(
            title="Choose antibody table",
            filetypes=[
                ("Antibody tables", "*.csv *.xlsx *.xlsm"),
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx *.xlsm"),
            ],
        )
        if not file_name:
            return

        try:
            self.raw_rows = load_antibody_table(Path(file_name))
        except Exception as error:
            messagebox.showerror("Load failed", str(error))
            return

        self.status_var.set(f"Loaded {len(self.raw_rows)} rows from {Path(file_name).name}")

    def start_search(self) -> None:
        target = self.target_var.get().strip()
        if not target:
            messagebox.showerror("Missing target", "Please enter a target gene or antigen.")
            return

        self.status_var.set("Searching...")
        threading.Thread(
            target=self.run_search,
            args=(target, self.limit_var.get(), self.selected_species_filters()),
            daemon=True,
        ).start()

    def run_search(self, target: str, limit: int, species_filters: list[str]) -> None:
        try:
            aliases = safe_fetch_gene_aliases(target)
            rows = search_all_sources(
                therasabdab_loader=lambda: self.raw_rows or load_antibody_table(),
                target_query=target,
                target_aliases=aliases,
                limit=limit,
                reference_counter=safe_count_pubmed_references,
                species_filters=species_filters,
            )
        except Exception as error:
            self.root.after(0, lambda: messagebox.showerror("Search failed", str(error)))
            self.root.after(0, lambda: self.status_var.set("Search failed"))
            return

        self.root.after(0, lambda: self.show_rows(rows))

    def show_rows(self, rows: list[dict[str, str | int]]) -> None:
        self.rows = rows
        self.table.delete(*self.table.get_children())
        for row in rows:
            values = [str(row.get(column, "")) for column in OUTPUT_COLUMNS]
            self.table.insert("", tk.END, values=values)
        self.status_var.set(f"Found {len(rows)} antibodies")

    def save_csv_results(self) -> None:
        if not self.rows:
            messagebox.showinfo("No results", "Run a search before saving.")
            return

        file_name = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="antibody_results_gui.csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not file_name:
            return
        output_path = Path(file_name)
        write_results(output_path, self.rows)
        messagebox.showinfo("Saved", f"Saved results to {output_path}")

    def save_excel_results(self) -> None:
        if not self.rows:
            messagebox.showinfo("No results", "Run a search before saving.")
            return

        file_name = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile="antibody_results_gui.xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not file_name:
            return
        output_path = Path(file_name)
        write_excel_results(output_path, self.rows)
        messagebox.showinfo("Saved", f"Saved results to {output_path}")


def main() -> None:
    root = tk.Tk()
    AntibodySearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
