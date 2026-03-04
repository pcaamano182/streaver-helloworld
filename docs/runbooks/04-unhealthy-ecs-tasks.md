# Runbook: Unhealthy ECS Tasks

**Alarm Name:** `StreaverHelloWorld-UnhealthyTargets-{environment}`
**Severity:** P1 (Critical)
**Auto-scaling:** May compound issue if unhealthy tasks keep spawning
**Last Updated:** 2026-03-03

---

## Overview

This runbook addresses situations where the ALB reports <2 healthy ECS tasks in the target group. This typically indicates tasks are failing health checks (`/health` endpoint), crashing, or unable to start properly.

### Alarm Configuration

- **Metric:** `HealthyHostCount` (ALB Target Group)
- **Threshold:** <2 healthy targets
- **Evaluation Period:** 1 datapoint within 1 minute
- **Action:** SNS notification to on-call team

---

## Impact Assessment

### Severity Matrix

| Healthy Tasks | Total Tasks | Impact | Action Required |
|---------------|-------------|--------|-----------------|
| desired_count | desired_count | None | Normal operation |
| ≥2 | any | Low | Service functional, investigate |
| 1 | any | **High** | **No redundancy** | **Act immediately** |
| 0 | any | **Critical** | **Complete outage** | **Emergency** |

### User Impact

- **<2 healthy:** No redundancy, single task failure = outage
- **0 healthy:** Complete service unavailability (503 errors from ALB)
- **Traffic concentration:** Remaining healthy tasks receive all traffic

---

## Triage (First 3 Minutes)

### Step 1: Assess Current State

```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn {target-group-arn} \
  | jq '.TargetHealthDescriptions[] | {ip: .Target.Id, state: .TargetHealth.State, reason: .TargetHealth.Reason}'

# Get ECS service status
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[desiredCount,runningCount,pendingCount]'
```

### Step 2: Check Recent Events

```bash
# ECS service events (last 10)
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].events[:10]' \
  --output table
```

**Key indicators:**
- `(service {name}) has stopped 3 running tasks` → Deployment or crash
- `Task failed ELB health checks` → Health endpoint failing
- `Task failed to start` → Image pull or resource issue

### Step 3: Test Health Endpoint Directly

```bash
# Test ALB health endpoint
curl -i http://{alb-dns}/health

# If accessible, test from task directly (exec required)
aws ecs execute-command \
  --cluster streaver-cluster-{env} \
  --task {task-id} \
  --container streaver-helloworld \
  --interactive \
  --command "curl -v http://localhost:5000/health"
```

---

## Investigation

### Common Failure Modes

#### 1. Tasks Crash on Startup

**Symptoms:**
- Tasks transition: PENDING → RUNNING → STOPPED
- Container exit code != 0
- Short runtime (seconds to minutes)

**Diagnosis:**
```bash
# Get stopped task details
aws ecs list-tasks \
  --cluster streaver-cluster-{env} \
  --service-name streaver-service-{env} \
  --desired-status STOPPED \
  | jq -r '.taskArns[0]' \
  | xargs -I {} aws ecs describe-tasks \
      --cluster streaver-cluster-{env} \
      --tasks {} \
      --query 'tasks[0].[stoppedReason,containers[0].exitCode,containers[0].reason]'

# Check container logs for crash
STOPPED_TASK=$(aws ecs list-tasks --cluster streaver-cluster-{env} --service-name streaver-service-{env} --desired-status STOPPED --query 'taskArns[0]' --output text)
aws logs tail /ecs/streaver-cluster-{env} --since 1h --filter-pattern $STOPPED_TASK
```

**Common causes:**
- Missing environment variables
- Import errors in Python code
- Port binding conflicts
- Insufficient memory (OOM kill)

#### 2. Health Endpoint Failing

**Symptoms:**
- Tasks stay RUNNING but marked unhealthy
- ALB returns 502 Bad Gateway
- Health check path returns non-200 status

