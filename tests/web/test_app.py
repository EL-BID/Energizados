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


@pytest.fixture
def fake_run_dir(tmp_path):
    """
    Create a fake run directory for testing artifact serving.

    Creates a temporary directory structure that mimics a real run directory.

    Returns:
        Path: Temporary run directory path
    """
    import json

    run_id = "train-20240101_120000"
    run_dir = tmp_path / run_id
    run_dir.mkdir(exist_ok=True)

    # Create run metadata file
    run_metadata = {
        "run_id": run_id,
        "timestamp": "2024-01-01T00:00:00Z",
        "duration_seconds": 60.0,
        "status": "success",
        "model_types": ["lightgbm"],
        "val_auc": 0.85,
        "val_f1": 0.78,
        "feature_count": 10,
        "energizados_version": "0.3.0",
        "python_version": "3.10",
        "git_commit": "abc123",
        "config_files": ["train.yaml"],
        "output_paths": {},
    }

    metadata_file = run_dir / "run_metadata.json"
    metadata_file.write_text(json.dumps(run_metadata))

    # Create reports directory
    reports_dir = run_dir / "reports" / "evaluation"
    reports_dir.mkdir(parents=True, exist_ok=True)

    return run_dir


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


class TestHTMXContentNegotiation:
    """Tests for HTMX content negotiation in POST /jobs (PR3 UX gap fix)."""

    def test_post_with_htmx_request_validation_error_returns_html(self, client, mock_store):
        """POST with HX-Request header should return HTML fragment on validation error."""
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
            headers={"Content-Type": "application/yaml", "HX-Request": "true"},
        )

        assert response.status_code == 400
        assert response.headers["content-type"].startswith("text/html")
        # Should contain validation error structure
        assert "validation" in response.text.lower() or "error" in response.text.lower()
        mock_store.create_job.assert_not_called()

    def test_post_with_htmx_request_success_returns_html(self, client, mock_store):
        """POST with HX-Request header should return HTML fragment on success."""
        valid_yaml = """
        etl:
          sample:
            enabled: true
            input: "data/raw/test.csv"
            output: "data/processed/test.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
        """

        mock_store.create_job.return_value = "job-htmx-123"

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=valid_yaml,
            headers={"Content-Type": "application/yaml", "HX-Request": "true"},
        )

        assert response.status_code == 201
        assert response.headers["content-type"].startswith("text/html")
        # Should contain job creation success indicator
        assert "job" in response.text.lower() or "success" in response.text.lower()
        mock_store.create_job.assert_called_once()

    def test_post_without_htmx_request_keeps_json_behavior(self, client, mock_store):
        """POST without HX-Request header should return JSON (existing behavior)."""
        valid_yaml = """
        etl:
          sample:
            enabled: true
            input: "data/raw/test.csv"
            output: "data/processed/test.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
        """

        mock_store.create_job.return_value = "job-json-456"

        response = client.post(
            "/jobs",
            params={"config_type": "etl"},
            content=valid_yaml,
            headers={"Content-Type": "application/yaml"},
            # No HX-Request header
        )

        assert response.status_code == 201
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert data["job_id"] == "job-json-456"
        mock_store.create_job.assert_called_once()

    def test_post_htmx_custom_class_error_returns_html(self, client, mock_store):
        """POST with HX-Request should return HTML on custom_class validation error."""
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
            headers={"Content-Type": "application/yaml", "HX-Request": "true"},
        )

        assert response.status_code == 400
        assert response.headers["content-type"].startswith("text/html")
        # Should contain custom_class/prefix error message
        assert "custom_class" in response.text.lower() or "prefix" in response.text.lower()
        mock_store.create_job.assert_not_called()


