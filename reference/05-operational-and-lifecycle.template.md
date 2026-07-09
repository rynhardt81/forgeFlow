# 05-operational-and-lifecycle.md

**Operational Procedures & System Lifecycle**

> **Audience:** Operations, SRE, DevOps
> **Authority:** Master Source-of-Truth (Tier 2)
> **Persona:** Site Reliability Engineer
> **Purpose:** Define how the system runs

---

## 1. Purpose of This Document

This document defines **operational procedures**, **deployment**, and **monitoring**.

---

## 2. Environments

<!-- CUSTOMIZE: Define your environments -->

| Environment | Purpose | URL |
|-------------|---------|-----|
| Development | Local development | `localhost` |
| Staging | Pre-production testing | [staging URL] |
| Production | Live system | [production URL] |

---

## 3. Deployment

### Deployment Process

<!-- CUSTOMIZE: Your deployment steps -->

```bash
# Build
npm run build

# Deploy to staging
npm run deploy:staging

# Deploy to production
npm run deploy:prod
```

### Deployment Checklist

- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Database migrations ready — paired with rollback, backup verified (`rules/migrations.md`)
- [ ] Rollback command identified AND verified runnable for this deploy target (`rules/release-engineering.md`)
- [ ] Feature-flag inventory below checked — nothing dormant wakes unintentionally

### Feature Flag Inventory

<!-- Every dormant capability (paywall, hidden flow, staged feature) is a flag. Keep this table current — flipping a flag IS a release. -->

| Flag / dormant capability | Current state | Flip condition | Rollback (flip-back verified?) | Owner |
|---|---|---|---|---|
| [example: paywall] | [dormant] | [≥N installs / metric threshold] | [yes/no] | [name] |

---

## 4. Monitoring & Alerting

> Discipline: `rules/observability.md` defines the metrics taxonomy (four golden signals / RED) this section's per-project targets should populate. Fill the tables below with your stack's actual metrics and thresholds.

### Metrics

<!-- CUSTOMIZE: Key metrics to monitor -->

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Response time | [< 200ms] | [> 500ms] |
| Error rate | [< 0.1%] | [> 1%] |
| Uptime | [99.9%] | [< 99.5%] |

### Monitoring Tools

| Tool | Purpose | Dashboard |
|------|---------|-----------|
| [Prometheus] | [Metrics] | [URL] |
| [Grafana] | [Visualization] | [URL] |
| [PagerDuty] | [Alerting] | [URL] |

---

## 5. Logging

> Discipline: `rules/observability.md` defines the structured-logging floor (JSON, correlation IDs, level discipline, no PII). The levels and format below are this project's concrete instantiation of that floor.

### Log Levels

| Level | When to Use |
|-------|-------------|
| ERROR | System failures, requires attention |
| WARN | Unexpected but handled |
| INFO | Normal operations |
| DEBUG | Development debugging |

### Log Format

```json
{
  "timestamp": "ISO-8601",
  "level": "INFO",
  "service": "service-name",
  "message": "Log message",
  "context": {}
}
```

---

## 6. Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P1 | System down | [15 min] |
| P2 | Major feature broken | [1 hour] |
| P3 | Minor issue | [24 hours] |
| P4 | Cosmetic | [Best effort] |

### Escalation Path

<!-- CUSTOMIZE to your actual team size. For a solo/small team this is typically:
     1. You (triage via /triage-incident)
     2. Platform support (Supabase/Vercel/store) when the fault is theirs
     Fictional org-chart ladders help nobody in an incident. -->

1. [Who triages — for solo projects: you, via `/triage-incident`]
2. [Who/what you escalate to when the fault is upstream — platform support, ISP, payment provider]

---

## 7. Backup & Recovery

### Backup Schedule

| Data | Frequency | Retention |
|------|-----------|-----------|
| Database | [Daily] | [30 days] |
| Files | [Weekly] | [90 days] |

### Recovery Procedures

<!-- CUSTOMIZE: Recovery steps -->

1. Identify scope of data loss
2. Restore from most recent backup
3. Verify data integrity
4. Update stakeholders

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | YYYY-MM-DD | [Author] | Initial version |
