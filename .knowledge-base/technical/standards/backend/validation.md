---
title: "Validation Standards"
category: "backend"
tags: ["validation", "class-validator", "dto", "nestjs", "error-handling", "typescript"]
description: "Server-side validation standards using class-validator with ErrorCode context, covering DTO patterns, nested object validation, enum handling, and best practices for NestJS applications."
last_updated: "2025-01-02"
---

# Validation Standards

> **Framework:** class-validator with ErrorCode context. Server-side validation is MANDATORY.

## Core Rules

| Rule              | Requirement                                               |
| ----------------- | --------------------------------------------------------- |
| Server validation | Always validate server-side, never trust client           |
| Error context     | Every validator MUST have ErrorCode + descriptive message |
| Property naming   | CamelCase in classes, `@Expose` for snake_case JSON       |
| Nested objects    | `@ValidateNested()` + `@Type(() => ChildDto)`             |
| Enums             | Use `@IsEnum()`, not `@IsIn()`                            |

## ErrorCode Context (MANDATORY)

```typescript
// ✅ GOOD - Always include ErrorCode context
@IsNotEmpty({ context: { code: ErrorCode.DEVICE_ID_REQUIRED, message: 'deviceId required' } })
@IsString({ context: { code: ErrorCode.DEVICE_ID_INVALID_TYPE, message: 'deviceId must be string' } })
deviceId: string;

// ❌ BAD - No context
@IsNotEmpty()
@IsString()
deviceId: string;
```

## Property Naming with @Expose

```typescript
export class DeviceEventDto {
  @Expose({ name: 'device_id' }) // Maps snake_case JSON to camelCase property
  @IsNotEmpty({ context: { code: ErrorCode.DEVICE_ID_REQUIRED } })
  deviceId: string;

  @Expose({ name: 'org_id' })
  @IsNotEmpty({ context: { code: ErrorCode.ORG_ID_REQUIRED } })
  orgId: string;
}
```

## Nested Object Validation

```typescript
export class ParentDto {
  @ValidateNested()
  @Type(() => ChildDto) // REQUIRED for class-transformer
  @IsNotEmptyObject({}, { context: { code: ErrorCode.METADATA_REQUIRED } })
  metadata: ChildDto;

  @ValidateNested({ each: true }) // For arrays
  @Type(() => ItemDto)
  @IsArray({ context: { code: ErrorCode.ITEMS_INVALID } })
  items: ItemDto[];
}
```

## Enum Validation

```typescript
enum AlertSeverity { LOW = 'low', MEDIUM = 'medium', HIGH = 'high', CRITICAL = 'critical' }

// ✅ GOOD - Proper enum with context
@IsEnum(AlertSeverity, {
  context: { code: ErrorCode.SEVERITY_INVALID, message: 'severity must be low|medium|high|critical' }
})
severity: AlertSeverity;

// ❌ BAD - Using @IsIn instead of @IsEnum
@IsIn(['low', 'medium', 'high'])
severity: string;
```

## Common Patterns

```typescript
// Optional with transform
@IsOptional()
@IsInt({ context: { code: ErrorCode.LIMIT_INVALID } })
@Min(1, { context: { code: ErrorCode.LIMIT_TOO_SMALL } })
@Max(100, { context: { code: ErrorCode.LIMIT_TOO_LARGE } })
@Transform(({ value }) => parseInt(value, 10))
limit?: number = 20;

// String array
@IsArray({ context: { code: ErrorCode.TAGS_INVALID } })
@IsString({ each: true, context: { code: ErrorCode.TAG_NOT_STRING } })
@ArrayMinSize(1, { context: { code: ErrorCode.TAGS_EMPTY } })
tags: string[];

// Conditional validation
@ValidateIf((o) => o.type === 'threshold')
@IsNumber({}, { context: { code: ErrorCode.VALUE_REQUIRED_FOR_THRESHOLD } })
thresholdValue?: number;
```

## Controller Validation

```typescript
@Controller('events')
export class EventController {
  @Post()
  async process(
    @Body(new ValidationPipe({
      transform: true,
      whitelist: true,  // Strip unknown properties
      forbidNonWhitelisted: true  // Reject unknown properties
    }))
    dto: CreateEventDto
  ) { ... }
}
```

## Best Practices

- Validate early, fail fast with specific errors
- Allowlists over blocklists
- Sanitize input to prevent injection
- Consistent validation at all entry points (API, Kafka, background jobs)

## Checklist

- [ ] Every decorator has ErrorCode context
- [ ] Nested objects have `@ValidateNested()` + `@Type()`
- [ ] Enums use `@IsEnum()` not `@IsIn()`
- [ ] CamelCase properties with `@Expose` for snake_case JSON
- [ ] Arrays validated with `{ each: true }`
- [ ] Optional fields have `@IsOptional()`
