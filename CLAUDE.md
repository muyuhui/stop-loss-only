# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

止损不止盈 — a local stop-loss monitoring tool for A-shares and funds. The system tracks quotes, calculates stop-loss triggers, and generates alerts. It does **not** connect to brokers or place orders.

**Tech stack:** Python/FastAPI backend + Vue 3/Vite frontend, SQLite database, akshare for market data.

## Commands

All scripts run from the project root via PowerShell:

| Command | Purpose |
|---------|---------|
| `.\setup.ps1` | Install runtime dependencies |
| `.\setup.ps1 -Dev` | Install runtime + test dependencies |
| `.\start.ps1` | Start backend (127.0.0.1:8001) + frontend (127.0.0.1:5173) in production mode |
| `.\stop.ps1` | Stop services by PID/time/project matching |
| `.\dev.ps1` | Start in dev mode (backend reload on, scheduler off) |
| `.\verify.ps1` | Full quality gate: backend tests, frontend tests + build, E2E smoke, OpenSpec validation |
| `.\backup.ps1` | Create database backup with SHA-256 manifest |
| `.\restore.ps1 -Backup <file> -Manifest <file>` | Restore database (stop backend first) |

**Backend-only (from `backend/`):**
```bash
python -m pytest -p no:cacheprovider -q          # Run all backend tests (offline by default)
python db_admin.py status                         # Check migration version
python db_admin.py upgrade                        # Run migrations (with auto-backup)
python db_admin.py downgrade                      # Rollback to previous version
python db_admin.py shadow-enable                  # Enable shadow reads (position migration)
python db_admin.py shadow-rebuild                 # Rebuild shadow after interruption
python db_admin.py cutover                        # Finalize position domain cutover (offline)
```

**Frontend-only (from `frontend/`):**
```bash
npm test                   # Node test runner + vitest
npm run dev                # Vite dev server
npm run build              # Production build + bundle budget check
```

## Architecture

### Backend (`backend/`)

```
main.py              FastAPI app factory, lifespan (scheduler start/stop), middleware
config.py            Frozen AppConfig dataclass — all config via STOP_LOSS_* env vars
database.py          SQLAlchemy engine + session factory (SQLite with WAL, FK pragma)
models.py            All ORM models (single file)
schemas.py           All Pydantic request/response models (single file)
migrations.py        Ordered schema migration runner (NOT Alembic) — idempotent revision-based
db_admin.py          CLI for migrations, shadow ops, and cutover
scheduler.py         APScheduler wrapper for periodic monitoring
observability.py     Structured JSON logging + request logging middleware
network_guard.py     SSRF protection for outbound requests
time_utils.py        Timezone-aware datetime helpers
routers/
  holdings.py        Legacy CRUD + history endpoint (compatibility DTOs during migration)
  positions.py       New position domain API (lots, close, acknowledge, rearm, history)
  prices.py          Quote retrieval + refresh (batch and per-instrument)
  alerts.py          Alert listing and read/unread management
  dashboard.py       Portfolio summary (cost, market value, P&L, coverage)
  settings.py        Runtime settings (poll/monitor intervals, webhook config, retention)
  monitoring.py      Monitoring cycle history and status
  operations.py      CSV import/export, diagnostics
services/
  stop_loss.py        Pure calculation engine: fixed, percentage, trailing stop methods
  price_fetcher.py    Orchestrates batch quote fetching via provider adapters
  provider_adapters.py Akshare-based market calendar + quote provider with circuit breaker
  quote_contracts.py  Protocols and dataclasses for QuoteProvider, MarketCalendar, QuoteState
  market_clock.py     A-share trading session detection (Asia/Shanghai timezone)
  monitoring.py       Core monitoring cycle: fetch quotes → evaluate stops → trigger alerts
  position_domain.py  Domain logic for the new Position model (open, close, lots, rearm)
  shadow_projection.py Legacy→Position bidirectional projection during migration
  delivery.py         Optional signed webhook delivery with HMAC + retry
  csv_portability.py  CSV import/export with formula escaping and schema validation
  price_history.py    Historical price chart data with caching
  presentation.py     DTO formatting for API responses
  retention.py        Scheduled cleanup of old quotes and diagnostics
  secret_store.py     Environment-based secret management
  fixture_adapters.py Test fixtures for calendar and quote providers
```

**Key architectural patterns:**

- **Position domain migration**: The codebase is mid-migration from a legacy `holdings` model to a new `positions` domain (accounts, instruments, positions, lots, stop rules, events, quotes). Migration progresses through three stages: `legacy` → `shadow-read` → `new-authoritative`. During shadow-read, both models are maintained; after cutover, positions are authoritative and holdings become read-only compatibility DTOs. The cutover is irreversible.

- **Quote trust model**: Every quote carries a `quote_state` (unpriced/live/delayed/close/nav/stale/error) and an `is_actionable` flag. Only actionable quotes can trigger stop-loss alerts. The backend adjudicates this — post-close quotes can display valuations but never fire alerts. Calendar degradation (weekday fallback when akshare is unavailable) further gates actionability.

