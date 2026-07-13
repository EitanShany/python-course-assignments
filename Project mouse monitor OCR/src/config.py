"""Load and validate the application's central JSON configuration."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"
MEASUREMENT_NAMES = ("W", "L", "Weight")


@dataclass(frozen=True)
class Config:
    """Validated application settings with paths resolved from the project root."""

    project_root: Path
    excel_template_path: Path
    output_folder: Path
    input_images_folder: Path
    sheet_name: str
    mouse_id_column: str
    output_columns: dict[str, str]
    valid_ranges: dict[str, tuple[float, float]]
    excel_rules: dict[str, bool]
    mapping_key: str
    zero_is_valid: bool
    decimal_separator: str
    decimal_places: int
    excel_number_format: str
    mouse_id_start_row: int = 1

    @classmethod
    def load(
        cls,
        settings_path: Path | str = DEFAULT_SETTINGS_PATH,
        *,
        excel_template_path_override: Path | str | None = None,
    ) -> "Config":
        """Load JSON settings and fail clearly when configuration is unusable."""
        path = Path(settings_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Settings file not found: {path}")

        try:
            with path.open(encoding="utf-8") as settings_file:
                raw = json.load(settings_file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in settings file {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError("The settings JSON root must be an object.")

        root = path.parent.parent
        required = {
            "excel_template_path",
            "output_folder",
            "input_images_folder",
            "sheet_name",
            "mouse_id_column",
            "output_columns",
            "valid_ranges",
            "excel_rules",
            "mapping_key",
            "zero_is_valid",
            "decimal_separator",
            "decimal_places",
            "excel_number_format",
        }
        missing = sorted(required.difference(raw))
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")

        template_path = (
            Path(excel_template_path_override).resolve()
            if excel_template_path_override is not None
            else cls._resolve_path(root, raw["excel_template_path"])
        )
        output_folder = cls._resolve_path(root, raw["output_folder"])
        input_folder = cls._resolve_path(root, raw["input_images_folder"])
        cls._validate_required_paths(template_path, output_folder, input_folder)

        output_columns = cls._measurement_mapping(raw["output_columns"], "output_columns")
        ranges = cls._parse_ranges(raw["valid_ranges"])
        excel_rules = raw["excel_rules"]
        if not isinstance(excel_rules, dict) or not all(
            isinstance(key, str) and isinstance(value, bool)
            for key, value in excel_rules.items()
        ):
            raise ValueError("excel_rules must map rule names to true/false values.")

        sheet_name = raw["sheet_name"]
        if not isinstance(sheet_name, str) or not sheet_name.strip():
            raise ValueError("sheet_name must be a non-empty string.")
        mapping_key = raw["mapping_key"]
        if mapping_key != "mouse_id":
            raise ValueError("mapping_key must be 'mouse_id'; image order is not allowed.")
        zero_is_valid = raw["zero_is_valid"]
        if zero_is_valid is not True:
            raise ValueError("zero_is_valid must be true.")

        mouse_id_column = cls._column_name(raw["mouse_id_column"], "mouse_id_column")
        output_columns = {
            name: cls._column_name(column, f"output_columns.{name}")
            for name, column in output_columns.items()
        }

        decimal_places = raw["decimal_places"]
        if not isinstance(decimal_places, int) or isinstance(decimal_places, bool) or decimal_places < 0:
            raise ValueError("decimal_places must be a non-negative integer.")
        if raw["decimal_separator"] != ".":
            raise ValueError("decimal_separator must be '.' for dot notation.")
        mouse_id_start_row = raw.get("mouse_id_start_row", 1)
        if (
            not isinstance(mouse_id_start_row, int)
            or isinstance(mouse_id_start_row, bool)
            or mouse_id_start_row < 1
        ):
            raise ValueError("mouse_id_start_row must be a positive integer.")

        return cls(
            project_root=root,
            excel_template_path=template_path,
            output_folder=output_folder,
            input_images_folder=input_folder,
            sheet_name=sheet_name,
            mouse_id_column=mouse_id_column,
            output_columns=output_columns,
            valid_ranges=ranges,
            excel_rules=dict(excel_rules),
            mapping_key=mapping_key,
            zero_is_valid=zero_is_valid,
            decimal_separator=raw["decimal_separator"],
            decimal_places=decimal_places,
            excel_number_format=str(raw["excel_number_format"]),
            mouse_id_start_row=mouse_id_start_row,
        )

    @staticmethod
    def _resolve_path(root: Path, value: Any) -> Path:
        """Resolve a configured path relative to the project root."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Configured paths must be non-empty strings.")
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    @staticmethod
    def _validate_required_paths(template: Path, output: Path, input_folder: Path) -> None:
        """Ensure the template file and working directories already exist."""
        if not template.is_file():
            raise FileNotFoundError(f"Excel template not found: {template}")
        for label, folder in (("Output folder", output), ("Input images folder", input_folder)):
            if not folder.is_dir():
                raise FileNotFoundError(f"{label} not found: {folder}")

    @staticmethod
    def _column_name(value: Any, setting: str) -> str:
        """Validate and normalize an Excel column name."""
        if not isinstance(value, str) or not value.isalpha():
            raise ValueError(f"{setting} must be an Excel column name.")
        return value.upper()

    @staticmethod
    def _measurement_mapping(value: Any, setting: str) -> dict[str, Any]:
        """Validate that a mapping contains exactly the three measurements."""
        if not isinstance(value, dict) or set(value) != set(MEASUREMENT_NAMES):
            raise ValueError(f"{setting} must contain W, L, and Weight.")
        return dict(value)

    @classmethod
    def _parse_ranges(cls, value: Any) -> dict[str, tuple[float, float]]:
        """Convert configured min/max objects to validated numeric tuples."""
        mappings = cls._measurement_mapping(value, "valid_ranges")
        result: dict[str, tuple[float, float]] = {}
        for name, limits in mappings.items():
            if not isinstance(limits, dict) or set(limits) != {"min", "max"}:
                raise ValueError(f"valid_ranges.{name} must contain min and max.")
            minimum, maximum = limits["min"], limits["max"]
            if (
                not isinstance(minimum, (int, float))
                or isinstance(minimum, bool)
                or not isinstance(maximum, (int, float))
                or isinstance(maximum, bool)
                or minimum > maximum
            ):
                raise ValueError(f"Invalid numeric range for {name}.")
            result[name] = (float(minimum), float(maximum))
        return result


def load_settings(path: Path | str = DEFAULT_SETTINGS_PATH) -> Config:
    """Load the central settings file into a :class:`Config` instance."""
    return Config.load(path)
