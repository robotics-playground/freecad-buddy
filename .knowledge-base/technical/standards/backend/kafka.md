---
title: "Kafka Consumer Standards"
category: "backend"
tags: ["kafka", "nestjs", "messaging", "event-driven", "consumers"]
description: "Standards and best practices for implementing Kafka consumers in NestJS, including offset management, error handling patterns, and common anti-patterns to avoid"
last_updated: "2025-01-02"
---

# Kafka Consumer Standards

> **Key Rule:** Trust NestJS auto offset management. Let errors propagate for automatic retry.

## Core Rules

| Rule | Requirement |
|------|-------------|
| Offset management | Automatic (NestJS handles) |
| Error handling | Let errors bubble for retry |
| Manual commits | NEVER implement |
| Try-catch | Only for selective error recovery |

## Standard Pattern

```typescript
@Controller()
export class EventConsumerController {
  @EventPattern('wne-${RUNTIME_ENV}-8ten-api-device-data')
  async handleEvent(@Payload() event: DeviceEventDto) {
    // No try-catch needed
    await this.service.process(event);
    // ✅ Offset auto-committed on success
    // ✅ If error thrown, offset NOT committed (message retried)
  }
}
```

## Anti-Patterns

```typescript
// ❌ Swallowing errors (message lost!)
@EventPattern('topic')
async handleEvent(event: EventDto) {
  try {
    await this.service.process(event);
  } catch (error) {
    this.logger.error('Failed');  // Error swallowed, offset committed!
  }
}

// ❌ Manual offset commits
async handleEvent(event: EventDto, @Ctx() context: KafkaContext) {
  await this.service.process(event);
  await context.getConsumer().commitOffsets([...]);  // Unnecessary!
}

// ❌ Tracking offsets in database
async handleEvent(event: EventDto, @Ctx() context: KafkaContext) {
  const offset = context.getMessage().offset;
  await this.offsetRepository.save({ offset });  // Unnecessary!
}
```

## Testing

```typescript
it('should propagate errors for automatic retry', async () => {
  const error = new Error('Processing failed');
  mockService.process.mockRejectedValue(error);

  await expect(controller.handleEvent(event)).rejects.toThrow(error);
});
```

## Checklist

- [ ] No manual offset commit code
- [ ] No try-catch wrapping entire method
- [ ] Errors propagate for automatic retry
- [ ] Selective error handling has business justification
- [ ] No offset tracking in database
- [ ] Tests verify error propagation
