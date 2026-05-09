def calculate_tumor_volume(length, width):
    """
    Calculate subcutaneous tumor volume in mice.

    Formula:
    Tumor Volume = (width^2 * length) / 2
    """

    if not isinstance(length, (int, float)) or not isinstance(width, (int, float)):
        raise ValueError("Length and width must be numbers.")

    if width > length:
        raise ValueError("Width cannot be greater than length.")

    return (width ** 2 * length) / 2