"""Visualize the Pima Diabetes population and model decision boundary."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier

try:
    from .data_utils import load_dataset, outcome_label
except ImportError:
    from data_utils import load_dataset, outcome_label

BASE = Path(__file__).parent
DATA_PATH = BASE / "data" / "pima-indians-diabetes.csv"
FEATURES = ["Glucose", "BMI"]


def load_data():
    return load_dataset(DATA_PATH)


def plot_population():
    df = load_data()
    X = df[FEATURES]
    y = df["Outcome"]

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)

    x_min, x_max = X["Glucose"].min() - 5, X["Glucose"].max() + 5
    y_min, y_max = X["BMI"].min() - 5, X["BMI"].max() + 5
    xx, yy = np.meshgrid(
        np.linspace(x_min, x_max, 200),
        np.linspace(y_min, y_max, 200),
    )

    grid = pd.DataFrame(
        np.c_[xx.ravel(), yy.ravel()],
        columns=FEATURES,
    )
    Z = clf.predict(grid)
    Z = Z.reshape(xx.shape)

    plt.figure(figsize=(10, 7))
    plt.contourf(xx, yy, Z, alpha=0.2, cmap="coolwarm")

    for label, color, marker in [(0, "tab:blue", "o"), (1, "tab:red", "s")]:
        subset = df[df["Outcome"] == label]
        plt.scatter(
            subset["Glucose"],
            subset["BMI"],
            c=color,
            label=outcome_label(label),
            edgecolor="k",
            alpha=0.7,
            marker=marker,
            s=60,
        )

    sample = X.mean().to_frame().T
    plt.scatter(
        sample["Glucose"],
        sample["BMI"],
        c="black",
        marker="X",
        s=200,
        label="Average example",
        edgecolor="white",
        linewidth=1.5,
    )

    plt.xlabel("Glucose")
    plt.ylabel("BMI")
    plt.title("Pima Diabetes population: Glucose vs BMI with model decision surface")
    plt.legend()
    plt.grid(alpha=0.3)
    out_path = BASE / "diabetes_population.png"
    plt.savefig(out_path, dpi=150)
    print(f"Saved visualization to {out_path}")
    plt.show()


if __name__ == "__main__":
    plot_population()
