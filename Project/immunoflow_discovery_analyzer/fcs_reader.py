from __future__ import annotations

import struct
from pathlib import Path

import pandas as pd


FCS_HEADER_SIZE = 58


def read_fcs_metadata(file_path: str | Path) -> dict[str, str]:
    """Read the TEXT metadata segment from an FCS 3.x file."""
    path = _validate_fcs_path(file_path)
    data = path.read_bytes()
    _validate_fcs_header(data, path)

    text_start, text_end, _, _ = _read_header_offsets(data)
    if text_start < FCS_HEADER_SIZE or text_end >= len(data) or text_start > text_end:
        raise ValueError(f"Invalid FCS TEXT segment offsets in: {path}")

    text = data[text_start : text_end + 1].decode("latin1", errors="replace")
    if not text:
        raise ValueError(f"Empty FCS TEXT segment in: {path}")

    delimiter = text[0]
    parts = text[1:].split(delimiter)
    return dict(zip(parts[0::2], parts[1::2]))


def read_fcs_events(file_path: str | Path) -> pd.DataFrame:
    """Read FCS event data into a DataFrame.

    This reader intentionally supports the simple FCS layout used in the course
    example files: FCS 3.x, 32-bit floating point event values.
    """
    path = _validate_fcs_path(file_path)
    data = path.read_bytes()
    _validate_fcs_header(data, path)

    metadata = read_fcs_metadata(path)
    parameter_count = _read_positive_int(metadata, "$PAR", path)
    event_count = _read_positive_int(metadata, "$TOT", path)
    _validate_float_parameters(metadata, parameter_count, path)

    data_start, data_end = _data_offsets(data, metadata)
    event_bytes = data[data_start : data_end + 1]
    expected_bytes = event_count * parameter_count * 4
    if len(event_bytes) < expected_bytes:
        raise ValueError(f"FCS DATA segment is shorter than expected in: {path}")
    event_bytes = event_bytes[:expected_bytes]

    byte_order = metadata.get("$BYTEORD", "1,2,3,4")
    endian = _struct_endian(byte_order, path)
    values = struct.unpack(f"{endian}{event_count * parameter_count}f", event_bytes)
    rows = [
        values[index : index + parameter_count]
        for index in range(0, len(values), parameter_count)
    ]

    return pd.DataFrame(rows, columns=_parameter_labels(metadata, parameter_count))


def _validate_fcs_path(file_path: str | Path) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"FCS file was not found: {path}")
    if not path.is_file():
        raise ValueError(f"FCS path is not a file: {path}")
    if path.suffix.lower() != ".fcs":
        raise ValueError(f"Expected an .fcs file: {path}")
    return path


def _validate_fcs_header(data: bytes, path: Path) -> None:
    if len(data) < FCS_HEADER_SIZE:
        raise ValueError(f"FCS file is too small: {path}")
    if data[:6] not in {b"FCS3.0", b"FCS3.1"}:
        raise ValueError(f"Unsupported or invalid FCS header in: {path}")


def _read_header_offsets(data: bytes) -> tuple[int, int, int, int]:
    header = data[:FCS_HEADER_SIZE].decode("ascii", errors="replace")
    return (
        int(header[10:18]),
        int(header[18:26]),
        int(header[26:34]),
        int(header[34:42]),
    )


def _data_offsets(data: bytes, metadata: dict[str, str]) -> tuple[int, int]:
    _, _, data_start, data_end = _read_header_offsets(data)
    if data_start == 0 and data_end == 0:
        data_start = int(metadata.get("$BEGINDATA", "0"))
        data_end = int(metadata.get("$ENDDATA", "0"))
    if data_end == len(data):
        data_end -= 1
    if data_start < FCS_HEADER_SIZE or data_end >= len(data) or data_start > data_end:
        raise ValueError("Invalid FCS DATA segment offsets.")
    return data_start, data_end


def _read_positive_int(metadata: dict[str, str], key: str, path: Path) -> int:
    try:
        value = int(metadata[key])
    except (KeyError, ValueError) as error:
        raise ValueError(f"Missing or invalid {key} in: {path}") from error
    if value <= 0:
        raise ValueError(f"{key} must be positive in: {path}")
    return value


def _validate_float_parameters(
    metadata: dict[str, str],
    parameter_count: int,
    path: Path,
) -> None:
    if metadata.get("$DATATYPE") != "F":
        raise ValueError(f"Only 32-bit float FCS data is supported in: {path}")

    for index in range(1, parameter_count + 1):
        bit_width = metadata.get(f"$P{index}B")
        if bit_width != "32":
            raise ValueError(f"Only 32-bit FCS parameters are supported in: {path}")


def _struct_endian(byte_order: str, path: Path) -> str:
    if byte_order == "1,2,3,4":
        return "<"
    if byte_order == "4,3,2,1":
        return ">"
    raise ValueError(f"Unsupported FCS byte order in {path}: {byte_order}")


def _parameter_labels(metadata: dict[str, str], parameter_count: int) -> list[str]:
    labels = []
    used_labels: set[str] = set()
    for index in range(1, parameter_count + 1):
        label = metadata.get(f"$P{index}S") or metadata.get(f"$P{index}N") or f"P{index}"
        if label in used_labels:
            label = metadata.get(f"$P{index}N") or f"{label}_{index}"
        labels.append(label)
        used_labels.add(label)
    return labels
