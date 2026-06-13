"""Download and validate the Pima Indians Diabetes dataset."""

import csv
import io
import math
from pathlib import Path
from urllib.parse import urlparse

import requests

URL = "https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv"
BASE = Path(__file__).parent
OUT_DIR = BASE / "data"
OUT_PATH = OUT_DIR / "pima-indians-diabetes.csv"

EXPECTED_HOST = "raw.githubusercontent.com"
EXPECTED_ROWS = 768
EXPECTED_COLUMNS = 9
MAX_DOWNLOAD_BYTES = 1_000_000
REQUEST_TIMEOUT = (5, 30)


def validate_dataset(content):
    """Validate downloaded bytes and return normalized UTF-8 CSV bytes."""
    if not content:
        raise ValueError("Downloaded dataset is empty.")
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Downloaded dataset is larger than the allowed limit.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Downloaded dataset is not valid UTF-8 text.") from exc

    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, but received {len(rows)}."
        )

    for row_number, row in enumerate(rows, start=1):
        if len(row) != EXPECTED_COLUMNS:
            raise ValueError(
                f"Row {row_number} has {len(row)} columns; "
                f"expected {EXPECTED_COLUMNS}."
            )
        try:
            values = [float(value) for value in row]
        except ValueError as exc:
            raise ValueError(f"Row {row_number} contains a non-numeric value.") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Row {row_number} contains a non-finite value.")
        if any(value < 0 for value in values[:-1]):
            raise ValueError(f"Row {row_number} contains a negative feature value.")

        outcome = values[-1]
        if outcome not in (0.0, 1.0):
            raise ValueError(
                f"Row {row_number} has an invalid Outcome value: {outcome}."
            )

    outcomes = {float(row[-1]) for row in rows}
    if outcomes != {0.0, 1.0}:
        raise ValueError("Dataset must contain both Outcome values: 0 and 1.")

    return text.encode("utf-8")


def download():
    """Download, validate, and safely save the dataset without overwriting."""
    if OUT_PATH.exists():
        raise FileExistsError(
            f"Dataset already exists and will not be overwritten: {OUT_PATH}"
        )

    print(f"Downloading {URL}...")
    response = requests.get(URL, timeout=REQUEST_TIMEOUT, stream=True)
    try:
        response.raise_for_status()

        final_url = urlparse(response.url)
        if final_url.scheme != "https" or final_url.hostname != EXPECTED_HOST:
            raise ValueError(f"Unexpected download location: {response.url}")

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError as exc:
                raise ValueError(
                    "Server returned an invalid Content-Length."
                ) from exc
            if declared_size < 0:
                raise ValueError("Server returned a negative Content-Length.")
            if declared_size > MAX_DOWNLOAD_BYTES:
                raise ValueError("Server response is larger than the allowed limit.")

        content = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > MAX_DOWNLOAD_BYTES:
                raise ValueError(
                    "Downloaded dataset is larger than the allowed limit."
                )
    finally:
        response.close()

    validated_content = validate_dataset(bytes(content))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = OUT_PATH.with_suffix(".csv.tmp")
    try:
        temporary_path.write_bytes(validated_content)
        temporary_path.replace(OUT_PATH)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    print(f"Validated {EXPECTED_ROWS} rows and saved dataset to {OUT_PATH}")
    return OUT_PATH


if __name__ == "__main__":
    download()
