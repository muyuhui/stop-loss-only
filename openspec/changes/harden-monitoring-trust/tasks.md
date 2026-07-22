## 1. Baseline and offline safety

- [ ] 1.1 Prepare privacy-safe representative schema v2 database fixtures and current API response fixtures.
- [ ] 1.2 Configure project-scoped writable temporary directories for backend and smoke tests.
- [ ] 1.3 Install a mandatory-test network sentinel that immediately rejects DNS and socket access.
- [ ] 1.4 Add regressions for cost placeholders, closed-position display, duplicate concurrent trigger, and fixture calendar isolation.
- [ ] 1.5 Run and record the current backend, frontend, build, strict OpenSpec, and offline smoke baseline.

## 2. Quote and calendar trust layer

- [ ] 2.1 Define Decimal `QuoteState`, normalized quote, market session, and stable provider error types.
- [ ] 2.2 Define injectable-clock quote provider and market calendar protocols outside adapters.
- [ ] 2.3 Implement deterministic fixture quote and calendar adapters that cannot import production providers.
- [ ] 2.4 Refactor stock, ETF/LOF, and fund adapters to map raw data into normalized quotes.
- [ ] 2.5 Add connection and total timeouts, bounded retry, jitter, circuit state, and redacted errors.
- [ ] 2.6 Implement market-calendar caching with expiry and explicit degraded fallback.
- [ ] 2.7 Implement cycle-level dataset caching so each market dataset downloads at most once per cycle.
- [ ] 2.8 Add provider contract fixtures for missing/renamed columns, empty data, invalid prices, delays, closes, NAVs, and holidays.

## 3. Monitoring transactions and diagnostics

- [ ] 3.1 Add ordered migration and indexes for monitoring cycles and compatible quote metadata.
- [ ] 3.2 Persist success, partial, skipped, degraded, and failed cycle summaries without sensitive values.
- [ ] 3.3 Implement `/api/monitoring/status` and paginated `/api/monitoring/cycles`.
- [ ] 3.4 Update existing quote and refresh schemas with state, timestamps, actionability, cycle ID, and stable errors.
- [ ] 3.5 Add stable trigger idempotency keys and optimistic version conditions.
- [ ] 3.6 Isolate each instrument with savepoints and rebuild responses from committed rows.
- [ ] 3.7 Coordinate scheduled and manual full refreshes with a bounded single-process mutex.
- [ ] 3.8 Add scoped manual refresh while preserving the compatible refresh route.
- [ ] 3.9 Add concurrent integration tests for winners, losers, uniqueness conflicts, partial commits, and busy database outcomes.

## 4. Minimal trust presentation and gates

- [ ] 4.1 Show quote state and data age anywhere a compatible current price is displayed.
- [ ] 4.2 Add a compact monitoring-trust summary without redesigning the full dashboard.
- [ ] 4.3 Verify logs and errors include cycle/correlation IDs but exclude sensitive values and raw responses.
- [ ] 4.4 Run all mandatory tests with network blocked and confirm accidental network access fails immediately.
- [ ] 4.5 Run production build, strict OpenSpec validation, provider contracts, concurrency tests, and complete offline smoke.
- [ ] 4.6 Document the supported single-process boundary, quote semantics, diagnostic APIs, and rollback procedure.