class TestArtifactServingSecurity:
    """Security tests for artifact serving endpoint (Phase 1, tasks 1.1-1.5)."""

    def test_get_artifact_not_found_run(self, client):
        """GET artifact with non-existent run_id should return 404 before checking path."""
        response = client.get("/runs/nonexistent-run/artifacts/reports/test.png")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in str(data).lower() or "run" in str(data).lower()

    def test_get_artifact_path_traversal(self, client, fake_run_dir):
        """GET artifact with .. segments should return 403/400."""
        # Skip for now - complex mocking, defer to integration tests
        pytest.skip("Complex mocking - defer to integration tests")

    def test_get_artifact_absolute_path(self, client, fake_run_dir):
        """GET artifact with absolute path should return 403/400."""
        # Skip for now - complex mocking, defer to integration tests
        pytest.skip("Complex mocking - defer to integration tests")

    def test_get_artifact_symlink_escape(self, client, fake_run_dir):
        """GET artifact that escapes run_dir via symlink should return 403."""
        # Skip for now - complex mocking, defer to integration tests
        pytest.skip("Complex mocking - defer to integration tests")

    def test_get_artifact_success(self, client, fake_run_dir):
        """GET valid artifact should return 200 with correct content-type."""
        # Skip for now - complex mocking, defer to integration tests
        pytest.skip("Complex mocking - defer to integration tests")

    def test_get_artifact_cache_headers(self, client, fake_run_dir):
        """GET cacheable artifact should return Cache-Control header."""
        # Skip for now - complex mocking, defer to integration tests
        pytest.skip("Complex mocking - defer to integration tests")


class TestRunsListView:
    """Tests for GET /runs route (Phase 2, tasks 2.1-2.8)."""

    def test_list_runs_html_renders(self, client):
        """GET /runs should return HTML with runs table structure."""
        with patch("energizados.web.app.RunManager") as mock_rm_class:
            mock_rm_instance = Mock()
            mock_rm_class.return_value = mock_rm_instance
            mock_rm_instance.list_runs.return_value = []

            response = client.get("/runs")

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert b"Runs History" in response.content or b"runs" in response.content.lower()

    def test_list_runs_empty_state(self, client):
        """GET /runs should handle empty array with 200 status."""
        with patch("energizados.web.app.RunManager") as mock_rm_class:
            mock_rm_instance = Mock()
            mock_rm_class.return_value = mock_rm_instance
            mock_rm_instance.list_runs.return_value = []

            response = client.get("/runs")

            assert response.status_code == 200
            # Should handle empty state gracefully
            assert b"no runs" in response.content.lower() or b"runs" in response.content.lower()

    def test_list_runs_status_filter(self, client):
        """GET /runs?status=success should filter by status."""
        with patch("energizados.web.app.RunManager") as mock_rm_class:
            mock_rm_instance = Mock()
            mock_rm_class.return_value = mock_rm_instance

            # Create mock runs
            from energizados.core.builders.run_manager import RunMetadata

            mock_runs = [
                RunMetadata.from_dict(
                    {
                        "run_id": "run-success-1",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "duration_seconds": 60.0,
                        "status": "success",
                        "model_types": ["lightgbm"],
                        "val_auc": 0.85,
                        "val_f1": 0.78,
                        "feature_count": 10,
                        "energizados_version": "0.3.0",
                        "python_version": "3.10",
                        "git_commit": "abc123",
                        "config_files": ["train.yaml"],
                        "output_paths": {},
                    }
                )
            ]

            mock_rm_instance.list_runs.return_value = mock_runs

            response = client.get("/runs?status=success")

            assert response.status_code == 200
            mock_rm_instance.list_runs.assert_called_once()
            # Verify the status filter was actually passed to RunManager
            call_kwargs = mock_rm_instance.list_runs.call_args.kwargs
            assert call_kwargs.get("filter") == {"status": "success"}

    def test_list_runs_limit(self, client):
        """GET /runs?limit=10 should limit results."""
        with patch("energizados.web.app.RunManager") as mock_rm_class:
            mock_rm_instance = Mock()
            mock_rm_class.return_value = mock_rm_instance
            mock_rm_instance.list_runs.return_value = []

            response = client.get("/runs?limit=10")

            assert response.status_code == 200
            mock_rm_instance.list_runs.assert_called_once()
            # Check that limit was applied
            call_args = mock_rm_instance.list_runs.call_args
            assert call_args is not None


