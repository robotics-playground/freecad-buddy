---
title: "Development Standards Index"
category: "indexes"
tags: ["development", "standards", "guidelines", "best-practices", "coding-standards", "team-roles"]
description: "Comprehensive index of mandatory development standards organized by team role, covering backend, frontend, testing, and global standards with quick lookup references"
last_updated: "2025-01-02"
---

# Development Standards Index

> **MANDATORY**: All developers and AI agents MUST follow these standards.

## Standards by Role

### All Roles (MANDATORY)
Everyone must read this index file before starting any work.

### Business Analyst / Product Manager
| Standard | When to Read |
|----------|--------------|
| [security](global/security.md) | Before creating requirements with security implications |

### Architect
| Standard | When to Read |
|----------|--------------|
| [coding-style](backend/coding-style.md) | Before creating architecture with code samples |
| [error-handling](backend/error-handling.md) | Before designing error handling patterns |
| [logging](backend/logging.md) | Before designing logging architecture |
| [validation](backend/validation.md) | Before designing validation patterns |
| [unit-testing](testing/unit-testing.md) | Before defining test strategy |
| [e2e-testing](testing/e2e-testing.md) | Before defining test strategy |
| [security](global/security.md) | Before designing security architecture |

### Developer / Solo Dev
| Standard | When to Read |
|----------|--------------|
| [coding-style](backend/coding-style.md) | Before writing any code |
| [error-handling](backend/error-handling.md) | Before implementing error handling |
| [logging](backend/logging.md) | Before adding any logging |
| [validation](backend/validation.md) | Before implementing validation |
| [commenting](global/commenting.md) | Before adding any comments |
| [unit-testing](testing/unit-testing.md) | Before writing unit tests |
| [e2e-testing](testing/e2e-testing.md) | Before writing E2E tests |

### Scrum Master
| Standard | When to Read |
|----------|--------------|
| This index file | Before creating stories (to include Task 1 with required standards) |

### Test Architect
| Standard | When to Read |
|----------|--------------|
| [unit-testing](testing/unit-testing.md) | Before designing test architecture |
| [e2e-testing](testing/e2e-testing.md) | Before designing test architecture |
| [coding-style](backend/coding-style.md) | Before writing code samples in test specs |

### Technical Writer
| Standard | When to Read |
|----------|--------------|
| [commenting](global/commenting.md) | Before creating documentation |
| [coding-style](backend/coding-style.md) | Before writing code samples in documentation |

### UX Designer
| Standard | When to Read |
|----------|--------------|
| [accessibility](frontend/accessibility.md) | Before creating UX designs |
| [components](frontend/components.md) | Before designing UI components |
| [css](frontend/css.md) | Before defining styles |
| [responsive](frontend/responsive.md) | Before designing layouts |

---

## Backend Standards

### Mandatory

| Standard | Key Points |
|----------|-----------|
| [coding-style](backend/coding-style.md) | PascalCase classes, camelCase functions, SOLID, <100 lines |
| [error-handling](backend/error-handling.md) | No try-catch for logging, let errors bubble |
| [logging](backend/logging.md) | NestJS Logger, minimal logging |
| [error-codes](backend/error-codes.md) | -300xxx range, SUBJECT_REASON pattern |
| [usecases](backend/usecases.md) | CQRS, HttpApiResponse<T>, rollback pattern |
| [domain-events](backend/domain-events.md) | Centralized handler, WNE codes, EventBus.publish() |
| [kafka](backend/kafka.md) | Auto offsets, let errors propagate |
| [telemetry](backend/telemetry.md) | Framework first, explicit requirements only |
| [validation](backend/validation.md) | ErrorCode context required, @ValidateNested + @Type |

### Design Patterns

| Pattern | When to Use | Key Points |
|---------|-------------|-----------|
| [Factory Pattern](backend/design-pattern-factory.md) | Multiple strategies, O(1) selection | Symbol token, Map registry, mandatory default fallback |
| [Factory + Explorer](backend/design-pattern-factory-and-explorer.md) | Auto-discovery, event routing | Custom decorator, reflection metadata, bootstrap lifecycle |
| [Chain of Responsibility](backend/design-pattern-chain-of-repository.md) | Sequential enrichment, repository chain | Clone pattern, data accumulation, fluent interface |

### Best Practices

| Standard | Key Points |
|----------|-----------|
| [api](backend/api.md) | RESTful, plural nouns, versioning |
| [models](backend/models.md) | Timestamps, indexes, constraints |
| [queries](backend/queries.md) | Parameterized, avoid N+1 |
| [migrations](backend/migrations.md) | Reversible, small, focused |

## Testing Standards

| Standard | Key Points |
|----------|-----------|
| [unit-testing](testing/unit-testing.md) | @golevelup/ts-jest, mongodb-memory-server, 80% coverage |
| [e2e-testing](testing/e2e-testing.md) | Replicate main.ts, --runInBand, 8s Kafka waits |

## Global Standards

| Standard | Key Points |
|----------|-----------|
| [commenting](global/commenting.md) | Zero-tolerance obvious comments, minimal JSDoc |
| [security](global/security.md) | No hardcoded secrets, OWASP Top 10 |
| [code-quality](global/code-quality.md) | Type safety, DI, SOLID |
| [conventions](global/conventions.md) | Project structure, version control |

## Frontend Standards (Best Practices)

| Standard | Key Points |
|----------|-----------|
| [components](frontend/components.md) | Single responsibility, minimal props |
| [css](frontend/css.md) | Consistent methodology, design tokens |
| [accessibility](frontend/accessibility.md) | Semantic HTML, 4.5:1 contrast |
| [responsive](frontend/responsive.md) | Mobile-first, 44x44px touch targets |

### Other Requirements

1. **Standards References Section** - Link applicable standards with specific requirements
2. **Conflict Check** - Flag standards conflicts before implementation
3. **Testing** - Unit & E2E tests required (exclude performance/security/load tests)
4. **Infrastructure** - No IaC changes in feature stories (architecture team handles)

## Quick Lookup

| Question | Standard |
|----------|----------|
| Should I log this? | [logging](backend/logging.md) |
| Do I need try-catch? | [error-handling](backend/error-handling.md) |
| How to name this? | [coding-style](backend/coding-style.md) |
| How to structure tests? | [unit-testing](testing/unit-testing.md) / [e2e-testing](testing/e2e-testing.md) |
| What error code? | [error-codes](backend/error-codes.md) |
| How to validate? | [validation](backend/validation.md) |
| Multiple strategies/implementations? | [Factory Pattern](backend/design-pattern-factory.md) |
| Need auto-discovery with decorators? | [Factory + Explorer](backend/design-pattern-factory-and-explorer.md) |
| Sequential data enrichment? | [Chain of Responsibility](backend/design-pattern-chain-of-repository.md) |
