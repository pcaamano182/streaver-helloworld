/**
 * K6 Load Testing Script for Streaver Hello World Application
 *
 * This script performs load testing on the deployed application with three stages:
 * 1. Ramp-up: Gradually increase load from 0 to 100 users over 2 minutes
 * 2. Steady: Maintain 100 users for 5 minutes
 * 3. Ramp-down: Decrease load from 100 to 0 over 1 minute
 *
 * Usage:
 *   k6 run tests/load/k6-load-test.js
 *   k6 run --env TARGET_URL=http://your-alb-dns tests/load/k6-load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp-up to 100 users over 2 minutes
    { duration: '5m', target: 100 },  // Stay at 100 users for 5 minutes
    { duration: '1m', target: 0 },    // Ramp-down to 0 users over 1 minute
  ],
  thresholds: {
    // 95% of requests should complete below 500ms
    'http_req_duration': ['p(95)<500'],
    // 99% of requests should complete below 1000ms
    'http_req_duration{type:home}': ['p(99)<1000'],
    // Error rate should be less than 1%
    'errors': ['rate<0.01'],
    // Request success rate should be above 99%
    'http_req_failed': ['rate<0.01'],
  },
  ext: {
    loadimpact: {
      projectID: 3558191,
      name: 'Streaver Hello World Load Test'
    }
  }
};

// Get target URL from environment variable or use default
const TARGET_URL = __ENV.TARGET_URL || 'http://localhost:5000';

export default function () {
  // Test 1: Home endpoint
  let homeResponse = http.get(`${TARGET_URL}/`, {
    tags: { type: 'home' },
  });

  check(homeResponse, {
    'home status is 200': (r) => r.status === 200,
    'home has correct content type': (r) => r.headers['Content-Type'].includes('application/json'),
    'home response time < 500ms': (r) => r.timings.duration < 500,
    'home contains message': (r) => r.json('message') !== undefined,
    'home contains service name': (r) => r.json('service') === 'streaver-helloworld',
  }) || errorRate.add(1);

  sleep(1);

  // Test 2: Health check endpoint
  let healthResponse = http.get(`${TARGET_URL}/health`, {
    tags: { type: 'health' },
  });

  check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
    'health response time < 200ms': (r) => r.timings.duration < 200,
    'health status is healthy': (r) => r.json('status') === 'healthy',
    'health has timestamp': (r) => r.json('timestamp') !== undefined,
  }) || errorRate.add(1);

  sleep(1);

  // Test 3: Metrics endpoint
  let metricsResponse = http.get(`${TARGET_URL}/metrics`, {
    tags: { type: 'metrics' },
  });

  check(metricsResponse, {
    'metrics status is 200': (r) => r.status === 200,
    'metrics has uptime': (r) => r.json('uptime_seconds') !== undefined,
    'metrics has counters': (r) => r.json('metrics.total_requests') !== undefined,
    'metrics response time < 300ms': (r) => r.timings.duration < 300,
  }) || errorRate.add(1);

  sleep(1);

  // Test 4: Error endpoint (should return 500)
  let errorResponse = http.get(`${TARGET_URL}/error`, {
    tags: { type: 'error' },
  });

  check(errorResponse, {
    'error status is 500': (r) => r.status === 500,
    'error has error field': (r) => r.json('error') !== undefined,
    'error has descriptive message': (r) => r.json('message').includes('intentional'),
  });
  // Note: We don't add to errorRate for intentional 500s

  sleep(2);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: '  ', enableColors: true }),
    'tests/load/k6-results.json': JSON.stringify(data),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const colors = options.enableColors;

  let summary = '\n' + indent + '=== Load Test Summary ===\n\n';

  // Test duration
  summary += indent + `Duration: ${data.state.testRunDurationMs / 1000}s\n`;

  // HTTP requests
  const requests = data.metrics.http_reqs;
  summary += indent + `Total Requests: ${requests.values.count}\n`;
  summary += indent + `Requests/sec: ${requests.values.rate.toFixed(2)}\n\n`;

  // Response times
  const duration = data.metrics.http_req_duration;
  summary += indent + 'Response Times:\n';
  summary += indent + `  Average: ${duration.values.avg.toFixed(2)}ms\n`;
  summary += indent + `  Median: ${duration.values.med.toFixed(2)}ms\n`;
  summary += indent + `  p95: ${duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += indent + `  p99: ${duration.values['p(99)'].toFixed(2)}ms\n`;
  summary += indent + `  Max: ${duration.values.max.toFixed(2)}ms\n\n`;

  // Success rate
  const failed = data.metrics.http_req_failed;
  const successRate = (1 - failed.values.rate) * 100;
  summary += indent + `Success Rate: ${successRate.toFixed(2)}%\n`;

  // Custom error rate
  if (data.metrics.errors) {
    const errorRate = data.metrics.errors.values.rate * 100;
    summary += indent + `Error Rate: ${errorRate.toFixed(2)}%\n`;
  }

  summary += '\n';

  return summary;
}
