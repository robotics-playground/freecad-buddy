---
title: "Security Standards"
category: "global"
tags: ["security", "owasp", "input-validation", "secrets-management", "vulnerability-prevention"]
description: "Mandatory security standards covering input validation, secrets management, OWASP Top 10 protection, and security review checklists for all project code"
last_updated: "2025-01-02"
---

# Security Standards

**Last Updated:** 2025-10-24
**Applies To:** All epics, all stories, all developers
**Status:** Mandatory

---

## Overview

This document defines mandatory security standards for the 8ten-alert-service project. These standards apply to **ALL code, ALL stories, and ALL epics** throughout the entire project lifecycle.

---

## 1. Input Validation

- **Always validate inputs:** Use class-validator DTOs with ErrorCode context
- **Sanitize outputs:** Prevent injection attacks
- **Rate limiting:** Implement for public APIs

**See full documentation:** `/docs/standards/global/validation.md` and `/docs/standards/global/error-codes.md`

---

## 2. Secrets Management

- **No hardcoded secrets:** Use environment variables
- **Never log secrets:** Mask sensitive data in logs
- **Secure storage:** Use proper secret management tools

### Transcript Redaction (Jarvis)

Transcripts captured by Jarvis are redacted in three layers:

1. **Client** (plugin hooks) — `hooks/lib/transcript.js` redacts before POSTing.
2. **Server** (`SecretScrubber`) — `app/services/secret_scrubber.py` redacts authoritatively before any DB write. Source of truth for the pattern set.
3. **Agent prompts** — every agent handling transcripts carries a "Secret-Handling Rule" block instructing the LLM to treat any `[REDACTED_*]` marker or credential-like string as non-information.

Rules:

- Never log or transmit the actual matched content — only per-pattern counts.
- Redact-and-proceed: a matched secret never causes a dropped request.
- Pattern set is maintained in Story 10.1 acceptance criteria (`_bmad-output/implementation-artifacts/10-1-secret-redaction.md`).

---

## 3. Common Security Vulnerabilities

Ensure protection against OWASP Top 10 vulnerabilities:

- **Command Injection:** Never execute user input directly in shell commands
- **XSS (Cross-Site Scripting):** Sanitize all user-provided content before rendering
- **SQL Injection:** Use parameterized queries and ORMs (not raw SQL with string concatenation)
- **Authentication/Authorization:** Implement proper authentication and authorization checks
- **Sensitive Data Exposure:** Never expose secrets, credentials, or PII in logs or error messages
- **Security Misconfiguration:** Follow security best practices for frameworks and libraries
- **Insecure Deserialization:** Validate and sanitize all deserialized data
- **Using Components with Known Vulnerabilities:** Keep dependencies updated and scan for vulnerabilities
- **Insufficient Logging & Monitoring:** Log security-relevant events without exposing sensitive data
- **Server-Side Request Forgery (SSRF):** Validate and restrict URLs when making external requests

---

## 4. Review Checklist

Before marking a story complete, verify:

- [ ] All inputs validated using class-validator DTOs
- [ ] No hardcoded secrets or credentials in code
- [ ] Secrets never logged (masked in logs)
- [ ] Environment variables used for configuration
- [ ] No command injection vulnerabilities
- [ ] No XSS vulnerabilities (sanitized outputs)
- [ ] No SQL injection vulnerabilities (parameterized queries)
- [ ] Proper authentication and authorization checks
- [ ] No sensitive data exposure in logs or errors
- [ ] Rate limiting implemented for public APIs
- [ ] Dependencies scanned for known vulnerabilities

---

## Related Standards

- **Validation Standards:** `/docs/standards/global/validation.md`
- **Error Code Standards:** `/docs/standards/global/error-codes.md`
- **Logging Standards:** `/docs/standards/global/logging.md`

---

## Version History

- **v1.0 (2025-10-24):** Initial security standards document
  - Extracted from project-overview.md Section 6
  - Input validation, secrets management, and OWASP Top 10 protection defined
  - Review checklist created
