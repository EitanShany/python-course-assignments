import os
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import pandas as pd
except ImportError:
    pd = None


def calculate_tumor_volume_excel(file_path):
    if pd is None:
        raise ImportError("pandas is not installed. Please run: pip install -r requirements.txt")

    if not file_path:
        raise ValueError("Please choose an Excel file.")

    df = pd.read_excel(file_path)

    if "W" not in df.columns or "L" not in df.columns:
        raise ValueError("The file must contain columns named 'W' and 'L'.")

    df["T.V"] = None
    df["Error"] = ""

    error_found = False

    for i in range(len(df)):
        width = df.loc[i, "W"]
        length = df.loc[i, "L"]

        if pd.isna(width) or pd.isna(length):
            df.loc[i, "Error"] = "Missing value"
            error_found = True
        elif width > length:
            df.loc[i, "Error"] = "W > L"
            error_found = True
        else:
            df.loc[i, "T.V"] = ((width ** 2) * length) / 2

    base_name = os.path.splitext(file_path)[0]
    new_file_path = base_name + "_TV.xlsx"
    df.to_excel(new_file_path, index=False)

    return new_file_path, error_found


def choose_file():
    file_path = filedialog.askopenfilename(
        title="Choose Excel file",
        filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
    )

    if file_path:
        file_path_var.set(file_path)


def run_calculation():
    try:
        output_path, error_found = calculate_tumor_volume_excel(file_path_var.get().strip())

        if error_found:
            messagebox.showwarning(
                "Done with warnings",
                "New file saved as:\n\n"
                f"{output_path}\n\n"
                "One or more errors were found. Please review the 'Error' column."
            )
        else:
            messagebox.showinfo("Done", f"New file saved as:\n\n{output_path}")

        status_var.set(f"Saved: {output_path}")
    except Exception as error:
        status_var.set("Error")
        messagebox.showerror("Error", str(error))


def build_gui():
    global file_path_var, status_var

    window = tk.Tk()
    window.title("Tumor Volume Excel Calculator")
    window.geometry("620x260")
    window.resizable(False, False)

    file_path_var = tk.StringVar(master=window)
    status_var = tk.StringVar(master=window, value="Ready")

    main_frame = tk.Frame(window, padx=24, pady=24)
    main_frame.pack(fill="both", expand=True)

    title_label = tk.Label(
        main_frame,
        text="Tumor Volume Excel Calculator",
        font=("Segoe UI", 16, "bold")
    )
    title_label.pack(anchor="w")

    instructions_label = tk.Label(
        main_frame,
        text="Choose an Excel file with columns named W and L, then calculate T.V.",
        font=("Segoe UI", 10)
    )
    instructions_label.pack(anchor="w", pady=(6, 18))

    file_frame = tk.Frame(main_frame)
    file_frame.pack(fill="x")

    file_entry = tk.Entry(file_frame, textvariable=file_path_var, font=("Segoe UI", 10))
    file_entry.pack(side="left", fill="x", expand=True)

    browse_button = tk.Button(file_frame, text="Browse...", command=choose_file, width=12)
    browse_button.pack(side="left", padx=(8, 0))

    calculate_button = tk.Button(
        main_frame,
        text="Calculate and Save",
        command=run_calculation,
        font=("Segoe UI", 11, "bold"),
        height=2
    )
    calculate_button.pack(fill="x", pady=(18, 12))

    status_label = tk.Label(
        main_frame,
        textvariable=status_var,
        anchor="w",
        justify="left",
        wraplength=560,
        fg="#255f38",
        font=("Segoe UI", 9)
    )
    status_label.pack(fill="x")

    return window


file_path_var = None
status_var = None


if __name__ == "__main__":
    app = build_gui()
    app.mainloop()
