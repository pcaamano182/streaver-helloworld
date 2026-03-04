# Runbook: High Response Time (Latency)

**Alarm Name:** `StreaverHelloWorld-HighLatency-{environment}`
**Severity:** P2 (High)
**Auto-scaling:** CPU/memory scaling may help if resource-bound
**Last Updated:** 2026-03-03

---

## Overview

This runbook addresses situations where the p99 response time exceeds 1 second for 5+ minutes. High latency degrades user experience even when availability is 100%.

### Alarm Configuration

- **Metric:** `TargetResponseTime` (ALB Target Group)
- **Statistic:** p99 (99th percentile)
- **Threshold:** >1 second (1000ms)
- **Evaluation Period:** 2 datapoints within 5 minutes
- **Action:** SNS notification to on-call team

---

## Impact Assessment

### Latency SLA Matrix

| p99 Latency | User Experience | SLA Status | Action Required |
|-------------|-----------------|------------|-----------------|
| <500ms | Excellent | Within SLA | Normal |
| 500-1000ms | Good | Within SLA | Monitor |
| 1000-2000ms | Degraded | **SLA warning** | **Investigate** |
| >2000ms | Poor | **SLA breach** | **Act immediately** |

### Performance Targets by Environment

| Environment | Target p50 | Target p99 | Max Acceptable |
|-------------|-----------|-----------|----------------|
| dev | <100ms | <500ms | 1s |
| cert | <100ms | <500ms | 1s |
| prod | <50ms | <300ms | 1s |

---

## Triage (First 5 Minutes)

### Step 1: Confirm Current Latency

```bash
# Get current p99 latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum \
  --extended-statistics p50,p90,p99
```

### Step 2: Identify Slow Endpoints

```bash
# Query application logs for slow requests (>500ms)
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '30 minutes ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, method, duration_ms, status
    | filter duration_ms > 500
    | stats count(), avg(duration_ms), max(duration_ms) by path
    | sort avg desc'
```

### Step 3: Check Resource Utilization

```bash
# CPU and Memory (high utilization causes throttling)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum
```

---

## Investigation

### Likely Causes

#### 1. High Traffic Load

**Symptoms:**
- Latency correlates with request count
- CPU/Memory also elevated
- All endpoints affected equally

**Verification:**
```bash
# Compare request count vs latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

#### 2. CPU Throttling

**Symptoms:**
- CPU at or near 100%
- Latency spikes correlate with CPU spikes
- Auto-scaling may be lagging

**Mitigation:**
See [High CPU Utilization](./01-high-cpu-utilization.md) runbook.

#### 3. Slow External Dependency

**Symptoms:**
- Specific endpoint slow (e.g., `/data`)
- Other endpoints fast
- No CPU/memory pressure

**Common culprits:**
- Database query timeout
- External API latency
- DNS resolution delays
- Network issues to dependency

#### 4. Cold Start / JIT Warm-up

**Symptoms:**
- High latency on first request after task start
- Improves over time
- Occurs after deployments

**Verification:**
```bash
# Check task age
aws ecs describe-tasks \
  --cluster streaver-cluster-{env} \
  --tasks $(aws ecs list-tasks --cluster streaver-cluster-{env} --service-name streaver-service-{env} --query 'taskArns' --output text) \
  --query 'tasks[*].[taskArn,createdAt,lastStatus]' \
  --output table
```

#### 5. Inefficient Code Path

**Symptoms:**
- Specific endpoint always slow
- Not correlated with traffic
- Reproducible

**Examples:**
- N+1 query problem
- Missing database index
- Inefficient algorithm (O(n²))
- Large JSON serialization

---

## Immediate Mitigation

### Option 1: Scale Out (if resource-bound)

```bash
# Increase task count to distribute load
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count $(($(aws ecs describe-services --cluster streaver-cluster-{env} --services streaver-service-{env} --query 'services[0].desiredCount' --output text) + 2))
```

### Option 2: Increase Task Resources

```yaml
# infrastructure/cdk/config/{env}.yaml
ecs:
  task:
    cpu: 1024     # Increase from 512
    memory: 2048  # Increase from 1024

# Deploy:
cd infrastructure/cdk
cdk deploy StreaverHelloWorldEcs-{env} -c environment={env}
```

### Option 3: Add Response Caching

```python
# app/main.py - Quick cache for expensive endpoints

from functools import lru_cache
from datetime import datetime, timezone, timedelta

# Cache with TTL
cache_timestamp = None
cache_data = None
CACHE_TTL_SECONDS = 60

@app.route("/expensive-endpoint")
def expensive():
    global cache_timestamp, cache_data

    # Check cache
    now = datetime.now(timezone.utc)
    if cache_data and cache_timestamp and (now - cache_timestamp).seconds < CACHE_TTL_SECONDS:
        return jsonify(cache_data), 200

    # Expensive computation
    result = compute_expensive_data()

    # Update cache
    cache_data = result
    cache_timestamp = now

    return jsonify(result), 200
