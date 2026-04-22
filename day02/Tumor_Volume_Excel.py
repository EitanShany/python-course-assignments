import pandas as pd
import os

# Ask user for file path
file_path = input("Enter the full path to the Excel file: ")

try:
    # Load Excel file
    df = pd.read_excel(file_path)

    # Check required columns exist
    if 'W' not in df.columns or 'L' not in df.columns:
        print("Error: The file must contain columns named 'W' and 'L'.")
    else:
        # Check condition W <= L
        invalid_rows = df[df['W'] > df['L']]
        if not invalid_rows.empty:
            print("Error: Some rows have W > L. Please fix the data before running again.")
        else:
            # Calculate tumor volume
            df['T.V'] = ((df['W'] ** 2) * df['L']) / 2

            # Create new file name
            base_name = os.path.splitext(file_path)[0]
            new_file_path = base_name + "_TV.xlsx"

            # Save new file
            df.to_excel(new_file_path, index=False)

            print(f"New file saved as: {new_file_path}")

except Exception as e:
    print(f"An error occurred: {e}")