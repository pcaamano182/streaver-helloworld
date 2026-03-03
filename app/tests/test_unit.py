"""
Unit tests for Streaver Hello World Flask application.

Tests cover all endpoints and core functionality.
"""

import pytest
import json
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app, metrics


@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        # Reset metrics before each test
        metrics["total_requests"] = 0
        metrics["successful_requests"] = 0
        metrics["error_requests"] = 0
        metrics["health_checks"] = 0
        yield client


class TestHomeEndpoint:
    """Tests for the home endpoint (/)."""

    def test_home_returns_200(self, client):
        """Test that home endpoint returns 200 status code."""
        response = client.get('/')
        assert response.status_code == 200

    def test_home_returns_json(self, client):
        """Test that home endpoint returns valid JSON."""
        response = client.get('/')
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_home_contains_message(self, client):
        """Test that home endpoint contains welcome message."""
        response = client.get('/')
        data = json.loads(response.data)
        assert 'message' in data
        assert 'Streaver Challenge' in data['message']

    def test_home_contains_service_info(self, client):
        """Test that home endpoint contains service information."""
        response = client.get('/')
        data = json.loads(response.data)
        assert data['service'] == 'streaver-helloworld'
        assert 'version' in data
        assert 'timestamp' in data

    def test_home_contains_endpoints_info(self, client):
        """Test that home endpoint lists available endpoints."""
        response = client.get('/')
        data = json.loads(response.data)
        assert 'endpoints' in data
        assert '/health' in data['endpoints']['health']
        assert '/error' in data['endpoints']['error']
        assert '/metrics' in data['endpoints']['metrics']


