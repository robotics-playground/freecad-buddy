---
title: "Use Case Standards"
category: "backend"
tags: ["cqrs", "use-cases", "typescript", "nestjs", "clean-architecture", "design-patterns"]
description: "Standards for implementing Use Cases following CQRS pattern with single responsibility, including return type conventions for queries and commands, transaction handling, and anti-patterns to avoid"
last_updated: "2025-01-02"
---

# Use Case Standards

> **Pattern:** CQRS with single responsibility. Use Cases return Presenter or Response Model, Controller wraps in HttpApiResponse.

## Core Rules

| Rule | Requirement |
|------|-------------|
| Pattern | CQRS: Separate command (write) and query (read) |
| GET Response | `Promise<Presenter>` - Controller wraps in `HttpApiResponse` |
| POST/PUT/DELETE Response | `Promise<ResponseModel>` - Controller wraps in `HttpApiResponse` |
| Entry point | Always name main method `execute()` |
| Errors | Let errors bubble unless rollback needed |
| File naming | `{verb}-{entity}.usecase.ts` |
| Class naming | `{Verb}{Entity}UseCase` |

**IMPORTANT:** Use Cases NEVER return raw Entities. Always convert to Presenter or Response Model.

## Return Type Pattern

| HTTP Method | Use Case Returns | Location |
|-------------|------------------|----------|
| **GET** | Presenter | `models/presenters/` |
| **POST/PUT/DELETE** | Response Model | `models/responses/` |
| **Event Handler** | `void` | - |

## GET Use Case (Returns Presenter)

```typescript
@Injectable()
export class GetBlogUseCase {
  private readonly logger = new Logger(GetBlogUseCase.name);

  constructor(
    @Inject(BLOG_REPOSITORY)
    private readonly repository: IBlogRepository,
  ) {}

  /**
   * Retrieves blog by ID
   * @param id - Blog ID
   * @returns Blog presenter
   * @throws NotFoundException if blog not found
   */
  async execute(id: string): Promise<BlogPresenter> {
    const blog = await this.repository.findById(id);
    if (!blog) {
      throw new NotFoundException(`Blog ${id} not found`);
    }
    return new BlogPresenter(blog);
  }
}

// Controller wraps in HttpApiResponse
@Get(':id')
async getById(@Param('id') id: string): Promise<HttpApiResponse<BlogPresenter>> {
  const presenter = await this.getBlogUseCase.execute(id);
  return HttpApiResponse.success(presenter);
}
```

## POST Use Case (Returns Response Model)

```typescript
@Injectable()
export class CreateBlogUseCase {
  private readonly logger = new Logger(CreateBlogUseCase.name);

  constructor(
    @Inject(BLOG_REPOSITORY)
    private readonly repository: IBlogRepository,
    private readonly eventBus: EventBus,
  ) {}

  /**
   * Creates blog with validation
   * @param request - Blog creation request
   * @returns Created blog response
   * @throws ValidateException if validation fails
   */
  async execute(request: CreateBlogRequest): Promise<CreateBlogResponse> {
    const blog = await this.repository.create({
      title: request.title,
      content: request.content,
      authorId: request.authorId,
    });

    this.eventBus.publish(new BlogCreatedEvent(blog));
    return new CreateBlogResponse(blog);
  }
}

// Controller wraps in HttpApiResponse
@Post()
async create(@Body() dto: CreateBlogRequest): Promise<HttpApiResponse<CreateBlogResponse>> {
  const response = await this.createBlogUseCase.execute(dto);
  return HttpApiResponse.success(response);
}
```

## Transaction/Rollback Pattern

```typescript
async execute(request: CreateBlogRequest): Promise<CreateBlogResponse> {
  let blog: Blog | null = null;

  try {
    blog = await this.repository.create(request);
    await this.externalService.deploy(blog);
    return new CreateBlogResponse(blog);
  } catch (error) {
    await this.rollback(blog, error as Error);
    throw error;
  }
}

private async rollback(blog: Blog | null, error: Error): Promise<void> {
  this.logger.error(`Failed: ${error.message}. Rolling back...`);
  if (blog) {
    try {
      await this.repository.delete(blog.id);
      this.logger.log(`Rollback: Deleted ${blog.id}`);
    } catch (rollbackError) {
      this.logger.error(`Rollback failed: ${rollbackError['message']}`);
    }
  }
}
```

## Query Use Case (Returns Paginated Presenter)

```typescript
async execute(searchDto: ListBlogsRequest): Promise<PaginatedBlogsPresenter> {
  const { items, total } = await this.repository.search({
    skip: (searchDto.page - 1) * searchDto.limit,
    limit: searchDto.limit,
  });

  return new PaginatedBlogsPresenter({
    items,
    total,
    page: searchDto.page,
    limit: searchDto.limit,
  });
}
```

## Event Handler (Returns void)

```typescript
async execute(event: DomainEventDto): Promise<void> {
  await this.repository.create({
    eventCode: event.code,
    entityType: event.source.module,
    entityId: event.payload.id,
    action: this.determineAction(event.code),
    payload: event.payload,
    actor: event.actor,
    timestamp: event.timestamp,
  });
}
```

## Anti-Patterns

```typescript
// ❌ Business logic in controller
@Post()
async create(@Body() dto: CreateDto) {
  const blog = await this.repository.create(dto);
  await this.publishEvent(blog);  // Should be in use case
  return blog;
}

// ❌ Returning raw entity
async execute(id: string): Promise<Blog> {
  return await this.repository.findById(id);
}

// ❌ Use Case returning HttpApiResponse (Controller's responsibility)
async execute(id: string): Promise<HttpApiResponse<Blog>> {
  const blog = await this.repository.findById(id);
  return HttpApiResponse.success(blog);
}

// ❌ Try-catch for logging only
try {
  await this.repository.create(dto);
} catch (error) {
  this.logger.error('Error');  // Global handler logs!
  throw error;
}

// ❌ God use case
class ManageBlogsUseCase {
  async create() { }
  async update() { }
  async delete() { }
}
```

## Checklist

- [ ] GET returns `Promise<Presenter>`
- [ ] POST/PUT/DELETE returns `Promise<ResponseModel>`
- [ ] Event handlers return `Promise<void>`
- [ ] Controller wraps result in `HttpApiResponse`
- [ ] Main method named `execute()`
- [ ] Single responsibility
- [ ] JSDoc on `execute()` method
- [ ] Implements rollback for multi-step operations
- [ ] Lets errors bubble (no try-catch for logging)
- [ ] Constructor injection for dependencies
- [ ] Repository interfaces, not implementations
