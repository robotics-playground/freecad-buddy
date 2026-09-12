---
title: 'Backend Coding Style Standards'
category: 'backend'
tags: ['typescript', 'nestjs', 'solid-principles', 'naming-conventions', 'code-quality']
description: 'Comprehensive coding style guidelines for backend development including naming conventions, SOLID principles, TypeScript best practices, and formatting rules'
last_updated: '2026-01-13'
---

# Coding Style Standards

> **Philosophy:** Write readable, maintainable code. Follow SOLID. Favor composition over complexity.

## Naming Conventions

| Type        | Pattern              | Example                                   |
| ----------- | -------------------- | ----------------------------------------- |
| Classes     | PascalCase noun      | `DeviceStateRepository`, `AlertEvaluator` |
| Functions   | camelCase verb       | `evaluateAlert`, `transformToMetrics`     |
| Variables   | camelCase noun       | `deviceState`, `maxRetryAttempts`         |
| Constants   | UPPER_SNAKE_CASE     | `MAX_RETRY_ATTEMPTS`, `DEFAULT_TIMEOUT`   |
| Booleans    | is/has/should prefix | `isValid`, `hasError`, `shouldRetry`      |
| Collections | Plural nouns         | `deviceStates`, `alertConditions`         |

```typescript
// ✅ GOOD
class DeviceStateRepository {}
function calculateAverageTemperature(readings: number[]): number {}
const maxRetryAttempts = 3;
const isValidationEnabled = true;

// ❌ BAD
class DSRepo {} // Abbreviated
function calc(r: number[]): number {} // Unclear
const max = 3; // Maximum what?
```

## SOLID Principles

### Single Responsibility (SRP)

Each class/function has ONE reason to change. Separate validation, transformation, persistence.

### Open-Closed (OCP)

Use interfaces/abstractions for extension without modification.

```typescript
// ✅ Extensible design
interface AlertEvaluator {
  evaluate(entity: EntityDto, condition: AlertCondition): boolean;
}
class ThresholdAlertEvaluator implements AlertEvaluator {}
class RangeAlertEvaluator implements AlertEvaluator {}
```

### Dependency Inversion (DIP)

Depend on abstractions, not concretions.

```typescript
// ✅ GOOD
class DeviceStateService {
  constructor(private repository: DeviceStateRepository) {} // Interface
}
```

## Function Rules

- **Maximum 100 lines** (prefer < 50)
- **Single responsibility** per function
- **Always use `await`** when calling async functions, even when returning

```typescript
// ✅ Explicit await
async function getDeviceState(id: string): Promise<DeviceState> {
  return await this.repository.findByDeviceId(id);
}
```

## TypeScript Type Safety

**Avoid `any` and `unknown`** unless justified and documented.

Better alternatives:

- **Generics** for flexible type-safe code
- **Union types** for multiple possibilities
- **Interfaces** for object structures
- **`Record<K, V>`** for typed dictionaries
- **Type guards** to narrow unknown types

```typescript
// ✅ Generics
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

// ✅ Justified unknown with type guard
function handleError(error: unknown): void {
  if (error instanceof Error) console.error(error.message);
}
```

## Domain Entity Pattern

### Partial Constructor (MANDATORY)

```typescript
export class AlertInstance {
  id?: string;
  ruleId: string;
  severity: AlertSeverity;

  constructor(init?: Partial<AlertInstance>) {
    Object.assign(this, init);
  }
}
```

### Framework-Independent Entities

- Use `id: string` not `_id: Types.ObjectId`
- No Mongoose/TypeORM imports in entities
- Repositories convert types at boundary with `mapToEntity()`

### Global Module Pattern

```typescript
@Global() // Shared infrastructure modules
@Module({
  imports: [
    MongooseModule.forRootAsync({
      /* config */
    }),
  ],
  exports: [MongooseModule, ...Repositories],
})
export class MongoDBModule {}

// Business modules: empty imports array
@Module({
  imports: [], // Global deps available automatically
  providers: [HandleAlertWebhookUseCase],
})
export class AlertModule {}
```

