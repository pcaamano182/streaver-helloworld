# Operational Runbooks

This directory contains operational runbooks for the Streaver Hello World application. These runbooks provide step-by-step procedures for responding to common incidents and operational scenarios.

## Quick Reference

| Runbook | Severity | Auto-Recovery | Typical Resolution Time |
|---------|----------|---------------|------------------------|
| [01 - High CPU Utilization](./01-high-cpu-utilization.md) | P2 (High) | Yes (auto-scaling) | 5-15 minutes |
| [02 - High Memory Utilization](./02-high-memory-utilization.md) | P2 (High) | Yes (auto-scaling) | 5-15 minutes |
| [03 - High 5XX Error Rate](./03-high-5xx-error-rate.md) | P1 (Critical) | Partial (circuit breaker) | 10-30 minutes |
| [04 - Unhealthy ECS Tasks](./04-unhealthy-ecs-tasks.md) | P1 (Critical) | Partial (task restart) | 5-20 minutes |
| [05 - High Response Time](./05-high-response-time.md) | P2 (High) | No | 10-40 minutes |
| [06 - Deployment Rollback](./06-deployment-rollback.md) | P1 (Critical) | Yes (circuit breaker) | 5-10 minutes |

---

## Incident Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **P0** | Complete outage | **<5 minutes** | All tasks down, ALB returning 503 |
| **P1** | Critical degradation | **<15 minutes** | >50% error rate, <2 healthy tasks |
| **P2** | Significant degradation | **<30 minutes** | High latency, resource pressure |
| **P3** | Minor issue | **<2 hours** | Single task unhealthy, isolated errors |
| **P4** | Informational | **<24 hours** | Monitoring anomaly, false alarm |

---

## Runbook Index

### Resource Utilization

#### [01 - High CPU Utilization](./01-high-cpu-utilization.md)
**Trigger:** CPU >80% for 5+ minutes

**Common Causes:**
- Traffic spike (most common)
- Inefficient code (CPU-intensive operations)
- Insufficient task CPU allocation

**Quick Fix:**
```bash
# Manual scale-out
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count {current + 2}
```

---

#### [02 - High Memory Utilization](./02-high-memory-utilization.md)
**Trigger:** Memory >80% for 5+ minutes

**Common Causes:**
- Memory leak (application bug)
- Traffic spike with in-memory caching
- Under-provisioned memory allocation

**Quick Fix:**
```bash
# Force task restart (clears memory)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --force-new-deployment
```

---

### Application Errors

#### [03 - High 5XX Error Rate](./03-high-5xx-error-rate.md)
**Trigger:** >10 HTTP 5XX errors in 5 minutes

**Common Causes:**
- Recent deployment with bugs
- External dependency failure
- Configuration error
- **Note:** `/error` endpoint always returns 500 (intentional for observability testing)

**Quick Fix:**
```bash
# Rollback to previous task definition
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:{previous-revision}
```

---

#### [04 - Unhealthy ECS Tasks](./04-unhealthy-ecs-tasks.md)
**Trigger:** <2 healthy targets in ALB

**Common Causes:**
- Tasks crashing on startup
- Health endpoint failing (`/health`)
- Tasks stuck in PENDING (image pull failure)
- Circuit breaker triggered

**Quick Fix:**
```bash
# Stop unhealthy tasks (ECS will replace)
aws ecs list-tasks \
  --cluster streaver-cluster-{env} \
  --service-name streaver-service-{env} \
  | jq -r '.taskArns[]' \
  | xargs -I {} aws ecs stop-task --cluster streaver-cluster-{env} --task {}
```

---

### Performance

#### [05 - High Response Time](./05-high-response-time.md)
**Trigger:** p99 latency >1 second for 5+ minutes

**Common Causes:**
- High traffic load (resource saturation)
- CPU throttling
- Slow external dependency
- Inefficient code path

**Quick Fix:**
```bash
# Scale out to distribute load
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count {current + 2}
```

---

### Deployments

