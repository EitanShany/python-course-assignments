"""Load a saved diabetes model and run an example prediction."""
from pathlib import Path

import joblib

try:
    from .data_utils import FEATURE_NAMES, load_dataset, outcome_label
except ImportError:
    from data_utils import FEATURE_NAMES, load_dataset, outcome_label

BASE = Path(__file__).parent
MODELS_DIR = BASE / "models"
DATA_PATH = BASE / "data" / "pima-indians-diabetes.csv"


def load_model():
    model_path = MODELS_DIR / "classifier.joblib"
    if not model_path.is_file():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Run train_model.py first."
        )
    return joblib.load(model_path)


def example():
    clf = load_model()
    df = load_dataset(DATA_PATH)
    sample = df[FEATURE_NAMES].mean().to_frame().T
    prob = clf.predict_proba(sample)[0, 1]
    label = clf.predict(sample)[0]
    print("Example patient profile (mean values):")
    print(sample.to_dict(orient="records")[0])
    print(f"Predicted diabetes risk probability: {prob:.3f}")
    print(f"Predicted diagnosis: {outcome_label(label)}")


if __name__ == "__main__":
    example()
