---
title: "Logging Standards"
category: "backend"
tags: ["logging", "nestjs", "observability", "error-handling", "best-practices"]
description: "Guidelines for minimal, effective logging in NestJS applications, covering log levels, what to log, anti-patterns, and rollback logging patterns"
last_updated: "2025-01-02"
---

# Logging Standards

> **Key Rule:** Minimal logging. Only critical business events and errors. Framework handles the rest.

## Framework

- **Logger:** NestJS Logger (`@nestjs/common`)
- **Correlation IDs:** Auto-injected by 8ten-libs-telemetry
- **Levels:** `debug`, `log` (info), `warn`, `error`

## Log Levels

| Level | Use Case |
|-------|----------|
| `error` | Exceptions, rollback failures, external service failures |
| `warn` | Recoverable issues, skipped events, degraded mode |
| `log` | Service startup, critical business events |
| `debug` | Development troubleshooting only |

## What TO Log

- Service startup/shutdown
- Critical business events (alerts triggered, payments processed)
- External service failures (API timeout, connection refused)
- Rollback operations and outcomes
- Configuration errors

## What NOT to Log

- Successful CRUD operations
- Every API request/response (framework logs this)
- Routine validation errors (global handler logs)
- Method entry/exit
- Query execution (telemetry handles this)

## Pattern

```typescript
@Injectable()
export class AlertService {
  private readonly logger = new Logger(AlertService.name);

  async process(alert: Alert): Promise<void> {
    // ❌ Don't log: this.logger.log(`Processing alert ${alert.id}`);

    try {
      await this.externalService.notify(alert);
      // ❌ Don't log success: this.logger.log('Notification sent');
    } catch (error) {
      // ✅ DO log external failures
      this.logger.error(`Notification failed for alert ${alert.id}`, error.stack);
      throw error;
    }
  }
}
```

## Rollback Logging

```typescript
private async rollback(entity: Entity | null): Promise<void> {
  this.logger.error(`Operation failed. Rolling back...`);

  if (entity) {
    try {
      await this.repository.delete(entity.id);
      this.logger.log(`Rollback: Deleted ${entity.id}`);  // ✅ Log rollback outcome
    } catch (rollbackError) {
      this.logger.error(`Rollback failed: ${rollbackError['message']}`);
    }
  }
}
```

## Anti-Patterns

```typescript
// ❌ Logging routine operations
this.logger.log(`Creating alert rule: ${dto.name}`);
const rule = await this.repository.create(dto);
this.logger.log(`Alert rule created: ${rule.id}`);

// ❌ Duplicate logging (global handler logs)
try {
  await this.service.process(data);
} catch (error) {
  this.logger.error('Processing failed', error);  // Redundant!
  throw error;
}
```

## Checklist

- [ ] Use NestJS Logger, not console.log
- [ ] Only log critical business events
- [ ] Log external service failures
- [ ] Log rollback operations
- [ ] No duplicate error logging
- [ ] No routine CRUD logging
