try:
    import pandas as pd
except ImportError:
    print("Error: pandas is not installed. Please run: pip install -r requirements.txt")
    exit()

import os

# Ask user for file path
file_path = input("Enter the full path to the Excel file: ").strip()

try:
    # Load Excel file
    df = pd.read_excel(file_path)

    # Check required columns exist
    if 'W' not in df.columns or 'L' not in df.columns:
        print("Error: The file must contain columns named 'W' and 'L'.")
    else:
        # Create new columns
        df['T.V'] = None
        df['Error'] = ""

        error_found = False

        # Go row by row
        for i in range(len(df)):
            W = df.loc[i, 'W']
            L = df.loc[i, 'L']

            # Check condition
            if pd.isna(W) or pd.isna(L):
                df.loc[i, 'Error'] = "Missing value"
                error_found = True

            elif W > L:
                df.loc[i, 'Error'] = "W > L"
                error_found = True

            else:
                df.loc[i, 'T.V'] = ((W ** 2) * L) / 2

        # Create new file name
        base_name = os.path.splitext(file_path)[0]
        new_file_path = base_name + "_TV.xlsx"

        # Save new file
        df.to_excel(new_file_path, index=False)

        print(f"New file saved as: {new_file_path}")

        if error_found:
            print("Warning: One or more errors were found. Please review the 'Error' column in the output file.")

except Exception as e:
    print(f"An error occurred: {e}")
