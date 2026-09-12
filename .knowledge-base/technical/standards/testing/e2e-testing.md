---
title: "E2E Testing Standards"
category: "testing"
tags: ["e2e", "nestjs", "jest", "supertest", "kafka", "mongodb", "test-isolation", "aaa-pattern"]
description: "Comprehensive standards for end-to-end testing including NestJS setup patterns, Kafka async testing, MongoDB isolation, assertion rules, and debugging guidelines"
last_updated: "2025-01-02"
---

# E2E Testing Standards

## Framework

```json
{
  "@nestjs/testing": "^11.0.12",
  "jest": "^29.7.0",
  "supertest": "^6.3.3"
}
```

## Core Rules

| Rule             | Requirement                                               |
| ---------------- | --------------------------------------------------------- |
| Setup            | Replicate `main.ts` configuration                         |
| Execution        | `--runInBand` (sequential)                                |
| Kafka topics     | Create explicitly in `beforeAll` (never rely on auto-creation) |
| Kafka wait       | Smart polling (50ms interval, 20s max) or 8-10s fixed wait |
| MongoDB cleanup  | `deleteMany({})` in beforeEach/afterEach                  |
| Timeouts         | 25s test, 90s beforeAll                                   |
| Logger           | File logging (DO NOT mock, DO NOT log to console)         |
| Log file         | `logs/e2e-test.log` configured via `.env.e2e`             |
| Log cleanup      | Delete previous `logs/e2e-test.log` before test execution |
| Test structure   | MUST follow GWT pattern (Given-When-Then)                 |

## Environment Configuration

E2E tests MUST use `.env.e2e` with file logging configuration:

```bash
# Logger configuration
LOG_LEVEL=debug
LOG_FILE_=./logs/e2e-test.log
LOG_SYNC_FILE_=./logs/application.pid
```

**Rationale:**

- ✅ Clean console output - no log clutter during test execution
- ✅ Full debug info preserved in file for investigation
- ✅ CI/CD uploads log file as artifact on failure
- ✅ Can tail logs in real-time with `npm run e2e:logs`

**Viewing Logs:**

```bash
# Tail logs in real-time during test execution
npm run e2e:logs

# View complete log file after test completion
cat logs/e2e-test.log

# Search for errors
grep -i error logs/e2e-test.log
```

## Critical Setup Pattern

E2E tests MUST replicate production setup from `main.ts`:

```typescript
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { HttpAdapterHost, Reflector } from '@nestjs/core';
import { ClsService } from 'nestjs-cls';
import { Transport } from '@nestjs/microservices';

describe('Feature E2E', () => {
  let app: INestApplication;
  jest.setTimeout(25000);

  beforeAll(async () => {
    const moduleFixture = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({ isGlobal: true, envFilePath: '.env.test' }),
        LoggerModule.forRoot({ output: 'text', level: 'info' }),
        YourFeatureModule,
      ],
    }).compile();

    app = moduleFixture.createNestApplication();

    const { httpAdapter } = app.get(HttpAdapterHost);
    const cls = app.get(ClsService);
    const reflector = app.get(Reflector);
    const configService = app.get(ConfigService);

    // ✅ CRITICAL: Use custom logger with file output (same as main.ts)
    app.useLogger(app.get(CustomLoggerService));

    // ✅ CRITICAL: Global interceptors (same as main.ts)
    app.useGlobalInterceptors(new HttpRequestLoggingInterceptor(cls, reflector));
    app.useGlobalInterceptors(new KafkaRequestLoggingInterceptor(cls, reflector));

    // ✅ CRITICAL: Global exception filters (same as main.ts)
    app.useGlobalFilters(new UnknownExceptionsFilter(httpAdapter));
    app.useGlobalFilters(new DefaultValidateExceptionFilter(httpAdapter));
    app.useGlobalFilters(new DefaultInternalExceptionFilter(httpAdapter));
    app.useGlobalFilters(new HttpExceptionFilter(httpAdapter));

    // ✅ CRITICAL: ValidationPipe BEFORE connectMicroservice
    app.useGlobalPipes(new ValidationPipe(DefaultValidationOptions));

    // ✅ CRITICAL: Kafka with inheritAppConfig: true
    const uniqueGroupId = `${configService.get('KAFKA_DEFAULT_GROUP_ID')}-e2e-${Date.now()}`;
    app.connectMicroservice(
      {
        transport: Transport.KAFKA,
        options: {
          client: {
            clientId: configService.get('KAFKA_DEFAULT_CLIENT_ID'),
            brokers: [configService.get('KAFKA_DEFAULT_BROKER_URL')],
          },
          consumer: { groupId: uniqueGroupId, allowAutoTopicCreation: true },
          subscribe: { fromBeginning: false }, // Skip old messages
        },
      },
      { inheritAppConfig: true },
    );

    await app.startAllMicroservices();
    await app.init();
  }, 90000);

  afterAll(async () => {
    await app?.close();
  }, 30000);
});
```

