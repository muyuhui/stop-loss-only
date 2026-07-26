## Context

The application is a local, single-user risk monitor with Decimal portfolio accounting, versioned stop rules, and a staged migration from legacy holdings to an authoritative position domain. It already calculates `estimated_loss_at_stop` for positions, but it has no account-level risk limit or pre-trade sizing workflow. The planner must reuse the same stop and loss semantics as monitoring, remain explainable, and never turn a preview into a business write.

The feature spans runtime settings, portfolio aggregation, a calculation service and API, and frontend workflows. It targets the `new-authoritative` position stage so that no new feature logic is added to the legacy write path.

## Goals / Non-Goals

**Goals:**

- Persist a manually maintained portfolio equity and percentage risk limits using exact decimal values.
- Calculate covered portfolio stop risk and make incomplete coverage explicit.
- Produce a deterministic, read-only position-size preview using the existing supported stop methods.
- Apply A-share board-lot and fund fractional-quantity rules consistently on the server.
- Explain every limiting value and allow a valid preview to prefill normal position creation.

**Non-Goals:**

- Broker connectivity, order placement, cash-balance reconciliation, or automatic position creation.
- Profit targets, expected-return predictions, risk/reward scoring, or investment recommendations.
- ATR, moving-average, composite, or other new stop-rule methods.
- Multi-user, cloud-sync, or multi-account allocation.
- Treating account equity as a live mark-to-market balance.

## Decisions

### Store risk policy in existing runtime settings

The settings store will add optional `portfolio_equity`, `portfolio_risk_limit_pct`, and `default_position_risk_limit_pct` values. The percentage defaults are 5% and 1%; equity has no fabricated default and must be explicitly configured before sizing is available. Values are validated together so the position limit cannot exceed the portfolio limit.

This avoids a new table for three singleton values in a local single-user deployment. Adding the values directly to `Account` was considered, but the current product exposes one effective portfolio and does not yet provide account-management behavior.

### Make the backend the calculation authority

A dedicated Decimal calculation service will be shared by the portfolio summary and a read-only `POST /api/risk/plans/preview` endpoint. POST is used because the structured preview input is not a persisted resource. The frontend only formats server-returned Decimal strings and MUST NOT recompute financial results.

Client-side calculation was rejected because browser number rounding and duplicated rule logic would undermine auditability.

### Define covered portfolio risk independently of quote actionability

For each open position with remaining cost, quantity, and an active valid stop rule:

`estimated_loss_at_stop = max(0, remaining_cost + estimated_exit_cost - stop_price * remaining_quantity)`

`used_risk_amount` is the sum of covered positions. Coverage is reported by open-position count and remaining cost. A current quote is not required because loss at the configured stop is a cost-and-rule calculation, not a current valuation.

If any open position lacks a calculable active stop, the response returns the covered subtotal and coverage details but marks remaining capacity as indeterminate. The planner does not recommend a quantity until coverage is complete, preventing a covered subtotal from being mistaken for total portfolio risk.

### Size from the tighter of position and portfolio capacity

The preview derives:

- `portfolio_limit_amount = portfolio_equity * portfolio_risk_limit_pct / 100`
- `position_limit_amount = portfolio_equity * effective_position_risk_limit_pct / 100`
- `remaining_portfolio_capacity = max(0, portfolio_limit_amount - used_risk_amount)`
- `allowed_plan_risk = min(position_limit_amount, remaining_portfolio_capacity)`
- `unit_price_risk = entry_price - initial_stop_price`
- `raw_quantity = (allowed_plan_risk - entry_fees - estimated_exit_fees) / unit_price_risk`

The service rejects an initial stop that is not below entry or a non-positive capacity. It rounds quantity down to 100 shares for A-shares and to the model quantity quantum (`0.000001`) for funds. It then recomputes projected loss and required capital from the rounded quantity. Fees are explicit fixed estimates supplied by the user; the service does not invent a brokerage fee schedule.

For a trailing rule, the entry price is the initial high-water mark. Percentage and fixed rules use existing stop-engine semantics.

### Separate preview from creation

Preview returns normalized inputs plus calculation outputs. The frontend may route these inputs into the authoritative position-opening form, but the user must review and explicitly submit that form. The preview endpoint does not insert positions, lots, rules, events, alerts, or imports.

Combining preview and creation in one endpoint was rejected because it would blur advisory output with an irreversible business action and weaken no-write testing.

### Gate rollout on authoritative positions

Risk summary and planning return a stable `new_authority_required` conflict while the migration authority is not `new-authoritative`. Legacy holdings endpoints remain unchanged. This keeps the feature from creating a third compatibility projection and makes cutover an explicit operational prerequisite.

## Risks / Trade-offs

- **[Manually entered equity becomes stale]** → Display that it is user-maintained, include its last update time, and never label it as live account value.
- **[Incomplete stop coverage understates risk]** → Return the covered subtotal with coverage counts, mark remaining capacity indeterminate, and suppress a recommended quantity.
- **[Fixed fee estimates differ from actual fees]** → Echo the fee assumptions and show them separately in the explanation.
- **[Board-lot rules vary for exceptional instruments or sell orders]** → Scope v1 to normal A-share opening lots and document the 100-share assumption; funds use the existing fractional precision.
- **[Risk-sized quantity may exceed available cash]** → Report required capital prominently and state that cash availability is not known; do not call the result affordable.
- **[Cutover is not complete]** → Keep implementation dormant behind the existing migration authority gate and perform no legacy-domain writes.

## Migration Plan

1. Add the optional settings keys without changing the database schema; existing installations continue with risk planning unavailable until equity is entered.
2. Add backend calculations and API contracts behind the `new-authoritative` gate.
3. Add risk summaries and planner UI, including explicit unavailable and incomplete-coverage states.
4. Enable the workflow only after the existing position cutover procedure has completed and its compatibility checks pass.
5. Roll back application code without deleting the new setting keys; older versions ignore unknown settings. No position or accounting data migration is introduced.

## Open Questions

- Whether a later change should support instrument-specific board-lot metadata instead of the v1 A-share 100-share rule.
- Whether estimated entry and exit fees should later be generated by configurable broker fee profiles rather than entered as fixed estimates.
