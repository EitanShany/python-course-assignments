import math
print("--------------------------------------------------")
print("Dilution Calculator (C1 * V1 = C2 * V2)")
print("Keep in mind: All the factors must be in the same units! (Concentration: Molarity, Volume: uL, mL, etc.)")
print("--------------------------------------------------")
print("Hello, Which variable would you like to calculate today?")
print("1 = C1 (Initial concentration)")
print("2 = V1 (Initial volume)")
print("3 = C2 (Final concentration)")
print("4 = V2 (Final volume)")

choice = input("Enter 1, 2, 3, or 4: ")

if choice == "1":
    V1 = float(input("Enter V1: "))
    C2 = float(input("Enter C2: "))
    V2 = float(input("Enter V2: "))
    if V1 == 0:
        print("Error: V1 cannot be zero, run again.")
    else:
        C1 = (C2 * V2) / V1
        print(f"\nC1 = {C1}")
        print("This means that the initial concentration of your solution is", C1, "Molarity units.")

elif choice == "2":
    C1 = float(input("Enter C1: "))
    C2 = float(input("Enter C2: "))
    V2 = float(input("Enter V2: "))
    if C1 == 0:
        print("Error: C1 cannot be zero, run again.")
    else:
        V1 = (C2 * V2) / C1
        print(f"\nV1 = {V1}")
        print("This means that the initial volume of your solution is", V1, "Volume units.")

elif choice == "3":
    C1 = float(input("Enter C1: "))
    V1 = float(input("Enter V1: "))
    V2 = float(input("Enter V2: "))
    if V2 == 0:
        print("Error: V2 cannot be zero, run again.")
    else:
        C2 = (C1 * V1) / V2
        print(f"\nC2 = {C2}")
        print("This means that the final concentration of your solution is", C2, "Molarity units.")

elif choice == "4":
    C1 = float(input("Enter C1: "))
    V1 = float(input("Enter V1: "))
    C2 = float(input("Enter C2: "))
    if C2 == 0:
        print("Error: C2 cannot be zero, run again.")
    else:
        V2 = (C1 * V1) / C2
        print(f"\nV2 = {V2}")
        print("This means that the final volume of your solution is", V2, "Volume units.")