## MongoDB Isolation

```typescript
beforeEach(async () => {
  await new Promise((r) => setTimeout(r, 1000)); // Wait for in-flight messages
  await yourModel.deleteMany({});
});

afterEach(async () => {
  await yourModel.deleteMany({});
});
```

## Kafka Async Testing

### Topic Creation (CRITICAL)

**ALWAYS create topics explicitly before tests** - Never rely on auto-creation timing.

```typescript
import { AdminClient, type IAdminClient, type LibrdKafkaError } from '@confluentinc/kafka-javascript';

// In KafkaTestHelper class
private adminClient: IAdminClient | null = null;

initializeAdmin(brokers: string = 'localhost:9092'): void {
  this.adminClient = AdminClient.create({
    'bootstrap.servers': brokers,
    'client.id': 'kafka-test-helper-admin',
  });
}

async createTopicIfNotExists(topic: string, numPartitions: number = 1, replicationFactor: number = 1): Promise<void> {
  return new Promise((resolve, reject) => {
    this.adminClient!.createTopic(
      { topic, num_partitions: numPartitions, replication_factor: replicationFactor },
      (err: LibrdKafkaError) => {
        if (err) {
          // Topic already exists (code 36) is acceptable
          if (err.code === 36) resolve();
          else reject(new Error(`Failed to create topic '${topic}': ${err.message}`));
        } else {
          resolve();
        }
      },
    );
  });
}

disconnectAdmin(): void {
  if (this.adminClient) {
    this.adminClient.disconnect();
    this.adminClient = null;
  }
}
```

**Usage in Tests:**

```typescript
beforeAll(async () => {
  kafkaHelper = new KafkaTestHelper();
  kafkaHelper.initializeAdmin('localhost:9092');

  // ✅ CRITICAL: Create topic before tests to avoid auto-creation timing issues
  await kafkaHelper.createTopicIfNotExists(testTopic, 1, 1);
}, 90000);

afterAll(async () => {
  kafkaHelper.clearAll();
  kafkaHelper.disconnectAdmin();
}, 30000);
```

**Why explicit topic creation?**

- ❌ Auto-creation timing is unpredictable (100-3000ms delay)
- ❌ `Broker: Unknown topic or partition` errors in fast tests
- ❌ Fixed waits (2-5s) are unreliable and slow
- ✅ Explicit creation guarantees topic exists before first message
- ✅ Faster test execution (no arbitrary waits)
- ✅ 100% reliable test runs

### Smart Polling (Preferred)

```typescript
// ✅ PREFERRED: Smart polling - returns immediately when ready
const messages = await kafkaHelper.waitForMessages(topic, 1, 20000);

// ❌ AVOID: Fixed waits - always waits full duration
await new Promise((r) => setTimeout(r, 8000));
```

### Legacy Fixed Wait Pattern

```typescript
// Only use when smart polling is not available
it('should process Kafka message', async () => {
  await kafkaClient.emit(topic, event);
  await new Promise((r) => setTimeout(r, 8000)); // Wait 8s for processing

  const result = await yourModel.findOne({ id: event.id });
  expect(result).toBeDefined();
});
```

## HTTP Mocking with Retry Logic

Mock ALL retry attempts, not just one:

```typescript
// ❌ BAD - Retry succeeds on 2nd attempt
mockHttpService.post.mockReturnValueOnce(of({ status: 500 }));

// ✅ GOOD - All 3 retry attempts fail
mockHttpService.post.mockClear();
mockHttpService.post.mockReturnValueOnce(of({ status: 500 })); // attempt 1
mockHttpService.post.mockReturnValueOnce(of({ status: 500 })); // attempt 2
mockHttpService.post.mockReturnValueOnce(of({ status: 500 })); // attempt 3

// Or use mockReturnValue for continuous failures
mockHttpService.post.mockReturnValue(of({ status: 500 }));
```

