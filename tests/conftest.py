"""Shared test fixtures / path setup for the Content Pipeline test suite."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))


@pytest.fixture
def repo_root():
    return ROOT


@pytest.fixture
def deba_config():
    return json.loads((ROOT / "config" / "clients" / "deba.json").read_text())