```

### Option 4: Disable Slow Endpoint (emergency)

```python
# app/main.py - Circuit breaker for slow endpoint

SLOW_ENDPOINT_ENABLED = os.getenv('SLOW_ENDPOINT_ENABLED', 'true') == 'true'

@app.route("/slow-endpoint")
def slow_endpoint():
    if not SLOW_ENDPOINT_ENABLED:
        return jsonify({"error": "Endpoint temporarily disabled due to performance issues"}), 503

    # ... normal code
```

---

## Resolution

### Performance Baseline Verification

```bash
# Check p99 latency returned to normal
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --extended-statistics p99

# Target: p99 <500ms
```

### Endpoint-Specific Testing

```bash
# Test each endpoint 10 times, measure latency
for endpoint in / /health /metrics; do
  echo "Testing $endpoint..."
  for i in {1..10}; do
    curl -s -o /dev/null -w "%{time_total}s\n" http://{alb-dns}$endpoint
  done | awk '{sum+=$1; count++} END {print "Average: " sum/count "s"}'
done
```

---

## Prevention

### Application Optimizations

#### 1. Add Request Timeout

```python
# app/main.py - Prevent hung requests

import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Request exceeded timeout")

@app.before_request
def set_timeout():
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5 second timeout

@app.after_request
def clear_timeout(response):
    signal.alarm(0)  # Cancel timeout
    return response

@app.errorhandler(TimeoutException)
def handle_timeout(e):
    return jsonify({"error": "Request timeout", "status_code": 504}), 504
```

#### 2. Add Performance Profiling

```python
# app/main.py - Log slow requests automatically

@app.after_request
def log_slow_requests(response):
    if hasattr(request, 'start_time'):
        duration = (datetime.now(timezone.utc) - request.start_time).total_seconds() * 1000

        # Warn on slow requests
        if duration > 500:
            StructuredLogger.log(
                "warning",
                "Slow request detected",
                path=request.path,
                method=request.method,
                duration_ms=round(duration, 2),
                status=response.status_code
            )

    return response
```

#### 3. Optimize Hot Paths

```python
# Example: Cache expensive computations
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_calculation(param):
    # This result will be cached
    return complex_computation(param)
```

### Infrastructure Optimizations

#### 1. Lower Auto-scaling Target

```yaml
# infrastructure/cdk/config/{env}.yaml
autoscaling:
  cpu:
    target_utilization: 50  # Lower from 70 (more headroom)
```

#### 2. Enable ALB Connection Draining

Already configured at 30s, but can increase:

```python
# infrastructure/cdk/stacks/ecs_stack.py
deregistration_delay=Duration.seconds(60)  # Increase from 30
```

#### 3. Add CloudWatch Alarm for p95

```bash
# Early warning at p95 >500ms
aws cloudwatch put-metric-alarm \
  --alarm-name StreaverHelloWorld-ModerateLatency-{env} \
  --metric-name TargetResponseTime \
  --namespace AWS/ApplicationELB \
  --statistic p95 \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.5 \
  --comparison-operator GreaterThanThreshold
```

### Monitoring Improvements

#### 1. Add Latency Dashboard

```json
{
  "type": "metric",
  "properties": {
    "metrics": [
      ["AWS/ApplicationELB", "TargetResponseTime", {"stat": "p50"}],
      ["...", {"stat": "p90"}],
      ["...", {"stat": "p99"}],
      ["...", {"stat": "Maximum"}]
    ],
    "period": 60,
    "region": "us-east-1",
    "title": "Response Time Percentiles"
  }
}
```

#### 2. Synthetic Performance Testing

```javascript
// tests/load/latency-test.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],  // SLA enforcement
  },
};

export default function() {
  let res = http.get('http://{alb-url}/');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'latency < 500ms': (r) => r.timings.duration < 500,
  });
}
```

Run in CI/CD:
```yaml
# .github/workflows/ci.yml
- name: Performance test
  run: |
    docker run --rm -i grafana/k6 run - < tests/load/latency-test.js
```

---

## Escalation Path

| Timeline | Action | Contact |
|----------|--------|---------|
| 0-10 min | On-call investigates | Auto-paged |
| 10-20 min | Identify slow endpoint/cause | On-call analysis |
| 20-40 min | Scale or optimize | On-call + app team |
| 40-60 min | If persistent: deep profiling | Senior engineer |
| >60 min | Escalate if SLA breach risk | Manager |

---

## Related Runbooks

- [High CPU Utilization](./01-high-cpu-utilization.md)
- [High Memory Utilization](./02-high-memory-utilization.md)
- [High 5XX Error Rate](./03-high-5xx-error-rate.md)

---

**Runbook Version:** 1.0
**Last Tested:** 2026-03-03
**Next Review:** 2026-06-03
