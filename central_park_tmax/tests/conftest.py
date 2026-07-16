import sys
from pathlib import Path

import pytest

# Ensure src/ is importable without installation.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def cfg(tmp_path):
    from central_park_tmax.config import load_config
    c = load_config(project_root=tmp_path)
    return c


@pytest.fixture
def report_fixtures():
    return FIXTURES / "nws_reports"
