---
title: "Error Handling Standards"
category: "backend"
tags: ["error-handling", "exceptions", "typescript", "nestjs", "best-practices"]
description: "Guidelines for handling errors in backend applications, including when to catch exceptions, rollback patterns, exception types, and anti-patterns to avoid."
last_updated: "2025-01-02"
---

# Error Handling Standards

> **Key Rule:** Let errors bubble to global handler. Only catch for specific recovery logic.

## Core Rules

| Rule | Requirement |
|------|-------------|
| Default | Let errors bubble to global exception handler |
| Try-catch | Only for rollback, recovery, or error transformation |
| Logging | Global handler logs automatically - no duplicate logging |
| Framework | NestJS exception filters |

## When to Let Errors Bubble (Default)

```typescript
// ✅ GOOD - Let global handler manage
async execute(id: string): Promise<HttpApiResponse<Entity>> {
  const entity = await this.repository.findById(id);
  if (!entity) {
    throw new ValidateException(ErrorCode.ENTITY_NOT_FOUND, `Entity ${id} not found`);
  }
  return HttpApiResponse.success(entity);
}
```

## When to Catch (Exceptions)

### 1. Rollback/Transaction Logic

```typescript
async execute(dto: CreateDto): Promise<HttpApiResponse<Entity>> {
  let entity: Entity | null = null;
  try {
    entity = await this.repository.create(dto);
    await this.externalService.deploy(entity);
    return HttpApiResponse.success(entity);
  } catch (error) {
    await this.rollback(entity, error as Error);
    throw error;  // ✅ Re-throw after rollback
  }
}

private async rollback(entity: Entity | null, error: Error): Promise<void> {
  this.logger.error(`Failed: ${error.message}. Rolling back...`);
  if (entity) {
    try {
      await this.repository.delete(entity.id);
    } catch (rollbackError) {
      this.logger.error(`Rollback failed: ${rollbackError['message']}`);
    }
  }
}
```

## Anti-Patterns

```typescript
// ❌ BAD - Catching just to log
try {
  await this.repository.create(dto);
} catch (error) {
  this.logger.error('Error creating');  // Global handler already logs!
  throw error;
}

// ❌ BAD - Swallowing errors
try {
  await this.service.process(event);
} catch (error) {
  this.logger.error('Failed');  // Error lost!
}
```

## Exception Types

| Type | HTTP | Use Case |
|------|------|----------|
| `ValidateException` | 400 | Input validation, business rule violations |
| `UnauthorizedException` | 401 | Authentication failures |
| `InternalException` | 500 | Infrastructure/external service failures |

## Best Practices

- User-friendly messages without exposing internals
- Fail fast with specific exception types
- Centralize handling at boundaries (controllers, filters)
- Log context: entity IDs, correlation IDs
- Never swallow errors silently

## Checklist

- [ ] No try-catch without specific recovery logic
- [ ] Rollback operations log but don't throw
- [ ] Original error re-thrown after rollback
- [ ] Correct exception type for HTTP status
- [ ] No duplicate logging (global handler logs)
