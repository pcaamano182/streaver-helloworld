# Runbook: High 5XX Error Rate

**Alarm Name:** `StreaverHelloWorld-High5XX-{environment}`
**Severity:** P1 (Critical)
**Auto-scaling:** No (errors may persist regardless of task count)
**Last Updated:** 2026-03-03

---

## Overview

This runbook addresses situations where the application is returning >10 HTTP 5XX errors within a 5-minute window. Unlike 4XX errors (client issues), 5XX errors indicate **server-side failures** that directly impact user experience and may indicate serious application or infrastructure problems.

### Alarm Configuration

- **Metric:** `HTTPCode_Target_5XX_Count` (ALB Target Group)
- **Threshold:** >10 errors in 5 minutes
- **Evaluation Period:** 1 datapoint within 5 minutes
- **Action:** SNS notification to on-call team

---

## Impact Assessment

### Severity Matrix

| 5XX Error Rate | Impact | User Experience | Action Required |
|----------------|--------|-----------------|-----------------|
| 1-5 errors/5min | Low | Isolated failures | Monitor |
| 6-10 errors/5min | Medium | Noticeable degradation | Investigate |
| >10 errors/5min | **High** | **Service degraded** | **Act immediately** |
| >100 errors/5min | **Critical** | **Service outage** | **Emergency response** |

### HTTP 5XX Error Types

| Code | Meaning | Likely Cause |
|------|---------|--------------|
| 500 | Internal Server Error | Application bug, unhandled exception |
| 502 | Bad Gateway | Task crash, unhealthy targets |
| 503 | Service Unavailable | All tasks down, deployment issue |
| 504 | Gateway Timeout | Task not responding within 60s |

### User Impact

- **Availability:** Users see error pages instead of content
- **Data loss:** Transactions may fail without retry
- **Trust:** Repeated errors erode user confidence
- **SLA breach:** Likely violating 99.9% availability target

---

## Triage (First 5 Minutes)

### Step 1: Identify Error Type Distribution

```bash
# Get ALB 5XX error breakdown
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value={alb-name} \
               Name=TargetGroup,Value={tg-name} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Check for 502/503 specifically (infrastructure vs app)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_ELB_5XX_Count \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

**Interpretation:**
- **HTTPCode_Target_5XX** = Errors from ECS tasks (app issue)
- **HTTPCode_ELB_5XX** = Errors from ALB itself (infrastructure issue)

### Step 2: Check Task Health

```bash
# Get current healthy task count
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[runningCount,desiredCount]'

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn {target-group-arn} \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason]' \
  --output table
```

**Healthy state indicators:**
- Running count == Desired count
- All targets in "healthy" state
- No "unhealthy" or "draining" targets

### Step 3: Review Application Logs (Last 15 Minutes)

```bash
# Find 500 errors in structured logs
aws logs tail /ecs/streaver-cluster-{env} \
  --since 15m \
  --filter-pattern '{ $.status = 500 || $.level = "ERROR" }' \
  --format short

# Count errors by endpoint
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '30 minutes ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, status, message, error
    | filter status >= 500
    | stats count() by path
    | sort count desc'
```

---

## Investigation

### Error Pattern Analysis

#### Pattern 1: Sudden Spike (Last 5-10 Minutes)

**Likely causes:**
- Recent deployment with bug
- External dependency failure (database, API)
- Configuration change

**Action:**
```bash
# Check recent deployments
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].deployments' \
  --output table

# Check task start times
aws ecs list-tasks \
  --cluster streaver-cluster-{env} \
  --service-name streaver-service-{env} \
  | jq -r '.taskArns[]' \
  | while read task; do
      aws ecs describe-tasks --cluster streaver-cluster-{env} --tasks $task \
        --query 'tasks[0].[taskArn,createdAt,lastStatus]' --output text
    done
