---
title: "Code Commenting Standards"
category: "global"
tags: ["code-quality", "comments", "jsdoc", "code-review", "best-practices"]
description: "Comprehensive guidelines for code commenting, defining when comments are appropriate (business rules, security, non-obvious behavior) versus forbidden (describing what code does), including JSDoc requirements and code review rejection criteria."
last_updated: "2025-01-02"
---

# Code Commenting Standards

> **Philosophy:** Code IS the documentation. Comments explain "why", never "what" or "how".

## Zero-Tolerance Policy

Comments that state the obvious = **code review rejection**. No exceptions.

---

## Forbidden Comments (WILL BE REJECTED)

### Category 1: Describing What Code Does

```typescript
// ❌ REJECTED - Describes what code does
// Check if existing instance found
if (existingInstance) { ... }

// ❌ REJECTED - Restates the condition
// If status is active
if (status === 'active') { ... }

// ❌ REJECTED - Describes the operation
// Create new alert rule
const rule = await this.repository.create(dto);

// ❌ REJECTED - Describes variable assignment
// Set the device ID
const deviceId = event.deviceId;

// ❌ REJECTED - Describes return statement
// Return the result
return result;
```

### Category 2: Restating Names or Types

```typescript
// ❌ REJECTED - Restates function name
// Validates the input
async validateInput(dto: CreateDto) { ... }

// ❌ REJECTED - Restates variable name
// The alert instance
const alertInstance = new AlertInstance();

// ❌ REJECTED - Restates parameter name
// @param deviceId - The device ID  ❌
// @param deviceId - Unique identifier for device lookup  ✅
```

### Category 3: Describing Control Flow

```typescript
// ❌ REJECTED - Describes if/else structure
// Check if rule exists, otherwise throw error
if (!rule) {
  throw new NotFoundException();
}

// ❌ REJECTED - Describes loop
// Loop through all devices
for (const device of devices) { ... }

// ❌ REJECTED - Describes try/catch
// Try to save, catch errors
try {
  await this.repository.save(entity);
} catch (error) {
  throw error;
}
```

### Category 4: Describing CRUD Operations

```typescript
// ❌ REJECTED - Describes save operation
// Save to database
await this.repository.save(entity);

// ❌ REJECTED - Describes find operation
// Find by ID
const entity = await this.repository.findById(id);

// ❌ REJECTED - Describes delete operation
// Delete the entity
await this.repository.delete(id);

// ❌ REJECTED - Describes update operation
// Update the status
await this.repository.update(id, { status: 'active' });
```

### Category 5: Error Handling Comments

```typescript
// ❌ REJECTED - Describes error code check
// MongoDB duplicate key error
if (error['code'] === 11000) { ... }

// ❌ REJECTED - Describes error throwing
// Throw validation error
throw new ValidateException(ErrorCode.INVALID);

// ❌ REJECTED - Describes error logging
// Log the error
this.logger.error('Failed', error);
```

---

## Acceptable Comments (WHEN TO COMMENT)

### Category 1: Business Rules & Regulations

```typescript
// ✅ GOOD - Legal/compliance requirement
// Per GDPR Article 17, anonymize instead of hard delete
await this.anonymizeUserData(userId);

// ✅ GOOD - Business rule explanation
// SLA requires 99.9% uptime - retry 3 times before failing
await this.retryWithBackoff(operation, 3);

// ✅ GOOD - Domain-specific logic
// ISO 8601 week starts on Monday, not Sunday
const weekStart = startOfISOWeek(date);
```

### Category 2: Non-Obvious Behavior

```typescript
// ✅ GOOD - Explains side effect
// SIDE EFFECT: Also invalidates related cache entries
await this.repository.delete(id);

// ✅ GOOD - Explains async behavior
// Fire-and-forget: notification failure shouldn't block response
this.notificationService.send(alert).catch(e => this.logger.warn(e));
```

### Category 3: Security Considerations

```typescript
// ✅ GOOD - Security warning
// SECURITY: Never log the full token, only last 4 chars
this.logger.log(`Token: ...${token.slice(-4)}`);

// ✅ GOOD - Security requirement
// Rate limited to 100 req/min per IP to prevent brute force
@RateLimit({ limit: 100, ttl: 60 })
```

