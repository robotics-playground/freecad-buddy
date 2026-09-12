---
title: "Telemetry Standards"
category: "backend"
tags: ["telemetry", "metrics", "observability", "monitoring", "8ten-libs"]
description: "Guidelines for implementing telemetry and custom metrics in backend services, emphasizing framework-provided telemetry over custom implementations"
last_updated: "2025-01-02"
---

# Telemetry Standards

> **Key Rule:** Trust 8ten-libs-telemetry. Only add custom metrics when explicitly required.

## What's Already Tracked (Don't Duplicate)

8ten-libs-telemetry provides:
- HTTP request/response times (P50, P95, P99), status codes, throughput
- Database query times, connection pools
- Kafka consumer lag, message processing, errors
- System metrics (memory, CPU, GC)
- Exception rates by type

## Core Rules

| Rule | Requirement |
|------|-------------|
| Default | Trust framework telemetry |
| Custom metrics | ONLY when explicitly required in story/PRD |
| Temporary metrics | Add TODO with removal plan |

## Decision Tree

```
Need to track something?
├─ Already tracked by 8ten-libs-telemetry? → Use framework ✅
├─ Explicitly required in story/PRD? → Implement custom metric ✅
├─ For debugging production issue? → Add temporary metric with TODO ✅
└─ None of the above? → Don't implement, ask for clarification ❓
```

## Anti-Patterns

```typescript
// ❌ Manually tracking latency (framework does this)
async processEvent(event: EventDto) {
  const startTime = Date.now();
  await this.repository.save(event);
  this.metricsService.recordLatency('processing_time', Date.now() - startTime);
}

// ❌ Success/failure counters (framework does this)
try {
  await this.repository.save(event);
  this.metricsService.incrementCounter('success');
} catch (error) {
  this.metricsService.incrementCounter('failure');
  throw error;
}

// ❌ "Just in case" metrics
this.metricsService.recordGauge('devices_in_processing', 1);
```

## When Custom Metrics Are Acceptable

```typescript
// ✅ GOOD - Explicit story requirement:
// "Track state transitions per device type for feature adoption"
async detectTransition(device: DeviceState) {
  const transition = await this.detectStateChange(device);
  if (transition) {
    this.metricsService.recordTransition(device.type, transition.from, transition.to);
  }
}

// ✅ GOOD - Temporary debugging
// TODO: Remove after investigating Story #456
async executeQuery(query: Query) {
  const startTime = Date.now();
  const result = await this.database.execute(query);
  this.metricsService.recordLatency('slow_query_investigation', Date.now() - startTime);
  return result;
}
```

## Naming Conventions (If Custom Metrics Needed)

```
{service}_{entity}_{action}_{unit}
```

| Type | Use Case | Example |
|------|----------|---------|
| Counter | Incrementing values | `alert_service_rule_evaluations_total` |
| Gauge | Current value | `alert_service_active_subscriptions_count` |
| Histogram | Distribution | `alert_service_evaluation_duration_ms` |

**Avoid high-cardinality labels:**
```typescript
// ✅ GOOD
{ severity: 'critical', ruleType: 'threshold' }

// ❌ BAD - High cardinality
{ deviceId: device.id, userId: user.id, timestamp: Date.now() }
```

## Testing

Don't test that metrics were recorded. Test business logic:

```typescript
// ❌ BAD
expect(mockMetricsService.recordLatency).toHaveBeenCalled();

// ✅ GOOD
expect(result.status).toBe('processed');
```

## Checklist

- [ ] No custom metrics without explicit requirements
- [ ] Metric names follow naming conventions
- [ ] No duplicate metrics (already in framework)
- [ ] No high-cardinality labels
- [ ] Temporary metrics have TODO + removal plan
- [ ] No assertions on metric recording in tests