## Whitespace and Formatting

### Validation Pattern (Immediate Check)

When a variable is declared solely for validation, **omit the blank line** between declaration and validation check.

```typescript
// ✅ GOOD - No blank line between variable and its validation
const authHeader = credentials['authorization'];
if (!authHeader) {
  throw new ValidateException(ErrorCode.MISSING_AUTH_HEADER, 'Authorization header is required');
}

const token = authHeader.split(' ')[1];
if (!token) {
  throw new ValidateException(ErrorCode.INVALID_AUTH_HEADER, 'Token is required');
}

// ❌ BAD - Unnecessary blank line disrupts validation flow
const authHeader = credentials['authorization'];

if (!authHeader) {
  throw new ValidateException(ErrorCode.MISSING_AUTH_HEADER, 'Authorization header is required');
}
```

**Rationale:** The variable and its validation are conceptually a single unit. The blank line creates visual separation that suggests they are unrelated operations.

### General Whitespace Rules

- Use blank lines to separate logical blocks of code
- No blank line between variable declaration and immediate validation/usage
- One blank line between function definitions
- Two blank lines between class methods (if following class-based style)

## Index File Export Pattern (MANDATORY)

### Module Component Registration

Index files (`index.ts`) in component directories (usecases, commands, events) **MUST export arrays ONLY**, not individual classes.

```typescript
// ✅ GOOD - Export ONLY the array
// src/modules/order/usecases/index.ts
import { CreateOrderUseCase } from './create-order.usecase';
import { UpdateOrderUseCase } from './update-order.usecase';
import { DeleteOrderUseCase } from './delete-order.usecase';

export const UseCases = [CreateOrderUseCase, UpdateOrderUseCase, DeleteOrderUseCase];

// ❌ BAD - Re-exporting individual classes
export * from './create-order.usecase';
export * from './update-order.usecase';
export * from './delete-order.usecase';

// ❌ BAD - Exporting both array and individual classes
export const UseCases = [
  /* ... */
];
export * from './create-order.usecase';
```

**Rationale:**

- ✅ **Clear module boundaries** - Array export makes registration explicit
- ✅ **Prevents namespace pollution** - No accidental direct imports
- ✅ **Enforces proper architecture** - Components accessed through their modules only
- ✅ **Single source of truth** - Module registration is the only export

**Usage in Module:**

```typescript
import { Module } from '@nestjs/common';
import { OrderController } from './order.controller';
import { UseCases } from './usecases';
import { CommandHandlers } from './commands';

@Module({
  controllers: [OrderController],
  providers: [...UseCases, ...CommandHandlers],
})
export class OrderModule {}
```

**Apply this pattern to:**

- `usecases/index.ts` → Export `UseCases` array
- `commands/index.ts` → Export `CommandHandlers` array
- `events/index.ts` → Export `EventHandlers` array
- `queries/index.ts` → Export `QueryHandlers` array (if using CQRS queries)

## General Best Practices

- Remove dead code, commented-out blocks, unused imports
- No backward compatibility code unless explicitly required
- DRY: Extract common logic into reusable functions
- Automated formatting via linter/prettier

## Quick Checklist

- [ ] Classes PascalCase, functions camelCase verbs
- [ ] Booleans have is/has/should prefix
- [ ] No abbreviations in names
- [ ] Functions < 100 lines, single responsibility
- [ ] No `any`/`unknown` without justification
- [ ] Always `await` async calls
- [ ] Entities use partial constructor pattern
- [ ] Entities framework-independent
- [ ] Global modules use `@Global()` decorator
- [ ] No blank line between variable and immediate validation check
- [ ] Index files export ONLY arrays (UseCases, CommandHandlers, EventHandlers)
- [ ] NO re-exporting individual classes from index.ts