## GWT Pattern (Given-When-Then)

**CRITICAL**: ALL E2E tests MUST follow GWT (Given-When-Then) pattern with comments.

```typescript
it('should create blog and publish domain event', async () => {
  // GIVEN: Test data is prepared
  const createBlogDto = { title: 'Test Blog', content: 'Content', authorId: 'author-123' };

  // WHEN: Creating a new blog
  const response = await request(setup.httpServer).post('/blogs').send(createBlogDto).expect(201);

  // THEN: Blog is created and event is published
  expect(response.body.code).toBe(ErrorCode.SUCCESS);
  await postgresHelper.assertRecordExists(BlogSchema, { id: response.body.data.id }, { title: 'Test Blog' });
  const event = await setup.waitForMessage(DOMAIN_EVENT_TOPIC, (msg) => msg.payload?.blogId === response.body.data.id, 8000);
  expect(event).toBeDefined();
});
```

**Rules**:

- Mark sections with `// GIVEN:`, `// WHEN:`, `// THEN:` (use uppercase and colon for consistency)
- GIVEN: Set up test data, preconditions, and context - describe the initial state
- WHEN: Execute ONE primary action only (single HTTP request/event) - describe what happens
- THEN: Verify all outcomes (response, database state, events) - describe expected results
- One test = one behavior (split multiple operations into separate tests)

**Rationale for GWT in E2E Tests**:

- **E2E tests describe system behavior** from user perspective, not implementation details
- **GWT reads like requirements** - easier to map to acceptance criteria and user stories
- **Clear separation** between context (GIVEN), action (WHEN), and expected outcome (THEN)
- **Better for non-technical stakeholders** to understand test intent
- **Aligns with BDD principles** - tests as living documentation

**Note**: Unit tests should continue using AAA pattern (Arrange-Act-Assert) as they focus on implementation details and technical behavior of code units.

## Assertion Rules

**Rule 1: Assert Specific Values** - Assert ALL properties with specific expected values, not just types or existence.

```typescript
// ❌ BAD
expect(response.body.data).toBeDefined();
expect(typeof response.body.data.id).toBe('string');

// ✅ GOOD
expect(response.body).toEqual({
  code: ErrorCode.SUCCESS,
  message: 'User retrieved successfully',
  data: { id: userId, email: 'test@example.com', name: 'John Doe' },
});
// For arrays: validate length AND all item properties
expect(response.body.data).toHaveLength(2);
expect(response.body.data[0]).toEqual({ id: '123', name: 'User One' });
```

**Rule 2: Tests Must Fail When Results Differ** - Test must fail if ANY field is incorrect.

```typescript
// ❌ BAD - Passes even if name is wrong
expect(response.body.data.id).toBeDefined();

// ✅ GOOD - Fails if any field doesn't match
expect(response.body.data).toMatchObject({ email: 'test@example.com', name: 'John Doe', role: 'user' });
const savedUser = await userModel.findById(response.body.data.id);
expect(savedUser.email).toBe('test@example.com');
```

**Rule 3: No Conditional Assertions** - NEVER use `if` statements in assertions. Split into separate deterministic tests.

```typescript
// ❌ BAD
if (response.status === 200) {
  expect(response.body.data).toBeDefined();
}

// ✅ GOOD - Separate tests
it('should return user on success', async () => {
  await userModel.create({ _id: userId, email: 'test@example.com' });
  const response = await request(app.getHttpServer()).get(`/users/${userId}`).expect(200);
  expect(response.body).toEqual({ code: ErrorCode.SUCCESS, data: { id: userId, email: 'test@example.com' } });
});

it('should return 404 when not found', async () => {
  const response = await request(app.getHttpServer()).get('/users/nonexistent').expect(404);
  expect(response.body).toEqual({ code: ErrorCode.NOT_FOUND, message: 'User not found' });
});
```

## Exception Types

| Exception               | HTTP Status | Use Case                                         |
| ----------------------- | ----------- | ------------------------------------------------ |
| `ValidateException`     | 400         | Input validation, malformed requests             |
| `InternalException`     | 500         | Infrastructure failures, external service errors |
| `UnauthorizedException` | 401         | Authentication failures                          |