#### [06 - Deployment Rollback](./06-deployment-rollback.md)
**Trigger:** Manual / Circuit Breaker

**When to Rollback:**
- 5XX errors increased post-deploy
- Health checks failing
- Performance degradation
- Circuit breaker triggered

**Quick Fix:**
```bash
# Rollback to previous revision
CURRENT=$(aws ecs describe-services --cluster streaver-cluster-{env} --services streaver-service-{env} --query 'services[0].taskDefinition' --output text | grep -oP '\d+$')
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:$((CURRENT - 1))
```

---

## General Troubleshooting Workflow

### Step 1: Assess Severity (30 seconds)

```bash
# Quick health check
curl -f http://{alb-dns}/health && echo "✓ Service responding" || echo "✗ Service down"

# Check target health
aws elbv2 describe-target-health --target-group-arn {tg-arn} | jq '.TargetHealthDescriptions[].TargetHealth.State'

# Check error rate (last 5 min)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

### Step 2: Check Recent Changes (1 minute)

```bash
# ECS deployments (last 24h)
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].events[:10]'

# CloudFormation stack changes
aws cloudformation describe-stack-events \
  --stack-name StreaverHelloWorldEcs-{env} \
  --max-items 10

# Git commits (last 24h)
cd ~/streaver-helloworld
git log --since="24 hours ago" --oneline
```

### Step 3: Review Logs (2 minutes)

```bash
# Application errors (last 15 min)
aws logs tail /ecs/streaver-cluster-{env} \
  --since 15m \
  --filter-pattern '{ $.level = "ERROR" }' \
  --format short

# Slow requests (>1s)
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '30 minutes ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, duration_ms, status
    | filter duration_ms > 1000
    | sort duration_ms desc
    | limit 20'
```

### Step 4: Apply Mitigation (5-15 minutes)

Refer to specific runbook for detailed steps.

### Step 5: Verify Resolution (5 minutes)

```bash
# Full smoke test
curl -f http://{alb-dns}/ && echo "✓ Home OK"
curl -f http://{alb-dns}/health && echo "✓ Health OK"
curl -f http://{alb-dns}/metrics && echo "✓ Metrics OK"

# Check all metrics normal
# - 0 5XX errors (or only from /error endpoint)
# - All targets healthy
# - p99 latency <500ms
# - CPU <70%, Memory <70%
```

---

## Common AWS CLI Commands

### ECS Service Management

```bash
# Get service status
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env}

# List running tasks
aws ecs list-tasks \
  --cluster streaver-cluster-{env} \
  --service-name streaver-service-{env}

# Stop a specific task
aws ecs stop-task \
  --cluster streaver-cluster-{env} \
  --task {task-arn} \
  --reason "Manual intervention"

# Update desired count
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count {new-count}

# Force new deployment
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --force-new-deployment
```

### ALB Target Health

```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn {target-group-arn}

# Describe target group
aws elbv2 describe-target-groups \
  --target-group-arns {target-group-arn}
```

### CloudWatch Metrics

```bash
# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace {namespace} \
  --metric-name {metric} \
  --dimensions Name={dim-name},Value={dim-value} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum

# List alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix StreaverHelloWorld
```

### CloudWatch Logs

```bash
# Tail logs (live)
aws logs tail /ecs/streaver-cluster-{env} --follow

# Tail with filter
aws logs tail /ecs/streaver-cluster-{env} \
  --since 15m \
  --filter-pattern '{ $.level = "ERROR" }'