**Diagnosis:**
```bash
# Check health check config
aws elbv2 describe-target-groups \
  --target-group-arns {target-group-arn} \
  --query 'TargetGroups[0].HealthCheckPath'

# View application logs for /health requests
aws logs tail /ecs/streaver-cluster-{env} \
  --since 15m \
  --filter-pattern '{ $.path = "/health" }'
```

**Health check requirements:**
- Path: `/health`
- Expected: HTTP 200
- Timeout: 5 seconds
- Interval: 30 seconds
- Healthy threshold: 2 consecutive successes
- Unhealthy threshold: 3 consecutive failures

#### 3. Tasks Stuck in PENDING

**Symptoms:**
- Desired count > Running count
- Tasks never reach RUNNING state
- Pending count > 0 for >2 minutes

**Diagnosis:**
```bash
# Check pending tasks
aws ecs describe-tasks \
  --cluster streaver-cluster-{env} \
  --tasks $(aws ecs list-tasks --cluster streaver-cluster-{env} --service-name streaver-service-{env} --desired-status PENDING --query 'taskArns[0]' --output text) \
  --query 'tasks[0].[lastStatus,stoppedReason,containers[0].reason]'
```

**Common causes:**
- ECR image pull failure (auth, network, or image doesn't exist)
- Insufficient ENI capacity in subnet
- Service quota limits reached
- Invalid task definition (resource constraints)

#### 4. Deployment Circuit Breaker Triggered

**Symptoms:**
- Deployment stuck in `IN_PROGRESS`
- Events show "deployment failed"
- Auto-rollback initiated

**Diagnosis:**
```bash
# Check deployment status
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].deployments[*].[status,rolloutState,failedTasks]'
```

---

## Immediate Mitigation

### Option 1: Manual Health Check (if false alarm)

```bash
# Test health endpoint
curl -f http://{alb-dns}/health || echo "Health check failed"

# If 200 OK, check ALB configuration
aws elbv2 modify-target-group \
  --target-group-arn {target-group-arn} \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3
```

### Option 2: Force Task Restart

```bash
# Stop unhealthy tasks (ECS will replace)
aws ecs list-tasks \
  --cluster streaver-cluster-{env} \
  --service-name streaver-service-{env} \
  | jq -r '.taskArns[]' \
  | xargs -I {} aws ecs stop-task \
      --cluster streaver-cluster-{env} \
      --task {} \
      --reason "Unhealthy - forced restart"

# Wait 60s for new tasks
sleep 60

# Verify recovery
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[runningCount,desiredCount]'
```

### Option 3: Rollback Deployment

**If issue started after deploy:**

```bash
# List deployments
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].deployments'

# Rollback to previous task definition
PREVIOUS_REVISION=$(($(aws ecs describe-task-definition --task-definition streaver-helloworld-task-{env} --query 'taskDefinition.revision') - 1))

aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:$PREVIOUS_REVISION \
  --force-new-deployment
```

### Option 4: Emergency Scale-Out

**If some tasks are healthy but overwhelmed:**

```bash
# Temporary increase to stabilize
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count $(($(aws ecs describe-services --cluster streaver-cluster-{env} --services streaver-service-{env} --query 'services[0].desiredCount' --output text) + 3))
```

---

## Resolution

### Verify All Tasks Healthy

```bash
# Check target health (all should be "healthy")
aws elbv2 describe-target-health \
  --target-group-arn {target-group-arn} \
  --query 'TargetHealthDescriptions[?TargetHealth.State!=`healthy`]'

# Should return empty array []
```

### Test Service Endpoints

```bash
# Test all critical endpoints
for endpoint in / /health /metrics; do
  echo "Testing $endpoint..."
  curl -s -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" http://{alb-dns}$endpoint
done
```

Expected output:
```
Testing /...
HTTP 200 - 0.045s
Testing /health...
HTTP 200 - 0.012s
Testing /metrics...
HTTP 200 - 0.018s
```

---

## Prevention

### Application Improvements

#### 1. Enhance Health Check Robustness

```python
# app/main.py - Improve /health endpoint

import psutil
from datetime import datetime, timezone

@app.route("/health", methods=["GET"])
def health() -> tuple:
    """
    Enhanced health check with dependency validation.
    """
    health_status = {
        "status": "healthy",
        "service": "streaver-helloworld",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_since": metrics["start_time"].isoformat(),
        "checks": {}
    }

    # Check 1: Memory headroom
    memory_percent = psutil.virtual_memory().percent
    health_status["checks"]["memory"] = {
        "status": "ok" if memory_percent < 90 else "warning",
        "percent": memory_percent
    }

    # Check 2: Disk space
    disk_percent = psutil.disk_usage('/').percent
    health_status["checks"]["disk"] = {
        "status": "ok" if disk_percent < 85 else "warning",
        "percent": disk_percent
    }

    # Check 3: Critical dependencies (example)
    # health_status["checks"]["database"] = check_db_connection()

    # Overall health: fail if any critical check fails
    overall_healthy = all(
        check.get("status") != "fail"
        for check in health_status["checks"].values()
    )

    status_code = 200 if overall_healthy else 503
    metrics["health_checks"] += 1

    return jsonify(health_status), status_code
```

#### 2. Add Readiness vs Liveness Separation

```python
# app/main.py - Separate readiness and liveness

@app.route("/health/live", methods=["GET"])
def liveness():
    """Liveness probe - is the app running?"""
    return jsonify({"status": "alive"}), 200

@app.route("/health/ready", methods=["GET"])
def readiness():
    """Readiness probe - can the app serve traffic?"""
    # Check if startup complete, dependencies ready
    if not app_ready:
        return jsonify({"status": "not_ready", "reason": "startup_in_progress"}), 503

    return jsonify({"status": "ready"}), 200
```

Then update ALB to use `/health/ready` as health check path.

### Infrastructure Improvements

#### 1. Increase Health Check Grace Period

```yaml
# infrastructure/cdk/stacks/ecs_stack.py
self.service = ecs.FargateService(
    # ...
    health_check_grace_period=Duration.seconds(120),  # Increase from 60
)
```

#### 2. Adjust Health Check Thresholds

```yaml
# infrastructure/cdk/stacks/ecs_stack.py
health_check=elbv2.HealthCheck(
    path="/health",
    interval=Duration.seconds(30),
    timeout=Duration.seconds(10),  # Increase from 5
    healthy_threshold_count=2,
    unhealthy_threshold_count=5,  # Increase from 3 (more tolerance)
)
```

#### 3. Add Startup Delay for Heavy Apps

```python
# Dockerfile - Add startup script
CMD ["sh", "-c", "sleep 5 && gunicorn ..."]
```

### Monitoring Improvements

```bash
# Create early-warning alarm (1 unhealthy)
aws cloudwatch put-metric-alarm \
  --alarm-name StreaverHelloWorld-SingleUnhealthy-{env} \
  --metric-name UnHealthyHostCount \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=LoadBalancer,Value={alb-name}
```

---

## Escalation Path

| Timeline | Action | Contact |
|----------|--------|---------|
| 0-3 min | On-call checks target health | Auto-paged |
| 3-10 min | Restart tasks or rollback | On-call action |
| 10-20 min | If persists: engage app team | Slack: #app-team |
| 20-40 min | Check infrastructure (VPC, subnets) | DevOps lead |
| >40 min | Major incident | VP Engineering |

---

## Related Runbooks

- [High 5XX Error Rate](./03-high-5xx-error-rate.md)
- [High Memory Utilization](./02-high-memory-utilization.md)
- [Deployment Rollback](./06-deployment-rollback.md)

---

**Runbook Version:** 1.0
**Last Tested:** 2026-03-03
**Next Review:** 2026-06-03
