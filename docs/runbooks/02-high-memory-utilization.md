# Runbook: High Memory Utilization

**Alarm Name:** `StreaverHelloWorld-HighMemory-{environment}`
**Severity:** P2 (High) - P1 if OOM kills occurring
**Auto-scaling:** Yes (scales out at >70% memory)
**Last Updated:** 2026-03-03

---

## Overview

This runbook addresses situations where ECS Fargate tasks are consuming >80% memory for an extended period. Unlike CPU, memory cannot be throttled - when a task exceeds its memory limit, it will be killed by the OOM (Out of Memory) killer, causing service disruption.

### Alarm Configuration

- **Metric:** `MemoryUtilization` (ECS Service)
- **Threshold:** >80%
- **Evaluation Period:** 2 datapoints within 5 minutes
- **Action:** SNS notification to on-call team

---

## Impact Assessment

### Severity Matrix

| Memory % | Impact | Risk | Action Required |
|----------|--------|------|-----------------|
| 60-70% | Low | Auto-scaling triggered | Monitor |
| 70-80% | Medium | New tasks starting | Investigate |
| 80-90% | High | OOM kill risk | **Act immediately** |
| >90% | Critical | **OOM kill imminent** | **Emergency response** |

### User Impact

- **Task restarts:** OOM kills cause 503 errors during restart
- **Data loss:** In-memory data (metrics, sessions) lost
- **Cascading failures:** Remaining tasks receive more traffic
- **Auto-scaling lag:** 60s cooldown may not prevent OOM

### Task Resource Limits

| Environment | Memory Limit | Headroom at 80% | Notes |
|-------------|--------------|-----------------|-------|
| dev         | 512 MB       | 102 MB          | Low headroom |
| cert        | 1024 MB      | 205 MB          | Medium headroom |
| prod        | 2048 MB      | 410 MB          | Good headroom |

---

## Triage (First 5 Minutes)

### Step 1: Check for Active OOM Kills

```bash
# Check ECS events for OOM kills (last 30 minutes)
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].events[?contains(message, `memory`)]' \
  --output table

# Check CloudWatch Logs for OOM messages
aws logs tail /ecs/streaver-cluster-{env} \
  --since 30m \
  --filter-pattern "OOM"
```

**OOM Kill Indicators:**
- `OutOfMemoryError: Container killed due to memory usage`
- `Task stopped (Essential container exited)`
- Sudden task restarts without code deployment

### Step 2: Get Current Memory State

```bash
# Current memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
               Name=ClusterName,Value=streaver-cluster-{env} \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum

# Task count (verify if auto-scaling is working)
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[desiredCount,runningCount,pendingCount]'
```

### Step 3: Identify Memory Growth Pattern

```bash
# Get memory trend (last 2 hours)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
               Name=ClusterName,Value=streaver-cluster-{env} \
  --start-time $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

**Growth Patterns:**
- **Sudden spike:** Traffic increase or large request payload
- **Gradual increase:** Memory leak (most concerning)
- **Periodic spikes:** Batch processing or cron jobs
- **Flat high:** Under-provisioned for current load

---

## Investigation

### Likely Causes

#### 1. Memory Leak (Application Bug)
**Indicators:**
- Steady linear growth over time
- Memory doesn't drop after traffic decreases
- Pattern repeats across all tasks

**Common sources:**
- Global variables accumulating data
- Event listeners not removed
- Circular references preventing GC
- Large in-memory caches without eviction

#### 2. Traffic Spike
**Indicators:**
- Correlated with request count increase
- Memory proportional to concurrent requests
- Drops after traffic normalizes

**Check:**
```bash
# Compare request count vs memory
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

#### 3. Large Request Payloads
**Indicators:**
- Sudden memory spike on specific requests
- Logs show large request bodies

**Check:**
```bash
# Find large requests in logs
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, method, path, @message
    | filter @message like /large|payload|bytes/
    | sort @timestamp desc
    | limit 20'
```

#### 4. Under-provisioned Resources
**Indicators:**
- Memory consistently high (>70%) even at normal traffic
- Baseline memory usage increased after feature deployment

### Diagnostic Commands

#### 1. Application Metrics Check

