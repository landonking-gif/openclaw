# Agent Health Monitoring Template

**Template Version:** 1.0  
**Created:** 2026-03-18  
**For Use By:** All Managers (Alpha, Beta, Gamma)  
**Applies To:** All Worker Agents

---

## Overview

This template provides a standardized approach for monitoring worker agent health across the OpenClaw orchestration system. Use this template to create consistent health checks, status reports, and escalation procedures for your worker pool.

## Quick Status Report Format

```markdown
## Worker Health Summary — [Manager Name]
**Report Time:** [ISO-8601 timestamp]  
**Manager Port:** [e.g., 18800]  
**Worker Pool:** [e.g., general-1 through general-4]

| Worker | Port | Status | CPU | Memory | Response Time | Failures (24h) | Load |
|--------|------|--------|-----|--------|---------------|----------------|------|
| [name] | [port] | ✅🟡🔴 | [%] | [GB/%] | [ms] | [#] | [low/med/high] |

### Alerts
- [List any active alerts]

### Actions Taken
- [List any remediation actions]
```

---

## 1. Metrics & Thresholds

### 1.1 CPU Utilization

| Level | Threshold | Indicator | Action |
|-------|-----------|-----------|--------|
| ✅ Healthy | < 70% | Normal operations | None |
| 🟡 Warning | 70-85% | Elevated usage | Monitor closely, prepare scaling |
| 🔴 Critical | > 85% | Sustained high load | Investigate, consider restart |
| 🔴 Failure | > 95% | Process degradation | Immediate restart, escalate to King AI |

**Measurement:** Average CPU % over 5-minute window
**Collection Interval:** Every 30 seconds
**Retention:** 30 days

### 1.2 Memory Utilization

| Level | Threshold | Indicator | Action |
|-------|-----------|-----------|--------|
| ✅ Healthy | < 60% | Normal operations | None |
| 🟡 Warning | 60-75% | Elevated usage | Monitor, check for leaks |
| 🔴 Critical | 75-90% | Approaching limit | Trigger GC, reduce batch sizes |
| 🔴 Failure | > 90% / OOM | Memory exhaustion | Immediate restart, escalate to King AI |

**Measurement:** RSS memory usage vs. allocated limit
**Collection Interval:** Every 30 seconds
**Retention:** 30 days

#### Memory Leak Detection
```
IF memory_growth_rate > 5% per hour AND sustained for > 2 hours:
    → Mark worker as "suspect_leak"
    → Increase monitoring frequency to 60s
    → Alert manager after 3 hours
```

### 1.3 Response Time Benchmarks

| Metric | Target | Warning | Critical | Action on Breach |
|--------|--------|---------|----------|------------------|
| P50 (median) | < 2s | 2-5s | > 5s | Scale or investigate |
| P95 | < 5s | 5-10s | > 10s | Throttle, then scale |
| P99 | < 10s | 10-20s | > 20s | Emergency intervention |
| Timeout Rate | < 1% | 1-5% | > 5% | Immediate escalation |

**Measurement:** End-to-end request latency (Orchestrator submission → Worker completion)
**Collection:** Per-request logging
**Alerting:** Rolling 5-minute windows

### 1.4 Failure Rate Tracking

| Failures/Hour | Classification | Response |
|---------------|----------------|----------|
| 0 | ✅ Optimal | None |
| 1-3 | 🟡 Elevated | Log and monitor |
| 4-10 | 🔴 High | Investigate root cause |
| > 10 | 🔴 Critical | Remove from pool, escalate to King AI |

**Failure Types to Track:**
```
- API_4XX: Client/request errors (worker-side validation)
- API_5XX: Server/service errors (external service failures)
- TIMEOUT: Request timeout (worker or dependency timeout)
- CRASH: Process termination (unhandled exception)
- OOM: Out of memory kill
- PERM: Permission denied (elevation failure)
```

**Rolling Window:** Hourly aggregates, 24-hour trend

---

## 2. Health Check Procedures

### 2.1 Active Health Checks (From Manager)

