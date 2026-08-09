"""
Integration tests for Phase 4 Web Console features.

Phase 4 Task 20: Integration testing (RED + GREEN combined for efficiency).
Tests navigation, cross-view consistency, graceful degradation, and security.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from energizados.web.app import app

    return TestClient(app)


class TestPhase4Integration:
    """Integration test suite for Phase 4 features."""

    def test_path_traversal_blocked_all_endpoints(self, client):
        """Path traversal attempts should be blocked across all endpoints."""
        # Test comparison endpoint
        response = client.get("/runs/compare?ids=../../etc/passwd,run1")
        assert response.status_code == 400  # Should reject path traversal

        # Test API endpoints
        response = client.get("/api/runs/compare?ids=../../etc/passwd,run1")
        assert response.status_code == 400

        # Test with backslash (Windows path traversal)
        response = client.get("/runs/compare?ids=..\\..\\windows\\system32,run1")
        assert response.status_code == 400

    def test_threshold_api_handles_missing_report(self, client):
        """Threshold API should return 404 when evaluation report missing."""
        # Test with non-existent run (will be caught by RunManager.get_run returning None)
        with patch("energizados.web.app.RunManager") as mock_run_manager:
            mock_manager_instance = Mock()
            mock_run_manager.return_value = mock_manager_instance
            mock_manager_instance.get_run.return_value = None

            response = client.get("/api/runs/non-existent-run/thresholds")
            assert response.status_code == 404  # Should return 404, not 500

    def test_status_filter_works_on_timeline(self, client):
        """Status filter should work on timeline API."""
        # Test with a simple status filter request
        response = client.get("/api/dashboard/timeline?status=success")
        # Should not crash and should return valid JSON structure
        assert response.status_code == 200
        data = response.json()
        assert "run_ids" in data
        assert "timestamps" in data
        assert "auc" in data
        assert "f1" in data

    def test_dashboard_loads_without_errors(self, client):
        """Dashboard page should load without crashing."""
        response = client.get("/dashboard")
        # Should load successfully even with no runs
        assert response.status_code == 200

    def test_comparison_validation_works(self, client):
        """Comparison endpoint should validate run IDs properly."""
        # Test with single ID (should fail)
        response = client.get("/runs/compare?ids=single-run")
        assert response.status_code == 400

        # Test with too many IDs (should fail)
        many_ids = ",".join([f"run{i}" for i in range(11)])
        response = client.get(f"/runs/compare?ids={many_ids}")
        assert response.status_code == 400

    def test_comparison_api_validation_works(self, client):
        """Comparison API should validate run IDs properly."""
        # Test with single ID (should fail)
        response = client.get("/api/runs/compare?ids=single-run")
        assert response.status_code == 400

        # Test with empty IDs (should fail)
        response = client.get("/api/runs/compare?ids=")
        assert response.status_code == 400

    def test_threshold_endpoint_structure(self, client):
        """Threshold endpoint should have correct URL structure."""
        # Test that the endpoint exists and has correct routing
        # This is a basic structural test
        with patch("energizados.web.app.RunManager") as mock_run_manager:
            mock_manager_instance = Mock()
            mock_run_manager.return_value = mock_manager_instance
            mock_manager_instance.get_run.return_value = None

            # Test the endpoint is reachable (even if run doesn't exist)
            response = client.get("/api/runs/test-run/thresholds")
            # Should return 404, not a routing error
            assert response.status_code == 404

    def test_run_detail_page_loads(self, client):
        """Run detail page should load with basic structure."""
        # Test with a simple request to a non-existent run to check routing
        with patch("energizados.web.app.RunManager") as mock_run_manager:
            mock_manager_instance = Mock()
            mock_run_manager.return_value = mock_manager_instance
            mock_manager_instance.get_run.return_value = None

            response = client.get("/runs/test-run")
            # Should return 404, not 500 (routing works correctly)
            assert response.status_code == 404
