---
title: "System Documentation Index"
category: "indexes"
tags: ["clean-architecture", "nestjs", "dependency-injection", "cqrs", "system-design", "documentation-index"]
description: "Index document guiding developers and AI agents through system architecture documentation, including Clean Architecture principles, NestJS patterns, CQRS, and component creation guidelines"
last_updated: "2025-01-02"
---

# System Documentation Index

> **MANDATORY**: All developers and AI agents MUST read system documentation before design and implementation work.

## Overview

This directory contains critical system architecture documentation that defines how the application is structured, how components interact, and what patterns must be followed.

---

## System Architecture Documents

### [Application Design Guide](clean-architecture-nestjs.md)

**READ THIS BEFORE:**
- Designing system architecture or making architectural decisions
- Creating technical specifications or implementation plans
- Writing any application code (use cases, controllers, repositories)
- Generating code samples in documentation or stories
- Creating stories, tasks, or technical work items
- Implementing cross-module communication
- Setting up dependency injection for repositories or external APIs

**Key Content Areas:**

#### 1. Clean Architecture + Modular Principles
- Four-layer architecture (Enterprise, Application, Interface Adapters, Frameworks)
- Dependency direction rules (domain ← use cases ← controllers ← frameworks)
- Layer responsibilities and boundaries
- Mapping Clean Architecture concepts to NestJS components

#### 2. Project Structure
- Complete folder structure with purpose of each directory
- When to create new components (modules, use cases, commands, events)
- File organization patterns
- Shared vs module-specific components

#### 3. Dependency Injection Patterns
- **Repository Pattern:** Interface definitions, DI token constants, implementation injection
- **API Pattern:** External service abstractions, avoiding direct framework client usage
- **Critical Rule:** NEVER use string literals for DI tokens - always use constants
- Type-safe dependency injection for maintainability

#### 4. Request Flow Patterns
- **Pattern 1:** Controller → Use Case → Repository/API (simple operations)
- **Pattern 2:** Controller → Use Case → Command (shared logic)
- **Pattern 3:** Module → Command → Use Case (cross-module communication)
- Understanding what each pattern returns (Response Models vs Presenters)

#### 5. Use Case Return Types
- **For Controllers:** Return Response Models (formatted HTTP/gRPC responses)
- **For Commands:** Return Presenters (data transformation for cross-module use)
- Why this distinction matters for code reusability

#### 6. CQRS and Event Patterns
- **Commands:** Cross-module operations, shared business logic
- **Normal Events:** In-process communication within/across modules
- **Domain Events:** Automatic Kafka publishing for external systems
- When to use each pattern

#### 7. Component Creation Guidance
- When and how to create: modules, use cases, commands, events
- Request/Response models vs Presenters
- Repository interfaces vs implementations
- Shared entities vs module-specific domain objects

#### 8. Framework Guidelines
- NestJS CLI commands for scaffolding
- Manual component creation patterns
- Config module setup with validation
- Global module imports (avoid re-importing)

#### 9. Best Practices
- Index files for component arrays (`UseCases`, `CommandHandlers`, `EventHandlers`)
- Single controller per module (all transports: HTTP, Kafka, gRPC)
- File naming conventions
- TypeScript strict mode and type safety

**Why This Document is Critical:**

This guide ensures:
- ✅ **Architectural Consistency:** All code follows Clean Architecture principles
- ✅ **Maintainability:** Clear separation of concerns, easy to test and modify
- ✅ **Type Safety:** Proper DI token usage prevents runtime errors
- ✅ **Scalability:** Modular design supports growth without coupling
- ✅ **Team Alignment:** Everyone writes code the same way
- ✅ **AI Agent Accuracy:** Prevents common mistakes in code generation

**Common Mistakes Prevented:**
- ❌ Using string literals for DI tokens instead of constants
- ❌ Direct framework dependencies in use cases (Mongoose, KafkaClient)
- ❌ Confusion between Commands and Events
- ❌ Returning wrong types (Response Models in commands, Presenters in controllers)
- ❌ Creating multiple controllers per module
- ❌ Re-importing global modules in business modules
- ❌ Implementing shared logic in separate use cases instead of command handlers
- ❌ Direct framework dependencies in business modules

---

## Quick Reference

| Role | When to Read Application Design |
|------|--------------------------------|
| **Business Analyst** | Before creating technical specifications that involve system components |
| **Architect** | **MANDATORY** - Before any architecture work, creating designs, or code samples |
| **Developer** | **MANDATORY** - Before writing any code, especially modules, use cases, or repositories |
| **Scrum Master** | Before creating stories (to include correct standards in Task 1) |
| **Test Architect** | Before designing test architecture or writing code samples in test specs |
| **Technical Writer** | Before writing documentation with code samples or architectural diagrams |
| **UX Designer** | When designing features that require understanding of backend module structure |

---

## Related Documentation

For implementation details and coding standards, see:
- [Development Standards Index](../standards/index.md) - Coding style, error handling, testing
- [Backend Standards](../standards/backend/) - Error handling, logging, validation, use cases
- [Testing Standards](../standards/testing/) - Unit and E2E testing patterns
- [Global Standards](../standards/global/) - Comments, security, code quality

---

**Last Updated:** 2025-12-25
**Document Status:** ✅ Active
**Next Review:** 2026-01-25
