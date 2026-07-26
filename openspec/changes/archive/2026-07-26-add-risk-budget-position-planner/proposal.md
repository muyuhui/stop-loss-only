## Why

The application can monitor an existing position and estimate its loss at the stop, but it cannot help the user decide how large a position is safe before opening it. Adding an explicit risk budget and position-sizing planner closes this gap while preserving the product boundary of advisory risk management without broker connectivity or automatic ordering.

## What Changes

- Add manually configured account equity, portfolio risk limit, and default per-position risk limit settings.
- Aggregate the estimated loss at stop for open positions with explicit active-rule coverage, and expose used, remaining, and exceeded risk-budget states.
- Add a read-only planning workflow that accepts a proposed instrument, entry price, stop rule, fees, and optional risk override, then returns a maximum risk-sized quantity, required capital, and transparent calculation details.
- Apply asset-specific quantity increments: whole board lots for A-share plans and supported fractional precision for fund plans.
- Allow a valid plan to prefill the authoritative position-opening workflow; creating a plan alone never writes a position or places an order.
- Show warnings instead of presenting false precision when inputs, stop calculations, account equity, or portfolio coverage are insufficient.
- Keep the planner advisory: it does not add profit targets, expected-return recommendations, broker credentials, or automatic execution.

## Capabilities

### New Capabilities

- `risk-budget-management`: Configure account-level risk limits and report covered portfolio stop risk, utilization, remaining capacity, and coverage.
- `position-sizing-planner`: Preview a proposed position size from entry, stop, costs, risk limits, asset quantity rules, and current portfolio risk without creating a position.

### Modified Capabilities

- `runtime-settings`: Persist and validate account equity, portfolio risk limit, and default per-position risk limit alongside the existing runtime settings.

## Impact

- Backend settings schemas, validation, and persistence gain Decimal monetary and percentage values.
- Portfolio presentation gains risk-budget aggregates derived from authoritative open positions and active stop rules.
- A new planning API performs deterministic calculations without database writes other than normal settings reads.
- The frontend gains risk-budget summaries, a planning form, calculation explanations, and a handoff into position creation.
- Tests must cover Decimal rounding, A-share lot sizing, fund precision, fees, exhausted budgets, missing coverage, and the no-write preview guarantee.
- Position creation remains owned by the new position domain; rollout depends on the `new-authoritative` stage and does not expand legacy holdings writes.
