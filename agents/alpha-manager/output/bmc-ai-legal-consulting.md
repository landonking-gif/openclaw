# Business Model Canvas: AI Vertical SaaS
## Legal & Consulting Firms Automation Platform

**Document Version:** Phase 2 — Task 2.1  
**Workflow ID:** a56a7528-cd4  
**Date:** 2026-03-09  
**Prepared By:** Alpha Manager (ai_final Orchestration System)

---

## 1. Customer Segments

### Primary Segments

| Segment | Profile | Firm Size | Key Characteristics |
|---------|---------|-----------|---------------------|
| **Mid-Market Law Firms** | General practice, boutique specialists | 10–50 attorneys | Manual document workflows, billable hour pressure, compliance concerns, partnership decision-making |
| ** boutique Consultancies** | Strategy, operations, niche advisory | 5–25 people | Project-based billing, knowledge-intensive, client confidentiality, lean ops team |

### Segment Sizing
- **Targetable Law Firms (US):** ~12,000 firms (10–50 attorney range)
- **Targetable Consultancies (US):** ~45,000 firms (5–25 person range)
- **Combined Addressable Accounts:** ~57,000 entities

### Personas
1. **Managing Partner / Firm Owner** — Budget authority, ROI-focused
2. **Operations Director** — Day-to-day workflow pain, implementation lead
3. **Senior Associates** — Power users, productivity beneficiaries

---

## 2. Value Proposition

### Core Value: Industry-Aware AI Automation

**"AI that understands your practice, not just your documents"**

| Capability | Law Firms | Consultancies |
|------------|-----------|---------------|
| **Document Intelligence** | Contract review, clause extraction, precedent analysis | Proposal generation, SOW drafting, deliverable templates |
| **Workflow Automation** | Court deadline tracking, filing automation, billing integration | Project milestone tracking, client reporting, resource allocation |
| **Compliance Guardrails** | Attorney-client privilege detection, ethical wall enforcement, retention policies | NDA compliance, confidentiality classification, export controls |
| **Knowledge Management** | Case law synthesis, internal precedent search, expert identification | Methodology libraries, past engagement search, expertise mapping |

