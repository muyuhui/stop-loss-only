# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

止损不止盈 (Stop Loss Only) — a local stop-loss monitoring tool for A-shares (Chinese stocks) and funds. Read-only: no broker integration, no automatic order placement. Tracks holdings, fetches market prices via AkShare, evaluates stop-loss rules, and generates alerts.

## Commands

All scripts run from the repo root:

```powershell
.\setup.ps1              # Install backend + frontend dependencies
.\setup.ps1 -Dev         # Include test dependencies
.\start.ps1              # Production start (backend on :8001, frontend on :5173, 127.0.0.1 only)
.\stop.ps1               # Stop services (only kills PID-matched project processes)
.\dev.ps1                # Dev mode: backend with reload, scheduler disabled
.\verify.ps1             # Full quality gate: backend tests → frontend tests → build → E2E smoke → OpenSpec
.\backup.ps1             # Create database backup with SHA-256 manifest
.\restore.ps1 -Backup <file> -Manifest <file>  # Restore from verified backup (stop backend first)
```

**Backend-only commands** (from `backend/` directory):
```bash
python db_admin.py status          # Show current schema version
python db_admin.py upgrade         # Run pending migrations
python db_admin.py downgrade       # Rollback latest version
python db_admin.py shadow-status   # Check position-domain migration stage
python db_admin.py shadow-enable   # Enable shadow-read stage
python db_admin.py shadow-rebuild  # Rebuild shadow projection after interruption
python db_admin.py cutover         # Irreversible: make positions authoritative (stop app first)
python -m pytest -p no:cacheprovider -q   # Run backend tests (hermetic, no real network)
```

**Frontend-only commands** (from `frontend/` directory):
```bash
npm run dev       # Vite dev server (proxies /api to :8001)
npm run build     # Production build + bundle budget check
npm test          # Run Node test runner + Vitest mount tests
```

## Architecture

### Backend (Python / FastAPI / SQLite)

**Entry point**: `backend/main.py` — `create_app()` factory with lifespan-managed scheduler. CORS restricted to `localhost:5173`.

**Request flow**: `main.py` → `routers/` (API layer) → `services/` (business logic) → `models.py` (SQLAlchemy ORM) → SQLite via `database.py`

**Configuration**: Immutable `AppConfig` dataclass in `backend/config.py`. All settings via `STOP_LOSS_*` env vars — no `.env` files. Key env vars: `STOP_LOSS_FIXTURE_PRICE` (enables fake prices for testing), `STOP_LOSS_SCHEDULER_ENABLED`.

**Schema migration**: Custom integer-revision runner in `backend/migrations.py` (NOT Alembic). Each revision is idempotent — inserts `OR IGNORE` into `schema_migrations`. `LATEST_SCHEMA_VERSION = 7`. Pre-upgrade auto-backup on first migration from unversioned state. The `upgrade()` function uses `Base.metadata.create_all()` followed by ALTER TABLE additions.

**Dual domain model** (v4+ migration in progress):
- **Legacy**: `holdings` table — simple flat model, the original authority
- **New**: `positions` + `position_lots` + `close_allocations` + `stop_rules` + `position_events` + `position_quotes` — FIFO lot tracking, event sourcing, versioned stop rules
- **Bridge**: `services/shadow_projection.py` — keeps new tables in sync with legacy writes. Three authority stages: `legacy` → `shadow-read` → `new-authoritative`. Cutover is irreversible offline operation.

**API Routers** (`backend/routers/`):

| Router | Prefix | Notes |
|--------|--------|-------|
| `holdings.py` | `/api/holdings` | Legacy CRUD; delegates to positions in new-authoritative stage; includes `/history` for price charts |
| `positions.py` | `/api/positions` | New domain (only active in new-authoritative): open, add lots, close, acknowledge, rearm, history |
| `prices.py` | `/api/prices` | Current prices + refresh trigger (delegates to monitoring cycle) |
| `alerts.py` | `/api/alerts` | List, count, mark-read for triggered alerts |
| `dashboard.py` | `/api/dashboard` | Aggregate metrics: active/toal cost, market value, P&L, alert counts |
| `settings.py` | `/api/settings` | Runtime settings: poll/monitor intervals, webhook config, retention |
| `monitoring.py` | `/api/monitoring` | Scheduler status, cycle history with pagination/filtering |
| `operations.py` | `/api/operations` | CSV import/export, diagnostics dump |

**Quote system** (`backend/services/quote_contracts.py`): `NormalizedQuote` is the universal data class. `QuoteState` enum: `unpriced → live | delayed | close | nav | stale | error`. Only `is_actionable=True` quotes trigger stop-loss. `CalendarDecision` encodes trading day + session with degradation tracking (authoritative → valid_cache → weekday_fallback).

