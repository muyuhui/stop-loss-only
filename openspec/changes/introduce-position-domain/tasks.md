## 1. Migration foundation

- [ ] 1.1 Confirm `harden-monitoring-trust` is archived and its offline/concurrency gates pass.
- [ ] 1.2 Select Alembic or document why an equivalent ordered migration runner satisfies revision requirements.
- [ ] 1.3 Add migration authority metadata for `legacy`, `shadow-read`, and `new-authoritative`.
- [ ] 1.4 Add instrument, default account, position, lot, close allocation, stop rule, event, and quote-history tables with indexes.
- [ ] 1.5 Define Decimal precision and asset-specific quantity/price validation centrally.

## 2. Domain and accounting services

- [ ] 2.1 Implement orthogonal lifecycle and risk-state types and derive partial-close facts from allocations.
- [ ] 2.2 Implement instrument identity and default local account creation.
- [ ] 2.3 Implement lot creation, remaining-quantity invariants, and fixed FIFO allocation.
- [ ] 2.4 Implement partial and complete close commands with fees, taxes, proceeds, and realized PnL.
- [ ] 2.5 Implement backend valuation, unrealized PnL, weights, stop-risk amount, estimated loss, and coverage.
- [ ] 2.6 Implement versioned stop rules and reset moving-stop high-water marks per rule lifecycle.
- [ ] 2.7 Implement versioned immutable position events with an injectable clock.
- [ ] 2.8 Implement risk acknowledgement and rearm commands with reason, expected version, and new trigger sequence.
- [ ] 2.9 Add domain tests for fractional funds, rounding, multiple lots, partial closes, state combinations, and concurrency.

## 3. Legacy migration and reconciliation

- [ ] 3.1 Migrate each legacy holding into instrument, position, initial lot, and active or historical rule records.
- [ ] 3.2 Convert closed holdings into close allocations while preserving price, timestamps, state, and alert snapshots.
- [ ] 3.3 Generate initial immutable events for active, triggered, and closed legacy facts.
- [ ] 3.4 Build reconciliation for quantities, costs, states, stop prices, alerts, and dashboard totals.
- [ ] 3.5 Test upgrade, interruption recovery, and declared downgrade on every representative database fixture.
- [ ] 3.6 Implement post-commit shadow projection while keeping the legacy model as the sole authoritative writer.
- [ ] 3.7 Block cutover readiness and expose a redacted reason whenever shadow reconciliation differs.

## 4. Controlled authority cutover and APIs

- [ ] 4.1 Implement the stopped-write cutover command with backup, final projection, reconciliation, and atomic authority update.
- [ ] 4.2 Implement explicit backup restore or verified reverse migration for post-cutover rollback.
- [ ] 4.3 Implement Decimal-safe `/api/positions` list, detail, lot, close, acknowledge, rearm, and history endpoints.
- [ ] 4.4 Extend alert and dashboard queries to use new event and accounting facts.
- [ ] 4.5 Map the new authoritative model to frozen holdings, alert, refresh, and dashboard compatibility DTOs.
- [ ] 4.6 Add API contract tests for unpriced, triggered, acknowledged, partially closed, and closed combinations.
- [ ] 4.7 Enable new-only operations only after `new-authoritative` cutover succeeds.

## 5. Verification and handoff

- [ ] 5.1 Run domain, API, migration, reconciliation, concurrency, offline smoke, and production build gates.
- [ ] 5.2 Verify no frontend path performs financial arithmetic or depends on the removed composite status model.
- [ ] 5.3 Document the one-stable-release compatibility window and require a separate removal change.
- [ ] 5.4 Document authority stages, irreversible boundary, backup restore, known limits, and FIFO policy.
