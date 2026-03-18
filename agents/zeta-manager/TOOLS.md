# TOOLS.md - Zeta Manager Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:
- Cloud account IDs and regions
- SSH bastion hosts and jump boxes
- Dashboard URLs (Datadog, Grafana, CloudWatch)
- Secret manager endpoints
- Infrastructure-as-Code repositories
- On-call escalation contacts
- SLI/SLO thresholds

## Infrastructure Registry

### Cloud Accounts
*Add as discovered:*
- AWS: account-id / region / profile
- GCP: project-id / zone
- Azure: subscription / region

### Monitoring Endpoints
*Add as configured:*
- Prometheus: URL
- Grafana: URL
- CloudWatch: Console URL
- DataDog: Org URL

### Secret Managers
*Add as configured:*
- HashiCorp Vault: URL / namespace
- AWS Secrets Manager: region
- GitHub Secrets: repo list

### IaC Repositories
*Add as discovered:*
- Terraform state backend
- Pulumi stacks
- CloudFormation templates

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your operational cheat sheet.

## Runbooks

*Add templates here for common scenarios:*

### Incident Response Template
1. Acknowledge the alert
2. Assess impact (who/what is affected)
3. Mitigate (stop the bleeding)
4. Investigate (root cause analysis)
5. Document (postmortem)

### Deployment Rollback
1. Check last known good commit
2. Initiate rollback procedure
3. Verify rollback success
4. Notify stakeholders
5. Schedule fix-forward planning

### Cost Spike Response
1. Identify the service/account causing spike
2. Check for anomalous usage patterns
3. Determine if scale is legitimate or runaway
4. Apply cost controls if needed
5. Alert and document
