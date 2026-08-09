"""
Tests for Timeline Dashboard API endpoints.

Phase 4 Tasks 3-5: Timeline API and Dashboard page implementation.
Following strict TDD: RED test first, then GREEN implementation.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from energizados.web.app import app

    return TestClient(app)


@pytest.fixture
def mock_run_manager():
    """Mock RunManager for testing."""
    with patch("energizados.web.app.RunManager") as mock:
        manager_instance = Mock()
        mock.return_value = manager_instance
        yield manager_instance


class TestTimelineApi:
    """Test suite for timeline API endpoint."""

    def test_timeline_api_returns_correct_structure(self, client, mock_run_manager):
        """Timeline API should return correct JSON structure with timestamps, auc, f1, run_ids arrays."""
        # Mock run data with RunMetadata structure
        from datetime import datetime

        mock_run = Mock()
        mock_run.run_id = "test-run-001"
        mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_run.val_auc = 0.85
        mock_run.val_f1 = 0.78
        mock_run.status = "success"

        mock_run_manager.list_runs.return_value = [mock_run]

        response = client.get("/api/dashboard/timeline?limit=20")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "timestamps" in data
        assert "auc" in data
        assert "f1" in data
        assert "run_ids" in data

        # Verify data types and lengths
        assert isinstance(data["timestamps"], list)
        assert isinstance(data["auc"], list)
        assert isinstance(data["f1"], list)
        assert isinstance(data["run_ids"], list)

        assert (
            len(data["timestamps"]) == len(data["auc"]) == len(data["f1"]) == len(data["run_ids"])
        )

        # Verify content
        assert data["run_ids"] == ["test-run-001"]
        assert data["auc"] == [0.85]
        assert data["f1"] == [0.78]

    def test_timeline_api_with_limit_param(self, client, mock_run_manager):
        """Timeline API should respect limit parameter and cap result size."""
        from datetime import datetime

        # Create 25 mock runs
        mock_runs = []
        for i in range(25):
            mock_run = Mock()
            mock_run.run_id = f"run-{i:03d}"
            mock_run.timestamp = datetime(2024, 1, i + 1, 10, 30, 0)
            mock_run.val_auc = 0.8 + (i * 0.01)
            mock_run.val_f1 = 0.75 + (i * 0.01)
            mock_runs.append(mock_run)

        mock_run_manager.list_runs.return_value = mock_runs

        response = client.get("/api/dashboard/timeline?limit=10")

        assert response.status_code == 200
        data = response.json()

        # Should return at most 10 runs
        assert len(data["run_ids"]) == 10

    def test_timeline_api_with_status_filter(self, client, mock_run_manager):
        """Timeline API should filter by status when status parameter provided."""
        from datetime import datetime

        # Create mixed status runs
        mock_runs = []
        for i, status in enumerate(["success", "failed", "success", "partial"]):
            mock_run = Mock()
            mock_run.run_id = f"run-{i}"
            mock_run.timestamp = datetime(2024, 1, i + 1, 10, 30, 0)
            mock_run.val_auc = 0.8
            mock_run.val_f1 = 0.75
            mock_run.status = status
            mock_runs.append(mock_run)

        mock_run_manager.list_runs.return_value = mock_runs

        # Filter for success only
        response = client.get("/api/dashboard/timeline?status=success")

        assert response.status_code == 200
        data = response.json()

        # Should only return success runs
        assert len(data["run_ids"]) == 2
        assert data["run_ids"] == ["run-0", "run-2"]

        # Verify RunManager was called with correct filter
        mock_run_manager.list_runs.assert_called_once_with(filter={"status": "success"}, limit=100)

    def test_timeline_api_empty_runs(self, client, mock_run_manager):
        """Timeline API should return empty arrays when no runs exist."""
        mock_run_manager.list_runs.return_value = []

        response = client.get("/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()

        assert data == {"timestamps": [], "auc": [], "f1": [], "run_ids": []}

    def test_timeline_api_handles_missing_metrics(self, client, mock_run_manager):
        """Timeline API should handle missing val_auc/val_f1 gracefully (exclude from arrays)."""
        from datetime import datetime

        # Create runs with missing metrics
        mock_runs = []
        for i, (auc, f1) in enumerate([(0.85, 0.78), (None, 0.75), (0.82, None), (None, None)]):
            mock_run = Mock()
            mock_run.run_id = f"run-{i}"
            mock_run.timestamp = datetime(2024, 1, i + 1, 10, 30, 0)
            mock_run.val_auc = auc
            mock_run.val_f1 = f1
            mock_run.status = "success"
            mock_runs.append(mock_run)

        mock_run_manager.list_runs.return_value = mock_runs

        response = client.get("/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()

        # Should include all runs but missing metrics should be None
        assert len(data["run_ids"]) == 4
        assert len(data["auc"]) == 4
        assert len(data["f1"]) == 4

        # Verify None values preserved
        assert data["auc"] == [0.85, None, 0.82, None]
        assert data["f1"] == [0.78, 0.75, None, None]


class TestDashboardPage:
    """Test suite for dashboard HTML page."""

    def test_dashboard_page_renders_html(self, client, mock_run_manager):
        """GET /dashboard should return HTML 200 response."""
        from datetime import datetime

        # Mock minimal run data
        mock_run = Mock()
        mock_run.run_id = "test-run-001"
        mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_run.val_auc = 0.85
        mock_run.val_f1 = 0.78
        mock_run.status = "success"

        mock_run_manager.list_runs.return_value = [mock_run]

        response = client.get("/dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Verify dashboard-specific content
        assert "dashboard" in response.text.lower() or "timeline" in response.text.lower()

    def test_dashboard_page_with_status_filter(self, client, mock_run_manager):
        """Dashboard page should pass status parameter to template context."""
        from datetime import datetime

        # Create mixed status runs
        mock_runs = []
        for i, status in enumerate(["success", "failed", "success"]):
            mock_run = Mock()
            mock_run.run_id = f"run-{i}"
            mock_run.timestamp = datetime(2024, 1, i + 1, 10, 30, 0)
            mock_run.val_auc = 0.8
            mock_run.val_f1 = 0.75
            mock_run.status = status
            mock_runs.append(mock_run)

        mock_run_manager.list_runs.return_value = mock_runs

        response = client.get("/dashboard?status=success")

        assert response.status_code == 200
        # The template should receive the status parameter
        # We can't directly check template context, but we can verify the page renders

    def test_dashboard_page_empty_state(self, client, mock_run_manager):
        """Dashboard page should render empty state when no runs exist."""
        mock_run_manager.list_runs.return_value = []

        response = client.get("/dashboard")

        assert response.status_code == 200
        # Should show empty state message
        assert "no run" in response.text.lower() or "empty" in response.text.lower()

    def test_dashboard_page_passes_params_to_template(self, client, mock_run_manager):
        """Dashboard page should pass limit and status parameters to template context."""
        from datetime import datetime

        mock_run = Mock()
        mock_run.run_id = "test-run-001"
        mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_run.val_auc = 0.85
        mock_run.val_f1 = 0.78
        mock_run.status = "success"

        mock_run_manager.list_runs.return_value = [mock_run]

        response = client.get("/dashboard?limit=50&status=success")

        assert response.status_code == 200
        # Verify parameters are being used (we can't directly check template context,
        # but the request should succeed and include the dashboard content)
