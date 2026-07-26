## ADDED Requirements

### Requirement: Configure a manual portfolio risk policy
The system SHALL support an explicitly entered positive Decimal portfolio equity, a portfolio risk limit from greater than 0 through 100 percent, and a default per-position risk limit greater than 0 and no greater than the portfolio limit. The system MUST identify the equity as manually maintained and return its last update time.

#### Scenario: Save a valid risk policy
- **WHEN** the user saves portfolio equity `100000`, portfolio risk limit `5`, and default position risk limit `1`
- **THEN** the system persists the exact values and reports portfolio and default position limits of `5000` and `1000`

#### Scenario: Reject an inconsistent position limit
- **WHEN** the user submits a default position risk limit greater than the portfolio risk limit
- **THEN** the system returns a stable field validation error and preserves the previously effective policy

#### Scenario: Equity has not been configured
- **WHEN** percentage defaults exist but the user has never entered portfolio equity
- **THEN** the system reports risk budgeting as unavailable and MUST NOT substitute current market value or a fabricated equity

### Requirement: Aggregate covered portfolio stop risk
The system SHALL calculate used risk as the sum of `estimated_loss_at_stop` for authoritative open positions that have calculable remaining cost, remaining quantity, and an active stop rule. It SHALL return the covered subtotal, portfolio limit, utilization percentage, coverage by position count and remaining cost, and either a known remaining capacity or an explicit indeterminate state.

#### Scenario: All open positions have stop coverage
- **WHEN** portfolio equity is `100000`, the portfolio risk limit is `5`, and fully covered open positions have estimated stop losses totaling `3800`
- **THEN** the system returns a limit of `5000`, used risk `3800`, utilization `76.00`, and remaining capacity `1200`

#### Scenario: Portfolio risk limit is exceeded
- **WHEN** covered estimated stop losses total more than the configured portfolio limit
- **THEN** the system returns zero remaining capacity, the positive exceeded amount, and an exceeded status

#### Scenario: An open position lacks an active stop
- **WHEN** at least one authoritative open position cannot produce an estimated loss at stop
- **THEN** the system returns the covered subtotal and reduced coverage, marks remaining capacity indeterminate, and MUST NOT represent the subtotal as complete portfolio risk

#### Scenario: A current quote is unavailable
- **WHEN** an open position has valid cost, quantity, and an active stop but no actionable current quote
- **THEN** its estimated loss at stop remains covered while current valuation coverage remains independently degraded

### Requirement: Expose risk budget status without false precision
The frontend SHALL show manually maintained equity, portfolio limit, used covered risk, remaining or indeterminate capacity, coverage, and exceeded status with text as well as visual styling. It MUST NOT display an unavailable or indeterminate amount as zero.

#### Scenario: Risk coverage is incomplete
- **WHEN** the risk-budget response marks remaining capacity indeterminate
- **THEN** the interface displays the coverage gap and a route to the affected positions instead of a numeric remaining-risk claim

#### Scenario: Mobile risk summary
- **WHEN** the user views the risk budget at a viewport between 360px and 767px
- **THEN** the values, coverage explanation, and primary action remain readable without page-level horizontal scrolling
