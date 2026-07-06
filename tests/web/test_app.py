"""
Tests for FastAPI web application.

Following strict TDD: write failing tests first, then implement.
Coverage for all routes (tasks 5.10-5.18) and custom_class validation (5.12, 5.20).
"""

import logging
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

# Import after creating the app in implementation phase
# from energizados.web.app import app, _check_custom_class_prefixes

logger = logging.getLogger(__name__)


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    # Import here to avoid import errors before implementation
    from energizados.web.app import app

    return TestClient(app)


@pytest.fixture
def mock_store():
    """Mock JobStore for testing."""
    with patch("energizados.web.app.JobStore") as mock:
        store_instance = Mock()
        store_instance.list_jobs.return_value = []  # Default empty list
        mock.return_value = store_instance
        yield store_instance


class TestRootRoute:
    """Tests for GET / route (task 5.10)."""

    def test_get_root_returns_html(self, client):
        """GET / should return HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


class TestPostJobs:
    """Tests for POST /jobs route (tasks 5.11, 5.12, 5.20)."""

    def test_post_valid_yaml_creates_job(self, client, mock_store):
        """POST valid YAML should create job and return job_id."""
        valid_yaml = """
        etl:
          sample:
            enabled: true
            input: "data/raw/test.csv"
            output: "data/processed/test.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
        """

        mock_store.create_job.return_value = "job-test-123"

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=valid_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "job-test-123"
        assert data["status"] == "queued"
        mock_store.create_job.assert_called_once()

    def test_post_invalid_yaml_returns_400(self, client, mock_store):
        """POST invalid YAML should return 400 with validation errors."""
        invalid_yaml = """
        etl:
          sample:
            enabled: true
            # Missing required fields
        """

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=invalid_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "errors" in data or "detail" in data
        mock_store.create_job.assert_not_called()

    def test_post_disallowed_custom_class_returns_400(self, client, mock_store):
        """POST YAML with disallowed custom_class prefix should return 400."""
        malicious_yaml = """
        etl:
          evil:
            enabled: true
            input: "data/input.csv"
            output: "data/output.parquet"
            custom_class: "evil.malicious.Thing"
        """

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=malicious_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "custom_class" in str(data).lower() or "prefix" in str(data).lower()
        mock_store.create_job.assert_not_called()

    def test_post_mixed_custom_classes_validates_all(self, client, mock_store):
        """POST should validate ALL custom_class entries in config."""
        mixed_yaml = """
        train:
          models:
            - type: "lightgbm"
              custom_class: "src.models.LightGBMModel"
            - type: "custom"
              custom_class: "malicious.EvilModel"
        """

        response = client.post(
            "/jobs",
            params={"config_type": "train"},
            content=mixed_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        mock_store.create_job.assert_not_called()

    def test_post_allowed_prefixes_accepted(self, client, mock_store):
        """POST should accept energizados.* and src.* prefixes."""
        valid_yaml = """
        etl:
          custom:
            enabled: true
            input: "data/input.csv"
            output: "data/output.parquet"
            custom_class: "src.etl.custom.MyCustomETL"
        """

        mock_store.create_job.return_value = "job-custom-456"

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=valid_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 201
        mock_store.create_job.assert_called_once()

    def test_post_json_content_type_creates_job(self, client, mock_store):
        """POST with Content-Type: application/json should create job."""
        import json

        valid_json_config = {
            "etl": {
                "sample": {
                    "enabled": True,
                    "input": "data/raw/test.csv",
                    "output": "data/processed/test.parquet",
                    "custom_class": "energizados.etl.pipeline.SourceETL",
                }
            }
        }

        mock_store.create_job.return_value = "job-json-789"

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=json.dumps(valid_json_config),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "job-json-789"
        assert data["status"] == "queued"
        mock_store.create_job.assert_called_once()

    def test_post_no_content_type_fallback_to_yaml(self, client, mock_store):
        """POST with no content-type should try YAML first, then JSON."""
        valid_yaml = """
        train:
          enabled: true
          input_path: 'data/processed/dataset.parquet'
          target_column: 'target'
          models:
            - type: 'lightgbm'
        """

        mock_store.create_job.return_value = "job-yaml-fallback"

        response = client.post(
            "/jobs",
            params={"config_type": "train"},
            content=valid_yaml,
            # No Content-Type header
        )

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "job-yaml-fallback"
        mock_store.create_job.assert_called_once()

    def test_post_no_content_type_json_fallback(self, client, mock_store):
        """POST with no content-type should fallback to JSON if YAML fails."""

        # Use a JSON structure that would fail YAML parsing
        # (trailing commas are valid in JSON but not in YAML)
        valid_json_config = """
        {
            "etl": {
                "sample": {
                    "enabled": true,
                    "input": "data/raw/test.csv",
                    "output": "data/processed/test.parquet",
                    "custom_class": "energizados.etl.pipeline.SourceETL",
                }
            }
        }
        """

        mock_store.create_job.return_value = "job-json-fallback"

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=valid_json_config,
            # No Content-Type header - should try YAML first, fail, then JSON
        )

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "job-json-fallback"
        mock_store.create_job.assert_called_once()


class TestGetJobs:
    """Tests for GET /jobs route (task 5.13)."""

    def test_get_jobs_returns_html_fragment(self, client, mock_store):
        """GET /jobs should return HTML fragment with job list."""
        from energizados.web.models import JobRow, JobStatus

        mock_jobs = [
            JobRow(
                job_id="job-1",
                config={"test": "config"},
                config_type="etl",
                status=JobStatus.QUEUED,
                enqueued_at="2024-01-01T00:00:00Z",
            ),
            JobRow(
                job_id="job-2",
                config={"test": "config2"},
                config_type="train",
                status=JobStatus.RUNNING,
                enqueued_at="2024-01-01T01:00:00Z",
            ),
        ]
        mock_store.list_jobs.return_value = mock_jobs

        response = client.get("/jobs")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        mock_store.list_jobs.assert_called_once()

    def test_get_jobs_with_status_filter(self, client, mock_store):
        """GET /jobs?status=running should filter by status."""
        response = client.get("/jobs?status=running")

        assert response.status_code == 200
        mock_store.list_jobs.assert_called_once()

    def test_get_jobs_renders_status_badge_correctly(self, client, mock_store):
        """GET /jobs should render status badge with correct CSS classes."""
        from energizados.web.models import JobRow, JobStatus

        mock_jobs = [
            JobRow(
                job_id="job-1",
                config={"test": "config"},
                config_type="etl",
                status=JobStatus.SUCCESS,
                enqueued_at="2024-01-01T00:00:00Z",
            ),
        ]
        mock_store.list_jobs.return_value = mock_jobs

        response = client.get("/jobs")
        content = response.text

        # Should contain status-badge class
        assert "status-badge" in content
        # Should contain the specific status class
        assert "status-success" in content
        # Should show the status text
        assert "Success" in content
        mock_store.list_jobs.assert_called_once()


class TestGetJobDetail:
    """Tests for GET /jobs/{id} route (task 5.14)."""

    def test_get_existing_job_returns_detail(self, client, mock_store):
        """GET /jobs/{id} should return job detail HTML or JSON."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-detail-1",
            config={"test": "config"},
            config_type="etl",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
            run_id="run-123",
            run_dir="/output/train-20240101_0000",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-detail-1")

        assert response.status_code == 200
        mock_store.get_job.assert_called_once_with("job-detail-1")

    def test_get_nonexistent_job_returns_404(self, client, mock_store):
        """GET /jobs/{id} should return 404 for non-existent job."""
        mock_store.get_job.return_value = None

        response = client.get("/jobs/nonexistent-job")

        assert response.status_code == 404
        mock_store.get_job.assert_called_once_with("nonexistent-job")

    def test_get_job_detail_renders_status_badge(self, client, mock_store):
        """GET /jobs/{id} should render status badge with correct CSS classes."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-failed-1",
            config={"test": "config"},
            config_type="train",
            status=JobStatus.FAILED,
            enqueued_at="2024-01-01T00:00:00Z",
            error={"error_code": "ERROR", "message": "Test error"},
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-failed-1")
        content = response.text

        # Should contain status-badge class
        assert "status-badge" in content
        # Should contain the specific status class
        assert "status-failed" in content
        # Should show the status text
        assert "Failed" in content
        mock_store.get_job.assert_called_once_with("job-failed-1")

    def test_get_job_detail_json_accept(self, client, mock_store):
        """GET /jobs/{id} with Accept: application/json should return JSON."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-json-1",
            config={"test": "config"},
            config_type="etl",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            run_id="run-123",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-json-1", headers={"Accept": "application/json"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert data["job_id"] == "job-json-1"
        assert data["status"] == "running"
        assert data["config"] == {"test": "config"}
        mock_store.get_job.assert_called_once_with("job-json-1")