### Category 4: TODOs and Technical Debt

```typescript
// ✅ GOOD - TODO with ticket reference
// TODO: [PROJ-123] Replace with Redis after infrastructure upgrade

// ✅ GOOD - Temporary workaround
// WORKAROUND: [PROJ-456] Upstream bug in kafka-js, remove after v3.0
```

### Category 5: Critical Warnings

```typescript
// ✅ GOOD - Critical system behavior
// CRITICAL: Offset MUST be committed after processing for at-least-once delivery

// ✅ GOOD - Data integrity warning
// WARNING: Changing this enum breaks existing database records
```

---

## JSDoc Requirements

### Public Functions - REQUIRED (Minimal)

```typescript
/**
 * Persists alert instance to MongoDB
 * @param alertInstance - Alert data to persist
 * @returns Persisted entity with generated ID
 */
async create(alertInstance: Partial<AlertInstance>): Promise<AlertInstance>
```

### JSDoc Rules

| Rule | Requirement |
|------|-------------|
| Summary | One sentence only, starts with verb |
| @param | Purpose/usage, NOT type (TypeScript provides type) |
| @returns | What is returned, when useful |
| @throws | Only if non-obvious or multiple exception types |
| @example | Only if genuinely complex usage |
| Length | Max 5-7 lines for simple functions |

### JSDoc Anti-Patterns

```typescript
// ❌ REJECTED - Too verbose
/**
 * This function creates a new alert rule in the system.
 * It takes a DTO containing the alert rule configuration
 * and persists it to the MongoDB database. The function
 * returns the created entity with a generated ID.
 * @param dto - The data transfer object
 * @returns The created alert rule
 */

// ✅ GOOD - Concise
/**
 * Creates alert rule with validation
 * @param dto - Alert rule configuration
 * @returns Created rule with generated ID
 */
```

```typescript
// ❌ REJECTED - Obvious @throws
/**
 * Finds entity by ID
 * @throws NotFoundException if entity not found  ❌ Obvious!
 */

// ✅ GOOD - Non-obvious @throws
/**
 * Validates PromQL expression against VictoriaMetrics
 * @throws ValidateException if syntax invalid
 * @throws InternalException if VictoriaMetrics unreachable
 */
```

### Private Functions - NO DOCS unless:

- Function > 50 lines
- Logic is complex/non-obvious
- Has important side effects
- Called from multiple places

---

## Self-Documenting Code

**Fix the code, don't add comments:**

```typescript
// ❌ BAD - Comment needed because code is unclear
function proc(d) {
  // Process the device data and update state
  return d.s === 1 ? updateActive(d) : updateInactive(d);
}

// ✅ GOOD - Code is self-documenting
function processDeviceStateChange(device: Device): DeviceState {
  return device.isActive
    ? this.activateDevice(device)
    : this.deactivateDevice(device);
}
```

```typescript
// ❌ BAD - Magic number with comment
// Timeout in milliseconds (30 seconds)
const timeout = 30000;

// ✅ GOOD - Named constant
const EXTERNAL_API_TIMEOUT_MS = 30000;
```

---

## Checklist: Before Adding ANY Comment

### Inline Comment Checklist

- [ ] Does this explain WHY, not WHAT?
- [ ] Would renaming the variable/function eliminate the need?
- [ ] Is this a business rule, regulation, or non-obvious behavior?
- [ ] Is this a security consideration?
- [ ] Is this a TODO with a ticket reference?
- [ ] Would another developer be confused without this comment?

**If you answered NO to all → DELETE THE COMMENT**

### JSDoc Checklist

- [ ] Is this a public function/method?
- [ ] Is the summary one sentence starting with a verb?
- [ ] Are @param descriptions about PURPOSE, not TYPE?
- [ ] Is @throws only for non-obvious exceptions?
- [ ] Is the total length under 7 lines?
- [ ] Does the function name not already explain everything?

**If the function is private or name is self-explanatory → NO JSDOC NEEDED**

---

## Quick Reference: Comment Decision Tree

