"""Local PaddleOCR recognizer for cropped handwritten numeric cells."""

import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from .config import PROJECT_ROOT


PADDLE_MODEL_NAME = "en_PP-OCRv5_mobile_rec"
REQUIRED_MODEL_FILES = (
    "config.json",
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)


class PaddleHandwritingRecognizer:
    """Recognize one numeric or printed-ID cell with PaddleOCR's English model."""

    def __init__(
        self,
        *,
        model_factory: Callable[..., Any] | None = None,
        model_name: str = PADDLE_MODEL_NAME,
    ) -> None:
        """Keep model loading lazy because initialization may download model files."""
        self.model_factory = model_factory
        self.model_name = model_name
        self._model: Any | None = None

    def recognize_number(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> tuple[str, float, dict[str, Any]]:
        """Return PaddleOCR text and confidence for one validated crop path."""
        if field_name not in {"mouse_id", "W", "L", "Weight"}:
            raise ValueError("field_name must be mouse_id, W, L, or Weight.")
        crop_path = Path(crop_image_path)
        if not crop_path.is_file():
            raise FileNotFoundError(f"PaddleOCR crop not found: {crop_path.resolve()}")

        model = self._get_model()
        results = list(model.predict(input=str(crop_path.resolve()), batch_size=1))
        if len(results) != 1:
            raise ValueError(
                f"PaddleOCR returned {len(results)} results for one cell crop."
            )
        payload = _result_payload(results[0])
        text = str(payload.get("rec_text") or "").strip()
        try:
            confidence = float(payload.get("rec_score", 0.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("PaddleOCR rec_score must be numeric.") from exc
        confidence = max(0.0, min(1.0, confidence))
        return text, confidence, {
            "backend": "paddleocr",
            "model_name": self.model_name,
            "result": payload,
        }

    def _get_model(self) -> Any:
        """Load the CPU recognition model once per application process."""
        if self._model is not None:
            return self._model
        factory = self.model_factory
        if factory is None:
            cache_root = _configure_local_model_cache()
            model_dir = _resolve_local_model_dir(cache_root, self.model_name)
            if model_dir is None:
                raise RuntimeError(
                    "PaddleOCR local model files are not available. "
                    "To keep image processing fully local, preload the model into "
                    f"{cache_root / 'paddlex' / 'official_models' / self.model_name}."
                )
            try:
                from paddleocr import TextRecognition
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is unavailable. Run the app with .venv-paddle."
                ) from exc
            factory = TextRecognition
            self._model = factory(
                model_name=self.model_name,
                model_dir=str(model_dir),
                device="cpu",
                enable_mkldnn=True,
                cpu_threads=4,
            )
            return self._model
        self._model = factory(
            model_name=self.model_name,
            device="cpu",
            enable_mkldnn=True,
            cpu_threads=4,
        )
        return self._model


def _result_payload(result: Any) -> dict[str, Any]:
    """Validate the documented PaddleOCR Result.json structure."""
    raw = getattr(result, "json", None)
    if callable(raw):
        raw = raw()
    if not isinstance(raw, dict):
        raise ValueError("PaddleOCR result does not contain a JSON object.")
    payload = raw.get("res", raw)
    if not isinstance(payload, dict):
        raise ValueError("PaddleOCR result 'res' must be an object.")
    return dict(payload)


def _configure_local_model_cache() -> Path:
    """Keep third-party model files in a writable local cache folder."""
    preferred = PROJECT_ROOT / ".model_cache"
    fallback = Path(tempfile.gettempdir()) / "mouse_monitor_ocr_model_cache"
    cache_root = _first_writable_folder(preferred, fallback)
    xdg_cache_root = cache_root / ".cache"
    paddle_home = xdg_cache_root / "paddle"
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_root / "paddlex")
    os.environ["XDG_CACHE_HOME"] = str(xdg_cache_root)
    os.environ["PADDLE_HOME"] = str(paddle_home)
    os.environ["HOME"] = str(cache_root)
    os.environ["USERPROFILE"] = str(cache_root)
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    return cache_root


def _resolve_local_model_dir(cache_root: Path, model_name: str) -> Path | None:
    """Return a ready local model directory only when all core files already exist."""
    candidates = [
        cache_root / "paddlex" / "official_models" / model_name,
        Path(os.environ["PADDLE_PDX_CACHE_HOME"]) / "official_models" / model_name,
        PROJECT_ROOT / ".model_cache" / "paddlex" / "official_models" / model_name,
        Path(tempfile.gettempdir())
        / "mouse_monitor_ocr_model_cache"
        / "paddlex"
        / "official_models"
        / model_name,
    ]
    for candidate in candidates:
        if all((candidate / filename).is_file() for filename in REQUIRED_MODEL_FILES):
            return candidate
    return None


def _first_writable_folder(*candidates: Path) -> Path:
    """Select a cache folder only after verifying an actual local write."""
    last_error: OSError | None = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=candidate, delete=True):
                pass
            return candidate
        except OSError as exc:
            last_error = exc
    raise PermissionError("No writable PaddleOCR model cache folder is available.") from last_error
