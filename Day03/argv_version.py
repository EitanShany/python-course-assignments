import sys
from tumor_volume import calculate_tumor_volume


def main():
    try:
        if len(sys.argv) != 3:
            print("Usage: py argv_version.py <length> <width>")
            return

        length = float(sys.argv[1])
        width = float(sys.argv[2])

        volume = calculate_tumor_volume(length, width)

        print(f"Tumor volume is: {volume}")

    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()