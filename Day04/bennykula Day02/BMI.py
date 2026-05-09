"""
BMI Calculator
A simple program to calculate Body Mass Index based on user input.
"""

def calculate_bmi(weight, height):
    """
    Calculate BMI given weight in kg and height in meters.
    
    Args:
        weight: Weight in kilograms
        height: Height in meters
    
    Returns:
        BMI value rounded to 2 decimal places
    """
    bmi = weight / (height ** 2)
    return round(bmi, 2)


def get_bmi_category(bmi):
    """
    Determine BMI category based on BMI value.
    
    Args:
        bmi: BMI value
    
    Returns:
        String describing BMI category
    """
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal weight"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def main():
    """Main function to run the BMI calculator."""
    print("=" * 40)
    print("Welcome to the BMI Calculator!")
    print("=" * 40)
    
    try:
        # Get user input
        weight = float(input("Enter your weight in kilograms (kg): "))
        height = float(input("Enter your height in meters (m): "))
        
        # Validate input
        if weight <= 0 or height <= 0:
            print("Error: Weight and height must be positive numbers!")
            return
        
        # Calculate BMI
        bmi = calculate_bmi(weight, height)
        category = get_bmi_category(bmi)
        
        # Display results
        print("\n" + "=" * 40)
        print(f"Your BMI: {bmi}")
        print(f"Category: {category}")
        print("=" * 40)
        
    except ValueError:
        print("Error: Please enter valid numbers for weight and height!")


if __name__ == "__main__":
    main()
    