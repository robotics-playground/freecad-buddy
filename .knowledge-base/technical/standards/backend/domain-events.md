---
title: "Domain Event Standards"
category: "backend"
tags: ["domain-events", "event-driven", "kafka", "nestjs", "cqrs", "event-sourcing"]
description: "Standards and best practices for implementing domain events, including event structure, publishing patterns, naming conventions, and anti-patterns to avoid"
last_updated: "2025-01-02"
---

# Domain Event Standards

> **Architecture:** Centralized `DomainEventsHandler` publishes ALL events to Kafka. Zero boilerplate.

## Core Rules

| Rule | Requirement |
|------|-------------|
| Publishing | Use `EventBus.publish()` in use case layer |
| Handler | Centralized `DomainEventsHandler` (NO per-event handlers) |
| Code format | `{Org}{ModuleNum}{EventNum}` |
| Location | `src/modules/{module}/events/{event}.event.ts` |
| Base class | Extend `DomainEvent<Payload>` |

## Event Structure (8TEN Schema)

```typescript
{
  id: string;           // Event/Aggregate ID
  refId?: string;       // Optional correlation ID
  code: string;         // Organization format
  timestamp: Date;      // Event occurrence
  source: { system: '8ten', service: 'alert-service', module: string };
  actor: { id?: string, name: string };  // 'system' or 'user-{id}'
  payload: T;           // Event-specific data
}
```

## Event Class Template

```typescript
import { DomainEvent, IDomainEventMetadata } from 'src/shared/common/models/seedwork/domain-event';

export class AlertActivatedPayload {
  alertRuleId: string;
  severity: AlertSeverity;

  constructor(init?: Partial<AlertActivatedPayload>) {
    Object.assign(this, init);
  }
}

export class AlertActivatedEvent extends DomainEvent<AlertActivatedPayload> {
  public readonly payload: AlertActivatedPayload;

  constructor(alert: AlertInstance, metadata?: IDomainEventMetadata) {
    super({
      id: alert.id,
      refId: metadata?.refId,
      timestamp: metadata?.timestamp,
      actor: metadata?.actor,
      source: metadata?.source || { module: 'alert-evaluation' },
    });

    this.payload = new AlertActivatedPayload({
      alertRuleId: alert.ruleId,
      severity: alert.severity,
    });
  }

  public get code(): string { return 'ORG02001'; }
  public key(): string { return this.id; }
}
```

## Publishing

```typescript
@Injectable()
export class HandleWebhookUseCase {
  constructor(private readonly eventBus: EventBus) {}

  async execute(webhook: WebhookDto): Promise<AlertInstance> {
    const alertInstance = await this.createAlertInstance(/* ... */);

    // ✅ Simple - DomainEventsHandler auto-publishes to Kafka
    this.eventBus.publish(new AlertActivatedEvent(alertInstance));

    return alertInstance;
  }
}
```

## Event Codes

| Range | Module |
|-------|--------|
| ORG00XXX | Core/System |
| ORG01XXX | Event Transformer |
| ORG02XXX | Alert Evaluation |
| ORG03XXX | Alert Rule Management |

## Anti-Patterns

```typescript
// ❌ Don't create per-event handlers
@EventsHandler(AlertActivatedEvent)
export class AlertActivatedEventHandler { ... }

// ❌ Don't inject Kafka directly
@Inject(KAFKA_CLIENT) private kafkaClient: ClientKafka;

// ❌ Don't await eventBus.publish (it's synchronous)
await this.eventBus.publish(event);

// ❌ Empty event code (won't publish)
public get code(): string { return ''; }
```

## Testing

```typescript
it('should publish AlertActivatedEvent', async () => {
  mockEventBus.publish = jest.fn();
  await target.execute(webhook);

  expect(mockEventBus.publish).toHaveBeenCalledWith(
    expect.objectContaining({
      code: 'ORG02001',
      source: expect.objectContaining({ system: '8ten' }),
      payload: expect.objectContaining({ severity: 'critical' }),
    })
  );
});
```

## Checklist

- [ ] Extends `DomainEvent<Payload>`
- [ ] Located in `src/modules/{module}/events/`
- [ ] Past tense name: `{Aggregate}{PastTense}Event`
- [ ] Unique organization code (Ex: `ORG02001`)
- [ ] Constructor accepts aggregate + `IDomainEventMetadata`
- [ ] Implements `code` getter and `key()` method
- [ ] Published via `EventBus.publish()`
- [ ] NO per-event handler created