```
Should I add a comment?
│
├─ Does it describe WHAT the code does?
│  └─ YES → ❌ DELETE IT
│
├─ Does it restate variable/function names?
│  └─ YES → ❌ DELETE IT
│
├─ Does it describe control flow (if/else/loop)?
│  └─ YES → ❌ DELETE IT
│
├─ Does it describe CRUD operations?
│  └─ YES → ❌ DELETE IT
│
├─ Does it explain a business rule or regulation?
│  └─ YES → ✅ KEEP IT
│
├─ Does it explain WHY a non-obvious decision was made?
│  └─ YES → ✅ KEEP IT
│
├─ Is it a security warning?
│  └─ YES → ✅ KEEP IT
│
├─ Is it a TODO with ticket reference?
│  └─ YES → ✅ KEEP IT
│
└─ None of the above?
   └─ ❌ DELETE IT
```

---

## Code Review Rejection Criteria

### Automatic Rejection - Inline Comments

| Pattern | Example | Verdict |
|---------|---------|---------|
| Describes code | `// Save to database` | ❌ REJECT |
| Restates names | `// The user service` | ❌ REJECT |
| Describes flow | `// If not found, throw` | ❌ REJECT |
| Describes CRUD | `// Delete the entity` | ❌ REJECT |
| No ticket on TODO | `// TODO: fix later` | ❌ REJECT |
| Commented-out code | `// const old = ...` | ❌ REJECT |

### Automatic Rejection - JSDoc

| Pattern | Example | Verdict |
|---------|---------|---------|
| Multi-sentence summary | `This function does X. It also does Y.` | ❌ REJECT |
| Obvious @throws | `@throws NotFoundException if not found` | ❌ REJECT |
| Type in @param | `@param id {string} - The ID` | ❌ REJECT |
| Repeating function name | `@description Creates alert rule` (for `createAlertRule`) | ❌ REJECT |
| Private function JSDoc | JSDoc on private helper | ❌ REJECT (unless complex) |
| >10 lines for CRUD | Long JSDoc for simple save/find | ❌ REJECT |

---

## Examples: Real Code Review Scenarios

### Scenario 1: Service Method

```typescript
// ❌ REJECTED CODE
/**
 * This method processes the incoming device event.
 * It validates the event data and then saves it to the database.
 * @param event - The device event to process
 * @returns The processed event
 */
async processEvent(event: DeviceEventDto): Promise<DeviceEvent> {
  // Validate the event
  await this.validateEvent(event);

  // Save to database
  const saved = await this.repository.save(event);

  // Return the result
  return saved;
}

// ✅ APPROVED CODE
/**
 * Validates and persists device event
 * @param event - Raw event from Kafka consumer
 * @returns Persisted event with generated ID
 */
async processEvent(event: DeviceEventDto): Promise<DeviceEvent> {
  await this.validateEvent(event);
  return await this.repository.save(event);
}
```

### Scenario 2: Error Handling

```typescript
// ❌ REJECTED CODE
try {
  // Try to reload vmalert
  await this.reloadVmalert();
} catch (error) {
  // Log the error
  this.logger.error('Reload failed', error);
  // Throw internal exception
  throw new InternalException(ErrorCode.RELOAD_FAILED);
}

// ✅ APPROVED CODE
try {
  await this.reloadVmalert();
} catch (error) {
  this.logger.error('Reload failed', error);
  throw new InternalException(ErrorCode.RELOAD_FAILED);
}
```

### Scenario 3: Complex Business Logic (Comments Appropriate)

```typescript
// ✅ APPROVED CODE - Comments explain non-obvious business rules
async evaluateAlert(device: Device): Promise<void> {
  // SLA: Alerts must be evaluated within 30s of event receipt
  const evaluationDeadline = Date.now() + 30000;

  // Dedupe window: Same alert fingerprint within 5min is ignored
  // per alerting best practices to prevent notification fatigue
  const existingAlert = await this.findRecentAlert(device.fingerprint, 300000);
  if (existingAlert) {
    return;
  }

  // Fire-and-forget: Notification failure shouldn't block alert creation
  this.notifySubscribers(alert).catch(e => this.logger.warn('Notify failed', e));
}
```
