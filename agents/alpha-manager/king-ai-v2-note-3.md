# King AI v2 Playbooks

Playbooks are executable recipes for common business scenarios. They codify institutional knowledge and enable consistent execution.

## Playbook Structure

```yaml
playbook:
  name: "string"
  version: "1.0.0"
  category: "dropshipping|saas|content|service"
  estimated_duration: "hours|days|weeks"
  required_capabilities: ["shopify", "meta_ads", "stripe"]
  
  stages:
    - name: "stage_name"
      tasks: []
      gates: []
      
  rollback:
    enabled: true
    steps: []
```

---

## Dropshipping Playbook

### Overview
**Typical Timeline:** 30-45 days to first sale  
**Initial Investment:** $500-$2,000  
**Target Margins:** 30-50% after ads

### Stage 1: Product Research (Days 1-7)

**Objective:** Identify winning products with validated demand

| Task | Tool | Success Criteria |
|------|------|------------------|
| Trend analysis | Google Trends, TikTok Creative Center | Rising 90-day trend |
| Competitor research | Meta Ad Library, TikTok Top Ads | <20 established competitors |
| Supplier vetting | AliExpress, CJ Dropshipping | <7 day shipping, >4.8 rating |
| Margin calculation | Custom tool | >40% margin after COGS + $20 CAC |

**Risk Gate:** Product must pass [[risk-approval-system#Product Risk Assessment]]

### Stage 2: Store Setup (Days 8-14)

**Objective:** Build conversion-optimized storefront

```
1. Shopify store creation
   - Theme: Premium ($350) or Custom
   - Apps: Reviews, upsell, email capture
   - Payment: Stripe + Shop Pay
   
2. Product page optimization
   - Hero videos (TikTok style)
   - Benefit-driven copy
   - Urgency elements (stock, shipping)
   - Trust signals (guarantees, reviews)
   
3. Legal compliance
   - Refund policy
   - Privacy policy
   - Terms of service
```

### Stage 3: Marketing Launch (Days 15-30)

**Objective:** Achieve first sales and validate channels

| Channel | Budget | Target ROAS | Success Metric |
|---------|--------|-------------|----------------|
| TikTok Ads | $500 | 2.0 | First sale <7 days |
| Meta Ads | $500 | 1.5 | CPA <$25 |
| Influencer | $200 | N/A | 3+ posts with swipe-up |

**Daily Optimization Loop:**
```
09:00 ──► Pull overnight metrics
09:30 ──► Pause underperforming ad sets (ROAS <1.0)
10:00 ──► Scale winners (increase budget 20%)
15:00 ──► Check creative fatigue, refresh if CTR <1%
17:00 ──► Update forecasting model
```

### Stage 4: Operations (Ongoing)

**Automations:**
- Order routing to suppliers (webhook)
- Customer service responses (AI chatbot)
- Review requests (post-delivery email)
- Inventory alerts (low stock webhook)

---

## SaaS Playbook

### Overview
**Typical Timeline:** 60-90 days to MVP  
**Initial Investment:** $1,000-$5,000 (infrastructure)  
**Target Metrics:** 10% MoM growth, <$500 CAC

### Stage 1: Problem Validation (Days 1-14)

**Objective:** Confirm painful problem worth solving

**Customer Development Process:**
```
1. Identify 50 potential users
   - LinkedIn Sales Navigator
   - Industry forums
   - Competitor customer reviews (G2/Capterra)
   
2. Conduct 15 interviews
   - Screen for: Pain level, budget authority, tech sophistication
   - Questions focus on: Current workflow, pain points, willingness to pay
   
3. Validate willingness to pay
   - Pre-sell waitlist
   - Target: 10+ commitments at $50+/mo
```

**Risk Gate:** Requires [[risk-approval-system#Market Validation]] approval

### Stage 2: MVP Development (Days 15-45)

**Objective:** Build minimal viable product with core value delivery

**MVP Scope Framework:**
```python
# Include if:
- Required for first customer to get value ✓
- Differentiator from existing solutions ✓
- Can be built in <30 days ✓

# Exclude if:
- Nice-to-have feature ✗
- Complex edge case ✗
- Requires external dependencies ✗
```

**Tech Stack Recommendations:**

| Component | Recommended | Alternatives |
|-----------|-------------|--------------|
| Frontend | Next.js 14 | Vue + Nuxt |
| Backend | Node.js/Express | Python/FastAPI |
| Database | PostgreSQL | MySQL |
| Auth | Clerk | Auth0 |
| Payments | Stripe | Paddle |
| Hosting | Vercel | Railway |
| AI | OpenAI | Anthropic |

### Stage 3: Beta Launch (Days 46-60)

**Objective:** Onboard beta users and collect feedback

**Beta Program Structure:**
- **Size:** 20-50 users
- **Expectations:** Frequent feedback, reported bugs ok, 50% discount
- **Support:** Discord/Slack community, 4hr response time
- **Success Criteria:** 40%+ weekly active, NPS >40

### Stage 4: Public Launch (Days 61-90)

**Launch Channels:**
1. **Product Hunt** - Coordinate launch day, maker comments
2. **Hacker News** - Show HN post, technical angle
3. **LinkedIn** - Founder story, problem narrative
4. **Paid Ads** - LinkedIn + Google, gated content
5. **Content SEO** - Launch blog, documentation

**Pricing Strategy:**
```
Free Tier: Core features, limited usage
Starter: $29/mo - Individual users
Pro: $99/mo - Teams, advanced features
Enterprise: Custom - SOC2, SLA, support
```

---

## Playbook Execution

### Triggering Playbooks

Playbooks are triggered via the Master Brain API:

```bash
POST /api/v1/playbooks/execute
{
  "playbook_id": "dropshipping-v2.1",
  "business_unit_id": "bu-123",
  "context": {
    "budget": 2000,
    "target_market": "US",
    "product_category": "home_goods"
  }
}
```

### Monitoring Progress

Real-time playbook status is tracked in the database:

| Field | Type | Description |
|-------|------|-------------|
| current_stage | VARCHAR | Active stage name |
| stage_progress | FLOAT | 0.0-1.0 completion |
| blocked_by | UUID | Elevation request ID if waiting |
| next_deadline | TIMESTAMP | Stage SLA |
| metrics | JSONB | Stage-specific KPIs |

---
**Related:** [[business-lifecycle]] | [[integrations]] | [[database-schema]]
