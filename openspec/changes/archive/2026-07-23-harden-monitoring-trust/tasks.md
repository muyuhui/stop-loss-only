## 1. Baseline and offline safety

- [x] 1.1 Prepare privacy-safe representative schema v2 database fixtures and current API response fixtures.
- [x] 1.2 Configure project-scoped writable temporary directories for backend and smoke tests.
- [x] 1.3 Install a mandatory-test network sentinel that immediately rejects DNS and socket access.
- [x] 1.4 Add regressions for cost placeholders, closed-position display, duplicate concurrent trigger, and fixture calendar isolation.
- [x] 1.5 Run and record the current backend, frontend, build, strict OpenSpec, and offline smoke baseline.

## 2. Quote and calendar trust layer

- [x] 2.1 Define Decimal `QuoteState`, normalized quote, market session, and stable provider error types.
- [x] 2.2 Define injectable-clock quote provider and market calendar protocols outside adapters.
- [x] 2.3 Implement deterministic fixture quote and calendar adapters that cannot import production providers.
- [x] 2.4 Refactor stock, ETF/LOF, and fund adapters to map raw data into normalized quotes.
- [x] 2.5 Add connection and total timeouts, bounded retry, jitter, circuit state, and redacted errors.
- [x] 2.6 Implement market-calendar caching with expiry and explicit `authoritative`/`valid_cache`/`weekday_fallback` sources; weekday fallback must not make quotes actionable without independently verified current-session timestamps.
- [x] 2.7 Implement cycle-level dataset caching so each market dataset downloads at most once per cycle.
- [x] 2.8 Add provider contract fixtures for missing/renamed columns, empty data, invalid prices, delays, closes, NAVs, holidays, and weekday-fallback actionability.

## 3. Monitoring transactions and diagnostics

- [x] 3.1 Add ordered migration and indexes for monitoring cycles and compatible quote metadata.
- [x] 3.2 Persist success, partial, skipped, degraded, and failed cycle summaries without sensitive values.
- [x] 3.3 Implement `/api/monitoring/status` and paginated `/api/monitoring/cycles`.
- [x] 3.4 Update existing quote and refresh schemas with state, timestamps, actionability, cycle ID, and stable errors.
- [x] 3.5 Add stable trigger idempotency keys and optimistic version conditions.
- [x] 3.6 Isolate each instrument with savepoints and rebuild responses from committed rows.
- [x] 3.7 Coordinate scheduled and manual full refreshes with a bounded single-process mutex.
- [x] 3.8 Add scoped manual refresh while preserving the compatible refresh route.
- [x] 3.9 Add concurrent integration tests for winners, losers, uniqueness conflicts, partial commits, and busy database outcomes.

## 4. Minimal trust presentation and gates

- [x] 4.1 Show quote state and data age anywhere a compatible current price is displayed.
- [x] 4.2 Add a compact monitoring-trust summary without redesigning the full dashboard.
- [x] 4.3 Verify logs and errors include cycle/correlation IDs but exclude sensitive values and raw responses.
- [x] 4.4 Run all mandatory tests with network blocked and confirm accidental network access fails immediately.
- [x] 4.5 Run production build, strict OpenSpec validation, provider contracts, concurrency tests, and complete offline smoke.
- [x] 4.6 Document the supported single-process boundary, quote semantics, diagnostic APIs, and rollback procedure.
