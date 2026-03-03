/**
 * K6 Smoke Testing Script for Streaver Hello World Application
 *
 * This is a lightweight smoke test with minimal load to verify basic functionality.
 * Ideal for quick validation after deployment.
 *
 * Usage:
 *   k6 run tests/load/k6-smoke-test.js
 *   k6 run --env TARGET_URL=http://your-alb-dns tests/load/k6-smoke-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,           // 5 virtual users
  duration: '1m',   // Run for 1 minute
  thresholds: {
    'http_req_duration': ['p(95)<1000'],  // 95% of requests under 1s
    'http_req_failed': ['rate<0.05'],     // Less than 5% failure rate
  },
};

const TARGET_URL = __ENV.TARGET_URL || 'http://localhost:5000';

export default function () {
  // Test all endpoints
  const endpoints = [
    { name: 'home', path: '/', expectedStatus: 200 },
    { name: 'health', path: '/health', expectedStatus: 200 },
    { name: 'metrics', path: '/metrics', expectedStatus: 200 },
    { name: 'error', path: '/error', expectedStatus: 500 },
  ];

  endpoints.forEach(endpoint => {
    const response = http.get(`${TARGET_URL}${endpoint.path}`);

    check(response, {
      [`${endpoint.name} status is ${endpoint.expectedStatus}`]: (r) => r.status === endpoint.expectedStatus,
      [`${endpoint.name} responds in time`]: (r) => r.timings.duration < 1000,
    });

    sleep(0.5);
  });
}