```javascript
// Health check protocol (via sessions_send ping)
async function healthCheckWorker(workerId) {
  const startTime = Date.now();
  try {
    const response = await sessions_send({
      target: `agent:main:${workerId}`,
      message: "HEALTH_CHECK_PING",
      timeout: 5000
    });
    
    const latency = Date.now() - startTime;
    
    return {
      status: "healthy",
      latency,
      timestamp: new Date().toISOString(),
      details: response
    };
  } catch (error) {
    return {
      status: "unhealthy",
      latency: Date.now() - startTime,
      timestamp: new Date().toISOString(),
      error: error.message
    };
  }
}
```

**Frequency:** Every 30 seconds per worker
**Timeout:** 5 seconds
**Failure Threshold:** 3 consecutive failures = "down"

### 2.2 Passive Health Checks (From Workers)

Workers should report:
```json
{
  "type": "health_beacon",
  "worker_id": "general-1",
  "timestamp": "2026-03-18T14:30:00Z",
  "metrics": {
    "cpu_percent": 45.2,
    "memory_mb": 512,
    "memory_percent": 25.6,
    "active_requests": 3,
    "queue_depth": 1
  },
  "status": "ready"
}
```

**Beacon Frequency:** Every 60 seconds
**Manager Action on Missed Beacon:** Mark "stale" after 2 missed, "down" after 3

---

## 3. Automatic Escalation Procedures

### 3.1 Escalation Matrix

| Severity | Trigger | First Response | Second Response | Third Response |
|----------|---------|----------------|-----------------|----------------|
| 🟡 Low | Warning threshold breach | Manager logging | Increase monitoring | — |
| 🟠 Medium | Critical threshold breach | Manager intervention | Worker restart | Log incident |
| 🔴 High | Failure threshold breach | Remove from pool | Manager notification | Escalate to Manager Pool |
| 🔴 Critical | >50% pool down or cascading failure | Pool halt | Immediate King AI alert | Human intervention if applicable |

### 3.2 Automatic Actions by Severity

```yaml
severity_low:
  actions:
    - log_metrics
    - increase_monitoring_frequency: 15s
  manual_review: false
  timeout: 5 minutes

severity_medium:
  actions:
    - log_alert
    - reduce_load: throttle_new_requests
    - attempt_self_heal
  manual_review: within 15 minutes
  timeout: 15 minutes

severity_high:
  actions:
    - log_incident
    - drain_connections
    - restart_worker
    - shift_load_to_healthy_workers
  manual_review: immediate
  notify: manager

severity_critical:
  actions:
    - halt_pool
    - preserve_logs
    - notify: king-ai
    - notify: orchestrator
  manual_review: immediate
  human_loop: required if available
```

### 3.3 Circuit Breaker Pattern

When failure rate exceeds threshold:

```
1. Detect: Rolling 5-min window > 10% failures
2. Open Circuit: Stop sending new requests to worker
3. Half-Open: After 30s cooldown, send test request
4. Close Circuit: Test succeeds, resume normal operation
5. Open Again: Test fails, repeat cooldown (exponential backoff: 30s, 60s, 120s)
```

**Circuit States:**
- `CLOSED` — Normal operation
- `OPEN` — Worker bypassed
- `HALF_OPEN` — Testing recovery

---

## 4. Weekly Health Report Template

### Executive Summary
```markdown
### Worker Health — Week of [date]
**Manager:** [Name]  
**Workers Managed:** [N]  
**Uptime Target:** 99.5%  
**Actual Uptime:** [XX.X%]

#### Availability
| Worker | Uptime | Downtime | Restarts | Avg Response |
|--------|--------|----------|----------|--------------|
| [name] | 99.8% | 10 min | 2 | 1.2s |

#### Incident Summary
- [List of incidents with severity and resolution]

#### Resource Trends
- CPU: [increasing/decreasing/stable] — [notes]
- Memory: [trend] — [notes]
- Response Time: [trend] — [notes]

#### Recommendations
- [Action items for next week]
```

---

## 5. Integration Notes

### Required Tools
- `sessions_list` — Check active sessions
- `subagents(action="list")` — Audit spawned subagents
- `check_permissions(agent_name="...")` — Verify worker capabilities
- `session_status` — Get session metrics

### Recommended Cron Jobs
```json
{
  "name": "manager-health-report",
  "schedule": { "kind": "cron", "expr": "0