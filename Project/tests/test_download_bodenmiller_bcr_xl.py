import zipfile

import pytest

from scripts.download_bodenmiller_bcr_xl import validate_extracted_fcs, validate_zip


def test_validate_zip_accepts_fcs_file(tmp_path):
    zip_path = tmp_path / "safe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("sample.fcs", b"FCS3.0 data")

    assert validate_zip(zip_path) == ["sample.fcs"]


def test_validate_zip_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../sample.fcs", b"FCS3.0 data")

    with pytest.raises(ValueError, match="Unsafe path"):
        validate_zip(zip_path)


def test_validate_zip_rejects_unexpected_file_type(tmp_path):
    zip_path = tmp_path / "unexpected.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("notes.txt", b"not an fcs file")

    with pytest.raises(ValueError, match="Unexpected file"):
        validate_zip(zip_path)


def test_validate_extracted_fcs_rejects_bad_header(tmp_path):
    fcs_dir = tmp_path / "fcs"
    fcs_dir.mkdir()
    (fcs_dir / "sample.fcs").write_bytes(b"not fcs")

    with pytest.raises(ValueError, match="Unexpected FCS header"):
        validate_extracted_fcs(fcs_dir, ["sample.fcs"])
