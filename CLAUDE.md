# CLAUDE.md

This file provides guidance to coding agents working in this repository.

## Project overview

止损不止盈 is a local stop-loss monitoring and risk-planning tool for A-shares and funds. It tracks holdings, retrieves quotes, evaluates stop-loss rules, produces alerts, and previews risk-budget-based position sizes. It does not connect to brokers or place orders.

Tech stack: Python/FastAPI, Vue 3/Vite, SQLite, SQLAlchemy, Element Plus, and AkShare.

## Commands

Run repository scripts from the project root:

```powershell
.\setup.ps1
.\setup.ps1 -Dev
.\start.ps1
.\stop.ps1
.\dev.ps1
.\verify.ps1
.\backup.ps1
.\restore.ps1 -Backup <file> -Manifest <file>
```

Backend commands, run from `backend/`:

```bash
python -m pytest -p no:cacheprovider -q
python db_admin.py status
python db_admin.py upgrade
python db_admin.py downgrade
python db_admin.py shadow-status
python db_admin.py shadow-enable
python db_admin.py shadow-rebuild
```

Frontend commands, run from `frontend/`:

```bash
npm test
npm run dev
npm run build
```

## Architecture

The backend request path is `main.py` → `routers/` → `services/` → SQLAlchemy models in `models.py` → SQLite through `database.py`. Configuration uses the immutable `AppConfig` in `config.py` and `STOP_LOSS_*` environment variables.

The custom integer-revision migration runner in `migrations.py` is authoritative; this project does not use Alembic. Migrations must remain idempotent and re-entrant.

The position-domain migration has three authority stages:

- `legacy`: `holdings` is authoritative.
- `shadow-read`: legacy writes are projected into the position domain.
- `new-authoritative`: `positions`, lots, stop rules, events, and quotes are authoritative.

Risk-budget planning and its fully stop-covered creation handoff require `new-authoritative`; other position-only writes remain outside the stable runtime. The stable legacy workflow remains available through `/api/holdings`. Do not bypass authority checks or represent previewed quantities as reserved or ordered.

Important backend modules:

- `routers/holdings.py`: stable legacy holding CRUD.
- `routers/positions.py`: authoritative position lifecycle.
- `routers/risk.py`: risk-budget summary and position-size preview.
- `routers/settings.py`: supported runtime and risk-policy settings.
- `services/monitoring.py`: central quote refresh and alert cycle.
- `services/position_domain.py`: lots, closes, risk acknowledgement, and stop rules.
- `services/risk_budget.py`: Decimal-safe risk aggregation and sizing.
- `services/shadow_projection.py`: migration bridge and authority state.
- `services/supported_runtime.py`: explicit guards for unavailable runtime features.

The frontend starts at `src/main.js`, uses Vue Router and Pinia, and centralizes HTTP behavior in `src/api/index.js`. Risk planning is exposed at `/risk-planner`; settings include manually maintained portfolio equity and risk limits.

## Design rules

- Use `Decimal` for all backend financial arithmetic and explicit quantization for prices and quantities.
- Only actionable, sufficiently trusted quotes may trigger stop-loss alerts.
- Browser notifications only present in-app alert snapshots and must not create business facts; permission is requested only on explicit user action, never at page load.
- Treat portfolio equity as manually maintained; never infer it from market value.
- A risk preview must not write business records.
- Keep unavailable or incomplete risk capacity explicit; never display it as zero.
- Runtime extensions marked unsupported must fail before side effects with a stable error code.
- Tests are hermetic and must not make external network calls.
- The scheduler is single-process and monitoring uses a bounded in-process lock.
- Preserve correlation IDs and structured errors without leaking provider internals.

## Verification

`.\verify.ps1` is the full quality gate. It runs backend tests, frontend tests, the production build, supported-runtime E2E checks, smoke checks, restore drills, dependency validation, and strict OpenSpec validation.