- **Monitoring cycle**: `run_monitoring_cycle()` is the central refresh path. It creates a `MonitoringCycle` record, acquires a bounded mutex (prevents overlapping refreshes), fetches quotes for all active holdings, evaluates stop-loss rules, creates alerts on trigger, and commits atomically. The same function serves scheduled, manual, and scoped (per-holding/per-code) refresh. Alert delivery (webhook) is enqueued after the commit and may fail independently.

- **Provider resilience**: `ProviderCallPolicy` wraps all akshare calls with hard total timeout, bounded retries with jitter, and a small circuit breaker. ETF quotes use Eastmoney's direct API as primary path, falling back to akshare batch downloads. Fund NAV is the last resort for unresolved fund codes.

### Frontend (`frontend/`)

```
src/
  main.js              App entry point
  App.vue              Root component
  api/index.js         Axios instance (base /api, 15s timeout, error interceptor)
  router/index.js      Vue Router routes (Dashboard, Holdings, HoldingDetail, Alerts, Settings)
  stores/
    resource.js        Generic async resource store factory (loading/error/data pattern)
    positions.js       Positions list store
    alert.js           Alert list store
    settings.js        Settings store
    monitoring.js      Monitoring status store
  views/
    Dashboard.vue      Portfolio summary cards + latest alert
    Holdings.vue       Holdings list with status filter (URL-synced)
    HoldingDetail.vue  Single holding: edit stop-loss, view price chart, close position
    PositionDetail.vue New position detail with risk workflow (acknowledge/rearm/close)
    Alerts.vue         Alert list with read/unread filter
    Settings.vue       Poll interval, monitoring interval, webhook config, retention
  components/
    HoldingForm.vue    Add/edit holding form
    HoldingPriceChart.vue ECharts price history chart with buy price + stop-loss lines
    FilterToolbar.vue  Reusable filter bar
    StatusBanner.vue   Quote state banner
    DataState.vue      Loading/error/empty state wrapper
  utils/
    holdingStatus.js   Status label/color mappings
    holdingForm.js     Form validation helpers
    dashboard.js       Dashboard data transforms
    historyChart.js    Chart data preparation
    quoteTrust.js      Actionable quote display logic
    format.js          Number/date formatters
    poller.js          Configurable polling utility
    refreshResult.js   Refresh result parsing
    requestState.js    Request state machine helpers
    settingsPresets.js Default settings values
```

**Key frontend patterns:**

- **URL-synced filters**: Holdings and Alerts filter state is stored in URL query params so the selected view is retained when navigating between list and detail pages.
- **Resource store pattern**: `createResource()` in `stores/resource.js` is a generic factory providing `loading`, `error`, `data`, and `refresh()` for any API-backed list.
- **Quote trust display**: The frontend uses `quoteTrust.js` to decide how to render quotes based on `quote_state` and `is_actionable` — delayed/stale/error states are displayed informatively but clearly marked as non-actionable.

## Testing

- **Backend**: pytest with `conftest.py` providing database fixtures. Tests use an in-memory SQLite database. The `STOP_LOSS_FIXTURE_PRICE` env var enables hermetic fixture mode — no real network calls. Default test runs are offline.
- **Frontend**: vitest for unit tests, Node test runner for behavioral tests.
- **E2E**: `scripts/smoke.py` runs an isolated end-to-end smoke test.
- **OpenSpec**: `openspec validate --changes --strict --no-interactive` validates change specifications.

## Database Migrations

The project uses a built-in ordered migration runner (NOT Alembic). Key rules:
- Each integer revision is idempotent and records the highest applied version
- Migrations auto-backup the old database before upgrading
- `LATEST_SCHEMA_VERSION` in `migrations.py` is the authority
- Downgrade only removes the version record; tables/columns remain for backward compatibility
- Migration logic must stay re-entrant and be covered by upgrade/downgrade tests

## Environment Variables

All configuration via `STOP_LOSS_*` prefixed env vars. Key ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `STOP_LOSS_DATABASE_URL` | `sqlite:///backend/stop_loss.db` | Database location |
| `STOP_LOSS_TIMEZONE` | `Asia/Shanghai` | Market timezone |
| `STOP_LOSS_SCHEDULER_ENABLED` | `1` | Enable periodic monitoring |
| `STOP_LOSS_QUOTE_MAX_AGE` | `900` | Seconds before a quote goes stale |
| `STOP_LOSS_FIXTURE_PRICE` | (empty) | Set to enable hermetic fixture mode for testing |
| `STOP_LOSS_LOG_FORMAT` | `json` | Log output format |
| `STOP_LOSS_PROVIDER_TOTAL_TIMEOUT` | `45` | Total timeout for akshare calls |
| `STOP_LOSS_PROVIDER_MAX_ATTEMPTS` | `2` | Retry attempts per provider call |
