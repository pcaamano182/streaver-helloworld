"""
Integration tests for Streaver Hello World Flask application.

These tests validate the application against a deployed environment.
When running locally without a deployed environment, tests will be skipped.
"""

import pytest
import requests
import os
from datetime import datetime

# Check if integration tests should run
# Set INTEGRATION_TEST_URL environment variable to the deployed app URL
INTEGRATION_TEST_URL = os.getenv("INTEGRATION_TEST_URL", None)

# Skip all integration tests if no URL is provided
pytestmark = pytest.mark.skipif(
    INTEGRATION_TEST_URL is None,
    reason="Integration tests require INTEGRATION_TEST_URL environment variable",
)


@pytest.fixture
def base_url():
    """Return the base URL for integration tests."""
    return INTEGRATION_TEST_URL.rstrip("/")


class TestIntegrationHomeEndpoint:
    """Integration tests for the home endpoint."""

    def test_home_endpoint_accessible(self, base_url):
        """Test that home endpoint is accessible over HTTP."""
        response = requests.get(f"{base_url}/", timeout=10)
        assert response.status_code == 200

    def test_home_endpoint_returns_json(self, base_url):
        """Test that home endpoint returns JSON content."""
        response = requests.get(f"{base_url}/", timeout=10)
        assert response.headers["Content-Type"] == "application/json"
        data = response.json()
        assert isinstance(data, dict)

    def test_home_endpoint_has_expected_structure(self, base_url):
        """Test that home endpoint has expected response structure."""
        response = requests.get(f"{base_url}/", timeout=10)
        data = response.json()
        assert "message" in data
        assert "service" in data
        assert "version" in data
        assert "timestamp" in data
        assert "endpoints" in data


class TestIntegrationHealthEndpoint:
    """Integration tests for the health check endpoint."""

    def test_health_endpoint_accessible(self, base_url):
        """Test that health endpoint is accessible."""
        response = requests.get(f"{base_url}/health", timeout=10)
        assert response.status_code == 200

    def test_health_endpoint_returns_healthy_status(self, base_url):
        """Test that health endpoint returns healthy status."""
        response = requests.get(f"{base_url}/health", timeout=10)
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint_has_timestamp(self, base_url):
        """Test that health endpoint returns timestamp."""
        response = requests.get(f"{base_url}/health", timeout=10)
        data = response.json()
        assert "timestamp" in data
        # Validate timestamp is recent (within last minute)
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        now = datetime.utcnow()
        diff = (now - timestamp.replace(tzinfo=None)).total_seconds()
        assert abs(diff) < 60  # Within 1 minute

    def test_health_endpoint_response_time(self, base_url):
        """Test that health endpoint responds quickly."""
        response = requests.get(f"{base_url}/health", timeout=10)
        # Health check should respond in less than 1 second
        assert response.elapsed.total_seconds() < 1.0


class TestIntegrationErrorEndpoint:
    """Integration tests for the error endpoint."""

    def test_error_endpoint_returns_500(self, base_url):
        """Test that error endpoint returns 500 status code."""
        response = requests.get(f"{base_url}/error", timeout=10)
        assert response.status_code == 500

    def test_error_endpoint_returns_json(self, base_url):
        """Test that error endpoint returns JSON."""
        response = requests.get(f"{base_url}/error", timeout=10)
        assert response.headers["Content-Type"] == "application/json"
        data = response.json()
        assert "error" in data

    def test_error_endpoint_has_descriptive_message(self, base_url):
        """Test that error endpoint has descriptive error message."""
        response = requests.get(f"{base_url}/error", timeout=10)
        data = response.json()
        assert "message" in data
        assert "intentional" in data["message"].lower()


class TestIntegrationMetricsEndpoint:
    """Integration tests for the metrics endpoint."""

    def test_metrics_endpoint_accessible(self, base_url):
        """Test that metrics endpoint is accessible."""
        response = requests.get(f"{base_url}/metrics", timeout=10)
        assert response.status_code == 200

    def test_metrics_endpoint_returns_metrics(self, base_url):
        """Test that metrics endpoint returns metrics data."""
        response = requests.get(f"{base_url}/metrics", timeout=10)
        data = response.json()
        assert "metrics" in data
        metrics = data["metrics"]
        assert "total_requests" in metrics
        assert "successful_requests" in metrics
        assert "error_requests" in metrics

    def test_metrics_increment_after_requests(self, base_url):
        """Test that metrics increment after making requests."""
        # Get initial metrics
        response1 = requests.get(f"{base_url}/metrics", timeout=10)
        data1 = response1.json()
        initial_total = data1["metrics"]["total_requests"]

        # Make some requests
        requests.get(f"{base_url}/", timeout=10)
        requests.get(f"{base_url}/health", timeout=10)

        # Get metrics again
        response2 = requests.get(f"{base_url}/metrics", timeout=10)
        data2 = response2.json()
        new_total = data2["metrics"]["total_requests"]

        # Total should have increased
        assert new_total > initial_total

    def test_metrics_uptime_is_positive(self, base_url):
        """Test that uptime is a positive number."""
        response = requests.get(f"{base_url}/metrics", timeout=10)
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] > 0


class TestIntegrationLoadBalancer:
    """Integration tests for load balancer behavior."""

    def test_multiple_requests_succeed(self, base_url):
        """Test that multiple requests succeed (basic load test)."""
        for _ in range(10):
            response = requests.get(f"{base_url}/", timeout=10)
            assert response.status_code == 200

    def test_concurrent_requests_handling(self, base_url):
        """Test that service handles concurrent requests."""
        import concurrent.futures

        def make_request():
            response = requests.get(f"{base_url}/health", timeout=10)
            return response.status_code

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All requests should succeed
        assert all(status == 200 for status in results)


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""

    def test_full_workflow(self, base_url):
        """Test complete workflow through all endpoints."""
        # 1. Check home page
        response = requests.get(f"{base_url}/", timeout=10)
        assert response.status_code == 200

        # 2. Check health
        response = requests.get(f"{base_url}/health", timeout=10)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # 3. Trigger error endpoint
        response = requests.get(f"{base_url}/error", timeout=10)
        assert response.status_code == 500

        # 4. Check metrics reflect the error
        response = requests.get(f"{base_url}/metrics", timeout=10)
        data = response.json()
        assert data["metrics"]["error_requests"] > 0
        assert data["metrics"]["error_rate_percentage"] > 0


if __name__ == "__main__":
    if INTEGRATION_TEST_URL:
        print(f"Running integration tests against: {INTEGRATION_TEST_URL}")
        pytest.main([__file__, "-v"])
    else:
        print("Skipping integration tests: INTEGRATION_TEST_URL not set")
        print("Set INTEGRATION_TEST_URL environment variable to run integration tests")
