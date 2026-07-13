"""Approximate the fixed monitoring table and create cell-by-cell OCR crops."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

import cv2
import numpy as np

from .config import PROJECT_ROOT


DEFAULT_CROPS_FOLDER = PROJECT_ROOT / "data" / "crops"
MAX_CAGES_PER_PAGE = 6
MAX_MICE_PER_CAGE = 5
MAX_MOUSE_ROWS = MAX_CAGES_PER_PAGE * MAX_MICE_PER_CAGE

# Relative column boundaries for the mostly fixed sheet layout. The full layout
# is: cage, mice, Ear marking, Treatment, W, L, Weight, Comment.
COLUMN_RANGES: dict[str, tuple[float, float]] = {
    "cage": (0.00, 0.065),
    "mouse_id": (0.065, 0.13),
    "ear_marking": (0.13, 0.24),
    "treatment": (0.24, 0.36),
    "W": (0.36, 0.50),
    "L": (0.50, 0.65),
    "Weight": (0.65, 0.80),
    "Comment": (0.80, 1.00),
}
OCR_FIELDS = ("mouse_id", "W", "L", "Weight", "Comment")
HEADER_HEIGHT_RATIO = 0.05
DATA_END_RATIO_WITH_FOOTER = 0.955
EXPECTED_TABLE_VERTICAL_LINES = 9


@dataclass(frozen=True)
class BoundingBox:
    """An integer image rectangle expressed as x, y, width, and height."""

    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        """Return the exclusive right coordinate."""
        return self.x + self.width

    @property
    def y2(self) -> int:
        """Return the exclusive bottom coordinate."""
        return self.y + self.height


@dataclass(frozen=True)
class CellRegion:
    """Describe one expected OCR cell and its saved image crop."""

    field_name: str
    page_row: int
    cage_number: int
    mouse_row_in_cage: int
    bbox: BoundingBox
    crop_path: Path | None = None


@dataclass(frozen=True)
class TableDetectionResult:
    """Return table geometry, cell crops, and optional alignment diagnostics."""

    source_image: str
    image_width: int
    image_height: int
    table_bbox: BoundingBox
    table_detection_method: str
    cells: list[CellRegion]
    debug_image_path: Path | None

    def cells_for_row(self, page_row: int) -> dict[str, CellRegion]:
        """Return field-name-to-cell mapping for one 1-based mouse row."""
        return {
            cell.field_name: cell
            for cell in self.cells
            if cell.page_row == page_row
        }


def detect_table(
    image: np.ndarray,
    source_image: str = "image.png",
    crops_folder: Path | str = DEFAULT_CROPS_FOLDER,
    *,
    debug: bool = False,
    mouse_rows: int = MAX_MOUSE_ROWS,
) -> TableDetectionResult:
    """Detect the table, calculate expected cells, and save every cell crop."""
    normalized = _normalize_image(image)
    folder = Path(crops_folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Crops folder not found: {folder.resolve()}")
    if not 1 <= mouse_rows <= MAX_MOUSE_ROWS:
        raise ValueError(f"mouse_rows must be between 1 and {MAX_MOUSE_ROWS}.")

    table_bbox, method = detect_table_bbox(normalized)
    data_bottom_y = estimate_data_bottom(normalized, table_bbox)
    row_boundaries, field_boundaries = detect_grid_boundaries(
        normalized,
        table_bbox,
        mouse_rows=mouse_rows,
        data_bottom_y=data_bottom_y,
    )
    regions = expected_cell_regions(
        table_bbox,
        mouse_rows=mouse_rows,
        data_bottom_y=data_bottom_y,
        row_boundaries=row_boundaries,
        field_boundaries=field_boundaries,
    )
    prefix = _source_prefix(source_image, normalized)
    saved_regions: list[CellRegion] = []
    for region in regions:
        crop = normalized[
            region.bbox.y : region.bbox.y2,
            region.bbox.x : region.bbox.x2,
        ]
        crop = _remove_cell_border(crop)
        crop_path = folder / (
            f"{prefix}_row{region.page_row:02d}_{region.field_name.lower()}.png"
        )
        _save_image(crop_path, crop)
        saved_regions.append(
            CellRegion(
                field_name=region.field_name,
                page_row=region.page_row,
                cage_number=region.cage_number,
                mouse_row_in_cage=region.mouse_row_in_cage,
                bbox=region.bbox,
                crop_path=crop_path.resolve(),
            )
        )

    debug_path: Path | None = None
    if debug:
        debug_path = folder / f"{prefix}_table_debug.png"
        _save_debug_image(normalized, table_bbox, saved_regions, debug_path)

    height, width = normalized.shape[:2]
    return TableDetectionResult(
        source_image=source_image,
        image_width=width,
        image_height=height,
        table_bbox=table_bbox,
        table_detection_method=method,
        cells=saved_regions,
        debug_image_path=debug_path.resolve() if debug_path else None,
    )


def detect_table_bbox(image: np.ndarray) -> tuple[BoundingBox, str]:
    """Find a large grid-like area, falling back to conservative page margins."""
    normalized = _normalize_image(image)
    gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    height, width = gray.shape
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(20, width // 12), 1)
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(20, height // 20))
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    grid = cv2.bitwise_or(horizontal, vertical)
    grid = cv2.morphologyEx(
        grid,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)),
        iterations=2,
    )
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = width * height
    candidates: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = box_width * box_height
        if area >= image_area * 0.20 and box_width >= width * 0.55 and box_height >= height * 0.35:
            candidates.append((x, y, box_width, box_height))
    if candidates:
        x, y, box_width, box_height = max(candidates, key=lambda item: item[2] * item[3])
        return BoundingBox(x, y, box_width, box_height), "detected_grid"

    margin_x = max(1, round(width * 0.03))
    margin_y = max(1, round(height * 0.05))
    return (
        BoundingBox(
            margin_x,
            margin_y,
            max(1, width - 2 * margin_x),
            max(1, height - 2 * margin_y),
        ),
        "relative_margin_fallback",
    )


def expected_cell_regions(
    table_bbox: BoundingBox,
    *,
    mouse_rows: int = MAX_MOUSE_ROWS,
    data_bottom_y: int | None = None,
    row_boundaries: list[int] | None = None,
    field_boundaries: dict[str, tuple[int, int]] | None = None,
) -> list[CellRegion]:
    """Return fixed-layout cell regions for mouse ID, W, L, Weight, and Comment."""
    if not 1 <= mouse_rows <= MAX_MOUSE_ROWS:
        raise ValueError(f"mouse_rows must be between 1 and {MAX_MOUSE_ROWS}.")
    body_y = table_bbox.y + round(table_bbox.height * HEADER_HEIGHT_RATIO)
    body_bottom = table_bbox.y2 if data_bottom_y is None else data_bottom_y
    if not body_y < body_bottom <= table_bbox.y2:
        raise ValueError("data_bottom_y must fall inside the table below its header.")
    if row_boundaries is None:
        body_height = max(1, body_bottom - body_y)
        row_boundaries = [
            body_y + round(body_height * row / mouse_rows)
            for row in range(mouse_rows + 1)
        ]
    else:
        if len(row_boundaries) != mouse_rows + 1:
            raise ValueError("row_boundaries must contain mouse_rows + 1 values.")
        if any(
            not table_bbox.y <= boundary <= table_bbox.y2
            for boundary in row_boundaries
        ):
            raise ValueError("row_boundaries must remain inside table_bbox.")
        if any(
            row_boundaries[index] >= row_boundaries[index + 1]
            for index in range(len(row_boundaries) - 1)
        ):
            raise ValueError("row_boundaries must be strictly increasing.")
    regions: list[CellRegion] = []
    for row_index in range(mouse_rows):
        y1, y2 = row_boundaries[row_index], row_boundaries[row_index + 1]
        for field_name in OCR_FIELDS:
            if field_boundaries and field_name in field_boundaries:
                x1, x2 = field_boundaries[field_name]
            else:
                left, right = COLUMN_RANGES[field_name]
                x1 = table_bbox.x + round(table_bbox.width * left)
                x2 = table_bbox.x + round(table_bbox.width * right)
            regions.append(
                CellRegion(
                    field_name=field_name,
                    page_row=row_index + 1,
                    cage_number=row_index // MAX_MICE_PER_CAGE + 1,
                    mouse_row_in_cage=row_index % MAX_MICE_PER_CAGE + 1,
                    bbox=BoundingBox(x1, y1, max(1, x2 - x1), max(1, y2 - y1)),
                )
            )
    return regions


def estimate_data_bottom(image: np.ndarray, table_bbox: BoundingBox) -> int:
    """Exclude a signature/footer row when the right-side table grid ends early."""
    normalized = _normalize_image(image)
    gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    vertical = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(
            cv2.MORPH_RECT, (1, max(20, normalized.shape[0] // 20))
        ),
    )
    bottom_start = table_bbox.y + round(table_bbox.height * 0.90)
    right_start = table_bbox.x + round(table_bbox.width * 0.75)
    bottom_right = vertical[bottom_start : table_bbox.y2, right_start : table_bbox.x2]
    has_full_height_right_grid = (
        bottom_right.size > 0
        and float(np.count_nonzero(bottom_right)) / float(bottom_right.size) >= 0.002
    )
    if has_full_height_right_grid:
        return table_bbox.y2
    return table_bbox.y + round(table_bbox.height * DATA_END_RATIO_WITH_FOOTER)


def detect_grid_boundaries(
    image: np.ndarray,
    table_bbox: BoundingBox,
    *,
    mouse_rows: int,
    data_bottom_y: int,
) -> tuple[list[int] | None, dict[str, tuple[int, int]] | None]:
    """Snap crop boundaries to detected grid lines when the photographed page is clear."""
    normalized = _normalize_image(image)
    table_roi = normalized[table_bbox.y : table_bbox.y2, table_bbox.x : table_bbox.x2]
    if table_roi.size == 0:
        return None, None
    gray = cv2.cvtColor(table_roi, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    height, width = gray.shape
    horizontal = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, width // 6), 1)),
    )
    vertical = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, height // 12))),
    )
    horizontal_centers = _line_centers(horizontal, axis=0, minimum_coverage=0.35)
    vertical_centers = _line_centers(vertical, axis=1, minimum_coverage=0.35)
    row_boundaries = _row_boundaries_from_horizontal_lines(
        horizontal_centers,
        table_bbox,
        mouse_rows=mouse_rows,
        data_bottom_y=data_bottom_y,
    )
    field_boundaries = _field_boundaries_from_vertical_lines(vertical_centers, table_bbox)
    return row_boundaries, field_boundaries


def _normalize_image(image: np.ndarray) -> np.ndarray:
    """Normalize grayscale/BGRA input to contiguous uint8 BGR."""
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("A non-empty NumPy image is required.")
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    elif image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Image must be grayscale, BGR, or BGRA.")
    return np.ascontiguousarray(image)


def _line_centers(
    binary: np.ndarray,
    *,
    axis: int,
    minimum_coverage: float,
) -> list[int]:
    """Return clustered center positions of long horizontal or vertical grid lines."""
    if binary.ndim != 2 or binary.size == 0:
        return []
    line_length = binary.shape[1] if axis == 0 else binary.shape[0]
    threshold = max(3, round(line_length * minimum_coverage))
    counts = np.count_nonzero(binary, axis=1 if axis == 0 else 0)
    indices = np.flatnonzero(counts >= threshold)
    if indices.size == 0:
        return []
    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    return [int(round(float(group[0] + group[-1]) / 2.0)) for group in groups if group.size]


def _row_boundaries_from_horizontal_lines(
    centers: list[int],
    table_bbox: BoundingBox,
    *,
    mouse_rows: int,
    data_bottom_y: int,
) -> list[int] | None:
    """Convert detected horizontal line centers to one boundary per data row."""
    selected = _best_line_window(
        centers,
        expected_count=mouse_rows + 2,
        start=0,
        end=max(1, data_bottom_y - table_bbox.y),
    )
    if selected is None:
        return None
    boundaries = [table_bbox.y + center for center in selected[1:]]
    return boundaries if len(boundaries) == mouse_rows + 1 else None


def _field_boundaries_from_vertical_lines(
    centers: list[int],
    table_bbox: BoundingBox,
) -> dict[str, tuple[int, int]] | None:
    """Map detected vertical table lines to the OCR fields we actually crop."""
    selected = _best_line_window(
        centers,
        expected_count=EXPECTED_TABLE_VERTICAL_LINES,
        start=0,
        end=max(1, table_bbox.width - 1),
    )
    if selected is None:
        return None
    global_lines = [table_bbox.x + center for center in selected]
    mapping = {
        "mouse_id": (global_lines[1], global_lines[2]),
        "W": (global_lines[4], global_lines[5]),
        "L": (global_lines[5], global_lines[6]),
        "Weight": (global_lines[6], global_lines[7]),
        "Comment": (global_lines[7], global_lines[8]),
    }
    if any(left >= right for left, right in mapping.values()):
        return None
    return mapping


def _best_line_window(
    centers: list[int],
    *,
    expected_count: int,
    start: int,
    end: int,
) -> list[int] | None:
    """Choose the most even consecutive run of detected line centers."""
    if len(centers) < expected_count:
        return None
    if len(centers) == expected_count:
        return list(centers)
    ideal_step = max(1.0, float(end - start) / float(expected_count - 1))
    best_window: list[int] | None = None
    best_score: float | None = None
    for offset in range(len(centers) - expected_count + 1):
        window = list(centers[offset : offset + expected_count])
        diffs = np.diff(window)
        if np.any(diffs <= 0):
            continue
        score = (
            float(np.std(diffs))
            + abs(float(np.mean(diffs)) - ideal_step)
            + abs(window[0] - start) * 0.15
            + abs(window[-1] - end) * 0.15
        )
        if best_score is None or score < best_score:
            best_score = score
            best_window = window
    return best_window


def _source_prefix(source_image: str, image: np.ndarray) -> str:
    """Create a safe, collision-resistant prefix for crop filenames."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(source_image).stem).strip("_-")
    stem = stem[:60] or "image"
    digest = hashlib.sha256(image.tobytes()).hexdigest()[:10]
    return f"{stem}_{digest}"


