# Runbook: High CPU Utilization

**Alarm Name:** `StreaverHelloWorld-HighCPU-{environment}`
**Severity:** P2 (High)
**Auto-scaling:** Yes (scales out at >70% CPU)
**Last Updated:** 2026-03-03

---

## Overview

This runbook addresses situations where ECS Fargate tasks are consuming >80% CPU for an extended period (5+ minutes). While auto-scaling should mitigate this automatically, sustained high CPU can indicate underlying performance issues.

### Alarm Configuration

- **Metric:** `CPUUtilization` (ECS Service)
- **Threshold:** >80%
- **Evaluation Period:** 2 datapoints within 5 minutes
- **Action:** SNS notification to on-call team

---

## Impact Assessment

### Severity Matrix

| CPU % | Impact | Action Required |
|-------|--------|-----------------|
| 60-70% | Low - Auto-scaling triggered | Monitor |
| 70-80% | Medium - New tasks starting | Investigate |
| 80-90% | High - Service degradation possible | **Act immediately** |
| >90% | Critical - Service at risk | **Escalate** |

### User Impact

- **Latency:** Response times increase (p99 >1s likely)
- **Availability:** Tasks may become unresponsive
- **Auto-scaling lag:** 60s cooldown before new tasks start

---

## Triage (First 5 Minutes)

### Step 1: Confirm Current State

```bash
# Get current CPU utilization for all tasks
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].deployments[0].runningCount'

# Check CloudWatch metrics (last 15 minutes)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=streaver-service-{env} \
               Name=ClusterName,Value=streaver-cluster-{env} \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum
```

### Step 2: Check Auto-scaling Activity

```bash
# Verify if auto-scaling is responding
aws application-autoscaling describe-scaling-activities \
  --service-namespace ecs \
  --resource-id service/streaver-cluster-{env}/streaver-service-{env} \
  --max-results 10
```

### Step 3: Identify Traffic Patterns

```bash
# Check ALB request count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --dimensions Name=LoadBalancer,Value={alb-name} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

---

## Investigation

### Likely Causes

1. **Traffic spike** (most common)
   - Check ALB metrics for request count increase
   - Review application logs for unusual traffic patterns

2. **Inefficient code** (application bug)
   - CPU-intensive operations (regex, parsing, computation)
   - Infinite loops or recursion
   - Missing caching

3. **Insufficient resources** (under-provisioned)
   - Task CPU allocation too low (256, 512 in dev/cert)
   - Need to increase vCPU allocation

4. **External dependency latency**
   - Slow API calls causing request pileup
   - Thread/worker exhaustion waiting for I/O

### Diagnostic Commands

#### 1. View Application Logs (Last 15 Minutes)

```bash
# Check for errors or slow requests
aws logs tail /ecs/streaver-cluster-{env} \
  --follow \
  --since 15m \
  --format short \
  --filter-pattern '{ $.level = "ERROR" || $.duration_ms > 1000 }'
```

#### 2. Identify Slow Endpoints

```bash
# Query structured logs for high-duration requests
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, path, duration_ms, method
    | filter duration_ms > 500
    | sort duration_ms desc
    | limit 20'
```

#### 3. Check Task-Level CPU (Container Insights)

```bash
# Get per-task CPU breakdown
aws cloudwatch get-metric-statistics \
  --namespace ECS/ContainerInsights \
  --metric-name CpuUtilized \
  --dimensions Name=ClusterName,Value=streaver-cluster-{env} \
               Name=ServiceName,Value=streaver-service-{env} \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum
```

#### 4. Analyze Request Patterns

```bash
# Count requests by endpoint (from application logs)
aws logs insights query \
  --log-group-name /ecs/streaver-cluster-{env} \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields path
    | stats count() by path
    | sort count desc'
```

---

## Immediate Mitigation

### Option 1: Manual Scale-Out (if auto-scaling is slow)

```bash
# Increase desired count manually (emergency)
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count {current_count + 2} \
  --force-new-deployment
```

**Rollback:**
```bash
# Return to original count
aws ecs update-service \
  --cluster streaver-cluster-{env} \
  --service streaver-service-{env} \
  --desired-count {original_count}
```

### Option 2: Block Malicious Traffic (if DDoS suspected)

```bash
# Add IP to ALB security group deny list (temporary)
aws ec2 authorize-security-group-ingress \
  --group-id {alb-sg-id} \
  --ip-permissions IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges='[{CidrIp={malicious-ip}/32,Description="Blocked-DDoS"}]'
```

### Option 3: Enable AWS WAF Rate Limiting (if not enabled)

```bash
# This requires WAF to be pre-configured
# Activate rate-limiting rule
aws wafv2 update-web-acl \
  --scope REGIONAL \
  --id {web-acl-id} \
  --name streaver-waf-{env} \
  --rules file://rate-limit-rule.json
