# 07-non-functional-requirements.md

**Non-Functional Requirements (NFRs)**

> **Audience:** Engineers, architects, QA
> **Authority:** Master Source-of-Truth (Tier 2)
> **Persona:** Principal Engineer
> **Purpose:** Define quality constraints

---

## 1. Purpose of This Document

This document defines **non-functional requirements** (quality attributes) that the system must meet.

📌 These are **critical constraints**. Features that violate NFRs should not be shipped.

---

## 2. Performance Requirements

<!-- CUSTOMIZE: Define your performance targets -->

### Response Time

| Endpoint Type | Target | Maximum |
|---------------|--------|---------|
| Read operations | [100ms] | [500ms] |
| Write operations | [200ms] | [1000ms] |
| Search/query | [300ms] | [2000ms] |

### Throughput

| Metric | Target |
|--------|--------|
| Requests/second | [1000] |
| Concurrent users | [500] |
| Peak load handling | [2x normal] |

---

## 3. Reliability Requirements

### Availability

| Environment | Target | Measurement |
|-------------|--------|-------------|
| Production | [99.9%] | [Monthly] |
| Staging | [99%] | [Weekly] |

### Recovery

| Metric | Target |
|--------|--------|
| RTO (Recovery Time Objective) | [1 hour] |
| RPO (Recovery Point Objective) | [15 minutes] |
| MTTR (Mean Time To Recovery) | [30 minutes] |

---

## 4. Scalability Requirements

<!-- CUSTOMIZE: Define scalability needs -->

### Horizontal Scaling

| Component | Min | Max | Scale Trigger |
|-----------|-----|-----|---------------|
| API servers | [2] | [10] | [CPU > 70%] |
| Workers | [1] | [5] | [Queue depth > 100] |

### Data Growth

| Data Type | Current | 1 Year | 3 Year |
|-----------|---------|--------|--------|
| Users | [10K] | [100K] | [1M] |
| Records | [1M] | [10M] | [100M] |

---

## 5. Security Requirements

See `03-security-auth-and-access.md` for detailed security requirements.

### Summary

| Requirement | Target |
|-------------|--------|
| Data encryption | [AES-256 at rest, TLS 1.3 in transit] |
| Authentication | [Multi-factor for admin, token-based for API] |
| Audit logging | [All write operations, auth events] |

---

## 6. Maintainability Requirements

### Code Quality

| Metric | Target |
|--------|--------|
| Test coverage | [80%] |
| Technical debt ratio | [< 5%] |
| Documentation coverage | [90%] |

### Deployment

| Metric | Target |
|--------|--------|
| Deployment frequency | [Daily capable] |
| Deployment time | [< 15 minutes] |
| Rollback time | [< 5 minutes] |

---

## 7. Usability Requirements

<!-- CUSTOMIZE: Define usability standards -->

### Performance Perception

| Metric | Target |
|--------|--------|
| First Contentful Paint | [< 1.8s] |
| Time to Interactive | [< 3.9s] |
| Cumulative Layout Shift | [< 0.1] |

### Accessibility

| Standard | Compliance |
|----------|------------|
| WCAG | [2.1 AA] |
| Screen reader | [Fully supported] |
| Keyboard navigation | [All features] |

---

## 8. Compliance Requirements

<!-- CUSTOMIZE: List applicable compliance -->

| Standard | Applicable | Status |
|----------|------------|--------|
| GDPR | [Yes/No] | [Status] |
| SOC2 | [Yes/No] | [Status] |
| ISO 27001 | [Yes/No] | [Status] |

---

## 9. Capacity Planning

### Resource Limits

| Resource | Soft Limit | Hard Limit |
|----------|------------|------------|
| CPU per service | [70%] | [90%] |
| Memory per service | [80%] | [95%] |
| Disk usage | [70%] | [90%] |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | YYYY-MM-DD | [Author] | Initial version |
