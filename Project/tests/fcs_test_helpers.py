import struct
from pathlib import Path


def write_test_fcs(
    path: Path,
    columns: list[str],
    rows: list[list[float]],
) -> None:
    parameter_count = len(columns)
    event_count = len(rows)
    text_start = 58

    text_parts = [
        "$BEGINANALYSIS",
        "0",
        "$ENDANALYSIS",
        "0",
        "$NEXTDATA",
        "0",
        "$TOT",
        str(event_count),
        "$PAR",
        str(parameter_count),
        "$BYTEORD",
        "1,2,3,4",
        "$DATATYPE",
        "F",
        "$MODE",
        "L",
    ]
    for index, column in enumerate(columns, start=1):
        text_parts.extend(
            [
                f"$P{index}B",
                "32",
                f"$P{index}N",
                column,
                f"$P{index}S",
                column,
                f"$P{index}R",
                "262144",
                f"$P{index}E",
                "0,0",
            ]
        )

    text = "\\" + "\\".join(text_parts) + "\\"
    text_bytes = text.encode("latin1")
    text_end = text_start + len(text_bytes) - 1
    data_start = text_end + 1
    flat_values = [value for row in rows for value in row]
    data_bytes = struct.pack(f"<{len(flat_values)}f", *flat_values)
    data_end = data_start + len(data_bytes) - 1
    header = (
        f"FCS3.0    "
        f"{text_start:>8}"
        f"{text_end:>8}"
        f"{data_start:>8}"
        f"{data_end:>8}"
        f"{0:>8}"
        f"{0:>8}"
    ).encode("ascii")

    path.write_bytes(header + text_bytes + data_bytes)
