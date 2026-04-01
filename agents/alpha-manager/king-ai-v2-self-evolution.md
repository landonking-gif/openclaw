# King AI v2 Self-Evolution

The self-evolution system enables King AI v2 to continuously improve its own capabilities through autonomous learning, optimization, and strategic self-modification.

## Evolution Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   SELF-EVOLUTION ENGINE                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   OBSERVE   │───►│   ANALYZE   │───►│   PROPOSE   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                      │      │
│                    ┌─────────────────────────────────┘      │
│                    ▼                                       │
│           ┌─────────────┐                               │
│           │   REVIEW    │                               │
│           └──────┬──────┘                               │
│                  │                                       │
│         ┌────────┴────────┐                            │
│         ▼                 ▼                             │
│    ┌──────────┐      ┌──────────┐                      │
│    │ APPROVED │      │ REJECTED │                      │
│    └────┬─────┘      └──────────┘                      │
│         │                                                │
│         ▼                                                │
│    ┌──────────┐                                         │
│    │  DEPLOY  │                                         │
│    └──────────┘                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## The Evolution Loop

### Phase 1: Observe (Data Collection)

Continuous monitoring of system performance:

| Data Source | Frequency | Metrics |
|-------------|-----------|---------|
| **Task Execution** | Real-time | Success rate, duration, cost |
| **Business Outcomes** | Hourly | Revenue, conversions, NPS |
| **Agent Performance** | Per-task | Quality scores, error rates |
| **User Feedback** | Event-driven | Ratings, corrections, overrides |
| **System Logs** | Continuous | Exceptions, latencies, bottlenecks |

**Instrumentation:** Every action tagged with trace ID for full lineage.

### Phase 2: Analyze (Pattern Detection)

ML models identify optimization opportunities:

```python
class PerformanceAnalyzer:
    def detect_anomalies(self, window: TimeWindow) -> List[Anomaly]:
        """Find performance regressions"""
        
        # Compare current vs baseline
        baseline = self.get_baseline(window.baseline_period)
        current = self.get_metrics(window.current_period)
        
        anomalies = []
        for metric in baseline.keys():
            if self.is_significant_change(baseline[metric], current[metric]):
                anomalies.append(Anomaly(
                    metric=metric,
                    expected=baseline[metric],
                    actual=current[metric],
                    severity=self.calculate_severity(...)
                ))
        
        return anomalies
    
    def identify_improvements(self) -> List[Opportunity]:
        """Find optimization opportunities"""
        
        opportunities = []
        
        # Pattern 1: High-cost tasks
        for task in self.expensive_tasks():
            if self.could_caching_help(task):
                opportunities.append(CachingOpportunity(task))
        
        # Pattern 2: Repeated failures  
        for task in self.failing_tasks():
            if self.could_retry_fix(task):
                opportunities.append(RetryOpportunity(task))
        
        # Pattern 3: Model misselection
        for task in self.suboptimal_model_tasks():
            opportunities.append(ModelSwitchOpportunity(task))
        
        return opportunities
```

### Phase 3: Propose (Evolution Proposals)

Generate structured proposals for improvement:

**Proposal Types:**

| Type | Description | Scope | Risk |
|------|-------------|-------|------|
| **Prompt Optimization** | Improve system prompts | Single agent | Low |
| **Model Tuning** | Switch to better model for task class | Agent pool | Low |
| **Workflow Adjustment** | Change task routing logic | Manager | Medium |
| **New Capability** | Add integration or tool | System | Medium |
| **Structure Change** | Modify agent hierarchy | Platform | High |
| **Architecture Revision** | Core system changes | Platform | High |

**Proposal Format:**

```json
{
  "proposal_id": "evo-2026-03-09-001",
  "type": "model_tuning",
  "target": "coding-tasks",
  "current_state": {
    "model": "gpt-4o",
    "success_rate": 0.82,
    "avg_cost": 0.45
  },
  "proposed_state": {
    "model": "claude-opus-4",
    "expected_success_rate": 0.91,
    "expected_cost": 0.72
  },
  "rationale": "8% failure rate drop justifies 60% cost increase",
  "evidence": {
    "sample_size": 247,
    "p_value": 0.003,
    "confidence": 0.95
  },
  "risk_assessment": {
    "financial_impact": "+$0.27 per task",
    "rollback_time": "immediate",
    "blast_radius": "coding agents only"
  },
  "experiment_plan": {
    "duration": "7 days",
    "traffic_split": "10% treatment",
    "success_metric": "task completion rate",
    "guardrail": "cost per task < $1.00"
  }
}
```

### Phase 4: Review (Approval Flow)

Proposals go through the [[risk-approval-system]]:

**Auto-approved Proposals (Profile A):**
- Single-agent prompt improvements
- Model switches within same capability class
- Configuration tuning within safe bounds

**Conditional Proposals (Profile B):**
- Multi-agent workflow changes
- New tool integrations
- Cost model adjustments

**Human Required (Profile C):**
- Architecture changes
- Security-affecting changes
- Irreversible modifications

### Phase 5: Deploy (Gradual Rollout)

**Canary Deployment Pattern:**

```
Time    │ Traffic Split    │ Action
───────│──────────────────│──────────────────
Day 0   │ 0% → 0%          │ Proposal approved
Day 1   │ 0% → 5%          │ Initial canary
Day 2   │ 5% → 20%         │ Monitor metrics
Day 3   │ 20% → 50%        │ Expand if healthy
Day 4   │ 50% → 100%       │ Full rollout (if safe)
Day 5   │ 100% → 100%      │ Promote to baseline
```

**Automatic Rollback Triggers:**
- Success rate drop >5%
- Error rate increase >3x
- Latency p99 increase >50%
- Cost increase >2x projection
- Any critical alert

## Evolution History

Current system state tracks all evolutions:

| Date | Type | Description | Impact | Status |
|------|------|-------------|--------|--------|
| 2026-03-01 | Model Tuning | Switched coding tasks to Claude 4 | +12% success | Production |
| 2026-02-20 | Prompt Opt | Improved agent task instructions | -15% clarification requests | Production |
|