```

---

## Resolution

### Short-Term Fixes

#### 1. Verify Auto-scaling Works

```bash
# Check if tasks were added
aws ecs describe-services \
  --cluster streaver-cluster-{env} \
  --services streaver-service-{env} \
  --query 'services[0].[desiredCount,runningCount,pendingCount]'
```

#### 2. Monitor Until CPU Normalizes

- Watch CloudWatch dashboard
- Ensure CPU drops below 70% after scale-out
- Verify response times return to normal (p99 <500ms)

#### 3. Document Incident Timeline

```bash
# Export alarm history for post-mortem
aws cloudwatch describe-alarm-history \
  --alarm-name StreaverHelloWorld-HighCPU-{env} \
  --history-item-type StateUpdate \
  --start-date $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --max-records 50
```

### Long-Term Fixes

#### If Cause: Traffic Spike

1. **Review auto-scaling settings:**
   ```yaml
   # infrastructure/cdk/config/{env}.yaml
   autoscaling:
     cpu:
       target_utilization: 60  # Lower from 70% (more aggressive)
       scale_out_cooldown: 30  # Faster scale-out (from 60s)
   ```

2. **Increase max capacity:**
   ```yaml
   ecs:
     task:
       max_capacity: 15  # Increase from 10 (prod)
   ```

3. **Consider predictive scaling** (if traffic is predictable)

#### If Cause: Inefficient Code

1. **Profile application:**
   ```bash
   # Add cProfile to find bottlenecks
   python -m cProfile -o profile.stats app.py
   ```

2. **Add caching** for expensive operations
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def expensive_operation(param):
       # ...
   ```

3. **Optimize hot paths** identified in profiling

#### If Cause: Under-provisioned Resources

1. **Increase task CPU/memory:**
   ```yaml
   # infrastructure/cdk/config/prod.yaml
   ecs:
     task:
       cpu: 2048      # Increase from 1024
       memory: 4096   # Increase from 2048
   ```

2. **Deploy change:**
   ```bash
   cd infrastructure/cdk
   cdk deploy StreaverHelloWorldEcs-prod -c environment=prod
   ```

---

## Prevention

### Monitoring Improvements

1. **Add predictive alarm** (trend-based)
   ```bash
   # Create alarm for sustained 60%+ CPU (early warning)
   aws cloudwatch put-metric-alarm \
     --alarm-name StreaverHelloWorld-ModerateCPU-{env} \
     --metric-name CPUUtilization \
     --namespace AWS/ECS \
     --statistic Average \
     --period 300 \
     --evaluation-periods 3 \
     --threshold 60 \
     --comparison-operator GreaterThanThreshold
   ```

2. **Enable detailed Container Insights metrics**

### Code Improvements

1. **Add request timeout handling**
   ```python
   # app/main.py
   import signal

   def timeout_handler(signum, frame):
       raise TimeoutError("Request exceeded 30s")

   signal.signal(signal.SIGALRM, timeout_handler)
   signal.alarm(30)  # 30s timeout
   ```

2. **Implement circuit breaker** for external dependencies

3. **Add performance tests to CI/CD**
   ```yaml
   # .github/workflows/ci.yml
   - name: Performance test
     run: k6 run --vus 100 --duration 2m tests/load/k6-load-test.js
   ```

### Capacity Planning

1. **Regular load testing** (monthly)
2. **Review CloudWatch metrics trends** (weekly)
3. **Right-size resources** based on actual usage

---

## Escalation Path

| Timeline | Action | Contact |
|----------|--------|---------|
| 0-15 min | On-call engineer investigates | Auto-paged |
| 15-30 min | Engage application team lead | Slack: #app-team |
| 30-60 min | Escalate to engineering manager | Email + Phone |
| >60 min | Involve VP Engineering | Emergency contact |

---

## Related Runbooks

- [High Memory Utilization](./02-high-memory-utilization.md)
- [High Response Time](./05-high-response-time.md)
- [Unhealthy ECS Tasks](./04-unhealthy-ecs-tasks.md)

---

## Post-Incident

### Post-Mortem Template

```markdown
## Incident Summary
- **Date/Time:**
- **Duration:**
- **Severity:**
- **Root Cause:**

## Timeline
- [HH:MM] Alarm triggered
- [HH:MM] Investigation started
- [HH:MM] Mitigation applied
- [HH:MM] Incident resolved

## Impact
- **Users Affected:**
- **Requests Failed:**
- **SLA Breach:** Yes/No

## Root Cause Analysis
[Detailed technical explanation]

## Action Items
- [ ] Fix X (Owner: @name, Due: YYYY-MM-DD)
- [ ] Improve monitoring Y
- [ ] Update runbook
```

---

**Runbook Version:** 1.0
**Last Tested:** 2026-03-03
**Next Review:** 2026-06-03
