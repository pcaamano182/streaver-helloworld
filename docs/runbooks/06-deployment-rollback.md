# Runbook: Deployment Rollback

**Trigger:** Manual / Circuit Breaker Auto-Rollback
**Severity:** P1 (Critical) - if production deployment fails
**Auto-mitigation:** Circuit breaker enabled (auto-rollback on failures)
**Last Updated:** 2026-03-03

---

## Overview

This runbook covers procedures for rolling back a failed deployment. ECS supports both automatic rollback (circuit breaker) and manual rollback procedures.

### When to Rollback

| Situation | Rollback? | Method |
|-----------|-----------|--------|
| 5XX errors increased post-deploy | Yes | Auto or manual |
| Health checks failing | Yes | Auto (circuit breaker) |
| Performance degradation | Yes | Manual |
| Feature not working as expected | Maybe | Manual (after assessment) |
| Minor UI bug | No | Forward fix |

---

## Circuit Breaker (Automatic Rollback)

### How It Works

The ECS circuit breaker monitors deployments and automatically rolls back if:

1. **Tasks fail to start** (>threshold)
2. **Health checks fail** repeatedly
3. **Essential container exits** with non-zero code

**Configuration:**
```python
# infrastructure/cdk/stacks/ecs_stack.py
circuit_breaker=ecs.DeploymentCircuitBreaker(
    rollback=True  # Enable auto-rollback
)
```

### Monitoring Auto-Rollback

```bash
# Watch deployment events
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].events[:20]' \
  --output table

# Check for circuit breaker messages:
# "deployment ... failed (circuit-breaker)"
# "rolling back to taskDefinition ..."
```

### Verify Rollback Completed

```bash
# Check deployment status
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].deployments[*].[status,rolloutState,taskDefinition]' \
  --output table

# Expected:
# PRIMARY deployment with COMPLETED status
# Old task definition active
```

---

## Manual Rollback Procedures

### Scenario 1: Rollback to Previous Task Definition

**Use when:** Recent deployment causing issues

```bash
# Step 1: Get current task definition revision
CURRENT_REV=$(aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].taskDefinition' \
  --output text | grep -oP '\d+$')

echo "Current revision: $CURRENT_REV"

# Step 2: Rollback to previous revision
PREVIOUS_REV=$((CURRENT_REV - 1))

aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:$PREVIOUS_REV \
  --force-new-deployment

# Step 3: Monitor rollback progress
watch -n 5 "aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[runningCount,desiredCount,deployments[0].rolloutState]' \
  --output table"
```

**Expected timeline:**
- 0-30s: New deployment starts
- 30s-2m: New tasks launching with old revision
- 2-5m: Old (problematic) tasks draining
- 5m+: Deployment complete

### Scenario 2: Rollback to Specific Known-Good Revision

**Use when:** Need to skip multiple bad revisions

```bash
# List recent task definition revisions
aws ecs list-task-definitions \
  --family-prefix streaver-helloworld-task-{env} \
  --sort DESC \
  --max-items 10

# Rollback to specific revision (e.g., revision 42)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:42
```

### Scenario 3: Rollback ECR Image Tag

**Use when:** Task definition unchanged but image is bad

```bash
# Step 1: Identify last known good image tag
aws ecr describe-images \
  --repository-name streaver-helloworld-{env} \
  --query 'imageDetails[*].[imageTags[0],imagePushedAt]' \
  --output table

# Step 2: Update task definition with good image tag
# Download current task definition
aws ecs describe-task-definition \
  --task-definition streaver-helloworld-task-{env} \
  --query 'taskDefinition' \
  > task-def-rollback.json

# Edit task-def-rollback.json:
# Change image to: {account}.dkr.ecr.{region}.amazonaws.com/streaver-helloworld-{env}:git-{good-sha}

# Register new task definition
aws ecs register-task-definition \
  --cli-input-json file://task-def-rollback.json

# Update service to use new revision
NEW_REV=$(aws ecs describe-task-definition --task-definition streaver-helloworld-task-{env} --query 'taskDefinition.revision' --output text)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --task-definition streaver-helloworld-task-{env}:$NEW_REV
```

