# Repository Guidelines

## Project Overview

**止损不止盈 (stop-loss-only)** is a local, single-user stop-loss monitoring tool for A-shares (A股) and funds. It records holdings, fetches quotes, computes stop-losses (fixed / buy-price-percentage / trailing), and alerts when triggers are breached. It **never connects to brokers and never auto-places orders**; portfolio equity is a manually maintained trial input, never inferred. The UI is Chinese-first (`lang="zh-CN"`, title 止损不止盈).

Constraints that shape every change (see `openspec/platform-evolution-roadmap.md`):
- Local only: loopback-bound ports, SQLite, single process / single worker / single scheduler. No cloud sync, multi-user, or public deploy.
- Only `legacy` (holdings authoritative) and `shadow-read` (read-only position-domain projection) runtime stages are supported. `new-authoritative` is deferred; `db_admin.py cutover` refuses with `cutover_not_supported`.
- Features enter the supported surface only via an archived OpenSpec change that passed `.\verify.ps1`.

## Architecture & Data Flow

Layered monoliths, no message bus:

```
Vue 3 SPA (frontend/, port 5173)
  └─ axios singleton (baseURL /api) ── Vite dev proxy ──► FastAPI backend (backend/, port 8001)
                                                          main.py (create_app factory, lifespan)
                                                            → routers/ (11 APIRouters, prefix /api)
                                                            → services/ (pure functions, db: Session first arg)
                                                            → models.py (SQLAlchemy 2.0 ORM) → SQLite
                                                          APScheduler (single-process, Asia/Shanghai)
                                                            → monitoring cycle: quotes → trigger alerts
```

- **Backend**: `main.py` builds the app via `create_app()` (title 止损不止盈 v2.0.0), starts/stops the scheduler in lifespan, registers middleware (`RequestLoggingMiddleware`, CORS for 5173) and 11 routers under `/api`: `holdings`, `positions`, `prices`, `alerts`, `dashboard`, `settings`, `monitoring`, `operations`, `risk`, `runtime`, `ai`. Health: `/api/health/live`, `/api/health/ready`, OpenAPI at `/docs`.
- **Request path example**: `POST /api/holdings` → `create_holding` service → `StopLossEngine.validate` → ORM insert + `StopRuleHistory` audit row → commit + `project_after_legacy_commit` (shadow projection) → `holding_payload` DTO.
- **Domain model**: Holding lifecycle `holding → triggered → closed`, plus rearm (`POST /api/holdings/{id}/rearm`) which increments `trigger_sequence`/`version` and starts a **new** alert lifecycle (re-breach after rearm ⇒ new alert). Quote states are adjudicated backend-side: `unpriced/live/delayed/close/nav/stale/error`; only fresh, actionable quotes (`is_actionable=true`) may trigger. Alerts carry read state **and** disposition (`triggered/closed/rearmed`) tracked separately; `stop_rule_history` snapshots every rule change (source `create`/`update`/`rearm`).
- **Monitoring**: `services/monitoring.py` runs the quote-refresh + trigger cycle under a bounded in-process lock (`max_instances=1`, coalesce). Triggers use optimistic version CAS (`begin_nested`) + a stable idempotency key (`_trigger_key(holding, sequence)`), guaranteeing ≤1 alert per lifecycle even with concurrent cycles. Cycle statuses: `success/partial/skipped/degraded/failed`.
- **Runtime capability gating**: `services/supported_runtime.py` derives `RuntimeCapabilities` per authority stage; unsupported writes fail with `409 feature_not_supported` before any side effect. Frontend mirrors this via `src/stores/runtimeCapabilities.js` (`isAvailable(name)`, frozen `CLOSED_CAPABILITIES`), e.g. `risk_plan_previews`, `browser_notifications`.
- **Migrations**: custom integer-revision runner in `backend/migrations.py` (`LATEST_SCHEMA_VERSION=8`) — **not Alembic**. Idempotent DDL + `schema_migrations` rows, pre-upgrade DB backup, non-destructive downgrade. CLI: `python db_admin.py status|upgrade|downgrade|shadow-*|backup|restore` (from `backend/`).
- **Data flow (frontend)**: pages fetch through Pinia stores or view composables → axios → `useRequestState` (`{hasData, loading, refreshing, error, isStale}`) keeps last good data on failure → `DataState.vue` renders loading/error/empty. Polling via `utils/poller.js` `createPoller(cb)`: interval, hidden-tab throttling (`max(60, interval×2)`), instant refresh on tab visibility; poll interval is user-configurable via settings store.

