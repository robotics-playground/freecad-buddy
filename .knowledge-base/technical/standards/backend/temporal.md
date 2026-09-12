# Temporal Coding Standards

## Workflow Code (replayable)

Temporal **replays** workflow code on recovery and worker failure. Any non-determinism breaks replay.

### Forbidden in workflow code
- `datetime.now()`, `datetime.utcnow()`, `time.time()`
- `random.*`, `secrets.*`
- `uuid.uuid4()`, `uuid.uuid1()`
- File I/O, network I/O, DB queries
- `asyncio.create_task()` (use `workflow.start_activity` / `workflow.execute_child_workflow`)
- Reading env vars or `sys.argv`

### Allowed (deterministic Temporal primitives)
- `workflow.now()`, `workflow.uuid4()`, `workflow.random()`
- `workflow.wait_condition()`, `workflow.execute_activity()`, `workflow.execute_child_workflow()`
- `workflow.signal` handlers, `workflow.query` handlers
- Pure-Python data manipulation (`collections.deque`, `dataclasses`, dict/list/set ops)
- `workflow.get_external_workflow_handle(...).signal(...)` (workflow-safe signal)

### Workflow registration
- `@workflow.defn(name="ExplicitName")` — name MUST match dispatch contract (e.g., DreamCoordinator's `_KIND_CONFIG`).
- `with workflow.unsafe.imports_passed_through():` is required for activity imports inside the workflow file (sandbox bypass for activity callables).

## Activity Code

Activities run outside the workflow sandbox — full Python, full I/O, full SDK access.

### Idempotency contract (mandatory)

Temporal retries activities. Every activity MUST be idempotent OR thread an idempotency key:

- **Git operations:** deterministic branch name + `git fetch && git checkout -B <branch>` (resets to known state). PR creation: `gh pr view <branch>` before `gh pr create` (returns existing URL on retry).
- **MemU writes:** thread an `idempotency_key` (use `dream-{dream_id}` or `workflow.run_id`); the underlying service must check and skip on duplicate key.
- **DB writes:** use `INSERT ... ON CONFLICT DO UPDATE` or check existence first.
- **File writes:** atomic temp-file + rename (existing `Story 11.11` pattern is sufficient).

### Retry policies

Every `workflow.execute_activity(...)` call MUST pass an explicit `retry_policy=RetryPolicy(...)` and `start_to_close_timeout=timedelta(...)`. Pick policies based on the operation's failure mode:

- LLM calls: `max_attempts=2` (LLM is expensive; don't retry many times).
- DB writes: `max_attempts=5` (idempotent and fast).
- Git operations: `max_attempts=3`.
- Bounded internal loops (e.g., `health_fix` 3-iteration loop): set Temporal `max_attempts=1` to prevent compounding.

### Soft-fail vs hard-fail

- Hard fail: `raise` an exception → Temporal retries per policy → eventually fails the workflow.
- `non_retryable=True`: raise `temporalio.exceptions.ApplicationError(non_retryable=True, ...)` for deterministic errors (missing record, schema violation) → Temporal stops retrying immediately.
- Soft fail: `try/except` inside activity, return a sentinel (e.g., `None` or `Result(status="incomplete")`). Workflow continues. Use this for **partial** semantics where downstream activities can still run with no upstream output.

## Activity catalogue

The authoritative per-activity spec — name, input/output, retry policy, idempotency contract, failure modes — lives in `design/temporal-workflows.md §5` (subsections §5.1 light, §5.2 deep, §5.3 weekly).

## References

- `design/temporal-workflows.md` — authoritative Epic 12 spec (workflow IDs, activity catalogue, schedules, cutover history)
- `app/workflows/coordinator.py` — DreamCoordinator (single-active-dream invariant proof in code comments)
- `app/workflows/light_dream_workflow.py` / `deep_dream_workflow.py` / `weekly_review_workflow.py` — three pipeline workflows
- `app/activities/{light,deep,weekly}/` — per-pipeline activity directories
- `app/temporal_client.py` — singleton client + `signal_coordinator(kind, payload)` helper
- `app/temporal_worker.py` — worker bootstrap (co-located in FastAPI lifespan)
- `app/temporal_schedules.py` — `register_schedules(client)` (idempotent on every server startup)
- `app/workflows/schedule_relay.py` — `ScheduleSignalRelayWorkflow` (computes fire-time date, signals coordinator)
