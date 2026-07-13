from __future__ import annotations

import shutil
import urllib.request
import zipfile
from pathlib import Path


DATA_URL = (
    "http://imlspenticton.uzh.ch/robinson_lab/HDCytoData/"
    "Bodenmiller_BCR_XL/Bodenmiller_BCR_XL_fcs_files.zip"
)
EXPECTED_CONTENT_TYPE = "application/zip"
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
USER_AGENT = "python-course-fcs-downloader/1.0"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dataset_dir = project_root / "example_data" / "bodenmiller_bcr_xl"
    source_dir = dataset_dir / "source"
    fcs_dir = dataset_dir / "fcs"
    zip_path = source_dir / "Bodenmiller_BCR_XL_fcs_files.zip"

    source_dir.mkdir(parents=True, exist_ok=True)
    fcs_dir.mkdir(parents=True, exist_ok=True)

    if zip_path.exists():
        raise FileExistsError(f"Download already exists: {zip_path}")
    if any(fcs_dir.iterdir()):
        raise FileExistsError(f"FCS output folder is not empty: {fcs_dir}")

    download_zip(DATA_URL, zip_path)
    fcs_names = validate_zip(zip_path)
    extract_fcs_files(zip_path, fcs_dir)
    validate_extracted_fcs(fcs_dir, fcs_names)

    print(f"Downloaded and validated {len(fcs_names)} FCS files.")
    print(f"FCS folder: {fcs_dir}")


def download_zip(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(request, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "")
        content_length = response.headers.get("Content-Length")

        if EXPECTED_CONTENT_TYPE not in content_type:
            raise ValueError(f"Unexpected content type: {content_type}")
        if content_length is not None and int(content_length) > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"Download is too large: {content_length} bytes")

        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)

    if destination.stat().st_size > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Downloaded file is too large: {destination.stat().st_size} bytes")
    if destination.read_bytes()[:4] != b"PK\x03\x04":
        raise ValueError("Downloaded file does not look like a ZIP archive.")


def validate_zip(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        bad_file = archive.testzip()
        if bad_file is not None:
            raise ValueError(f"ZIP integrity check failed for: {bad_file}")

        fcs_names = []
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member.is_dir():
                continue
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe path inside ZIP: {member.filename}")
            if member_path.suffix.lower() != ".fcs":
                raise ValueError(f"Unexpected file inside ZIP: {member.filename}")
            if member.file_size <= 0:
                raise ValueError(f"Empty FCS file inside ZIP: {member.filename}")
            fcs_names.append(member.filename)

    if not fcs_names:
        raise ValueError("ZIP archive does not contain FCS files.")
    return sorted(fcs_names)


def extract_fcs_files(zip_path: Path, fcs_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            target_path = fcs_dir / Path(member.filename).name
            if target_path.exists():
                raise FileExistsError(f"Refusing to overwrite existing file: {target_path}")
            with archive.open(member) as source, target_path.open("wb") as output:
                shutil.copyfileobj(source, output)


def validate_extracted_fcs(fcs_dir: Path, expected_names: list[str]) -> None:
    expected_base_names = sorted(Path(name).name for name in expected_names)
    extracted_files = sorted(fcs_dir.glob("*.fcs"))
    extracted_base_names = [path.name for path in extracted_files]

    if extracted_base_names != expected_base_names:
        raise ValueError("Extracted FCS files do not match ZIP contents.")

    for fcs_file in extracted_files:
        header = fcs_file.read_bytes()[:6]
        if header not in {b"FCS3.0", b"FCS3.1"}:
            raise ValueError(f"Unexpected FCS header in {fcs_file.name}: {header!r}")


if __name__ == "__main__":
    main()