## Key Directories

| Path | Purpose |
|---|---|
| `backend/routers/` | FastAPI routers; one file per resource, `APIRouter(prefix=..., tags=...)`, `Depends(get_db)` |
| `backend/services/` | Business logic; pure function modules taking `db: Session` first; small class islands (`StopLossEngine`, frozen dataclasses, Protocol providers) |
| `backend/models.py`, `schemas.py` | SQLAlchemy 2.0 classic-Column models; Pydantic v2 request/response schemas |
| `backend/tests/` | pytest suite (hermetic; see Testing & QA) |
| `frontend/src/views/` | Route-level pages (`Dashboard.vue`, `Holdings.vue`, `HoldingDetail.vue`, `Alerts.vue`, `RiskPlanner.vue`, `Settings.vue`) |
| `frontend/src/components/` | Shared SFCs (`HoldingForm.vue`, `HoldingPriceChart.vue`, `DataState.vue`, `FilterToolbar.vue`, `StatusBanner.vue`) |
| `frontend/src/stores/` | Pinia setup stores, camelCase files (`settings.js`, `positions.js`, `runtimeCapabilities.js`, `riskBudget.js`, `alert.js`, `monitoring.js`, `resource.js`) |
| `frontend/src/utils/` | Pure logic: `poller.js`, `requestState.js`, `format.js`, `holdingForm.js`, `historyChart.js`, `requestPolicy.js`, `market.js`, `notifications.js` |
| `frontend/tests/` | `*.test.js` (node:test units), `*.mount.spec.js` (vitest), `e2e/` (Playwright) |
| `scripts/` | `smoke.py`, `e2e_backend.py`, `restore_drill.py`, PowerShell helpers (`npm_environment.ps1`, `process_identity.ps1`) |
| `openspec/specs/` | Main specs: `stop-loss-engine`, `holdings-crud`, `alert-system`, `dashboard` (+ `notification-delivery`, `monitoring-diagnostics`, `frontend-shell`) |
| `openspec/changes/archive/` | Archived changes; **no active change is currently in flight** |

Root PowerShell scripts (`start.ps1`, `stop.ps1`, `dev.ps1`, `setup.ps1`, `verify.ps1`, `backup.ps1`, `restore.ps1`) are the Windows orchestration layer — use them rather than raw commands.

## Development Commands

Run from repo root (PowerShell) unless noted:

```powershell
.\setup.ps1            # install runtime deps (pip -r requirements.txt + npm ci)
.\setup.ps1 -Dev       # + test deps (pytest)
.\start.ps1            # migrations → backend (uvicorn, :8001) + frontend (vite, :5173), waits for readiness
.\stop.ps1             # ownership-verified process-tree stop
.\dev.ps1              # backend only, --reload, scheduler disabled (STOP_LOSS_SCHEDULER_ENABLED=0)
.\verify.ps1           # full offline quality gate (see Testing & QA)
.\backup.ps1           # python db_admin.py backup
.\restore.ps1 -Backup <file> -Manifest <json>   # refuses while backend running
```

Backend (cwd `backend/`):

```powershell
python -m pytest -p no:cacheprovider --basetemp <tmp>\pytest -q   # unit/API tests
python db_admin.py status|upgrade|downgrade|shadow-status|shadow-enable|shadow-rebuild
```

Frontend (cwd `frontend/`):

```powershell
npm test          # node --test && vitest run  (unit + mount tests)
npm run test:e2e  # playwright test (3 viewports, own servers)
npm run build     # vite build && node scripts/check-bundle.mjs  (bundle budget gate)
npm run dev       # vite dev :5173, /api proxied to http://localhost:8001
```

URLs: frontend `http://127.0.0.1:5173`, API `http://127.0.0.1:8001`, docs `/docs`, readiness `/api/health/ready` (returns `status == 'ok'`).

## Code Conventions & Common Patterns

