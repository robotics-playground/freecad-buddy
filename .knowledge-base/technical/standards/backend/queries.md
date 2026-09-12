---
title: "Database Query Best Practices"
category: "backend"
tags: ["database", "sql", "performance", "security", "queries"]
description: "Guidelines for writing secure, efficient, and maintainable database queries including SQL injection prevention, N+1 query avoidance, indexing strategies, and caching recommendations"
last_updated: "2025-01-02"
---

## Database query best practices

- **Prevent SQL Injection**: Always use parameterized queries or ORM methods; never interpolate user input into SQL strings
- **Avoid N+1 Queries**: Use eager loading or joins to fetch related data in a single query instead of multiple queries
- **Select Only Needed Data**: Request only the columns you need rather than using SELECT * for better performance
- **Index Strategic Columns**: Index columns used in WHERE, JOIN, and ORDER BY clauses for query optimization
- **Use Transactions for Related Changes**: Wrap related database operations in transactions to maintain data consistency
- **Set Query Timeouts**: Implement timeouts to prevent runaway queries from impacting system performance
- **Cache Expensive Queries**: Cache results of complex or frequently-run queries when appropriate
