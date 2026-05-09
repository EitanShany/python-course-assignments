import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def excel_temp_dir():
    temp_root = Path("_test_temp")
    temp_dir = temp_root / str(uuid.uuid4())
    temp_dir.mkdir(parents=True)

    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(temp_root, ignore_errors=True)