```typescript
// Infrastructure failure = InternalException (500)
throw new InternalException(ErrorCode.VMALERT_RELOAD_FAILED, 'vmalert unreachable');

// Client error = ValidateException (400)
throw new ValidateException(ErrorCode.INVALID_PROMQL, 'Invalid expression');
```

## Handling Failed Test Cases

**CRITICAL**: Fix ONE test at a time. NEVER fix multiple simultaneously.

**Workflow**:

1. Create `_e2e-failures.md` tracking file with test name, file, error, status
2. Select ONE failing test
3. Run ONLY that test: `npm run test:e2e test/blog.e2e-spec.ts -t "test name"`
4. Analyze logs: `cat logs/e2e-test.log | grep -A 20 "FAIL"`
5. Fix and re-run SAME test to verify
6. Mark as fixed in tracking file
7. Repeat for next test
8. Run full suite ONLY after ALL individual tests pass
9. Delete tracking file when complete

**Why?**

- Prevents cascading failures from obscuring root causes
- Easier to identify which fix resolved which issue
- Incremental progress tracking
- Clean git history with isolated fixes

## Debugging

```bash
# View logs
cat logs/e2e-test.log
grep -i error logs/e2e-test.log
tail -n 100 logs/e2e-test.log

# Find failures in console output
grep -E "FAIL|Error|expected.*got" e2e-output.log
```

## Checklist

**Environment:**

- [ ] `.env.e2e` with file logging configuration
- [ ] `LOG_FILE=./logs/e2e-test.log`
- [ ] `LOG_SYNC_FILE=./logs/application.pid`
- [ ] `logs/` directory in `.gitignore`
- [ ] Global setup deletes previous `logs/e2e-test.log` file before test execution

**Setup:**

- [ ] Use real logger via `app.useLogger(app.get(CustomLoggerService))`
- [ ] DO NOT mock logger (MockLoggerService)
- [ ] DO NOT log to console (use file output)
- [ ] Global filters (UnknownExceptions, Validate, Internal, Http)
- [ ] Global interceptors
- [ ] ValidationPipe BEFORE connectMicroservice
- [ ] `inheritAppConfig: true` for Kafka
- [ ] Unique consumer group ID
- [ ] `--runInBand` in package.json

**Test Structure:**

- [ ] ALL tests follow GWT pattern (Given-When-Then)
- [ ] GWT sections marked with comments: `// GIVEN:`, `// WHEN:`, `// THEN:` (uppercase with colon)
- [ ] One test, one behavior (no multiple WHEN actions in single test)
- [ ] GIVEN section creates all test data upfront and describes preconditions
- [ ] WHEN section contains only one primary action
- [ ] THEN section verifies all relevant outcomes

**Test Isolation:**

- [ ] MongoDB cleanup in beforeEach/afterEach
- [ ] 1s wait before cleanup for in-flight messages

**Kafka Setup:**

- [ ] Create topics explicitly in `beforeAll` using `createTopicIfNotExists()`
- [ ] Initialize admin client before topic creation
- [ ] Disconnect admin client in `afterAll`
- [ ] Use smart polling instead of fixed waits
- [ ] 20s max timeout for message polling

**Async:**

- [ ] 25s timeout for async tests
- [ ] Use smart polling (preferred) or 8-10s wait after Kafka emit
- [ ] 90s timeout for beforeAll

**Mocking:**

- [ ] Mock ALL retry attempts
- [ ] Use correct exception type for expected HTTP status
- [ ] Verify mock call counts match retry behavior

**Assertions:**

- [ ] Assert specific values, not just types or property existence
- [ ] Validate ALL response properties with expected values
- [ ] Tests fail when any field differs from expectations
- [ ] No conditional assertions (no `if` statements)
- [ ] Separate test cases for different scenarios (success vs error)
- [ ] For list responses, validate array length and all item properties
- [ ] Verify database state matches expected values

**Failure Handling:**

- [ ] When failures found, create `_e2e-failures.md` tracking file
- [ ] Fix ONE test case at a time (NEVER multiple simultaneously)
- [ ] Run individual test to verify fix before moving to next
- [ ] Update tracking file status after each fix
- [ ] Run full suite ONLY after all tests fixed individually
- [ ] Delete tracking file when all tests pass
