"""Save Streamlit uploads and prepare images for later OCR stages."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
from pathlib import Path
import re
from typing import Any
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import PROJECT_ROOT


DEFAULT_INPUT_FOLDER = PROJECT_ROOT / "data" / "input_images"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
GROUP_PANEL_REDACTION_RIGHT_RATIO = 0.34
GROUP_PANEL_REDACTION_BOTTOM_RATIO = 0.30
MAX_GROUP_PANEL_BOTTOM_RATIO = 0.22


@dataclass(frozen=True)
class ImageMetadata:
    """Describe a saved and decoded source image."""

    source_name: str
    safe_filename: str
    saved_path: Path
    width: int
    height: int
    channels: int
    dtype: str
    file_size_bytes: int
    sha256: str


@dataclass(frozen=True)
class PreprocessedImage:
    """Hold the consistent source image and each basic preprocessing stage."""

    metadata: ImageMetadata
    original_bgr: np.ndarray
    grayscale: np.ndarray
    contrast_enhanced: np.ndarray
    thresholded: np.ndarray
    deskewed: np.ndarray
    perspective_corrected: np.ndarray


def load_uploaded_images(
    uploaded_files: list[Any],
    input_folder: Path | str = DEFAULT_INPUT_FOLDER,
) -> list[PreprocessedImage]:
    """Save and preprocess Streamlit UploadedFile objects in upload order."""
    folder = Path(input_folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Input images folder not found: {folder.resolve()}")
    return [load_uploaded_image(upload, folder) for upload in uploaded_files]


def load_uploaded_image(
    uploaded_file: Any,
    input_folder: Path | str = DEFAULT_INPUT_FOLDER,
) -> PreprocessedImage:
    """Save one uploaded image safely, decode it with OpenCV, and preprocess it."""
    folder = Path(input_folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Input images folder not found: {folder.resolve()}")

    source_name = Path(str(getattr(uploaded_file, "name", "uploaded_image"))).name
    extension = Path(source_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image extension '{extension or '(none)'}' for {source_name}."
        )
    content = _uploaded_bytes(uploaded_file)
    if not content:
        raise ValueError(f"Uploaded image is empty: {source_name}")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Uploaded image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit: "
            f"{source_name}"
        )

    original_bgr = _decode_image_bytes(content, source_name)
    redacted_bgr = _redact_group_panel(original_bgr)
    saved_bytes = _encode_image_bytes(redacted_bgr, extension, source_name)
    digest = hashlib.sha256(saved_bytes).hexdigest()
    safe_filename = _safe_filename(source_name, digest)
    saved_path = folder / safe_filename
    if not saved_path.exists() or saved_path.read_bytes() != saved_bytes:
        saved_path.write_bytes(saved_bytes)

    original_bgr = load_image(saved_path)
    gray = to_grayscale(original_bgr)
    enhanced = enhance_contrast(gray)
    binary = apply_threshold(enhanced)
    skew_angle = estimate_skew_angle(binary)
    deskewed_image = deskew(binary, skew_angle=skew_angle)
    perspective_image = correct_perspective(
        _rotate_image(original_bgr, skew_angle) if abs(skew_angle) >= 0.3 else original_bgr
    )
    height, width = original_bgr.shape[:2]
    channels = original_bgr.shape[2]

    return PreprocessedImage(
        metadata=ImageMetadata(
            source_name=source_name,
            safe_filename=safe_filename,
            saved_path=saved_path.resolve(),
            width=width,
            height=height,
            channels=channels,
            dtype=str(original_bgr.dtype),
            file_size_bytes=len(saved_bytes),
            sha256=digest,
        ),
        original_bgr=original_bgr,
        grayscale=gray,
        contrast_enhanced=enhanced,
        thresholded=binary,
        deskewed=deskewed_image,
        perspective_corrected=perspective_image,
    )


def load_image(path: Path | str) -> np.ndarray:
    """Decode an image with OpenCV and normalize it to uint8 three-channel BGR."""
    image_path = Path(path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path.resolve()}")
    return _decode_image_bytes(image_path.read_bytes(), str(image_path))


def _decode_image_bytes(content: bytes, source_name: str) -> np.ndarray:
    """Decode image bytes with EXIF-aware orientation handling."""
    try:
        with Image.open(BytesIO(content)) as pil_image:
            oriented = ImageOps.exif_transpose(pil_image)
            if oriented.width * oriented.height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    f"Decoded image exceeds the {MAX_IMAGE_PIXELS:,}-pixel safety limit: {source_name}"
                )
            rgb = oriented.convert("RGB")
            image = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
            return np.ascontiguousarray(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"OpenCV could not decode image: {source_name}") from exc


def _encode_image_bytes(image_bgr: np.ndarray, extension: str, source_name: str) -> bytes:
    """Encode a normalized BGR image for local redacted storage."""
    encoded_extension = ".jpg" if extension == ".jpeg" else extension
    success, encoded = cv2.imencode(encoded_extension, image_bgr)
    if not success:
        raise OSError(f"OpenCV could not encode image: {source_name}")
    return encoded.tobytes()


def _redact_group_panel(image_bgr: np.ndarray) -> np.ndarray:
    """Mask the upper-left group-name panel before any local file is persisted."""
    redacted = image_bgr.copy()
    height, width = redacted.shape[:2]
    search_window = redacted[
        : max(1, round(height * GROUP_PANEL_REDACTION_BOTTOM_RATIO)),
        : max(1, round(width * GROUP_PANEL_REDACTION_RIGHT_RATIO)),
    ]
    x2 = _leading_activity_extent(_activity_flags(search_window, axis=1))
    y2 = _leading_activity_extent(_activity_flags(search_window, axis=0))
    if x2 is None or y2 is None:
        return redacted
    cap_y = _group_panel_bottom_cap(redacted)
    if cap_y is not None:
        y2 = min(y2, cap_y)
    else:
        y2 = min(y2, max(1, round(height * MAX_GROUP_PANEL_BOTTOM_RATIO)))
    redacted[:y2, :x2] = 255
    return redacted


def _activity_flags(window_bgr: np.ndarray, *, axis: int) -> np.ndarray:
    """Detect dark content density across rows or columns in the top-left legend window."""
    gray = cv2.cvtColor(window_bgr, cv2.COLOR_BGR2GRAY)
    mask = gray < 235
    if axis == 0:
        minimum = max(2, round(window_bgr.shape[1] * 0.04))
        return np.count_nonzero(mask, axis=1) >= minimum
    if axis == 1:
        minimum = max(2, round(window_bgr.shape[0] * 0.04))
        return np.count_nonzero(mask, axis=0) >= minimum
    raise ValueError("axis must be 0 (rows) or 1 (columns).")


def _leading_activity_extent(flags: np.ndarray) -> int | None:
    """Keep only the first occupied block so redaction stops before the main table."""
    started = False
    last_active = -1
    gap = 0
    max_gap = max(3, len(flags) // 35)
    for index, active in enumerate(flags):
        if bool(active):
            started = True
            last_active = index
            gap = 0
            continue
        if not started:
            continue
        gap += 1
        if gap > max_gap:
            break
    if not started or last_active < 0:
        return None
    return last_active + 1


def _first_table_header_line_y(image_bgr: np.ndarray) -> int | None:
    """Detect the first long horizontal table line so redaction stops above the grid."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        15,
    )
    height, width = binary.shape
    search_top = max(1, round(height * 0.08))
    search_bottom = max(search_top + 1, round(height * 0.45))
    roi = binary[search_top:search_bottom, :]
    if roi.size == 0:
        return None
    horizontal = cv2.morphologyEx(
        roi,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, width // 5), 1)),
    )
    counts = np.count_nonzero(horizontal, axis=1)
    threshold = max(20, round(width * 0.30))
    indices = np.flatnonzero(counts >= threshold)
    if indices.size == 0:
        return None
    groups = np.split(indices, np.where(np.diff(indices) > 2)[0] + 1)
    first_group = groups[0]
    return search_top + int(round(float(first_group[0] + first_group[-1]) / 2.0))