class TestCancelJob:
    """Tests for POST /jobs/{id}/cancel route (task 5.15)."""

    def test_cancel_running_job_succeeds(self, client, mock_store):
        """POST /jobs/{id}/cancel should cancel running job."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-running-1",
            config={"test": "config"},
            config_type="etl",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        mock_store.get_job.return_value = mock_job
        mock_store.cancel_job.return_value = True

        response = client.post("/jobs/job-running-1/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "aborted"
        mock_store.cancel_job.assert_called_once_with("job-running-1")

    def test_cancel_queued_job_noop(self, client, mock_store):
        """POST /jobs/{id}/cancel should no-op for queued job."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-queued-1",
            config={"test": "config"},
            config_type="etl",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T00:00:00Z",
        )
        mock_store.get_job.return_value = mock_job
        mock_store.cancel_job.return_value = False

        response = client.post("/jobs/job-queued-1/cancel")

        assert response.status_code == 200
        mock_store.cancel_job.assert_called_once_with("job-queued-1")

    def test_cancel_nonexistent_job_returns_404(self, client, mock_store):
        """POST /jobs/{id}/cancel should return 404 for non-existent job."""
        mock_store.get_job.return_value = None

        response = client.post("/jobs/nonexistent-job/cancel")

        assert response.status_code == 404
        mock_store.cancel_job.assert_not_called()

    def test_cancel_job_called_with_correct_id(self, client, mock_store):
        """POST /jobs/{id}/cancel should call cancel_job with correct job_id."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-to-cancel",
            config={"test": "config"},
            config_type="etl",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        mock_store.get_job.return_value = mock_job
        mock_store.cancel_job.return_value = True

        response = client.post("/jobs/job-to-cancel/cancel")

        assert response.status_code == 200
        mock_store.cancel_job.assert_called_once_with("job-to-cancel")


class TestRetryJob:
    """Tests for POST /jobs/{id}/retry route (task 5.16)."""

    def test_retry_failed_job_creates_new_job(self, client, mock_store):
        """POST /jobs/{id}/retry should create new job."""
        from energizados.web.models import JobRow, JobStatus

        mock_original = JobRow(
            job_id="job-failed-1",
            config={"test": "config"},
            config_type="etl",
            status=JobStatus.FAILED,
            enqueued_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:02:00Z",
            error={"error_code": "ERROR", "message": "Test error"},
        )
        mock_store.get_job.return_value = mock_original
        mock_store.retry_job.return_value = "job-retry-2"

        response = client.post("/jobs/job-failed-1/retry")

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "job-retry-2"
        assert data["status"] == "queued"
        mock_store.retry_job.assert_called_once_with("job-failed-1")

    def test_retry_nonexistent_job_returns_404(self, client, mock_store):
        """POST /jobs/{id}/retry should return 404 for non-existent job."""
        mock_store.get_job.return_value = None

        response = client.post("/jobs/nonexistent-job/retry")

        assert response.status_code == 404
        mock_store.retry_job.assert_not_called()

    def test_retry_job_called_with_correct_id(self, client, mock_store):
        """POST /jobs/{id}/retry should call retry_job with correct job_id."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-to-retry",
            config={"test": "config"},
            config_type="train",
            status=JobStatus.FAILED,
            enqueued_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:02:00Z",
            error={"error_code": "ERROR", "message": "Test error"},
        )
        mock_store.get_job.return_value = mock_job
        mock_store.retry_job.return_value = "job-retried-new"

        response = client.post("/jobs/job-to-retry/retry")

        assert response.status_code == 201
        mock_store.retry_job.assert_called_once_with("job-to-retry")