### Scenario 4: Rollback Infrastructure Change (CDK)

**Use when:** IaC change caused issues

```bash
cd infrastructure/cdk

# Option A: Git revert
git log --oneline -10  # Find problematic commit
git revert {commit-sha}
git push origin main

# Option B: Redeploy previous state
git checkout {good-commit}
cdk deploy --all -c environment={env} --require-approval never
git checkout main  # Return to main after rollback

# Monitor stack update
aws cloudformation describe-stack-events \
  --stack-name StreaverHelloWorldEcs-{env} \
  --max-items 20
```

### Scenario 5: Emergency Stop (Zero Downtime)

**Use when:** Need to immediately stop all new traffic

```bash
# Option 1: Set desired count to 0 (FULL OUTAGE)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count 0

# Option 2: Drain ALB targets (graceful shutdown)
aws elbv2 modify-target-group \
  --target-group-arn {target-group-arn} \
  --health-check-interval-seconds 5 \
  --unhealthy-threshold-count 2

# Wait for unhealthy, then revert
```

---

## Rollback Verification

### Post-Rollback Checklist

```bash
# 1. Verify correct task definition active
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].taskDefinition'

# 2. All tasks healthy
aws elbv2 describe-target-health \
  --target-group-arn {target-group-arn} \
  --query 'TargetHealthDescriptions[?TargetHealth.State!=`healthy`]'

# Should return: []

# 3. No 5XX errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# 4. Response time normal
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --extended-statistics p99

# 5. Test critical endpoints
curl -f http://{alb-dns}/ && echo "✓ Home OK"
curl -f http://{alb-dns}/health && echo "✓ Health OK"
curl -f http://{alb-dns}/metrics && echo "✓ Metrics OK"
```

### Full Smoke Test

```bash
# Run automated smoke test suite
cd tests/load
docker run --rm -i grafana/k6 run --vus 5 --duration 30s - < k6-smoke-test.js

# Expected: 0 failed requests, p95 <500ms
```

---

## Prevention

### Pre-Deployment Checklist

Before ANY production deployment:

- [ ] Code reviewed by 2+ engineers
- [ ] All CI tests passing (unit, security, Docker build)
- [ ] Deployed and validated in dev environment
- [ ] Deployed and validated in cert environment
- [ ] Load tested in cert (k6 load test)
- [ ] Runbooks updated if new failure modes introduced
- [ ] Rollback plan documented
- [ ] On-call engineer aware of deployment

### Deployment Best Practices

#### 1. Canary Deployments (Future)

```yaml
# Future: AWS CodeDeploy canary
deployment_config:
  type: Canary10Percent5Minutes
  # 10% traffic → wait 5min → 100%
  # Auto-rollback on alarm
```

#### 2. Blue/Green Deployments

Already implemented via ECS deployment config:

```python
# infrastructure/cdk/stacks/ecs_stack.py
deployment_configuration=ecs.DeploymentConfiguration(
    maximum_percent=200,           # Blue + Green running
    minimum_healthy_percent=100,   # No downtime
)
```

#### 3. Feature Flags

```python
# app/main.py - Feature toggles

FEATURE_NEW_ENDPOINT = os.getenv('FEATURE_NEW_ENDPOINT', 'false') == 'true'

@app.route("/new-feature")
def new_feature():
    if not FEATURE_NEW_ENDPOINT:
        return jsonify({"error": "Feature not enabled"}), 404

    # New code
```

Deploy with feature disabled, enable gradually:
```bash
# Enable for 10% of tasks
aws ecs update-service \
  --cluster streaver-cluster-prod \
  --service streaver-service-prod \
  --deployment-configuration file://canary-config.json
```

#### 4. Automated Rollback Triggers

```bash
# Create CloudWatch alarm that triggers Lambda rollback
aws cloudwatch put-metric-alarm \
  --alarm-name StreaverHelloWorld-AutoRollback-prod \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 20 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:lambda:region:account:function:auto-rollback-function
```

