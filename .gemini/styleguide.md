# MacTech Pull Request Review Standard

## Review priorities

Review for correctness, security, tenant isolation, authorization, data integrity, maintainability, test coverage, user-facing workflow completeness, and regressions.

Prioritize substantive defects over stylistic preferences.

## Security and authorization

- Flag authentication or authorization bypasses.
- Never trust tenant IDs, organization IDs, user IDs, roles, entitlements, or permissions supplied only by the browser.
- Verify authorization on the server for every protected operation.
- Preserve the established authentication and Hub authorization boundaries.
- Flag direct access that bypasses the designated source-of-truth service.
- Flag cross-tenant data exposure, insecure direct-object references, privilege escalation, and missing ownership checks.
- Flag secrets, tokens, credentials, CUI, sensitive customer information, personal information, or internal security data written to source code, logs, analytics, URLs, or client state.
- Flag insecure defaults, fail-open behavior, weak cryptography, unsafe deserialization, injection risks, SSRF, XSS, CSRF, path traversal, and command execution.
- Do not recommend disabling security controls merely to make a workflow pass.

## Application architecture

- Preserve existing repository and suite architecture unless the PR explicitly documents an approved migration.
- Do not duplicate an existing service, API, schema, authorization resolver, workflow engine, or source of truth.
- Flag frontend capabilities that appear functional but are disconnected from the backend.
- Flag backend capabilities that are unintentionally inaccessible through the intended UI.
- Verify loading, empty, success, partial-failure, validation, unauthorized, forbidden, and server-error states.
- Flag breaking API or schema changes that lack a compatibility or migration plan.
- Flag hidden coupling between applications or tenants.

## TypeScript and Node.js

- Prefer strict TypeScript and explicit domain types.
- Flag unsafe use of any, unchecked casts, ignored compiler errors, and unvalidated external input.
- Validate request bodies, query parameters, environment variables, webhook payloads, and third-party responses at runtime.
- Handle asynchronous errors explicitly.
- Avoid swallowed exceptions and misleading success responses.
- Flag unbounded concurrency, blocking operations, resource leaks, retry storms, and missing timeouts.
- Do not weaken lint, test, type-check, or build configuration to make a change pass.

## Data and database behavior

- Flag destructive, irreversible, or non-backward-compatible migrations.
- Require authorization and tenant filtering in data-access operations.
- Flag race conditions, non-atomic multi-step updates, duplicate event handling, and missing idempotency.
- Do not expose internal database identifiers unnecessarily.
- Require safe rollback or recovery considerations for high-impact changes.

## Testing

- Require meaningful tests for new logic and corrected defects.
- Tests must validate behavior rather than merely duplicate implementation details.
- Flag tests that are skipped, weakened, deleted, or replaced with superficial assertions.
- Require negative authorization and tenant-isolation tests for protected workflows.
- Require regression coverage when a PR fixes a defect.
- Do not accept mocked success paths as the only evidence for an integration workflow.

## UI and accessibility

- Maintain visual and interaction consistency with the rest of the MacTech Suite.
- Flag dead controls, placeholder interactions, missing confirmation states, silent failures, and inaccessible workflows.
- Require keyboard accessibility, meaningful labels, focus handling, and adequate error messaging.
- Avoid large UI rewrites unrelated to the PR's stated purpose.

## Operational safety

- Flag undocumented environment-variable additions.
- Flag changes that can alter production behavior without an explicit rollout plan.
- Do not recommend committing secrets or production configuration.
- Flag changes to GitHub Actions, deployment workflows, branch protections, and release processes for mandatory human review.
- Require logging and audit events for security-sensitive administrative actions, without logging sensitive content.

## Review response quality

Each finding should include:

1. Severity
2. Exact file and location
3. Why the behavior is defective or risky
4. A realistic failure or abuse scenario
5. The smallest safe correction
6. Whether a test should be added

Do not flood the PR with cosmetic observations. Consolidate closely related findings.