# Logs Insights query
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string '{query-string}'
```

---

## Environment-Specific Details

### Development (dev)

- **Account:** 111111111111
- **Region:** us-east-1
- **Cluster:** streaver-cluster-dev
- **Service:** streaver-service-dev
- **ALB:** streaver-alb-dev
- **Tasks:** 1-2 (0.25 vCPU, 512MB)
- **Auto-scaling:** 70% CPU/Memory

### Certification (cert)

- **Account:** 222222222222
- **Region:** us-east-1
- **Cluster:** streaver-cluster-cert
- **Service:** streaver-service-cert
- **ALB:** streaver-alb-cert
- **Tasks:** 2-4 (0.5 vCPU, 1024MB)
- **Auto-scaling:** 70% CPU/Memory

### Production (prod)

- **Account:** 333333333333
- **Region:** us-east-1
- **Cluster:** streaver-cluster-prod
- **Service:** streaver-service-prod
- **ALB:** streaver-alb-prod
- **Tasks:** 3-10 (1 vCPU, 2048MB)
- **Auto-scaling:** 60% CPU/Memory

---

## Escalation Matrix

| Role | Contact Method | Escalation Trigger |
|------|----------------|-------------------|
| **On-call Engineer** | PagerDuty auto-page | Alarm triggered |
| **Application Team Lead** | Slack: #app-team | Issue not resolved in 15 min |
| **DevOps Lead** | Slack: #devops + Phone | Infrastructure issue |
| **Engineering Manager** | Email + Phone | Issue not resolved in 30 min |
| **VP Engineering** | Emergency contact | Outage >1 hour or major data loss |

---

## Post-Incident Process

### 1. Immediate Documentation (During Incident)

Create Slack thread in #incidents:
```
🚨 INCIDENT: {Short description}
- Severity: P{1/2/3}
- Started: {timestamp}
- Affected: {environment}
- On-call: @{engineer}
- Status: {investigating/mitigating/resolved}
```

### 2. Post-Mortem (Within 24 Hours)

Use template:
```markdown
## Incident Summary
- **Date/Time:** YYYY-MM-DD HH:MM UTC
- **Duration:** X minutes
- **Severity:** P{1/2/3}
- **Affected Environment:** {dev/cert/prod}

## Impact
- **Users Affected:** {number or percentage}
- **Requests Failed:** {count}
- **SLA Breach:** Yes/No

## Timeline
- [HH:MM] Alarm triggered
- [HH:MM] Investigation started
- [HH:MM] Root cause identified
- [HH:MM] Mitigation applied
- [HH:MM] Incident resolved
- [HH:MM] Monitoring confirmed stable

## Root Cause
{Detailed technical explanation}

## Resolution
{What was done to fix it}

## Action Items
- [ ] {Task} (Owner: @name, Due: YYYY-MM-DD)
- [ ] {Task} (Owner: @name, Due: YYYY-MM-DD)

## Lessons Learned
{What we learned, what we'll do differently}
```

### 3. Runbook Updates

If new learnings emerge:
- Update relevant runbook with new troubleshooting steps
- Add new error patterns to investigation section
- Document new mitigation techniques

---

## Testing Runbooks

**Recommendation:** Test runbooks quarterly in dev environment.

```bash
# Example: Test High CPU runbook
# 1. Generate load
docker run --rm -i grafana/k6 run --vus 100 --duration 5m - < tests/load/k6-load-test.js

# 2. Verify alarm triggers
aws cloudwatch describe-alarms --alarm-names StreaverHelloWorld-HighCPU-dev

# 3. Follow runbook steps
# 4. Document any gaps or improvements
```

---

## Contributing to Runbooks

When updating runbooks:

1. **Test changes** in dev environment first
2. **Update version number** at bottom of runbook
3. **Update "Last Tested" date**
4. **Get peer review** from another SRE
5. **Communicate changes** in Slack #devops

---

## Additional Resources

- **Main README:** [../../README.md](../../README.md)
- **Architecture Decisions:** [../../ASSUMPTIONS.md](../../ASSUMPTIONS.md)
- **Monitoring Setup:** [../../README.md#monitoring-and-observability](../../README.md#monitoring-and-observability)
- **Deployment Guide:** [../../README.md#deployment-with-aws-cdk](../../README.md#deployment-with-aws-cdk)

---

**Runbooks Version:** 1.0
**Last Updated:** 2026-03-03
**Next Review:** 2026-06-03
**Maintained By:** DevOps Team