### Deployment Windows

**Production deployments restricted to:**
- **Weekdays:** 10am - 4pm (business hours, team available)
- **Avoid:** Fridays after 2pm, weekends, holidays
- **Exception:** Critical security patches (requires approval)

### Deployment Communication

**Before deployment:**
```
# Slack: #deployments
@here Deploying streaver-helloworld v2.3.1 to PROD
- PR: https://github.com/.../pull/123
- Changes: Fix memory leak in /metrics endpoint
- Rollback plan: Revert to task def revision 87
- ETA: 5 minutes
```

**After deployment:**
```
# Slack: #deployments
✅ Deployment complete
- All 10 tasks healthy
- 0 errors in last 10 minutes
- p99 latency: 245ms (normal)
- Monitoring for 30 minutes
```

---

## Escalation Path

| Timeline | Action | Contact |
|----------|--------|---------|
| 0-5 min | Identify deployment issue | On-call engineer |
| 5-10 min | Initiate rollback | On-call action |
| 10-20 min | Verify rollback success | On-call verification |
| 20-40 min | If rollback fails: troubleshoot | DevOps lead |
| >40 min | Major incident | VP Engineering |

---

## Rollback Failure Scenarios

### Issue: Rollback Deployment Also Failing

**Symptom:** Previous revision also unhealthy

**Cause:** Infrastructure issue, not code

**Action:**
```bash
# Check for infrastructure changes in last 24h
cd infrastructure/cdk
git log --since="24 hours ago" --oneline

# Rollback infrastructure too
git revert {infra-commit}
cdk deploy --all -c environment={env}
```

### Issue: All Task Revisions Failing

**Symptom:** Even known-good revisions fail

**Cause:** Account/region issue, quota limits

**Action:**
```bash
# Check AWS service health
aws health describe-events --filter services=ecs,ec2

# Check account limits
aws service-quotas list-service-quotas \
  --service-code ecs \
  | grep -A 5 "tasks per service"

# Emergency: deploy to backup region
cd infrastructure/cdk
cdk deploy --all -c environment={env} --region us-west-2
```

### Issue: Database Migration Ran

**Symptom:** Code rollback causes DB schema mismatch

**Cause:** Non-backwards-compatible migration

**Action:**
```bash
# Option 1: Rollback migration (if possible)
# (Requires migration tooling)

# Option 2: Deploy hotfix with compatibility layer
# (Add code that handles both old and new schema)

# Option 3: Forward fix only
# (Do not rollback, fix issue in new version)
```

---

## Post-Rollback Actions

### Immediate (Within 1 hour)

- [ ] Document what went wrong (Slack thread or ticket)
- [ ] Notify stakeholders deployment was rolled back
- [ ] Ensure service is stable (monitor for 1 hour)
- [ ] Create Jira ticket for root cause fix

### Short-term (Within 24 hours)

- [ ] Root cause analysis meeting
- [ ] Create post-mortem document
- [ ] Identify preventive measures
- [ ] Update CI/CD pipeline if needed
- [ ] Add regression test for the bug

### Long-term (Within 1 week)

- [ ] Share post-mortem with team
- [ ] Implement preventive measures
- [ ] Update runbooks with new learnings
- [ ] Consider process changes (code review, testing)

---

## Related Runbooks

- [High 5XX Error Rate](./03-high-5xx-error-rate.md)
- [Unhealthy ECS Tasks](./04-unhealthy-ecs-tasks.md)
- [High CPU Utilization](./01-high-cpu-utilization.md)

---

## Common Pitfalls

1. **Don't panic:** Rollbacks are normal, stay calm
2. **Document first:** Capture current state before rollback
3. **Communicate:** Keep team informed via Slack
4. **Test rollback:** Verify in dev/cert environments periodically
5. **Post-mortem:** Always do post-mortem, even for quick rollbacks

---

**Runbook Version:** 1.0
**Last Tested:** 2026-03-03
**Next Review:** 2026-06-03
