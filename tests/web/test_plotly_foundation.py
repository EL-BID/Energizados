"""
Tests for Plotly foundation in web console.

Phase 4 Task 1-2: Ensure Plotly CDN is available for dashboard charts.
Following strict TDD: RED test first, then GREEN implementation.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from energizados.web.app import app

    return TestClient(app)


class TestPlotlyFoundation:
    """Test suite for Plotly.js foundation in base template."""

    def test_base_template_includes_plotly_cdn(self, client):
        """GET / should render base.html with Plotly CDN script tag."""
        response = client.get("/")
        assert response.status_code == 200
        # Check for Plotly CDN in the HTML response
        assert "plotly-2.27.0.min.js" in response.text
        assert "<script" in response.text and "plotly" in response.text.lower()