```

#### Pattern 2: Gradual Increase Over Hours

**Likely causes:**
- Memory leak causing crashes (see runbook 02)
- Resource exhaustion (connections, file descriptors)
- Data corruption accumulating

**Action:**
```bash
# Check memory/CPU trends
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
  --start-time $(date -u -d '4 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

#### Pattern 3: Intermittent/Sporadic

**Likely causes:**
- Specific endpoint failing under certain conditions
- Race condition or concurrency bug
- Transient external dependency issues

**Action:**
```bash
# Find which endpoints are failing
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '2 hours ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, method, status, error, message
    | filter status = 500
    | sort @timestamp desc
    | limit 50'
```

### Root Cause Investigation

#### 1. Check for Known /error Endpoint

**⚠️ IMPORTANT:** This app has an **intentional** `/error` endpoint that always returns 500!

```bash
# Verify if errors are from intentional /error endpoint
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '30 minutes ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, status
    | filter status = 500
    | stats count() by path'
```

**Expected result:**
```json
{
  "/error": 12,    // ← Intentional, can ignore
  "/": 0,
  "/health": 0,
  "/metrics": 0
}
```

**If only `/error` has 500s:** This is expected behavior for observability testing. **Alarm is false positive.**

**If other endpoints have 500s:** Genuine issue, continue investigation.

#### 2. Analyze Error Messages

```bash
# Get detailed error messages
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '30 minutes ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, error, message
    | filter status = 500 and path != "/error"
    | sort @timestamp desc
    | limit 20'
```

**Common error patterns:**

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `KeyError: 'x'` | Missing config/env var | Add environment variable |
| `ConnectionError` | External API down | Check dependency health |
| `TimeoutError` | Slow backend | Increase timeout or optimize |
| `JSONDecodeError` | Invalid response parsing | Add error handling |
| `MemoryError` | OOM imminent | See runbook 02 |

#### 3. Check External Dependencies

```bash
# If app calls external APIs, test them manually
curl -i https://external-api.example.com/health

# Check DNS resolution
dig external-api.example.com

# Check connectivity from task (if exec enabled)
aws ecs execute-command \
  --cluster streaver-cluster-{env} \
  --task {task-id} \
  --container streaver-helloworld \
  --interactive \
  --command "curl -v https://external-api.example.com"
```

#### 4. Review Recent Changes

```bash
# Git history (last 24 hours)
cd ~/streaver-helloworld
git log --since="24 hours ago" --oneline

# Check CI/CD pipeline runs
gh run list --workflow=cd-{env}.yml --limit 10

# Check infrastructure changes
cd infrastructure/cdk
git log --since="24 hours ago" --oneline -- .
```

---

## Immediate Mitigation

### Option 1: Rollback Recent Deployment

**If errors started after recent deploy:**

```bash
# Get previous task definition
aws ecs describe-task-definition \
  --task-definition streaver-helloworld-task-{env} \
  --query 'taskDefinition.revision'

# Rollback to previous revision (e.g., revision 5 → 4)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:{previous-revision}

# Monitor rollback progress
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].events[:5]'
```

**Expected time:** 2-5 minutes for rolling update

### Option 2: Restart Unhealthy Tasks

**If specific tasks are failing:**

```bash
# List all tasks
aws ecs list-tasks \
  --cluster streaver-cluster-{env} \
  --service-name streaver-service-{env}

# Stop problematic task (ECS will start replacement)
aws ecs stop-task \
  --cluster streaver-cluster-{env} \
  --task {task-arn} \
  --reason "Excessive 5XX errors - manual intervention"

# Verify replacement started
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[runningCount,desiredCount]'
```

### Option 3: Circuit Breaker (Code Fix)

**If error is from specific endpoint, disable it:**

```python
# Emergency hotfix: app/main.py
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'false') == 'true'

@app.route("/problematic-endpoint")
def problematic():
    if MAINTENANCE_MODE:
        return jsonify({"error": "Endpoint temporarily disabled"}), 503
    # ... normal code
```

Deploy with environment variable:
```bash
# Update task definition with env var
aws ecs register-task-definition \
  --cli-input-json file://task-def-with-maintenance.json

aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:{new-revision}
```

### Option 4: Traffic Throttling (ALB Level)

**If issue is load-related:**

```bash
# Reduce ALB connection count temporarily
# (Requires WAF or ALB listener rules configured)

# Example: Add rate limiting rule to WAF
aws wafv2 update-web-acl \
  --scope REGIONAL \
  --id {web-acl-id} \
  --rules file://emergency-rate-limit.json
```

---

## Resolution

### Verification Steps

```bash
# 1. Confirm error rate dropped
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# 2. Check all targets healthy
aws elbv2 describe-target-health \
  --target-group-arn {target-group-arn} \
  | jq '.TargetHealthDescriptions[] | select(.TargetHealth.State != "healthy")'

# 3. Sample endpoint tests
curl -s http://{alb-dns}/ | jq .
curl -s http://{alb-dns}/health | jq .
curl -s http://{alb-dns}/metrics | jq .
```

### Post-Mitigation Monitoring (2 hours)

Monitor every 10 minutes:

1. **5XX error count** - should be 0 (or only /error endpoint)
2. **Response time p99** - should be <500ms
3. **Task count** - should equal desired count
4. **CPU/Memory** - should be <70%

### Document Incident

```bash
# Export relevant metrics for post-mortem
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time {incident-start} \
  --end-time {incident-end} \
  --period 60 \
  --statistics Sum \
  > incident-{date}-5xx-metrics.json
```

---

## Prevention

### Application-Level Improvements

#### 1. Add Comprehensive Error Handling

```python
# app/main.py - Improve error handling

@app.errorhandler(Exception)
def handle_exception(e):
    """Catch ALL exceptions and log structured errors"""
    # Log with full context
    StructuredLogger.log(
        "error",
        "Unhandled exception",
        error=str(e),
        error_type=type(e).__name__,
        path=request.path,
        method=request.method,
        traceback=traceback.format_exc()  # Full stack trace
    )

    # Return user-friendly error
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "request_id": request.headers.get('X-Request-ID'),
        "status_code": 500
    }), 500
```

#### 2. Add Request Validation

```python
# app/main.py - Validate input early

from flask import request
from werkzeug.exceptions import BadRequest

@app.before_request
def validate_request():
    # Example: Reject malformed JSON
    if request.is_json:
        try:
            _ = request.get_json()
        except Exception as e:
            raise BadRequest(f"Invalid JSON: {e}")

    # Example: Validate headers
    if 'User-Agent' not in request.headers:
        raise BadRequest("User-Agent header required")
```

#### 3. Add Circuit Breaker for Dependencies

```python
# app/utils/circuit_breaker.py

import time
from functools import wraps

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def call(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = 'HALF_OPEN'
                else:
                    raise Exception("Circuit breaker OPEN")

            try:
                result = func(*args, **kwargs)
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                raise e

        return wrapper

# Usage:
# external_api_breaker = CircuitBreaker()
# @external_api_breaker.call
# def call_external_api():
#     ...
```

#### 4. Add Retry Logic with Exponential Backoff

```python
# app/utils/retry.py

import time
from functools import wraps

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        raise e
                    sleep_time = backoff_in_seconds * (2 ** x)
                    time.sleep(sleep_time)
                    x += 1
        return wrapper
    return decorator
```

### Monitoring Improvements

#### 1. Separate /error Endpoint from Real Errors

```bash
# Create filtered alarm (exclude /error endpoint)
aws cloudwatch put-metric-alarm \
  --alarm-name StreaverHelloWorld-Real5XX-{env} \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=LoadBalancer,Value={alb-name}

# Then filter in logs:
# Only alert if errors NOT from /error endpoint
```

#### 2. Add Error Rate SLI

Define Service Level Indicator:
```
Error Rate SLI = (1 - (5XX_count / total_requests)) * 100
Target: >99.9% (max 0.1% errors)
```

Monitor in CloudWatch:
```bash
aws cloudwatch put-metric-math-alarm \
  --alarm-name StreaverHelloWorld-ErrorRate-{env} \
  --metric-math 'Id=e1,Expression=(1 - (m2/m1))*100'
```

#### 3. Add Synthetic Monitoring

```bash
# Create CloudWatch Synthetics canary
aws synthetics create-canary \
  --name streaver-{env}-canary \
  --code file://canary-script.zip \
  --artifact-s3-location s3://bucket/canaries/ \
  --execution-role-arn {role-arn} \
  --schedule Expression="rate(5 minutes)" \
  --run-config TimeoutInSeconds=60
```

### Testing Improvements

#### 1. Add Chaos Testing

```bash
# tests/chaos/inject-500-errors.sh
# Randomly kill tasks to test resilience

TASKS=$(aws ecs list-tasks --cluster streaver-cluster-dev --service-name streaver-service-dev --query 'taskArns[]' --output text)

# Kill random task
RANDOM_TASK=$(echo $TASKS | tr ' ' '\n' | shuf -n 1)
aws ecs stop-task --cluster streaver-cluster-dev --task $RANDOM_TASK --reason "Chaos test"

# Verify service recovers
sleep 30
# Check 5XX error count is still <10
```

#### 2. Add Error Scenario Tests

```python
# app/tests/test_error_handling.py

def test_unhandled_exception_returns_500(client):
    """Test that unhandled exceptions return 500 with proper structure"""
    # Simulate error by calling non-existent function
    # (Requires adding test endpoint)
    response = client.get('/test/trigger-error')
    assert response.status_code == 500
    data = response.get_json()
    assert 'error' in data
    assert 'status_code' in data
    assert data['status_code'] == 500
```

---

## Escalation Path

| Timeline | Action | Contact |
|----------|--------|---------|
| 0-5 min | On-call investigates | Auto-paged |
| 5-15 min | Identify if deployment-related | On-call checks logs |
| 15-30 min | Rollback if new deploy, or engage app team | Slack: #app-team |
| 30-60 min | If persists: escalate to senior engineer | Manager contact |
| >60 min | Major incident declared | VP Engineering |

---

## Related Runbooks

- [Unhealthy ECS Tasks](./04-unhealthy-ecs-tasks.md)
- [High Response Time](./05-high-response-time.md)
- [Deployment Rollback](./06-deployment-rollback.md)

---

## Common False Positives

### 1. Intentional /error Endpoint

**Symptom:** Alarm triggers but only /error endpoint has 500s

**Resolution:**
```bash
# Verify it's only /error
aws logs insights query ... | grep -v "/error"
```

**Action:** Update alarm to exclude /error path, or document as expected

### 2. Health Check Failures During Deployment

**Symptom:** Brief spike in 502s during rolling deployment

**Resolution:** This is expected during task replacement

**Action:** Increase alarm threshold to >20 errors to avoid noise

### 3. Load Testing

**Symptom:** Alarm during scheduled load tests

**Resolution:** Silence alarm during known test windows

```bash
# Disable alarm temporarily
aws cloudwatch disable-alarm-actions \
  --alarm-names StreaverHelloWorld-High5XX-dev
```

---

## Post-Incident Checklist

- [ ] Error rate returned to <1 per 5 minutes
- [ ] Root cause identified and documented
- [ ] Code fix deployed (if application bug)
- [ ] Infrastructure adjusted (if resource issue)
- [ ] Monitoring improved to detect earlier
- [ ] Tests added to prevent regression
- [ ] Runbook updated with learnings
- [ ] Post-mortem completed and shared

---

**Runbook Version:** 1.0
**Last Tested:** 2026-03-03
**Next Review:** 2026-06-03