def _group_panel_bottom_cap(image_bgr: np.ndarray) -> int | None:
    """Return a safe bottom edge for redaction based on detected table start."""
    height = image_bgr.shape[0]
    table_top = _table_bbox_top(image_bgr)
    if table_top is not None:
        return max(1, table_top - max(8, height // 80))
    header_line = _first_table_header_line_y(image_bgr)
    if header_line is not None:
        return max(1, header_line - max(8, height // 80))
    return None


def _table_bbox_top(image_bgr: np.ndarray) -> int | None:
    """Reuse table detection when a strong grid is visible in the phone photo."""
    try:
        from .table_detection import detect_table_bbox
    except Exception:
        return None
    try:
        table_bbox, method = detect_table_bbox(image_bgr)
    except Exception:
        return None
    if method != "detected_grid":
        return None
    return int(table_bbox.y)


def to_grayscale(image_bgr: np.ndarray) -> np.ndarray:
    """Convert a consistent BGR source image to an eight-bit grayscale image."""
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("to_grayscale expects a three-channel BGR image.")
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def enhance_contrast(grayscale: np.ndarray) -> np.ndarray:
    """Improve local contrast with CLAHE while limiting noise amplification."""
    if grayscale.ndim != 2:
        raise ValueError("enhance_contrast expects a grayscale image.")
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(_to_uint8(grayscale))


def apply_threshold(grayscale: np.ndarray) -> np.ndarray:
    """Create a binary image using automatic Otsu threshold selection."""
    if grayscale.ndim != 2:
        raise ValueError("apply_threshold expects a grayscale image.")
    _, thresholded = cv2.threshold(
        _to_uint8(grayscale), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return thresholded


def deskew(image: np.ndarray, *, skew_angle: float | None = None) -> np.ndarray:
    """Rotate a thresholded page gently back toward horizontal grid/text lines."""
    if image.ndim != 2:
        raise ValueError("deskew expects a grayscale or binary image.")
    source = _to_uint8(image)
    angle = estimate_skew_angle(source) if skew_angle is None else float(skew_angle)
    if abs(angle) < 0.3:
        return source.copy()
    rotated = _rotate_image(source, angle)
    _, thresholded = cv2.threshold(rotated, 127, 255, cv2.THRESH_BINARY)
    return thresholded


def correct_perspective(image: np.ndarray) -> np.ndarray:
    """Straighten a phone photo when a large page/table quadrilateral is visible."""
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("correct_perspective expects a non-empty image.")

    source = _to_uint8(image)
    if source.ndim == 2:
        gray = source
    elif source.ndim == 3 and source.shape[2] == 3:
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError("correct_perspective expects grayscale or BGR image.")

    contour = _find_document_contour(gray)
    if contour is None:
        return source.copy()

    ordered = _order_corner_points(contour.reshape(4, 2).astype("float32"))
    top_left, top_right, bottom_right, bottom_left = ordered
    target_width = int(
        max(
            np.linalg.norm(bottom_right - bottom_left),
            np.linalg.norm(top_right - top_left),
        )
    )
    target_height = int(
        max(
            np.linalg.norm(top_right - bottom_right),
            np.linalg.norm(top_left - bottom_left),
        )
    )
    if target_width < 20 or target_height < 20:
        return source.copy()

    destination = np.array(
        [
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1],
        ],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(ordered, destination)
    return cv2.warpPerspective(source, matrix, (target_width, target_height))


def estimate_skew_angle(image: np.ndarray) -> float:
    """Estimate a small page-rotation angle from long near-horizontal lines."""
    if image.ndim != 2:
        raise ValueError("estimate_skew_angle expects a grayscale or binary image.")
    source = _to_uint8(image)
    binary = cv2.threshold(
        source,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )[1]
    lines = cv2.HoughLinesP(
        binary,
        1,
        np.pi / 180,
        threshold=max(20, min(source.shape) // 3),
        minLineLength=max(20, source.shape[1] // 4),
        maxLineGap=max(5, source.shape[1] // 30),
    )
    if lines is None:
        return 0.0
    weighted_angles: list[float] = []
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0:
            continue
        angle = float(np.degrees(np.arctan2(dy, dx)))
        if abs(angle) > 30.0:
            continue
        length = max(1, int(round(np.hypot(dx, dy) / 20.0)))
        weighted_angles.extend([angle] * length)
    if not weighted_angles:
        return 0.0
    return float(np.median(np.asarray(weighted_angles, dtype=np.float32)))


def find_images(folder: Path | str) -> list[Path]:
    """Return supported image files already stored in the input folder."""
    root = Path(folder)
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _uploaded_bytes(uploaded_file: Any) -> bytes:
    """Read bytes from Streamlit UploadedFile or a compatible file-like object."""
    if hasattr(uploaded_file, "getvalue"):
        content = uploaded_file.getvalue()
    elif hasattr(uploaded_file, "read"):
        content = uploaded_file.read()
    else:
        raise TypeError("Uploaded image must provide getvalue() or read().")
    if not isinstance(content, bytes):
        raise TypeError("Uploaded image content must be bytes.")
    return content


def _safe_filename(source_name: str, digest: str) -> str:
    """Create a traversal-safe ASCII name with a content hash to avoid collisions."""
    extension = Path(source_name).suffix.lower()
    stem = unicodedata.normalize("NFKD", Path(source_name).stem).encode(
        "ascii", "ignore"
    ).decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("._-") or "image"
    return f"{stem[:80]}_{digest[:12]}{extension}"


def _to_uint8(image: np.ndarray) -> np.ndarray:
    """Normalize decoded integer or floating image data to OpenCV-friendly uint8."""
    if image.dtype == np.uint8:
        return np.ascontiguousarray(image)
    normalized = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)
    return np.ascontiguousarray(normalized.astype(np.uint8))


def _rotate_image(image: np.ndarray, angle_degrees: float) -> np.ndarray:
    """Rotate a grayscale or BGR image around its center while keeping a white border."""
    if abs(float(angle_degrees)) < 0.3:
        return np.ascontiguousarray(image.copy())
    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, float(angle_degrees), 1.0)
    border_value = 255 if image.ndim == 2 else (255, 255, 255)
    interpolation = cv2.INTER_NEAREST if image.ndim == 2 else cv2.INTER_CUBIC
    rotated = cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=interpolation,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value,
    )
    return np.ascontiguousarray(rotated)


def _find_document_contour(grayscale: np.ndarray) -> np.ndarray | None:
    """Find the largest convex four-corner contour suitable for perspective warp."""
    blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
        iterations=2,
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = grayscale.shape[0] * grayscale.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(contour)
        if area < image_area * 0.20:
            continue
        perimeter = cv2.arcLength(contour, True)
        corners = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(corners) == 4 and cv2.isContourConvex(corners):
            return corners
    return None


def _order_corner_points(points: np.ndarray) -> np.ndarray:
    """Return corner points ordered as top-left, top-right, bottom-right, bottom-left."""
    ordered = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(4)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[3] = points[np.argmax(differences)]
    return ordered
