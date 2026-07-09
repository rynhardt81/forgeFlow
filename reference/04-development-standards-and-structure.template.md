# 04-development-standards-and-structure.md

**Development Standards & Code Structure**

> **Audience:** Engineers, Claude Code
> **Authority:** Master Source-of-Truth (Tier 2)
> **Persona:** Staff Engineer
> **Purpose:** Define how code is written

---

## 1. Purpose of This Document

This document defines **coding standards**, **project structure**, and **development practices**.

---

## 2. Code Organization

<!-- CUSTOMIZE: Define your project structure -->

```
project/
├── src/                    # Source code
│   ├── components/         # UI components (if applicable)
│   ├── services/           # Business logic
│   ├── models/             # Data models
│   ├── utils/              # Utilities
│   └── config/             # Configuration
├── tests/                  # Test files
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── docs/                   # Documentation
└── scripts/                # Build/deploy scripts
```

---

## 3. Coding Standards

### Naming Conventions

<!-- CUSTOMIZE: Define your naming rules -->

| Element | Convention | Example |
|---------|------------|---------|
| Files | [kebab-case] | `user-service.ts` |
| Classes | [PascalCase] | `UserService` |
| Functions | [camelCase] | `getUserById` |
| Constants | [SCREAMING_SNAKE] | `MAX_RETRIES` |
| Database | [snake_case] | `user_accounts` |

### Code Style

<!-- CUSTOMIZE: Define your style rules -->

| Rule | Standard |
|------|----------|
| Max line length | [100 characters] |
| Indentation | [2 spaces / 4 spaces / tabs] |
| Quotes | [single / double] |
| Semicolons | [always / never] |

### Linting & Formatting

```bash
# CUSTOMIZE: Your linting commands
npm run lint        # ESLint
npm run format      # Prettier
```

---

## 4. Git Workflow

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<description>` | `feature/user-auth` |
| Bug fix | `fix/<description>` | `fix/login-error` |
| Hotfix | `hotfix/<description>` | `hotfix/security-patch` |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

feat(auth): add password reset
fix(api): handle null response
docs(readme): update setup instructions
```

---

## 5. Testing Standards

### Test Organization

<!-- CUSTOMIZE: Your test structure -->

```
tests/
├── unit/                   # Fast, isolated tests
├── integration/            # Component interaction tests
└── e2e/                    # End-to-end tests
```

### Coverage Requirements

| Type | Minimum | Target |
|------|---------|--------|
| Unit | [60%] | [80%] |
| Integration | [40%] | [60%] |
| Critical paths | [90%] | [100%] |

---

## 6. Documentation Standards

All documentation must follow `.claude/standards/documentation-style.md`.

### Required Documentation

- [ ] README.md at project root
- [ ] API documentation for all endpoints
- [ ] Inline comments for complex logic
- [ ] ADRs for architectural decisions

---

## 7. Code Review Checklist

- [ ] Code follows naming conventions
- [ ] Tests included and passing
- [ ] No security vulnerabilities
- [ ] Documentation updated
- [ ] No unnecessary complexity

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | YYYY-MM-DD | [Author] | Initial version |