**Provider abstraction** (`backend/services/provider_adapters.py`): `AkshareQuoteProvider` and `AkshareMarketCalendar` for live data; `FixtureQuoteProvider` and `FixtureCalendar` for testing (activated when `STOP_LOSS_FIXTURE_PRICE` is set).

**Stop-loss engine** (`backend/services/stop_loss.py`): Three methods — `fixed` (absolute price floor), `percentage` (% below buy price), `trailing` (% below highest price since purchase). All math uses `Decimal` with 4-decimal precision.

**Monitoring** (`backend/services/monitoring.py`): `run_monitoring_cycle()` acquires a threading lock, fetches prices, evaluates stop-loss, creates alerts, and records a `MonitoringCycle`. Used by both scheduler and manual refresh.

**Network guard** (`backend/network_guard.py`): Monkey-patches `socket.getaddrinfo`/`create_connection` to block external network. Tests install it with `allow_loopback=True` for hermetic runs.

**Logging** (`backend/observability.py`): JSON-structured logs with correlation IDs; `RequestLoggingMiddleware` attaches `x-correlation-id` to every response.

### Frontend (Vue 3 / Element Plus / Vite)

**Entry**: `frontend/src/main.js` → `App.vue` → router

**Routes**: `/` (Dashboard), `/holdings` (list), `/holdings/:id` (detail + chart), `/alerts`, `/settings`

**State**: Pinia stores in `src/stores/` — `resource.js` (generic async resource pattern with polling), `alert.js`, `settings.js`, `monitoring.js`, `positions.js`

**API layer** (`src/api/index.js`): Axios instance with base `/api`, 15s timeout. Response interceptor extracts error details for toast messages. Two special functions with 60s timeout: `requestPriceRefresh()` and `requestHoldingHistory()`.

**Key components**: `HoldingPriceChart.vue` (ECharts-based price history with stop-loss lines), `HoldingForm.vue` (create/edit holdings), `FilterToolbar.vue` (URL-persisted filter state), `DataState.vue` (quote state badges), `StatusBanner.vue`

**Vite config**: Dev proxy `/api` → `http://localhost:8001`. Production build splits echarts/zrender into separate chunks. Bundle budget enforced by `scripts/check-bundle.mjs`.

### Database

SQLite with `PRAGMA foreign_keys=ON`. Check constraints on status enums. Key tables: `holdings` (legacy), `positions`/`position_lots`/`close_allocations`/`stop_rules`/`position_events`/`position_quotes` (new domain), `alerts`, `settings`, `schema_migrations`, `monitoring_cycles`, `instruments`, `accounts`, `migration_authority`, `delivery_attempts`, `channel_metadata`, `import_audits`, `retention_state`, `price_history`.

### Testing

- **Backend**: pytest with session-scoped hermetic network fixture (`conftest.py`). Tests use `FixtureQuoteProvider`/`FixtureCalendar` — never hit real APIs. Tests in `backend/tests/` organized by domain: `test_api.py`, `test_monitoring.py`, `test_monitoring_trust.py`, `test_quote_providers.py`, `test_position_domain.py`, `test_shadow_projection.py`, etc.
- **Frontend**: Node native test runner for behavior tests (`tests/frontend-experience.test.js`, etc.) + Vitest with jsdom for mount tests (`*.mount.spec.js`).
- **E2E smoke**: `scripts/smoke.py` — starts backend + static frontend server on random ports, runs CRUD + refresh + alert flow against them, then terminates.

### OpenSpec

Spec-driven development in `openspec/`. `config.yaml` sets `schema: spec-driven`. Change proposals archived under `openspec/changes/archive/`.

## Key Design Conventions

- **Immutability**: `AppConfig` is a frozen dataclass. Quote contracts use frozen dataclasses. Services return new state, never mutate in place.
- **Single-process assumption**: Single worker, single scheduler, no multiprocess coordination. The `_refresh_lock` is a threading lock, not a distributed lock.
- **Hermetic testing**: Tests block external network at the socket level. Use fixture prices for deterministic test data.
- **Migration is revision-authoritative**: The in-app migration runner owns the schema; never run external DDL on the database.
- **Quote trust chain**: Only fresh, calendar-verified quotes with `is_actionable=True` trigger stop-loss. Weekend/closed-session quotes are informational only.
- **Error handling**: Services raise typed exceptions (`ProviderFailure`, `MonitoringDatabaseBusy`, `HistoryUnavailable`). Routers convert to HTTP exceptions with structured detail objects.
- **Precision**: All financial math uses `Decimal` with explicit quantization. Never use floats for prices/costs/quantities in backend.
