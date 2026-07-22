## 1. Frontend state and design foundation

- [ ] 1.1 Confirm monitoring and position API changes are archived and their contracts pass.
- [ ] 1.2 Add shared Decimal-string formatters, unavailable-value handling, and tabular-number styles.
- [ ] 1.3 Add accessible quote, monitoring, risk, stale-data, loading, error, and empty-state components.
- [ ] 1.4 Add a reusable URL-synchronized search, filter, sort, and pagination toolbar.
- [ ] 1.5 Create monitoring, positions, alerts, and settings stores with last-success data and request deduplication.
- [ ] 1.6 Consolidate application polling into one timer per resource with visibility-aware frequency.

## 2. Risk-first pages

- [ ] 2.1 Redesign the dashboard monitoring bar, risk summary, coverage metrics, and risk-position table.
- [ ] 2.2 Migrate the position list to the new API with desktop table and expandable mobile cards.
- [ ] 2.3 Redesign active position detail around quote trust, PnL, stop risk, lots, rules, and events.
- [ ] 2.4 Implement add-lot and partial/complete-close forms with server result previews.
- [ ] 2.5 Implement distinct acknowledge, rearm, and close disposition flows for triggered positions.
- [ ] 2.6 Implement closed-position review mode without active quote or stop controls.
- [ ] 2.7 Redesign alerts with read/disposition filters, stable pagination, event links, and mobile cards.
- [ ] 2.8 Group settings by responsibility and show configured versus effective runtime values.

## 3. Responsive accessibility and behavior tests

- [ ] 3.1 Implement desktop, tablet, and mobile navigation/density behavior with safe-area spacing.
- [ ] 3.2 Verify every state uses text, icon, sign, or structure in addition to color.
- [ ] 3.3 Add real component-mount tests for loading, background errors, URL restoration, forms, and single timers.
- [ ] 3.4 Add browser E2E for create, refresh, trigger, acknowledge, rearm, partial close, and full close.
- [ ] 3.5 Run E2E at 390x844, 768x1024, and 1440x900 with overflow, overlap, focus, and truncation checks.
- [ ] 3.6 Run frontend tests, production build, complete offline smoke, and strict OpenSpec validation.
- [ ] 3.7 Update user help for quote trust, risk disposition, partial closes, and closed-position review.