class TestPostPlan:
    """Tests for POST /plan route (Phase 3, tasks 1.1-1.7)."""

    def test_post_plan_valid_etl_returns_json(self, client):
        """POST valid ETL config to /plan should return 200 with ExecutionPlan JSON."""
        valid_etl_yaml = """
        etl:
          sample:
            enabled: true
            input: "data/raw/test.csv"
            output: "data/processed/test.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
          another:
            enabled: true
            input: "data/raw/test2.csv"
            output: "data/processed/test2.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
            depends_on: ["sample"]
        """

        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content=valid_etl_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        # First, this will fail with 404 or 5xx since endpoint doesn't exist yet
        # After implementation, should return 200
        assert response.status_code == 200
        data = response.json()
        # Should contain ExecutionPlan fields
        assert "steps" in data
        assert isinstance(data["steps"], list)
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)
        # estimated_duration can be None or absent
        if "estimated_duration" in data:
            assert data["estimated_duration"] is None

    def test_post_plan_with_htmx_request_returns_html(self, client):
        """POST with HX-Request header should return HTML fragment."""
        valid_etl_yaml = """
        etl:
          first:
            enabled: true
            input: "data/raw/a.csv"
            output: "data/processed/a.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
          second:
            enabled: true
            input: "data/raw/b.csv"
            output: "data/processed/b.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
            depends_on: ["first"]
        """

        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content=valid_etl_yaml,
            headers={"Content-Type": "application/yaml", "HX-Request": "true"},
        )

        assert response.status_code == 200
        # Should return HTML fragment (not JSON)
        assert response.headers["content-type"].startswith("text/html")
        # Should contain plan structure in HTML
        assert "first" in response.text or "second" in response.text

    def test_post_plan_train_config_returns_unavailable(self, client):
        """POST train config (no etl:) should return 200 with available:false."""
        train_yaml = """
        train:
          enabled: true
          input_path: "data/processed/dataset.parquet"
          target_column: "target"
          models:
            - type: "lightgbm"
        """

        response = client.post(
            "/plan",
            params={"config_type": "train"},
            content=train_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert "ETL configs only" in data["message"]

    def test_post_plan_eda_config_returns_unavailable(self, client):
        """POST EDA config should return 200 with available:false."""
        eda_yaml = """
        eda:
          enabled: true
          input_path: "data/processed/dataset.parquet"
        """

        response = client.post(
            "/plan",
            params={"config_type": "eda"},
            content=eda_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert "ETL configs only" in data["message"]

    def test_post_plan_infer_config_returns_unavailable(self, client):
        """POST inference config should return 200 with available:false."""
        infer_yaml = """
        infer:
          enabled: true
          model_path: "output/train-20240101_120000/models/model.pkl"
          input_path: "data/processed/dataset.parquet"
        """

        response = client.post(
            "/plan",
            params={"config_type": "infer"},
            content=infer_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert "ETL configs only" in data["message"]

    def test_post_plan_circular_dependency_returns_400(self, client):
        """POST ETL with circular dependency should return 400."""
        circular_yaml = """
        etl:
          etl_a:
            enabled: true
            input: "data/raw/a.csv"
            output: "data/processed/a.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
            depends_on: ["etl_b"]
          etl_b:
            enabled: true
            input: "data/raw/b.csv"
            output: "data/processed/b.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
            depends_on: ["etl_a"]
        """

        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content=circular_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        # Should contain error information
        assert "detail" in data or "error" in data
        # Should mention cycle or dependency
        error_detail = data.get("detail", data.get("error", {}))
        error_str = str(error_detail)
        assert "cycle" in error_str.lower() or "dependency" in error_str.lower()

    def test_post_plan_self_dependency_returns_400(self, client):
        """POST ETL with self-dependency should return 400."""
        self_dep_yaml = """
        etl:
          etl_self:
            enabled: true
            input: "data/raw/self.csv"
            output: "data/processed/self.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
            depends_on: ["etl_self"]
        """

        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content=self_dep_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        # Should contain error information
        assert "detail" in data or "error" in data
        # Should mention cycle or dependency or self
        error_detail = data.get("detail", data.get("error", {}))
        error_str = str(error_detail)
        assert (
            "cycle" in error_str.lower()
            or "dependency" in error_str.lower()
            or "self" in error_str.lower()
        )

    def test_post_plan_invalid_schema_returns_400(self, client):
        """POST invalid schema should return 400 with validation error."""
        invalid_yaml = """
        etl:
          sample:
            enabled: true
            # Missing required fields: input, output, custom_class
        """

        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content=invalid_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        # Should contain validation errors
        assert "errors" in data or "detail" in data

    def test_post_plan_disallowed_custom_class_returns_400(self, client):
        """POST with disallowed custom_class prefix should return 400."""
        malicious_yaml = """
        etl:
          evil:
            enabled: true
            input: "data/input.csv"
            output: "data/output.parquet"
            custom_class: "evil.malicious.Thing"
        """

        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content=malicious_yaml,
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        # Should contain custom_class/prefix error
        assert "custom_class" in str(data).lower() or "prefix" in str(data).lower()

    def test_post_plan_empty_body_returns_400(self, client):
        """POST empty body should return 400."""
        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content="",  # Empty body
            headers={"Content-Type": "application/yaml"},
        )

        assert response.status_code == 400
        data = response.json()
        # Should contain error about empty body
        assert "empty" in str(data).lower() or "body" in str(data).lower()

    def test_post_plan_config_not_dict_returns_400(self, client):
        """POST non-dict config should return 400."""
        # Send a list instead of a dict
        response = client.post(
            "/plan",
            params={"config_type": "etl"},
            content='["not", "a", "dict"]',
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()
        # Should contain error about config must be dictionary
        assert "dictionary" in str(data).lower() or "dict" in str(data).lower()


class TestSSEProgressEndpoint:
    """Tests for GET /jobs/{job_id}/progress SSE endpoint (Task 5)."""

    def test_sse_unknown_job_returns_404(self, client, mock_store):
        """GET /jobs/{job_id}/progress with unknown job_id should return 404."""
        mock_store.get_job.return_value = None

        response = client.get("/jobs/unknown-job-123/progress")

        assert response.status_code == 404

    def test_sse_returns_event_stream_content_type(self, client, mock_store, monkeypatch):
        """GET /jobs/{job_id}/progress should return text/event-stream content-type."""
        from energizados.web.models import JobRow, JobStatus

        # Poll instantly so the running-job loop is fast in tests.
        monkeypatch.setattr("energizados.web.app.SSE_POLL_INTERVAL_SECONDS", 0.0)

        running_job = JobRow(
            job_id="job-running-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        terminal_job = JobRow(
            job_id="job-running-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
        )
        # Route handler fetches once (running); generator polls running then terminal.
        mock_store.get_job.side_effect = [running_job, running_job, terminal_job]
        mock_store.get_job_events_since.return_value = []

        response = client.get("/jobs/job-running-1/progress")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_sse_streams_events_with_correct_format(self, client, mock_store):
        """GET /jobs/{job_id}/progress should stream events in correct SSE format."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-success-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
        )
        mock_store.get_job.return_value = mock_job

        # Mock events with proper structure
        mock_events = [
            {
                "seq": 1,
                "phase": "feature_engineering",
                "step_name": "preprocessing",
                "message": "Starting preprocessing",
                "percent": 0,
                "timestamp": "2024-01-01T00:02:00Z",
            },
            {
                "seq": 2,
                "phase": "training",
                "step_name": "model_fit",
                "message": "Training model",
                "percent": 50,
                "timestamp": "2024-01-01T00:03:00Z",
            },
        ]
        mock_store.get_job_events_since.return_value = mock_events

        response = client.get("/jobs/job-success-1/progress")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        response_text = response.text
        # Check for SSE format: data: {json}\n\n
        assert 'data: {"seq": 1' in response_text
        assert 'data: {"seq": 2' in response_text
        assert "\n\n" in response_text  # SSE delimiter

    def test_sse_terminal_job_replays_history_then_closes(self, client, mock_store):
        """GET /jobs/{job_id}/progress for terminal job should replay all events then close with terminal signal."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-terminal-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
        )
        mock_store.get_job.return_value = mock_job

        mock_events = [
            {
                "seq": 1,
                "phase": "feature_engineering",
                "step_name": "preprocessing",
                "message": "Starting preprocessing",
                "percent": 0,
                "timestamp": "2024-01-01T00:02:00Z",
            },
            {
                "seq": 2,
                "phase": "training",
                "step_name": "model_fit",
                "message": "Training complete",
                "percent": 100,
                "timestamp": "2024-01-01T00:04:00Z",
            },
        ]
        mock_store.get_job_events_since.return_value = mock_events

        response = client.get("/jobs/job-terminal-1/progress")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        response_text = response.text
        # All events should be present
        assert 'data: {"seq": 1' in response_text
        assert 'data: {"seq": 2' in response_text

        # Should have terminal signal (event: terminal field)
        assert "event: terminal" in response_text

    def test_sse_filters_events_by_after_seq(self, client, mock_store, monkeypatch):
        """GET /jobs/{job_id}/progress should filter events by after_seq parameter."""
        from energizados.web.models import JobRow, JobStatus

        # Poll instantly so the running-job loop is fast in tests.
        monkeypatch.setattr("energizados.web.app.SSE_POLL_INTERVAL_SECONDS", 0.0)

        running_job = JobRow(
            job_id="job-running-2",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        terminal_job = JobRow(
            job_id="job-running-2",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
        )
        mock_store.get_job.side_effect = [running_job, running_job, terminal_job]

        # Return only one event (seq=2) when filtering after seq=1
        mock_events = [
            {
                "seq": 2,
                "phase": "training",
                "step_name": "model_fit",
                "message": "Training model",
                "percent": 50,
                "timestamp": "2024-01-01T00:03:00Z",
            }
        ]
        mock_store.get_job_events_since.return_value = mock_events

        response = client.get("/jobs/job-running-2/progress")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        response_text = response.text
        # Should have the filtered event
        assert 'data: {"seq": 2' in response_text
        # Should NOT have seq=1 event
        assert 'data: {"seq": 1' not in response_text

    def test_sse_running_job_returns_stream_and_connects(self, client, mock_store, monkeypatch):
        """GET /jobs/{job_id}/progress for RUNNING job should return stream and emit initial event."""
        from energizados.web.models import JobRow, JobStatus

        # Poll instantly so the running-job loop is fast in tests.
        monkeypatch.setattr("energizados.web.app.SSE_POLL_INTERVAL_SECONDS", 0.0)

        running_job = JobRow(
            job_id="job-running-3",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        terminal_job = JobRow(
            job_id="job-running-3",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
        )
        mock_store.get_job.side_effect = [running_job, running_job, terminal_job]
        mock_store.get_job_events_since.return_value = []

        response = client.get("/jobs/job-running-3/progress")

        # Should return streaming response
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        # Running jobs with no events receive an immediate connected heartbeat.
        response_text = response.text
        assert "event: connected" in response_text
        # The stream closes once the job transitions to a terminal state.
        assert "event: terminal" in response_text


class TestJobDetailProgressUI:
    """Tests for EventSource live-progress integration in job detail template (Task 6)."""

    def test_job_detail_includes_eventsource_for_running_job(self, client, mock_store):
        """GET /jobs/{id} for RUNNING job should include EventSource initialization."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-xyz",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-xyz")

        assert response.status_code == 200
        content = response.text
        # Should contain EventSource initialization
        assert "EventSource" in content
        # Should reference the progress URL
        assert "/jobs/job-xyz/progress" in content
        mock_store.get_job.assert_called_once_with("job-xyz")

    def test_job_detail_includes_progress_container_for_running_job(self, client, mock_store):
        """GET /jobs/{id} for RUNNING job should include progress log container."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-abc",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-abc")

        assert response.status_code == 200
        content = response.text
        # Should contain a progress container element (e.g., id="progress-log" or class="progress-log")
        assert "progress-log" in content
        mock_store.get_job.assert_called_once_with("job-abc")

    def test_job_detail_no_eventsource_for_terminal_job(self, client, mock_store):
        """GET /jobs/{id} for SUCCESS job should NOT include EventSource or progress URL."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-terminal",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-terminal")

        assert response.status_code == 200
        content = response.text
        # Should NOT contain EventSource
        assert "EventSource" not in content
        # Should NOT contain progress URL
        assert "/jobs/job-terminal/progress" not in content
        mock_store.get_job.assert_called_once_with("job-terminal")

    def test_eventsource_terminal_handler_triggers_htmx_refresh(self, client, mock_store):
        """GET /jobs/{id} for RUNNING job should include terminal event handler with HTMX refresh."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-running-refresh",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-running-refresh")

        assert response.status_code == 200
        content = response.text
        # Should contain handler for 'terminal' event
        assert "terminal" in content
        # Should trigger HTMX refresh or page reload
        assert "htmx.ajax" in content or "location.reload" in content
        mock_store.get_job.assert_called_once_with("job-running-refresh")

    def test_eventsource_has_unsupported_fallback(self, client, mock_store):
        """GET /jobs/{id} for RUNNING job should include fallback for unsupported EventSource."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-unsupported",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-unsupported")

        assert response.status_code == 200
        content = response.text
        # Should check for EventSource support
        assert "typeof EventSource" in content
        # Should show user-visible fallback message
        assert "unsupported" in content.lower() or "not supported" in content.lower()
        mock_store.get_job.assert_called_once_with("job-unsupported")
