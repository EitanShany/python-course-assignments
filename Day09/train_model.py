"""Train a classification model on the Pima Indians Diabetes dataset.

Usage:
    python train_model.py

Outputs:
    - models/classifier.joblib
"""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

try:
    from .data_utils import COLUMN_NAMES, FEATURE_NAMES, load_dataset
except ImportError:
    from data_utils import COLUMN_NAMES, FEATURE_NAMES, load_dataset

BASE = Path(__file__).parent
DATA_PATH = BASE / "data" / "pima-indians-diabetes.csv"
MODELS_DIR = BASE / "models"


def load_data():
    return load_dataset(DATA_PATH)


def train():
    df = load_data()
    X = df.drop(columns=["Outcome"])
    y = df["Outcome"]
    if set(y.unique()) != {0, 1}:
        raise ValueError("Training data must contain both Outcome values: 0 and 1.")
    if len(df) < 10 or y.value_counts().min() < 2:
        raise ValueError(
            "Training data is too small for a stratified train/test split."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)

    pred = clf.predict(X_test)
    prob = clf.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, pred)
    auc = roc_auc_score(y_test, prob)

    print(f"Classifier Accuracy: {acc:.4f}")
    print(f"Classifier ROC AUC: {auc:.4f}")
    print(classification_report(y_test, pred))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODELS_DIR / "classifier.joblib")

    importances = pd.Series(
        clf.feature_importances_,
        index=FEATURE_NAMES,
    ).sort_values(ascending=False)
    print("Top features:")
    print(importances.head(10))
    return clf


if __name__ == "__main__":
    train()
