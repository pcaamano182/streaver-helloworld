"""
Flask application for Streaver DevOps Challenge.

This application provides a simple HTTP service with health checks,
intentional error endpoints for testing observability, and basic metrics.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
import signal

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Helper class for structured JSON logging."""

    @staticmethod
    def log(level: str, message: str, **kwargs) -> None:
        """Log structured JSON messages."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "message": message,
            "service": "streaver-helloworld",
            **kwargs,
        }
        logger.info(json.dumps(log_entry))


# Initialize Flask app
app = Flask(__name__)

# Metrics storage (in-memory for simplicity)
metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "error_requests": 0,
    "health_checks": 0,
    "start_time": datetime.now(timezone.utc),
}


@app.before_request
def before_request():
    """Log incoming requests and track metrics."""
    metrics["total_requests"] += 1
    request.start_time = datetime.now(timezone.utc)

    StructuredLogger.log(
        "info",
        "Incoming request",
        method=request.method,
        path=request.path,
        remote_addr=request.remote_addr,
        user_agent=str(request.user_agent),
    )


@app.after_request
def after_request(response):
    """Log response and track metrics."""
    if hasattr(request, "start_time"):
        duration = (
            datetime.now(timezone.utc) - request.start_time
        ).total_seconds() * 1000

        if response.status_code < 400:
            metrics["successful_requests"] += 1
        elif response.status_code >= 500:
            metrics["error_requests"] += 1

        StructuredLogger.log(
            "info",
            "Request completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=round(duration, 2),
        )

    return response


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all exceptions with structured logging."""
    if isinstance(e, HTTPException):
        StructuredLogger.log(
            "warning", "HTTP exception", error=str(e), status_code=e.code
        )
        return jsonify(
            {"error": e.name, "message": e.description, "status_code": e.code}
        ), e.code

    StructuredLogger.log(
        "error", "Unhandled exception", error=str(e), error_type=type(e).__name__
    )

    return jsonify(
        {
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "status_code": 500,
        }
    ), 500


@app.route("/", methods=["GET"])
def home() -> tuple:
    """
    Home endpoint returning a welcome message.

    Returns:
        JSON response with welcome message and service info
    """
    return jsonify(
        {
            "message": "Hello World from Streaver Challenge!",
            "service": "streaver-helloworld",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoints": {
                "health": "/health",
                "error": "/error",
                "metrics": "/metrics",
            },
        }
    ), 200


@app.route("/health", methods=["GET"])
def health() -> tuple:
    """
    Health check endpoint for load balancer and monitoring.

    Returns:
        JSON response with health status
    """
    metrics["health_checks"] += 1

    health_status = {
        "status": "healthy",
        "service": "streaver-helloworld",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_since": metrics["start_time"].isoformat(),
    }

    return jsonify(health_status), 200


@app.route("/error", methods=["GET"])
def intentional_error() -> tuple:
    """
    Intentional error endpoint for testing observability and alerting.

    This endpoint always returns a 500 error to validate monitoring
    and alerting systems.

    Returns:
        JSON response with error details and 500 status code
    """
    StructuredLogger.log(
        "error",
        "Intentional error endpoint triggered",
        endpoint="/error",
        purpose="testing_observability",
    )

    return jsonify(
        {
            "error": "Internal Server Error",
            "message": "This is an intentional error for testing observability and alerting systems",
            "status_code": 500,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ), 500


@app.route("/metrics", methods=["GET"])
def get_metrics() -> tuple:
    """
    Metrics endpoint exposing basic application metrics.

    Returns:
        JSON response with application metrics
    """
    current_time = datetime.now(timezone.utc)
    start_time = metrics["start_time"]
    uptime_seconds = (current_time - start_time).total_seconds()

    error_rate = 0.0
    if metrics["total_requests"] > 0:
        error_rate = (metrics["error_requests"] / metrics["total_requests"]) * 100

    return jsonify(
        {
            "service": "streaver-helloworld",
            "timestamp": current_time.isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "metrics": {
                "total_requests": metrics["total_requests"],
                "successful_requests": metrics["successful_requests"],
                "error_requests": metrics["error_requests"],
                "health_checks": metrics["health_checks"],
                "error_rate_percentage": round(error_rate, 2),
            },
        }
    ), 200


def graceful_shutdown(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    StructuredLogger.log(
        "info", "Received shutdown signal, gracefully shutting down", signal=signum
    )
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)


if __name__ == "__main__":
    StructuredLogger.log(
        "info", "Starting Streaver Hello World application", port=5000, debug=False
    )

    # Run with production WSGI server would be preferred (gunicorn/waitress)
    # For simplicity in this challenge, using Flask's built-in server
    app.run(host="0.0.0.0", port=5000, debug=False)
