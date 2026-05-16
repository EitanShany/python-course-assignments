"""
Graphical interface for the tumor-growth analysis workflow.

The GUI lets the user choose an Excel input file and an output folder, then
runs the analysis in a background thread so the window stays responsive.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False

from tumor_growth_analysis import analyze_tumor_growth


class TumorGrowthApp:
    """Small Tkinter application for running tumor-growth analysis."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tumor Growth Analysis")
        self.root.geometry("720x360")
        self.root.minsize(640, 320)

        self.input_file_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select an Excel file to begin.")

        self.build_ui()
        self.configure_drag_and_drop()

    def build_ui(self) -> None:
        """Create and arrange all widgets."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=18)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(4, weight=1)

        title = ttk.Label(
            main,
            text="Tumor Growth Analysis",
            font=("Segoe UI", 16, "bold"),
        )
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        ttk.Label(main, text="Excel input file").grid(row=1, column=0, sticky="w")
        ttk.Entry(main, textvariable=self.input_file_var).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=8,
        )
        ttk.Button(main, text="Browse...", command=self.browse_input_file).grid(
            row=1,
            column=2,
            sticky="e",
        )

        ttk.Label(main, text="Output folder").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        ttk.Entry(main, textvariable=self.output_dir_var).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=8,
            pady=(10, 0),
        )
        ttk.Button(main, text="Browse...", command=self.browse_output_dir).grid(
            row=2,
            column=2,
            sticky="e",
            pady=(10, 0),
        )

        self.run_button = ttk.Button(
            main,
            text="Run Analysis",
            command=self.run_analysis_threaded,
        )
        self.run_button.grid(row=3, column=0, columnspan=3, pady=18)

        status_frame = ttk.LabelFrame(main, text="Status", padding=10)
        status_frame.grid(row=4, column=0, columnspan=3, sticky="nsew")
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)

        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            justify="left",
            anchor="nw",
            wraplength=640,
        )
        self.status_label.grid(row=0, column=0, sticky="nsew")

        if not DND_AVAILABLE:
            ttk.Label(
                main,
                text="Optional drag-and-drop support requires tkinterdnd2.",
            ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def configure_drag_and_drop(self) -> None:
        """Enable dropping an Excel file on the window when tkinterdnd2 exists."""
        if not DND_AVAILABLE:
            return

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.handle_drop)

    def handle_drop(self, event) -> None:
        """Use the first dropped file as the input Excel file."""
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return

        self.input_file_var.set(paths[0])
        self.status_var.set("Input file selected.")

    def browse_input_file(self) -> None:
        """Open a file dialog for selecting the Excel input file."""
        filename = filedialog.askopenfilename(
            title="Select Excel input file",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self.input_file_var.set(filename)

    def browse_output_dir(self) -> None:
        """Open a folder dialog for selecting the output directory."""
        directory = filedialog.askdirectory(title="Select output folder")
        if directory:
            self.output_dir_var.set(directory)

    def validate_inputs(self) -> tuple[Path, Path] | None:
        """Validate user input and return normalized paths."""
        input_file_text = self.input_file_var.get().strip()
        output_dir_text = self.output_dir_var.get().strip()

        if not input_file_text:
            messagebox.showerror("Missing input file", "Please select an Excel file.")
            return None

        if not output_dir_text:
            messagebox.showerror("Missing output folder", "Please select an output folder.")
            return None

        input_file = Path(input_file_text)
        output_dir = Path(output_dir_text)

        if not input_file.exists():
            messagebox.showerror("Invalid input file", "The selected file does not exist.")
            return None

        if input_file.suffix.lower() not in [".xlsx", ".xls"]:
            messagebox.showerror(
                "Invalid file",
                "Please select an Excel file with .xlsx or .xls extension.",
            )
            return None

        return input_file, output_dir

    def run_analysis_threaded(self) -> None:
        """Run analysis in a separate thread so the GUI does not freeze."""
        validated = self.validate_inputs()
        if validated is None:
            return

        input_file, output_dir = validated

        self.run_button.config(state="disabled")
        self.status_var.set("Running analysis...")

        thread = threading.Thread(
            target=self.run_analysis,
            args=(input_file, output_dir),
            daemon=True,
        )
        thread.start()

    def run_analysis(self, input_file: Path, output_dir: Path) -> None:
        """Run the tumor-growth analysis and update the GUI when finished."""
        try:
            results = analyze_tumor_growth(input_file=input_file, output_dir=output_dir)
            message = (
                "Analysis completed successfully.\n"
                f"Excel report: {results['output_excel']}\n"
                f"Mean TV graph: {results['mean_tv_graph']}\n"
                f"Responder graph: {results['responder_graph']}\n"
                f"Mice analyzed: {results['num_mice_analyzed']}\n"
                f"Errors/warnings: {results['num_errors']}"
            )
            self.root.after(0, self.analysis_success, message)
        except Exception as error:
            self.root.after(0, self.analysis_failed, str(error))

    def analysis_success(self, message: str) -> None:
        """Update GUI after successful analysis."""
        self.status_var.set(message)
        self.run_button.config(state="normal")
        messagebox.showinfo("Analysis completed", message)

    def analysis_failed(self, error_message: str) -> None:
        """Update GUI after failed analysis."""
        self.status_var.set("Analysis failed.")
        self.run_button.config(state="normal")
        messagebox.showerror("Analysis failed", error_message)


def main() -> None:
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    TumorGrowthApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