### Backend (Python)
- **Money**: `Decimal` for ALL financial arithmetic (`to_decimal` quantizes to 0.0001, `ROUND_HALF_UP`); DB columns `Numeric(18,4)`/`Numeric(18,6)`. Risk/AI schemas carry money as `str`; legacy holdings schemas use `float` (compat). Never float-math money.
- **Schemas**: Pydantic v2, named `XxxCreate` / `XxxUpdate` / `XxxResponse` / `XxxPage` / `XxxRequest` (not `In`/`Out`); `Literal` aliases for enums in payloads; strict AI schemas use `extra='forbid'`.
- **Sync-first**: routes and services are plain `def` (run in threadpool); only lifespan and middleware are `async def`. External provider calls (akshare, DeepSeek) run in `ThreadPoolExecutor` with hard timeouts (`ProviderCallPolicy`: timeout, jitter retries, circuit breaker).
- **Errors**: routers raise `HTTPException` with Chinese message strings, or structured dicts `{message, error_code, feature, correlation_id, cycle_id}`. Codes are snake_case (`feature_not_supported`, `new_authority_required`, `ai_rate_limited`); statuses `400/404/409/422/429/502/503/504`, writes return `201/204`. Capability/feature gates must fail **before** side effects.
- **DI**: no container — `Depends(get_db)` (generator in `database.py` yielding a session) + `db: Session` as first service arg. Tests override via `app.dependency_overrides[get_db]`.
- **Config**: frozen dataclass `AppConfig` singleton in `config.py`, driven by `STOP_LOSS_*` env vars (`STOP_LOSS_DATABASE_URL`, `STOP_LOSS_TIMEZONE`, `STOP_LOSS_SCHEDULER_ENABLED`, `STOP_LOSS_LOG_FORMAT`, `STOP_LOSS_DEEPSEEK_*`, …).
- **Observability**: JSON structured logging (`observability.py`, whitelisted extra fields); `x-correlation-id` ContextVar middleware; propagate `correlation_id`/`cycle_id` in errors without leaking provider internals.
- **Style**: `from __future__ import annotations` (used in ~33 modules); Chinese business comments; snake_case event names.

### Frontend (Vue 3 / plain JS — no TypeScript)
- **SFCs**: `<script setup>`, `defineProps` (object syntax with type/required/default) + `defineEmits`; PascalCase files in `views/`/`components/`; Element Plus as kebab tags (`el-table`, `el-form-item`). No ESLint/Prettier config exists.
- **Styling**: scoped plain CSS per SFC + one global `src/styles.css` with design tokens (`--color-brand: #355f52`, `--color-profit/loss`, `--space-*`, `--radius-*`, `--shadow-panel`) that also retheme Element Plus (`--el-color-primary`). BEM-ish class names (`app-header__inner`, `disposition-card__identity`, `metric-card--primary`); responsive split `.desktop-only`/`.mobile-only` + `@media (max-width: 767px)` bottom nav; never color-only risk signals; `:deep()` to style EP internals. All UI strings and comments are Chinese.
- **State**: Pinia setup stores (`defineStore('id', () => {...})`) calling `api` directly (no service layer); `src/stores/resource.js` exports `createResource(loader)` for last-good-data-on-failure + in-flight coalescing (basis of `positions.js`/`monitoring.js`).
- **API**: single axios instance (`src/api/index.js`, `baseURL: '/api'`, 15s timeout); global response interceptor surfaces `ElMessage.error` and maps `error.response.data.detail` (array joined with `'；'`, string passthrough, or `error_code` → message map). Suppress globally via `config.suppressGlobalError: true` or `config.suppressErrorCodes: [...]` (see `riskBudget.js`). Per-request timeouts for slow calls (price refresh 60s). API fields are snake_case (`poll_interval`, `trigger_price`); money arrives as Decimal strings.
- **Forms**: `el-form` + `:rules` object, validated in submit via `formRef.value.validate().catch(() => false)`; input meta centralized in `utils/holdingForm.js` (`priceInputMeta`/`stopLossInputMeta` → `{precision, step, min, unit, help}`) driving `el-input-number`.
- **Charts**: ECharts 6 modular on-demand (`echarts/core` + `LineChart`, `echarts.use([...])`), manual lifecycle init → `setOption(opt, true)` → resize via `ResizeObserver` → dispose; option built in `utils/historyChart.js`.
- **Money display**: `utils/format.js` `formatDecimal` (regex-validated), `--` for null/invalid; semantic tones via `valueTone`/`stopLossRisk` → CSS classes (`tone-profit`, `risk-text--danger`).

