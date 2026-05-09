import os

try:
    import pandas as pd
except ImportError:
    print("Error: pandas is not installed. Please run: pip install -r requirements.txt")
    exit()


def process_excel_file(input_file):
    """
    Read an Excel file, calculate tumor volume, and save a new Excel file.

    Required columns:
    L = length
    W = width

    Formula:
    T.V. = (W^2 * L) / 2

    If W > L, the row is marked with an error message
    and the code continues processing the rest of the file.
    """

    data = pd.read_excel(input_file)

    if "L" not in data.columns or "W" not in data.columns:
        raise ValueError("Excel file must contain 'L' and 'W' columns.")

    if "T.V." not in data.columns:
        data["T.V."] = float("nan")

    if "Error" not in data.columns:
        data["Error"] = ""

    errors_found = False

    for index, row in data.iterrows():
        length = row["L"]
        width = row["W"]

        if pd.isna(length) or pd.isna(width):
            data.at[index, "Error"] = "Missing length or width value."
            errors_found = True
            continue

        if not isinstance(length, (int, float)) or not isinstance(width, (int, float)):
            data.at[index, "Error"] = "Length and width must be numbers."
            errors_found = True
            continue

        if width > length:
            data.at[index, "Error"] = "Width cannot be greater than length."
            errors_found = True
            continue

        data.at[index, "T.V."] = (width ** 2 * length) / 2
        data.at[index, "Error"] = ""

    file_name, file_extension = os.path.splitext(input_file)
    output_file = file_name + "_TV" + file_extension

    data.to_excel(output_file, index=False)

    if errors_found:
        print("File created, but one or more errors were found. Please check the Error column.")
    else:
        print("File created successfully with no errors.")

    return output_file


if __name__ == "__main__":
    input_file = input("Enter Excel file path: ")
    process_excel_file(input_file)
    