### Differentiation
- **Vertical-Specific Models:** Pre-trained on legal/regulatory and consulting frameworks (Porter's Five Forces, SWOT, etc.)
- **Role-Based UI:** Different experiences for partners vs. associates vs. ops
- **Zero-Config Onboarding:** Industry templates ready out-of-the-box

---

## 3. Channels

### Acquisition Channels

| Channel | Stage | CAC Contribution |
|---------|-------|------------------|
| **Industry Associations** | Primary | 25% (bar associations, consulting alliances) |
| **LinkedIn Outbound** | Primary | 35% (targeted ABM to ops directors) |
| **Referral Program** | Secondary | 15% (existing customer advocacy) |
| **Content/SEO** | Secondary | 20% (practice management blogs, whitepapers) |
| **Events/Webinars** | Tertiary | 5% (legal tech conferences, consulting summits) |

### Delivery Channels
- Web application (primary)
- Browser extensions (Chrome/Edge for document interaction)
- API access (for integration with existing practice management tools)
- Mobile companion (notifications, approvals)

---

## 4. Customer Relationships

| Relationship Type | Application |
|-------------------|-------------|
| **Self-Service** | Initial signup, small firm tier (<10 users) |
| **Assisted Onboarding** | Implementation package ($2,500), dedicated success manager |
| **Account Management** | Enterprise tier (25+ seats), quarterly business reviews |
| **Community** | Template marketplace, best practice sharing forums |
| **Support** | In-app chat, knowledge base, escalation to CS |

### Lifecycle Touchpoints
1. **Awareness:** Educational content on AI in professional services
2. **Consideration:** Free trial (14 days, 3 seats)
3. **Adoption:** 30-day implementation with template configuration
4. **Retention:** Monthly usage reports, workflow optimization reviews
5. **Expansion:** Seat additions, module upgrades

---

## 5. Revenue Streams

### Primary: Subscription SaaS

| Tier | Price | Target Segment |
|------|-------|----------------|
| **Starter** | $79/seat/month (<10 seats) | Solo practitioners, micro-consultancies |
| **Professional** | $69/seat/month (10–25 seats) | Mid-market firms, established consultancies |
| **Enterprise** | Custom pricing (25+ seats) | Large boutiques, multi-office firms |

### Secondary: Services & Add-ons

| Stream | Price | Description |
|--------|-------|-------------|
| **Implementation** | $2,500 one-time | Setup, template config, training, integrations |
| **Custom Model Training** | $5,000–$15,000 | Firm-specific fine-tuning on proprietary documents |
| **Priority Support** | $500/month | <2hr response, dedicated Slack channel |
| **API Overages** | $0.05/request | Beyond included 10K calls/month |

### Revenue Model Summary
- **Target ACV:** $9,480 ($79 × 10 seats × 12 months)
- **Target LTV:** $4,740 (based on 3-year retention assumption)
- **LTV/CAC Ratio:** 10.5x (healthy, well above 3x threshold)

---

## 6. Key Resources

### Intellectual Property
- Vertical-trained LLM weights (legal/consulting domain adaptation)
- Proprietary document parsers (contract clause extraction, framework detection)
- Template library (10,000+ industry-specific templates)

### Human Resources
- Engineering: Platform, ML, integrations (8 FTEs)
- Customer Success: Onboarding, support, expansion (4 FTEs)
- Sales: Industry specialists, SDRs (3 FTEs)
- Domain Experts: Retired partners (advisory, content curation)

### Technical Infrastructure
- GPU inference cluster (NVIDIA A100s)
- Document storage (tiered: hot SSD, cold S3)
- Multi-tenant SaaS platform (Kubernetes, auto-scaling)

---

## 7. Key Activities

### Core Operations
1. **Model Development:** Continuous fine-tuning, evaluation, safety testing
2. **Platform Engineering:** Uptime, security, integrations
3. **Customer Success:** Onboarding, adoption, retention
4. **Go-to-Market:** Industry marketing, sales development, partnerships

### Critical Path Activities
| Activity | Frequency | Owner |
|----------|-----------|-------|
| Model retraining on new case law/regulations | Monthly | ML Team |
| Security audits (SOC 2 Type II) | Annual | Security |
| Template marketplace curation | Weekly | Content |
| Customer health scoring | Daily | CS |
| Feature releases | Bi-weekly | Product |

---

## 8. Key Partnerships

### Strategic Partners

| Partner | Type | Value |
|---------|------|-------|
| **Clio / PracticePanther** | Integration | Practice management data sync |
| **Salesforce** | Integration | CRM connectivity for consultancies |
| **State Bar Associations** | Channel | Endorsement, member discounts |
| **Big 4 Advisory Alumni** | Advisory | Credibility, case study sources |
| **NVIDIA** | Infrastructure | GPU credits, technical support |

### API Dependencies
- OpenAI / Anthropic (base model inference, rate limits)
- Azure / AWS (compute, storage)
- Stripe (billing)

---

## 9. Cost Structure

### Fixed Costs

| Category | Monthly | Annual |
|----------|---------|--------|
| **Engineering** | $100,000 | $1.2M |
| **Sales & Marketing** | $50,000 | $600K |
| **Customer Success** | $30,000 | $360K |
| **G&A / Legal** | $20,000 | $240K |
| **Office / Infrastructure** | $15,000 | $180K |
| **Fixed Subtotal** | $215,000 | $2.58M |

### Variable Costs (Per-Account)

| Cost Driver | Unit Cost | At Scale |
|-------------|-----------|----------|
| **LLM API Costs** | $15/seat/month | $150/seat/year |
| **Cloud Infrastructure** | $8/seat/month | $80/seat/year |
| **Customer Acquisition (CAC)** | $450 one-time | — |
| **Onboarding (implementation)** | $800 one-time | — |
| **Support Burden** | $5/seat/month | $60/seat/year |
| **Variable Subtotal** | ~$33/month + $1,250 one-time | ~$290/year +