class TestHealthEndpoint:
    """Tests for the health check endpoint (/health)."""

    def test_health_returns_200(self, client):
        """Test that health endpoint returns 200 status code."""
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """Test that health endpoint returns valid JSON."""
        response = client.get('/health')
        assert response.content_type == 'application/json'

    def test_health_contains_status(self, client):
        """Test that health endpoint contains status field."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert data['status'] == 'healthy'

    def test_health_contains_service_name(self, client):
        """Test that health endpoint contains service name."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert data['service'] == 'streaver-helloworld'

    def test_health_contains_timestamp(self, client):
        """Test that health endpoint contains timestamp."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert 'timestamp' in data
        # Validate timestamp format
        timestamp = data['timestamp'].replace('Z', '+00:00')
        datetime.fromisoformat(timestamp)

    def test_health_increments_counter(self, client):
        """Test that health checks increment the counter."""
        initial_count = metrics['health_checks']
        client.get('/health')
        assert metrics['health_checks'] == initial_count + 1


class TestErrorEndpoint:
    """Tests for the intentional error endpoint (/error)."""

    def test_error_returns_500(self, client):
        """Test that error endpoint returns 500 status code."""
        response = client.get('/error')
        assert response.status_code == 500

    def test_error_returns_json(self, client):
        """Test that error endpoint returns valid JSON."""
        response = client.get('/error')
        assert response.content_type == 'application/json'

    def test_error_contains_error_field(self, client):
        """Test that error endpoint contains error field."""
        response = client.get('/error')
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Internal Server Error'

    def test_error_contains_message(self, client):
        """Test that error endpoint contains descriptive message."""
        response = client.get('/error')
        data = json.loads(response.data)
        assert 'message' in data
        assert 'intentional' in data['message'].lower()

    def test_error_contains_status_code(self, client):
        """Test that error endpoint includes status code in response."""
        response = client.get('/error')
        data = json.loads(response.data)
        assert data['status_code'] == 500

    def test_error_increments_error_counter(self, client):
        """Test that error endpoint increments error counter."""
        initial_errors = metrics['error_requests']
        client.get('/error')
        assert metrics['error_requests'] > initial_errors


class TestMetricsEndpoint:
    """Tests for the metrics endpoint (/metrics)."""

    def test_metrics_returns_200(self, client):
        """Test that metrics endpoint returns 200 status code."""
        response = client.get('/metrics')
        assert response.status_code == 200

    def test_metrics_returns_json(self, client):
        """Test that metrics endpoint returns valid JSON."""
        response = client.get('/metrics')
        assert response.content_type == 'application/json'

    def test_metrics_contains_service_name(self, client):
        """Test that metrics endpoint contains service name."""
        response = client.get('/metrics')
        data = json.loads(response.data)
        assert data['service'] == 'streaver-helloworld'

    def test_metrics_contains_uptime(self, client):
        """Test that metrics endpoint contains uptime."""
        response = client.get('/metrics')
        data = json.loads(response.data)
        assert 'uptime_seconds' in data
        assert data['uptime_seconds'] >= 0

    def test_metrics_contains_counters(self, client):
        """Test that metrics endpoint contains all counters."""
        response = client.get('/metrics')
        data = json.loads(response.data)
        assert 'metrics' in data
        metrics_data = data['metrics']
        assert 'total_requests' in metrics_data
        assert 'successful_requests' in metrics_data
        assert 'error_requests' in metrics_data
        assert 'health_checks' in metrics_data

    def test_metrics_contains_error_rate(self, client):
        """Test that metrics endpoint contains error rate."""
        response = client.get('/metrics')
        data = json.loads(response.data)
        assert 'error_rate_percentage' in data['metrics']

    def test_metrics_calculates_error_rate_correctly(self, client):
        """Test that error rate is calculated correctly."""
        # Make some requests
        client.get('/')
        client.get('/health')
        client.get('/error')

        response = client.get('/metrics')
        data = json.loads(response.data)

        total = data['metrics']['total_requests']
        errors = data['metrics']['error_requests']
        error_rate = data['metrics']['error_rate_percentage']

        expected_rate = (errors / total) * 100
        assert abs(error_rate - expected_rate) < 0.01  # Allow small floating point differences


class TestMetricsTracking:
    """Tests for metrics tracking functionality."""

    def test_total_requests_increments(self, client):
        """Test that total requests counter increments."""
        initial_count = metrics['total_requests']
        client.get('/')
        assert metrics['total_requests'] == initial_count + 1

    def test_successful_requests_increments(self, client):
        """Test that successful requests counter increments."""
        initial_count = metrics['successful_requests']
        client.get('/')
        assert metrics['successful_requests'] == initial_count + 1

    def test_error_requests_increments_on_5xx(self, client):
        """Test that error requests counter increments on 5xx errors."""
        initial_count = metrics['error_requests']
        client.get('/error')
        assert metrics['error_requests'] == initial_count + 1

    def test_metrics_tracking_across_multiple_requests(self, client):
        """Test metrics tracking across multiple requests."""
        initial_total = metrics['total_requests']

        # Make various requests
        client.get('/')
        client.get('/health')
        client.get('/error')
        client.get('/metrics')

        # Total should have increased by 4
        assert metrics['total_requests'] == initial_total + 4


class TestNotFoundEndpoint:
    """Tests for 404 handling."""

    def test_nonexistent_endpoint_returns_404(self, client):
        """Test that non-existent endpoints return 404."""
        response = client.get('/nonexistent')
        assert response.status_code == 404

    def test_404_returns_json(self, client):
        """Test that 404 responses return JSON."""
        response = client.get('/nonexistent')
        assert response.content_type == 'application/json'


class TestMethodNotAllowed:
    """Tests for method not allowed handling."""

    def test_post_to_get_endpoint_returns_405(self, client):
        """Test that POST to GET-only endpoint returns 405."""
        response = client.post('/')
        assert response.status_code == 405

    def test_put_to_get_endpoint_returns_405(self, client):
        """Test that PUT to GET-only endpoint returns 405."""
        response = client.put('/health')
        assert response.status_code == 405


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
