# ADR 0001: SQLite for Phase A

## Status

Accepted — Phase A

## Context

Continuum needs persistent typed memory immediately for hackathon vertical slice: ingest Session A, pack in Session B, inspector UI, forgetting audit. Full Alibaba Tablestore/RDS provisioning is Phase B.

## Decision

Use **SQLite** via `continuum_memory.store.MemoryStore` at `data/continuum.db` (configurable via `CONTINUUM_DB_PATH`).

## Consequences

**Pros**

- Zero infra for local dev and judges
- Single-file DB for smoke eval temp databases
- Full SQL audit log for forget events

**Cons**

- Not multi-tenant production scale
- Migration required for cloud store (Phase B)

## Follow-up

Abstract store interface; add Tablestore adapter behind same `MemoryService` API.
