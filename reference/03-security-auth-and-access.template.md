# 03-security-auth-and-access.md

**Security, Authentication & Access Control**

> **Audience:** Security team, engineers, Claude Code
> **Authority:** Master Source-of-Truth (Tier 2)
> **Persona:** Security Architect
> **Purpose:** Define the security contract

---

## 1. Purpose of This Document

This document defines **security policies**, **authentication**, and **access control**.

📌 This is a **critical document**. Security requirements override convenience.

---

## 2. Authentication

<!-- CUSTOMIZE: Define your auth approach -->

### Authentication Methods

| Method | Use Case | Implementation |
|--------|----------|----------------|
| [JWT] | [API access] | [Details] |
| [API Keys] | [Service-to-service] | [Details] |
| [OAuth2] | [Third-party login] | [Details] |

### Token Management

<!-- CUSTOMIZE: Token policies -->

| Token Type | Expiration | Refresh Policy |
|------------|------------|----------------|
| Access Token | [1 hour] | [Via refresh token] |
| Refresh Token | [30 days] | [Single use] |

---

## 3. Authorization

<!-- CUSTOMIZE: Define your authz model -->

### Authorization Model
[e.g., RBAC, ABAC, or hybrid]

### Roles

| Role | Permissions | Description |
|------|-------------|-------------|
| [Admin] | [All] | [Full access] |
| [User] | [Read, Write own] | [Standard user] |

---

## 4. Data Security

### Data Classification

| Classification | Examples | Protection |
|----------------|----------|------------|
| Public | [Marketing content] | [None required] |
| Internal | [Logs, metrics] | [Auth required] |
| Confidential | [User data] | [Encrypted, access-logged] |
| Secret | [Credentials] | [Vault, rotation] |

### Encryption

| Data State | Method |
|------------|--------|
| At Rest | [AES-256] |
| In Transit | [TLS 1.3] |

---

## 5. Security Requirements

<!-- CUSTOMIZE: List your security requirements -->

### Must Have
- [ ] All endpoints require authentication
- [ ] Passwords hashed with bcrypt/argon2
- [ ] All PII encrypted at rest
- [ ] Audit logging enabled

### Should Have
- [ ] Rate limiting on all endpoints
- [ ] MFA support
- [ ] IP allowlisting option

---

## 6. Compliance

<!-- CUSTOMIZE: List applicable compliance -->

| Standard | Applicable | Status |
|----------|------------|--------|
| GDPR | [Yes/No] | [Status] |
| SOC2 | [Yes/No] | [Status] |
| HIPAA | [Yes/No] | [Status] |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | YYYY-MM-DD | [Author] | Initial version |
