"""Prepare corrected cell crops for a future deeper handwriting OCR model."""

from dataclasses import dataclass
from pathlib import Path
import random
from collections import Counter

from .learning_store import CORRECTIONS_FILENAME, DEFAULT_LEARNING_FOLDER, load_corrections
from .validation import DEFAULT_RANGES


SUPPORTED_FIELDS = ("W", "L", "Weight")


@dataclass(frozen=True)
class TrainingSample:
    """One verified crop and its reviewer-provided numeric label."""

    crop_path: Path
    label: str
    field_name: str
    source_image: str
    mouse_id: str


@dataclass(frozen=True)
class DatasetStatistics:
    """Summary of labels available for future model training."""

    corrected_samples: int
    samples_per_field: dict[str, int]
    unique_corrected_labels: list[str]
    skipped_missing_labels: int
    skipped_invalid_labels: int


@dataclass(frozen=True)
class TrainingDataset:
    """Deterministic train/validation split plus dataset statistics."""

    train_samples: list[TrainingSample]
    validation_samples: list[TrainingSample]
    statistics: DatasetStatistics


def prepare_training_data(
    corrections_csv: Path | str = DEFAULT_LEARNING_FOLDER / CORRECTIONS_FILENAME,
    *,
    validation_fraction: float = 0.20,
    random_seed: int = 42,
) -> TrainingDataset:
    """Load corrections, verify crops, split samples, and print statistics."""
    csv_path = Path(corrections_csv)
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be at least 0 and less than 1.")

    latest_corrections = {}
    available_corrections = load_corrections(csv_path.parent)
    if not available_corrections:
        raise FileNotFoundError(f"Corrections CSV not found: {csv_path.resolve()}")

    for correction in available_corrections:
        if correction.field_name not in SUPPORTED_FIELDS:
            continue
        latest_corrections[
            (
                correction.source_image,
                correction.mouse_id,
                correction.field_name,
            )
        ] = correction

    samples: list[TrainingSample] = []
    skipped_missing_labels = 0
    skipped_invalid_labels = 0
    missing_crops: list[str] = []
    for correction in latest_corrections.values():
        if correction.corrected_value is None:
            skipped_missing_labels += 1
            continue
        minimum, maximum = DEFAULT_RANGES[correction.field_name]
        if not minimum <= correction.corrected_value <= maximum:
            skipped_invalid_labels += 1
            continue
        if not correction.crop_path:
            missing_crops.append(
                f"{correction.source_image}/{correction.mouse_id}/{correction.field_name}: no path"
            )
            continue
        crop_path = Path(correction.crop_path).resolve()
        if not crop_path.is_file():
            missing_crops.append(str(crop_path))
            continue
        samples.append(
            TrainingSample(
                crop_path=crop_path,
                label=f"{correction.corrected_value:.2f}",
                field_name=correction.field_name,
                source_image=correction.source_image,
                mouse_id=correction.mouse_id,
            )
        )

    if missing_crops:
        preview = "\n  - ".join(missing_crops[:10])
        suffix = "" if len(missing_crops) <= 10 else f"\n  ... and {len(missing_crops) - 10} more"
        raise FileNotFoundError(
            f"{len(missing_crops)} correction crop(s) are missing:\n  - {preview}{suffix}"
        )

    shuffled = list(samples)
    random.Random(random_seed).shuffle(shuffled)
    validation_count = _validation_count(len(shuffled), validation_fraction)
    validation_samples = shuffled[:validation_count]
    train_samples = shuffled[validation_count:]
    field_counts = Counter(sample.field_name for sample in samples)
    statistics = DatasetStatistics(
        corrected_samples=len(samples),
        samples_per_field={field: field_counts.get(field, 0) for field in SUPPORTED_FIELDS},
        unique_corrected_labels=sorted(
            {sample.label for sample in samples}, key=float
        ),
        skipped_missing_labels=skipped_missing_labels,
        skipped_invalid_labels=skipped_invalid_labels,
    )
    dataset = TrainingDataset(train_samples, validation_samples, statistics)
    print_dataset_statistics(dataset)
    return dataset


def print_dataset_statistics(dataset: TrainingDataset) -> None:
    """Print a concise summary before any future training work begins."""
    stats = dataset.statistics
    print(f"Corrected samples: {stats.corrected_samples}")
    for field_name in SUPPORTED_FIELDS:
        print(f"  {field_name}: {stats.samples_per_field[field_name]}")
    labels = ", ".join(stats.unique_corrected_labels) or "none"
    print(f"Unique corrected labels ({len(stats.unique_corrected_labels)}): {labels}")
    print(f"Train samples: {len(dataset.train_samples)}")
    print(f"Validation samples: {len(dataset.validation_samples)}")
    if stats.skipped_missing_labels:
        print(f"Skipped corrections without a numeric label: {stats.skipped_missing_labels}")
    if stats.skipped_invalid_labels:
        print(f"Skipped out-of-range labels: {stats.skipped_invalid_labels}")


def _validation_count(sample_count: int, fraction: float) -> int:
    """Keep both splits non-empty when at least two labeled samples exist."""
    if sample_count < 2 or fraction == 0:
        return 0
    return min(sample_count - 1, max(1, round(sample_count * fraction)))
