"""
Tests for Comparison View validation and helpers.

Phase 4 Tasks 6-13: Comparison View implementation.
Following strict TDD: RED test first, then GREEN implementation.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from energizados.web.app import app

    return TestClient(app)


class TestRunIdParsing:
    """Test suite for run ID parsing and validation."""

    def test_parse_valid_run_ids(self, client):
        """Valid comma-separated IDs should be parsed correctly."""
        from energizados.web.app import _parse_and_validate_run_ids

        ids_str = "run1,run2,run3"
        result = _parse_and_validate_run_ids(ids_str, max_count=10)

        assert result == ["run1", "run2", "run3"]

    def test_parse_less_than_2_ids_returns_400(self, client):
        """Single ID should be rejected with 400 error."""
        from fastapi import HTTPException

        from energizados.web.app import _parse_and_validate_run_ids

        with pytest.raises(HTTPException) as exc_info:
            _parse_and_validate_run_ids("run1", max_count=10)

        assert exc_info.value.status_code == 400
        assert "At least 2 run IDs required" in exc_info.value.detail

    def test_parse_more_than_10_ids_returns_400(self, client):
        """More than 10 IDs should be rejected with 400 error."""
        from fastapi import HTTPException

        from energizados.web.app import _parse_and_validate_run_ids

        # Create 11 IDs
        ids_str = ",".join([f"run{i}" for i in range(11)])

        with pytest.raises(HTTPException) as exc_info:
            _parse_and_validate_run_ids(ids_str, max_count=10)

        assert exc_info.value.status_code == 400
        assert "Maximum 10 run IDs allowed" in exc_info.value.detail

    def test_parse_empty_ids_returns_400(self, client):
        """Empty string should be rejected."""
        from fastapi import HTTPException

        from energizados.web.app import _parse_and_validate_run_ids

        with pytest.raises(HTTPException) as exc_info:
            _parse_and_validate_run_ids("", max_count=10)

        assert exc_info.value.status_code == 400
        assert "required" in exc_info.value.detail.lower()

    def test_parse_path_traversal_rejected(self, client):
        """IDs with .. or / should be rejected as path traversal attempts."""
        from fastapi import HTTPException

        from energizados.web.app import _parse_and_validate_run_ids

        # Test various path traversal attempts
        malicious_ids = [
            "run1,../../etc/passwd,run2",
            "run1,../config,run2",
            "run1,/etc/passwd,run2",
            "run1,\\windows\\system32,run2",
        ]

        for ids_str in malicious_ids:
            with pytest.raises(HTTPException) as exc_info:
                _parse_and_validate_run_ids(ids_str, max_count=10)

            assert exc_info.value.status_code == 400
            assert "Invalid run_id" in exc_info.value.detail

    def test_parse_whitespace_handled(self, client):
        """Extra whitespace should be stripped correctly."""
        from energizados.web.app import _parse_and_validate_run_ids

        ids_str = "  run1  ,  run2  , run3  "
        result = _parse_and_validate_run_ids(ids_str, max_count=10)

        assert result == ["run1", "run2", "run3"]
