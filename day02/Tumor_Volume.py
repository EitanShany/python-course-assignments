# Request input from the user
W = float(input("Enter tumor width (W): "))
L = float(input("Enter tumor length (L): "))

# Check condition
if W > L:
    print("Error: Width (W) must be smaller than or equal to Length (L).")
else:
    # Calculate tumor volume
    tumor_volume = ((W ** 2) * L) / 2
    print(f"Tumor volume is: {tumor_volume}")