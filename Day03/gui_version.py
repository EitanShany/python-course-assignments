import tkinter as tk
from tumor_volume import calculate_tumor_volume


def calculate():
    try:
        length = float(length_entry.get())
        width = float(width_entry.get())

        volume = calculate_tumor_volume(length, width)

        result_label.config(
            text=f"Tumor volume is: {volume}",
            fg="darkgreen"
        )

    except ValueError as error:
        result_label.config(
            text=f"Error: {error}",
            fg="red"
        )


def exit_program():
    window.destroy()


window = tk.Tk()
window.title("Tumor Volume Calculator")
window.geometry("420x320")
window.configure(bg="#f2f2f2")

title_label = tk.Label(
    window,
    text="Tumor Volume Calculator",
    font=("Arial", 16, "bold"),
    bg="#f2f2f2",
    fg="#333333"
)
title_label.pack(pady=15)

length_label = tk.Label(
    window,
    text="Tumor length:",
    font=("Arial", 11),
    bg="#f2f2f2"
)
length_label.pack()

length_entry = tk.Entry(
    window,
    font=("Arial", 11),
    width=20
)
length_entry.pack(pady=5)

width_label = tk.Label(
    window,
    text="Tumor width:",
    font=("Arial", 11),
    bg="#f2f2f2"
)
width_label.pack()

width_entry = tk.Entry(
    window,
    font=("Arial", 11),
    width=20
)
width_entry.pack(pady=5)

calculate_button = tk.Button(
    window,
    text="Calculate",
    font=("Arial", 11, "bold"),
    bg="#4CAF50",
    fg="white",
    width=15,
    command=calculate
)
calculate_button.pack(pady=10)

exit_button = tk.Button(
    window,
    text="Exit",
    font=("Arial", 11),
    bg="#cc4444",
    fg="white",
    width=15,
    command=exit_program
)
exit_button.pack()

result_label = tk.Label(
    window,
    text="",
    font=("Arial", 12, "bold"),
    bg="#f2f2f2"
)
result_label.pack(pady=15)

window.mainloop()