```bash
# Check /metrics endpoint for memory-related data
# (requires port-forward or exec into running task)
aws ecs execute-command \
  --cluster streaver-cluster-{env} \
  --task {task-id} \
  --container streaver-helloworld \
  --interactive \
  --command "/bin/sh"

# Inside container:
curl http://localhost:5000/metrics
```

#### 2. Analyze Application Logs

```bash
# Look for memory warnings or large object allocations
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '2 hours ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, level, message, path
    | filter level = "ERROR" or level = "WARNING"
    | sort @timestamp desc
    | limit 50'
```

#### 3. Check for Stuck Connections

```bash
# In Python app, we track request counts in memory
# Check if request_count keeps growing without dropping
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp
    | filter path = "/metrics"
    | sort @timestamp desc
    | limit 10'
```

#### 4. Container Insights Memory Breakdown

```bash
# Get detailed memory metrics
aws cloudwatch get-metric-statistics \
  --namespace ECS/ContainerInsights \
  --metric-name MemoryUtilized \
  --dimensions Name=ClusterName,Value=streaver-cluster-{env} \
               Name=ServiceName,Value=streaver-service-{env} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum
```

---

## Immediate Mitigation

### Option 1: Force Task Rotation (Restart All Tasks)

**Purpose:** Clear memory if leak is suspected

```bash
# Force new deployment (graceful rolling restart)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --force-new-deployment

# Monitor deployment
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].deployments'
```

**Expected behavior:**
- New tasks start with fresh memory (0%)
- Old tasks drained and stopped
- Total time: 2-5 minutes (depending on environment)

### Option 2: Emergency Scale-Out

**Purpose:** Reduce per-task load immediately

```bash
# Double the task count
CURRENT_COUNT=$(aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].desiredCount' \
  --output text)

aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count $((CURRENT_COUNT * 2))
```

**Rollback:**
```bash
# Return to auto-scaling managed count
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count {original_count}
```

### Option 3: Temporary Memory Increase (Production Only)

**⚠️ WARNING:** Requires task definition update and full restart

```bash
# Update task definition with higher memory
cd infrastructure/cdk
# Edit config/prod.yaml:
# ecs.task.memory: 4096  (from 2048)

cdk deploy StreaverHelloWorldEcs-prod -c environment=prod --require-approval never
```

**Rollback:**
```bash
# Revert config change and redeploy
cdk deploy StreaverHelloWorldEcs-prod -c environment=prod
```

---

## Resolution

### Verify Mitigation Success

```bash
# 1. Check memory dropped
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
               Name=ClusterName,Value=streaver-cluster-{env} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum

# 2. Verify no OOM kills in last 15 minutes
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].events[:10]'

# 3. Check all tasks are healthy
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[runningCount,desiredCount]'
```

### Post-Mitigation Monitoring (4 hours)

Monitor these metrics every 15 minutes:

1. **Memory utilization** - should stabilize <70%
2. **Task count** - should match desired count
3. **5XX errors** - should be near zero
4. **Response times** - should return to normal (p99 <500ms)

### Root Cause Identification

If memory leak is suspected:

```python
# Add memory profiling to application
# app/main.py

import tracemalloc
import logging

# Start memory tracing
tracemalloc.start()

@app.route("/debug/memory")
def memory_snapshot():
    """Debug endpoint to check top memory consumers"""
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    return jsonify({
        "top_10_memory": [
            {
                "file": str(stat.traceback),
                "size_mb": stat.size / 1024 / 1024,
                "count": stat.count
            }
            for stat in top_stats[:10]
        ]
    })
```

Deploy this change and monitor `/debug/memory` endpoint during high memory periods.

---

## Prevention

### Code-Level Fixes

#### 1. Implement Memory Limits for In-Memory Structures

```python
# app/main.py - Fix metrics dictionary
from collections import deque

# Use bounded deque instead of unlimited dict
MAX_METRICS_SIZE = 1000
metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "error_requests": 0,
    "health_checks": 0,
    "start_time": datetime.now(timezone.utc),
    "recent_requests": deque(maxlen=MAX_METRICS_SIZE)  # Bounded!
}
```

#### 2. Add Request Size Limits

