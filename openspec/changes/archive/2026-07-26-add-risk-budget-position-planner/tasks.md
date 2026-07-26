## 1. Risk Settings Contract

- [x] 1.1 Extend backend settings schemas and effective defaults with optional Decimal-safe portfolio equity, 5% portfolio risk limit, 1% default position risk limit, and an equity-update timestamp stored as a companion setting key.
- [x] 1.2 Implement cross-field validation and atomic persistence so invalid risk settings preserve all prior settings and interval-only updates preserve the risk policy.
- [x] 1.3 Add backend API tests for unset equity, valid policy persistence, inconsistent percentages, invalid equity, Decimal serialization, update timestamps, and partial settings updates.

## 2. Risk Calculation Domain

- [x] 2.1 Add a Decimal risk-budget service that aggregates authoritative open-position estimated loss at stop, applies the existing exit-cost policy, and returns limit, used, exceeded, remaining, and count/cost coverage fields.
- [x] 2.2 Add deterministic position-plan sizing for fixed, percentage, and trailing initial stops, explicit fixed entry/exit fees, per-plan overrides, A-share 100-share increments, and fund six-decimal increments.
- [x] 2.3 Define stable unavailable and refusal reason codes for unset equity, incomplete stop coverage, exhausted capacity, invalid inputs, non-positive unit risk, fees consuming capacity, and zero rounded quantity.
- [x] 2.4 Add unit tests for all formulas, Decimal rounding boundaries, limiting-budget selection, fee treatment, quote-independent stop coverage, board-lot rounding, and fund precision.

## 3. Backend Risk APIs

- [x] 3.1 Add response and request schemas that expose financial values as Decimal-safe strings and include normalized inputs plus a complete calculation explanation.
- [x] 3.2 Add a risk-budget summary endpoint and a read-only `POST /api/risk/plans/preview` endpoint, both gated by the existing `new-authoritative` migration stage.
- [x] 3.3 Add API tests for full, incomplete, exceeded, and unavailable budget states and for the stable `new_authority_required` response.
- [x] 3.4 Prove the preview no-write guarantee with integration tests that compare positions, lots, rules, events, alerts, imports, and delivery records before and after successful and rejected previews.

## 4. Frontend Risk Budget Experience

- [x] 4.1 Extend the settings store and settings page with manual-equity and percentage fields, clear manual/staleness language, cross-field errors, and mobile-safe layout.
- [x] 4.2 Add a shared risk-budget store and dashboard summary for limit, covered used risk, remaining or indeterminate capacity, utilization, exceeded status, and routes to uncovered positions.
- [x] 4.3 Add frontend tests ensuring unavailable and indeterminate amounts are not rendered as zero and that risk, coverage, and manual-equity states do not rely on color alone.

## 5. Position Planner and Handoff

- [x] 5.1 Add a responsive planner route and form for instrument identity, asset type, entry price, existing stop methods, fee estimates, and optional per-plan risk override.
- [x] 5.2 Render server-returned limiting values, formula breakdown, raw and rounded quantities, projected loss, required capital, refusal reasons, and the advisory/no-order/no-cash-knowledge disclosures without recalculating financial values in the browser.
- [x] 5.3 Add an explicit continue action that prefills the authoritative position-opening form and keeps final position creation as a separate reviewed submission to `/api/positions`.
- [x] 5.4 Add frontend behavior tests for successful A-share and fund plans, incomplete coverage, zero-lot results, request failures, stale preview handoff, keyboard use, and 360px responsive layout.
- [x] 5.5 Align every planner numeric input step with its displayed precision so valid decimal prices, fees, and percentages pass native browser validation.

## 6. Integration and Documentation

- [x] 6.1 Add an end-to-end fixture journey covering settings configuration, existing portfolio risk aggregation, preview, unchanged business records, handoff, explicit creation, and refreshed budget usage.
- [x] 6.2 Update the README with the risk formulas, coverage semantics, manual-equity warning, authority-stage prerequisite, quantity assumptions, and advisory product boundary.
- [x] 6.3 Run backend tests, frontend tests and production build, isolated smoke tests, bundle budget checks, and strict OpenSpec validation through the project verification gate.
