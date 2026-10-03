from pathlib import Path

import pytest

from cursus.cli import load_reading

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def expense():
    return load_reading(EXAMPLES / "expense-claim" / "reading.json")


@pytest.fixture
def expense_source():
    return (EXAMPLES / "expense-claim" / "process.txt").read_text(encoding="utf-8")


@pytest.fixture
def hello():
    return load_reading(EXAMPLES / "hello" / "reading.json")