```python
# app/main.py - Limit request payload size
from werkzeug.exceptions import RequestEntityTooLarge

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB limit

@app.errorhandler(RequestEntityTooLarge)
def handle_large_request(e):
    return jsonify({"error": "Request too large", "max_size_mb": 10}), 413
```

#### 3. Implement Memory Circuit Breaker

```python
# app/main.py - Reject requests if memory is critical
import psutil

@app.before_request
def check_memory():
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 90:
        return jsonify({
            "error": "Service under high memory pressure",
            "status_code": 503
        }), 503
```

### Infrastructure-Level Fixes

#### 1. Adjust Auto-scaling Thresholds

```yaml
# infrastructure/cdk/config/{env}.yaml
autoscaling:
  memory:
    target_utilization: 60  # Lower from 70% (more headroom)
    scale_out_cooldown: 30  # Faster response
    scale_in_cooldown: 600  # Slower scale-in to observe
```

#### 2. Increase Memory Allocation

For production, if baseline usage is consistently >50%:

```yaml
# infrastructure/cdk/config/prod.yaml
ecs:
  task:
    memory: 4096  # Increase from 2048
```

#### 3. Add Memory-Based Alarms (Early Warning)

```bash
# Create alarm at 70% (before 80% critical alarm)
aws cloudwatch put-metric-alarm \
  --alarm-name StreaverHelloWorld-ModerateMemory-{env} \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
              Name=ClusterName,Value=streaver-cluster-{env}
```

### Monitoring Improvements

#### 1. Enable Memory Profiling in Development

```bash
# Run app with memory profiling
pip install memory_profiler
python -m memory_profiler app/main.py
```

#### 2. Add Synthetic Load Tests

```javascript
// tests/load/memory-stress-test.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '5m', target: 100 },  // Ramp up
    { duration: '30m', target: 100 }, // Sustained load
  ],
};

export default function() {
  let res = http.get('http://{alb-url}/metrics');

  // Check memory via /metrics endpoint
  let metrics = JSON.parse(res.body);
  check(metrics, {
    'memory under control': (m) => m.total_requests < 1000000,
  });
}
```

Run monthly to detect memory leaks early.

#### 3. CloudWatch Dashboard Widget

Add memory trend widget:

```json
{
  "type": "metric",
  "properties": {
    "metrics": [
      [ "AWS/ECS", "MemoryUtilization",
        { "stat": "Average", "label": "Memory Avg" }
      ],
      [ "...", { "stat": "Maximum", "label": "Memory Max" }
      ]
    ],
    "period": 300,
    "stat": "Average",
    "region": "us-east-1",
    "title": "Memory Trend (24h)",
    "yAxis": { "left": { "min": 0, "max": 100 } }
  }
}
```

---

## Escalation Path

| Timeline | Action | Contact |
|----------|--------|---------|
| 0-10 min | On-call investigates | Auto-paged |
| 10-20 min | If OOM kills: restart tasks | On-call action |
| 20-40 min | Engage app team for leak analysis | Slack: #app-team |
| 40-60 min | If persistent: emergency memory increase | Manager approval |
| >60 min | Escalate to VP Engineering | Emergency contact |

---

## Related Runbooks

- [High CPU Utilization](./01-high-cpu-utilization.md)
- [Unhealthy ECS Tasks](./04-unhealthy-ecs-tasks.md)
- [Deployment Rollback](./06-deployment-rollback.md)

---

## Common Pitfalls

1. **Don't wait too long:** At >90% memory, OOM is seconds away
2. **Task restart isn't always enough:** If leak is severe, it will recur quickly
3. **Auto-scaling helps but doesn't fix root cause:** Temporary relief only
4. **Memory leaks compound:** With each scale-out, total memory waste increases

---

## Post-Incident Checklist

- [ ] Memory returned to baseline (<70%)
- [ ] No OOM kills in last 2 hours
- [ ] Auto-scaling stabilized
- [ ] Root cause identified (traffic vs leak vs under-provisioned)
- [ ] Code fix deployed (if leak found)
- [ ] Infrastructure adjusted (if under-provisioned)
- [ ] Post-mortem documented
- [ ] Runbook updated with new learnings

---

**Runbook Version:** 1.0
**Last Tested:** 2026-03-03
**Next Review:** 2026-06-03
