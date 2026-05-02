from tumor_volume import calculate_tumor_volume


def main():
    try:
        length = float(input("Enter tumor length: "))
        width = float(input("Enter tumor width: "))

        volume = calculate_tumor_volume(length, width)

        print(f"Tumor volume is: {volume}")

    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()