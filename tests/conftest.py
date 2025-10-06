"""Shared pytest fixtures and utilities for Phonenv test suite."""

import shutil
import sys
from pathlib import Path
from typing import Callable

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_dir(tmp_path_factory) -> Path:
    """Create a temporary directory for tests.

    Uses pytest's tmp_path_factory for proper cleanup and isolation.
    Falls back to project directory if needed for path validation.
    """
    # Create in project data directory for path validation security
    test_dir = PROJECT_ROOT / "data" / ".test_tmp"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir

    # Cleanup
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def dataset_factory(temp_dir: Path) -> Callable[[str, str], Path]:
    """Factory for creating test dataset files.

    Returns:
        Callable that takes (filename, content) and returns the file path.

    Example:
        dataset = dataset_factory("data.txt", "pʰɪn\\nbɪn")
    """

    def _create_dataset(filename: str, content: str) -> Path:
        """Create a dataset file with the given content."""
        path = temp_dir / filename
        # Strip leading/trailing whitespace and ensure trailing newline
        normalized = content.strip() + "\n"
        path.write_text(normalized, encoding="utf-8")
        return path

    return _create_dataset


@pytest.fixture
def targets_factory(temp_dir: Path) -> Callable[[str, str], Path]:
    """Factory for creating test targets files.

    Returns:
        Callable that takes (filename, content) and returns the file path.

    Example:
        targets = targets_factory("targets.txt", "p\\ns\\np ~ b")
    """

    def _create_targets(filename: str, content: str) -> Path:
        """Create a targets file with the given content."""
        path = temp_dir / filename
        # Strip leading/trailing whitespace and ensure trailing newline
        normalized = content.strip() + "\n"
        path.write_text(normalized, encoding="utf-8")
        return path

    return _create_targets


@pytest.fixture
def output_dir(temp_dir: Path) -> Path:
    """Create a dedicated output directory for test results."""
    out_dir = temp_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# Test markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "targets: tests related to regular target analysis"
    )
    config.addinivalue_line(
        "markers",
        "alternations: tests related to alternation pattern detection",
    )
    config.addinivalue_line(
        "markers", "output: tests related to output format generation"
    )
    config.addinivalue_line(
        "markers", "edge: tests for edge cases and error handling"
    )
    config.addinivalue_line(
        "markers", "regression: regression tests for known issues"
    )
    config.addinivalue_line(
        "markers", "performance: performance and scalability tests"
    )