### Cross-cutting (both sides)
- Spec-driven development: OpenSpec (`openspec/config.yaml`, schema: spec-driven). Change workflow: implement → `.\verify.ps1` full gate → `/opsx:sync` (delta → main specs) → `/opsx:archive`. Feature wording is Chinese-first; specs use SHALL/MUST in Chinese with English scenario headings.
- No documented branching or commit-message convention — follow repo history.
- Windows process management is ownership-verified: `start.ps1` writes `.{backend,frontend}.process.json` (`{port, root, pid, started_at}`); `stop.ps1` kills only processes matching recorded identity + command-line/service probes, and **never** kills unverified ones. Tests/smoke must not leave child processes.

## Important Files

| File | Why it matters |
|---|---|
| `backend/main.py` | App factory `create_app()`, router registration, lifespan, health endpoints |
| `backend/config.py` | `AppConfig` frozen dataclass; all `STOP_LOSS_*` env vars |
| `backend/database.py` | Engine, `SessionLocal`, `get_db()` dependency |
| `backend/models.py` / `backend/schemas.py` | ORM models / Pydantic schemas (naming + Decimal conventions) |
| `backend/migrations.py` | Custom integer-revision migration runner (v8), **authoritative — no Alembic** |
| `backend/db_admin.py` | Migration/backup/restore CLI |
| `backend/services/stop_loss.py` | Core engine: `StopLossEngine.calculate/is_triggered/validate` (fixed/percentage/trailing) |
| `backend/services/monitoring.py` | Central refresh + trigger cycle, CAS + idempotency, cycle statuses |
| `backend/services/risk_budget.py` | Decimal-safe risk budgeting (`preview_position_plan`/`preview_add_on_plan`; statuses unavailable/incomplete/available/exhausted/exceeded) |
| `backend/services/supported_runtime.py` | Authority-stage capability gates; `reject_cutover()` |
| `backend/services/shadow_projection.py` | Legacy → position-domain projection bridge |
| `backend/services/ai_provider.py` / `ai_review.py` | DeepSeek provider (httpx, retry w/ validation feedback) + review service; `secret_store.py` DPAPI-encrypts the API key (never in DB/logs) |
| `backend/network_guard.py` | Hermetic network sentinel (loopback-only), used by tests/smoke/E2E |
| `backend/scheduler.py` | APScheduler singleton (single-process, `max_instances=1`) |
| `frontend/src/api/index.js` | Central axios instance + error envelope handling |
| `frontend/src/router/index.js` | Routes: `/`, `/holdings`, `/holdings/:id`, `/alerts`, `/planner`, `/settings` (lazy) |
| `frontend/src/App.vue` | Shell: nav, feature gating, alert polling, notifications |
| `frontend/src/stores/runtimeCapabilities.js` | Feature gates shared across views |
| `frontend/vite.config.js` | Dev/preview `/api` proxy (`VITE_API_PROXY_TARGET`), vitest config, build code-splitting |
| `frontend/playwright.config.js` | E2E projects/ports (backend 18101, frontend 14173), per-run output dir |
| `start.ps1` / `stop.ps1` / `verify.ps1` | Canonical lifecycle + quality gate |
| `scripts/smoke.py` / `scripts/e2e_backend.py` / `scripts/restore_drill.py` | Offline integration checks (see Testing & QA) |
| `openspec/specs/*/spec.md` | Authoritative behavior contracts (stop-loss engine, holdings CRUD, alert system, dashboard) |

Note: `frontend/src/views/PositionDetail.vue` is an orphan (no route, no imports) — do not build on it. `README.md` has a stale "v4 回滚" section; latest schema revision is 8.

## Runtime/Tooling Preferences