def _save_image(path: Path, image: np.ndarray) -> None:
    """Encode and save an image without relying on Unicode path support in imwrite."""
    if image.size == 0:
        raise ValueError(f"Cannot save an empty crop: {path.name}")
    success, encoded = cv2.imencode(path.suffix, image)
    if not success:
        raise OSError(f"OpenCV could not encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _remove_cell_border(crop: np.ndarray) -> np.ndarray:
    """Inset a crop slightly so printed grid lines do not dominate OCR."""
    height, width = crop.shape[:2]
    inset_x = max(1, round(width * 0.025))
    inset_y = max(1, round(height * 0.08))
    if width <= 2 * inset_x or height <= 2 * inset_y:
        return crop.copy()
    return crop[inset_y : height - inset_y, inset_x : width - inset_x].copy()


def _save_debug_image(
    image: np.ndarray,
    table_bbox: BoundingBox,
    cells: list[CellRegion],
    path: Path,
) -> None:
    """Draw the table and every expected OCR cell for visual alignment checks."""
    canvas = image.copy()
    cv2.rectangle(
        canvas,
        (table_bbox.x, table_bbox.y),
        (table_bbox.x2 - 1, table_bbox.y2 - 1),
        (255, 0, 255),
        3,
    )
    colors = {
        "mouse_id": (255, 128, 0),
        "W": (0, 180, 0),
        "L": (0, 180, 180),
        "Weight": (0, 100, 255),
        "Comment": (180, 0, 180),
    }
    for cell in cells:
        cv2.rectangle(
            canvas,
            (cell.bbox.x, cell.bbox.y),
            (cell.bbox.x2 - 1, cell.bbox.y2 - 1),
            colors[cell.field_name],
            1,
        )
    _save_image(path, canvas)