class TestHealthRoute:
    """Tests for GET /health route (task 5.17)."""

    def test_health_returns_ok(self, client):
        """GET /health should return JSON health status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True


class TestApiRunsRoute:
    """Tests for GET /api/runs route (task 5.18)."""

    def test_get_runs_proxies_run_manager(self, client):
        """GET /api/runs should proxy RunManager.list_runs()."""
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.list_runs.return_value = ["run-1", "run-2"]

            response = client.get("/api/runs")

            assert response.status_code == 200
            data = response.json()
            assert "runs" in data or isinstance(data, list)
            mock_rm.list_runs.assert_called_once()

    def test_get_runs_error_returns_500(self, client):
        """GET /api/runs should return 500 on RunManager error."""
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.list_runs.side_effect = Exception("Test error")

            response = client.get("/api/runs")

            assert response.status_code == 500
            data = response.json()
            assert "runs" in data
            assert data["runs"] == []
            assert "error" in data
            assert "Test error" in data["error"]
            mock_rm.list_runs.assert_called_once()


class TestCustomClassPrefixValidation:
    """Tests for _check_custom_class_prefixes helper (tasks 5.12, 5.20)."""

    def test_validate_allowed_prefixes(self):
        """Allowed prefixes (energizados.*, src.*) should pass validation."""
        from energizados.web.app import _check_custom_class_prefixes

        config = {
            "etl": {"custom": {"custom_class": "src.etl.CustomETL"}},
            "train": {"models": [{"custom_class": "energizados.modeling.LGBMModel"}]},
        }

        invalid = _check_custom_class_prefixes(config)
        assert invalid == []

    def test_validate_disallowed_prefixes(self):
        """Disallowed prefixes should be returned in invalid list."""
        from energizados.web.app import _check_custom_class_prefixes

        config = {"etl": {"evil": {"custom_class": "evil.malicious.Thing"}}}

        invalid = _check_custom_class_prefixes(config)
        assert len(invalid) == 1
        assert "evil.malicious.Thing" in invalid

    def test_validate_nested_custom_classes(self):
        """Should find custom_class entries at any nesting level."""
        from energizados.web.app import _check_custom_class_prefixes

        config = {
            "train": {
                "feature_engineering": {
                    "preprocessing": {
                        "columns": {"test_col": [{"custom_class": "malicious.Transformer"}]}
                    }
                }
            }
        }

        invalid = _check_custom_class_prefixes(config)
        assert len(invalid) == 1
        assert "malicious.Transformer" in invalid

    def test_validate_empty_config(self):
        """Empty config should have no invalid paths."""
        from energizados.web.app import _check_custom_class_prefixes

        config = {}
        invalid = _check_custom_class_prefixes(config)
        assert invalid == []

    def test_validate_config_without_custom_class(self):
        """Config without custom_class should have no invalid paths."""
        from energizados.web.app import _check_custom_class_prefixes

        config = {"etl": {"sample": {"enabled": True, "input": "data/test.csv"}}}

        invalid = _check_custom_class_prefixes(config)
        assert invalid == []

    def test_validate_multiple_disallowed(self):
        """Should return all disallowed prefixes."""
        from energizados.web.app import _check_custom_class_prefixes

        config = {
            "train": {
                "models": [{"custom_class": "evil.Model1"}, {"custom_class": "malicious.Model2"}]
            }
        }

        invalid = _check_custom_class_prefixes(config)
        assert len(invalid) == 2
        assert "evil.Model1" in invalid
        assert "malicious.Model2" in invalid