- **OS**: Windows-first. PowerShell scripts (UTF-8 **with BOM**, Chinese messages) own install/start/stop/verify; `backend/services/secret_store.py` uses `win32crypt` (DPAPI). Keep cross-platform Python code working, but don't break the ps1 layer.
- **Python**: no version pin in repo (observed: 3.12 in test bytecode; code uses modern syntax like `str | None`). Manifest is `backend/requirements.txt` with **exact `==` pins** (`fastapi==0.115.0`, `uvicorn==0.30.0`, `sqlalchemy==2.0.35`, `pydantic==2.9.0`, `apscheduler==3.10.4`, `akshare==1.18.70`, `tzdata==2025.2`, `httpx==0.28.1`; dev adds `pytest==9.0.3`). **No** pyproject/poetry/uv. Always pip-install new deps with a pinned `==` version.
- **Node/npm**: no `engines` field; effective floor from lockfile: Node `^20.19.0 || >=22.12.0` (vite 8). Use **npm** (`npm ci` for installs, lockfile v3); no pnpm/yarn/bun. Registry is mixed (npmjs.org + npmmirror.com) — don't assume one. `npm_environment.ps1` isolates npm config via `NPM_CONFIG_USERCONFIG`.
- **Build guards**: `frontend/scripts/check-dependencies.mjs` (lockfile vs installed parity, run pre-build) and `scripts/check-bundle.mjs` (post-build budget: entry ≤500 KiB, chunk ≤400 KiB) — both exit 1 on violation.
- **Ports**: backend 8001, frontend 5173 (loopback only); E2E uses 18101/14173. `dev.ps1` disables the scheduler (`STOP_LOSS_SCHEDULER_ENABLED=0`).
- **No linting/formatting/CI**: no ESLint/Prettier, no CI files, no coverage tooling. `verify.ps1` is the only gate.
- **Secrets**: DeepSeek API key is DPAPI-encrypted in a local file under the temp dir — never write keys to SQLite, logs, backups, or code. Root `.gitignore` does **not** ignore `.env` (no `.env` mechanism exists).
- **OpenSpec CLI** (`openspec validate --all --strict --no-interactive`) is required by verify.ps1 but not installed by setup.ps1.

## Testing & QA

Layered, all hermetic (no external network; real provider checks are optional and excluded from the offline gate):

1. **Backend pytest** (`backend/tests/`, run from `backend/`): plain `python -m pytest -p no:cacheprovider -q` — no pytest config file exists. `conftest.py` session fixture installs the network sentinel (loopback-only) and redirects temp dirs. App bootstrap per module (not a shared fixture): in-memory `sqlite://` engine with `StaticPool` + `check_same_thread=False`, `Base.metadata.create_all`, `app.include_router(router, prefix="/api")`, `app.dependency_overrides[get_db]`, `TestClient(app, raise_server_exceptions=False)` — copy this pattern (see `test_api.py::api`, `test_risk_budget.py::api`). Conventions: `monkeypatch` for time/price loaders, `httpx.MockTransport` for DeepSeek, exact `Decimal` assertions, `@pytest.mark.parametrize`, Chinese or bilingual test names. File-backed DBs (`tmp_path/monitoring.db`, migration/backup tests) for SQLite-concurrency coverage.
2. **Frontend unit + mount** — `npm test` = `node --test && vitest run`:
   - `tests/*.test.js` — Node built-in `node:test` + `assert/strict`, pure logic with fakes (e.g. `poller.test.js` fake timers; 12 files).
   - `tests/*.mount.spec.js` — vitest + jsdom + `@vue/test-utils`, `createPinia`, `createRouter(createMemoryHistory())`, `vi.mock('../src/api')`, stubbed Element Plus components (6 files).
3. **Playwright E2E** — `npm run test:e2e`: `frontend/tests/e2e/`, 3 projects `mobile-390`/`tablet-768`/`desktop-1440`, `workers: 1`, 45s timeout. No `webServer` key: `global-setup.js` spawns the real backend (`scripts/e2e_backend.py` with per-run `e2e.db` under `.tmp/playwright-<pid>-<ts>`, fixture quotes `STOP_LOSS_FIXTURE_PRICE=8.8`, scheduler off) + `vite preview`. Scenarios (Chinese titles) seed via `page.request.post('/api/holdings')`, assert page integrity (no horizontal scroll, no browser errors), stub notifications via `addInitScript`.
4. **Offline scripts** — `python scripts/smoke.py` (full API journey against real uvicorn + `frontend/dist`, requires a production build; asserts no leftover child processes) and `python scripts/restore_drill.py` (backup/restore integrity incl. corrupted-manifest rejection).
5. **`.\verify.ps1`** — the single full gate, in order: backend import precheck → `check-dependencies.mjs` → pytest → `npm test` → `npm run build` (bundle budget) → playwright e2e → `smoke.py` → `restore_drill.py` → `openspec validate --all --strict --no-interactive`.

**Coverage**: not measured — no `--cov`, no thresholds, on either side. Do not invent a coverage gate. The acceptance bar is behavioral: specs (openspec) + the verify.ps1 chain + hermeticity (tests must never hit the network).
