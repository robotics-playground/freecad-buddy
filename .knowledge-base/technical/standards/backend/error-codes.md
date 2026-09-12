---
title: "Error Code Standards"
category: "backend"
tags: ["error-handling", "error-codes", "validation", "typescript", "standards"]
description: "Defines mandatory error code standards including organization, naming conventions, ranges, and usage patterns for consistent error handling across the application"
last_updated: "2025-01-02"
---

# Error Code Standards

**Last Updated:** 2025-10-24
**Applies To:** All error codes, all error handling, all developers
**Status:** Mandatory

---

## Overview

This document defines mandatory error code standards for the project. These standards ensure consistent error code organization, naming conventions, and usage patterns across the entire application.

---

## 1. Error Code Organization

### 1.1 Error Code Location

All error codes **MUST** be defined in:
```
src/utils/error.code.ts
```

### 1.2 Error Code Structure

```typescript
export enum ErrorCode {
  // Special System Codes
  UNKNOWN = -999999,
  UNAUTHORIZED = -888888,
  VALIDATION_FAILED = -777777,
  SUCCESS = 1,

  // Business Error Codes (-400xxx range)
  TITLE_INVALID = -400001,
  TEMPLATE_NOT_FOUND = -400002,
  CART_NOT_EXIST = -400003,
  // ... continue in sequence
}
```

---

## 2. Error Code Ranges

### 2.1 Reserved Error Code Ranges

| Range | Purpose | Example |
|-------|---------|---------|
| `1` | Success code | `SUCCESS = 1` |
| `-777777` | Generic validation failure | `VALIDATION_FAILED = -777777` |
| `-888888` | Authentication/authorization | `UNAUTHORIZED = -888888` |
| `-999999` | Unknown/unexpected errors | `UNKNOWN = -999999` |
| `-400001 to -400999` | Business logic errors | All application-specific errors |

### 2.2 Business Error Code Range (-400xxx)

**All application-specific error codes MUST use the -400xxx range**

### 2.3 Sequential Allocation

Error codes **MUST** be allocated sequentially without gaps

---

## 3. Error Code Naming Conventions

### 3.1 Standard Naming Pattern

Error codes **MUST** follow this pattern:
```
<SUBJECT>_<REASON>
```

Examples:
- `ORG_ID_INVALID` - Organization ID is invalid
- `AREA_TYPE_INVALID` - Area type is invalid
- `DEVICE_NOT_FOUND` - Device not found
- `ENTITY_CATEGORY_INVALID` - Entity category is invalid

### 3.2 Common Suffixes

| Suffix | Meaning | Example |
|--------|---------|---------|
| `_INVALID` | Field value doesn't meet validation rules | `ORG_ID_INVALID` |
| `_NOT_FOUND` | Resource doesn't exist | `DEVICE_NOT_FOUND` |
| `_FAILED` | Operation failed | `CHECKOUT_CART_FAILED` |
| `_NOT_EXIST` | Resource doesn't exist (synonym) | `CART_NOT_EXIST` |
| `_EMPTY` | Required collection is empty | `ITEM_LIST_EMPTY` |
| `_EXCEEDED` | Limit exceeded | `ORDER_LIMIT_EXCEEDED` |

---

## 4. Error Code Categories

### 4.1 Validation Error Codes

For field validation (used in DTO validation context):

```typescript
// Organization validation
ORG_ID_INVALID = -400035,
ORG_NAME_INVALID = -400036,
ORG_INVALID = -400067,          // Parent object validation

// Area validation
AREA_ID_INVALID = -400037,
AREA_NAME_INVALID = -400038,
AREAS_INVALID = -400065,        // Array validation
```

**Pattern:**
- Individual field: `<PARENT>_<FIELD>_INVALID`
- Parent object: `<PARENT>_INVALID`
- Array: `<PARENT_PLURAL>_INVALID`

### 4.2 Business Logic Error Codes

For business rule violations:

```typescript
CART_NOT_EXIST = -400003,
ITEM_NOT_BELONG_TO_CART = -400024,
ORDER_LIMIT_EXCEEDED = -400029,
STATUS_CHANGE_INVALID = -400028,
```

### 4.3 Operation Error Codes

For failed operations:

```typescript
GET_CART_FAILED = -400009,
ADD_CART_ITEM_FAILED = -400010,
CHECKOUT_CART_FAILED = -400013,
CONFIRM_ORDER_FAILED = -400017,
```

---

## 5. Error Code Usage in Validation

### 5.1 Field-Level Validation

Use error codes in validation decorator context:

```typescript
import { ErrorCode } from 'src/utils/error.code';

export class OrgDto {
  @IsNotEmpty({ context: { code: ErrorCode.ORG_ID_INVALID, message: 'org.id is required' } })
  @IsString({ context: { code: ErrorCode.ORG_ID_INVALID, message: 'org.id must be a string' } })
  id: string;
}
```

### 5.2 Same Error Code for Related Validators

Multiple validators on the same field **MUST** use the same error code:

```typescript
// ✅ CORRECT - Same error code
@IsNotEmpty({ context: { code: ErrorCode.DEVICE_ID_INVALID, message: 'device.id is required' } })
@IsString({ context: { code: ErrorCode.DEVICE_ID_INVALID, message: 'device.id must be a string' } })
@IsUUID(4, { context: { code: ErrorCode.DEVICE_ID_INVALID, message: 'device.id must be a valid UUID' } })
id: string;
```

---

## 6. Adding New Error Codes

### 6.1 Process for Adding Error Codes

1. **Check existing codes:** Ensure no duplicate or similar code exists
2. **Find next sequential number:** Use the next available number in -300xxx range
3. **Follow naming conventions:** Use standard suffixes and patterns
4. **Group related codes:** Add new codes near related codes with comments
5. **Update documentation:** Document the purpose if not obvious

### 6.2 Example: Adding Error Codes

```typescript
export enum ErrorCode {
  // ... existing codes ...
  CANCEL_ORDER_FAILED = -400033,

  // Device Event Validation Error Codes (Story 1.2)
  TIMESTAMP_INVALID = -400034,
  ORG_ID_INVALID = -400035,
  ORG_NAME_INVALID = -400036,
  AREA_ID_INVALID = -400037,
  // ... continue sequentially ...
}
```

---

## Quick Reference Checklist

### Before Adding New Error Codes:

- [ ] Using -400xxx range (not -100xxx or -300xxx)
- [ ] Sequential number allocation (no gaps)
- [ ] Descriptive name following naming conventions
- [ ] Same error code for all validators on same field
- [ ] Grouped with related error codes
- [ ] Comment added to describe error code group
- [ ] No duplicate error codes

---

**Version:** 1.0.0
**Last Updated:** 2025-10-24
**Maintained By:** Product & Engineering Teams
