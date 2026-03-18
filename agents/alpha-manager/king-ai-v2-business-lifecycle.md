# King AI v2 Business Lifecycle

The business lifecycle is the core state machine that governs how King AI v2 manages business operations. Each business passes through well-defined stages with clear entry/exit criteria.

## State Machine Overview

```
                    ┌─────────────┐
                    │   IDEATION  │
                    └──────┬──────┘
                           │ validates
                           ▼
                    ┌─────────────┐
         ┌─────────│  VALIDATION │─────────┐
         │         └──────┬──────┘         │
    fails │                │ succeeds       │ pivot
         │                ▼                │
         │         ┌─────────────┐       │
         └────────►│   LAUNCH    │◄──────┘
                   └──────┬──────┘
                          │ matures
                          ▼
                   ┌─────────────┐
              ┌───│   GROWTH    │───┐
              │   └──────┬──────┘   │
       stalls │          │ peaks     │ thrives
              │          ▼           │
              │   ┌─────────────┐   │
              └──►│   MATURE    │◄──┘
                  └──────┬──────┘
                         │ declines
                         ▼
                  ┌─────────────┐
                  │  SUNSET     │
                  └─────────────┘
```

## Stage Definitions

### 1. Ideation
**Purpose:** Generate and evaluate business concepts

| Aspect | Details |
|--------|---------|
| **Entry Triggers** | Manual creation, market opportunity detection, competitive gap analysis |
| **Activities** | Market research, competitor analysis, MVP scoping, financial modeling |
| **Duration** | 1-7 days typical |
| **Success Criteria** | Validated problem, identifiable customer, feasible solution |
| **Exit Triggers** | Validation approval, pivot decision, abandonment |

**Key Outputs:**
- Business model canvas
- Competitive landscape analysis
- Go-to-market strategy
- 90-day launch plan

### 2. Validation
**Purpose:** Test core assumptions before full investment

| Aspect | Details |
|--------|---------|
| **Entry Triggers** | Ideation approval |
| **Activities** | Landing page tests, waitlist building, user interviews, prototype testing |
| **Duration** | 14-30 days |
| **Success Criteria** | Market demand confirmed, unit economics viable, customer acquisition channels identified |
| **Exit Triggers** | Launch approval, pivot, or abandonment |

**Risk Gates:**
- Minimum 100 signups for digital products
- Minimum 10 customer interviews
- Unit economics must show path to profitability

### 3. Launch
**Purpose:** Execute go-to-market and achieve initial traction

| Aspect | Details |
|--------|---------|
| **Entry Triggers** | Validation success |
| **Activities** | Product development, marketing campaigns, sales operations, support setup |
| **Duration** | 30-90 days |
| **Success Criteria** | First revenue, 50+ active users, repeatable acquisition |
| **Exit Triggers** | Sustained growth, stagnation, or pivot |

**Launch Playbooks:**
- [[playbooks#Dropshipping Launch]]
- [[playbooks#SaaS Launch]]

### 4. Growth
**Purpose:** Scale operations and expand market presence

| Aspect | Details |
|--------|---------|
| **Entry Triggers** | Product-market fit signals |
| **Activities** | Channel expansion, team building, process automation, feature development |
| **Duration** | Ongoing until growth plateaus |
| **Success Criteria** | 20%+ MoM growth, <$X CAC, >$Y LTV |
| **Exit Triggers** | Growth stall, market saturation |

**Growth Metrics Dashboard:**
- MRR/ARR growth rate
- CAC payback period
- Net revenue retention
- Magic number (S&M efficiency)

### 5. Mature
**Purpose:** Optimize profitability and defend market position

| Aspect | Details |
|--------|---------|
| **Entry Triggers** | Growth plateau or market leadership |
| **Activities** | Cost optimization, efficiency improvements, incremental innovation |
| **Duration** | Indefinite |
| **Success Criteria** | Stable margins, strong cash flow, market position maintained |
| **Exit Triggers** | Market disruption, declining fundamentals |

**Optimization Priorities:**
1. Customer success (reduce churn)
2. Operational efficiency (reduce costs)
3. Incremental revenue (upsell/cross-sell)

### 6. Sunset
**Purpose:** Gracefully wind down the business

| Aspect | Details |
|--------|---------|
| **Entry Triggers** | Sustained decline, strategic exit, market disruption |
| **Activities** | Customer migration, asset liquidation, team transition, data archival |
| **Duration** | 30-180 days |
| **Success Criteria** | All obligations fulfilled, stakeholders compensated |
| **Exit Triggers** | Complete dissolution |

**Sunset Checklist:**
- [ ] Customer notification (60 days advance)
- [ ] Data export/migration
- [ ] Subscription cancellations
- [ ] Contract terminations
- [ ] Asset sale/transfer
- [ ] Final reporting

## Transition Triggers

Transitions between stages are triggered by specific events:

```python
class StageTransition:
    def can_transition(self, business_unit) -> bool:
        """Check if all criteria met for next stage"""
        return all([
            self.check_metrics(business_unit),
            self.check_risk_approval(business_unit),
            self.check_timeline(business_unit)
        ])
    
    def execute(self, business_unit) -> TransitionResult:
        """Perform the transition with rollback capability"""
        if not self.can_transition(business_unit):
            raise TransitionBlocked()
        
        # Execute transition hooks
        self.pre_transition(business_unit)
        self.update_state(business_unit)
        self.post_transition(business_unit)
        
        return TransitionResult(success=True, new_stage=self.target)
```

## Automated Monitoring

Each stage has automated health checks:

| Stage | Check Frequency | Key Metrics | Alert Threshold |
|-------|-----------------|-------------|-----------------|
| Ideation | Daily | Tasks completed, time in stage | >7 days |
| Validation | Daily | Signups, interviews, pre-sales | <10% target |
| Launch | Hourly | Revenue, users, support tickets | <50% revenue target |
| Growth | Hourly | Growth rate, CAC, churn | <10% MoM growth |
| Mature | Weekly | Margins, cash flow, market share | Margin compression |
| Sunset | Daily | Assets remaining, obligations | Outstanding items |

## Manual Overrides

King AI can force stage transitions via elevation request:

**Emergency Transitions:**
- **Fast-track launch** - Skip validation (requires human approval)
- **Emergency sunset** - Immediate wind-down (legal/compliance issues)
- **Stage hold** - Pause progression (due diligence, external factors)

---
**Related:** [[architecture-overview]] | [[playbooks]] | [[risk-approval-system]]
