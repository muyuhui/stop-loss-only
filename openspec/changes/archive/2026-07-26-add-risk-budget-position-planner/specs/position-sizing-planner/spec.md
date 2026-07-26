## ADDED Requirements

### Requirement: Preview position size without business writes
The system SHALL provide a preview operation for the authoritative position domain that reads the effective risk policy and current covered portfolio risk, calculates a proposed size, and performs no writes to positions, lots, rules, events, alerts, imports, or delivery records.

#### Scenario: Preview a valid A-share plan
- **WHEN** a user previews an A-share entry with complete valid inputs and available risk capacity
- **THEN** the system returns calculation results and normalized handoff inputs without changing any business record count

#### Scenario: Position authority has not cut over
- **WHEN** the migration stage is not `new-authoritative`
- **THEN** the preview returns the stable `new_authority_required` conflict and performs no writes

### Requirement: Calculate risk-sized quantity deterministically
The system SHALL use Decimal arithmetic to calculate the initial stop with an existing supported stop method, use the lesser of the per-position limit and remaining portfolio capacity, subtract explicit estimated entry and exit fees, divide by positive entry-to-stop unit risk, and round quantity down to the asset increment. It SHALL recompute projected loss and required capital from the rounded quantity and return every formula input and limiting value as Decimal strings.

#### Scenario: A-share quantity rounds to a board lot
- **WHEN** raw risk-sized quantity is `495` shares for an A-share
- **THEN** recommended quantity is `400`, and projected risk is recomputed from `400`

#### Scenario: Fund quantity preserves supported precision
- **WHEN** a fund plan produces a positive fractional raw quantity
- **THEN** recommended quantity is rounded down to six fractional places without binary floating-point conversion

#### Scenario: Fees consume part of the risk limit
- **WHEN** allowed plan risk is `1000`, estimated entry and exit fees total `10`, entry price is `20`, and initial stop is `18`
- **THEN** the raw quantity is calculated from `(1000 - 10) / 2` before asset-increment rounding

#### Scenario: Trailing stop is previewed
- **WHEN** the user selects the existing trailing percentage rule
- **THEN** the planner uses entry price as the initial high-water mark and returns the resulting initial stop explicitly

### Requirement: Refuse misleading recommendations
The system MUST NOT return a recommended quantity when equity is unset, portfolio stop coverage is incomplete, remaining capacity is zero, fees consume the allowed risk, the stop is not below entry, or any required input is invalid. It SHALL return stable reason codes and the safe partial explanation that remains available.

#### Scenario: Portfolio coverage is incomplete
- **WHEN** used risk is only a covered subtotal because an open position lacks a calculable stop
- **THEN** the preview returns no recommended quantity and identifies incomplete portfolio risk coverage

#### Scenario: Stop is at or above entry
- **WHEN** the proposed initial stop is equal to or greater than the entry price
- **THEN** the preview returns no quantity and identifies non-positive unit risk

#### Scenario: Rounded quantity is zero
- **WHEN** an A-share raw quantity is less than one 100-share board lot
- **THEN** the preview returns no recommended quantity and explains that available risk cannot support the minimum opening increment

### Requirement: Explain advisory scope and required capital
The frontend SHALL present the risk limit, portfolio capacity, fee assumptions, unit risk, raw quantity, rounded quantity, projected stop loss, and required capital. It SHALL state that the result is advisory, that available cash is not known, and that no order has been placed.

#### Scenario: Display a successful plan
- **WHEN** a valid preview recommends a positive quantity
- **THEN** the interface shows the calculation breakdown and required capital before offering a position-opening handoff

#### Scenario: Required capital exceeds the user's actual cash
- **WHEN** the user reviews a plan whose required capital cannot be verified against any broker cash balance
- **THEN** the interface makes no affordability claim and requires the user to verify available cash independently

### Requirement: Hand off a reviewed plan to position creation
The frontend SHALL allow a valid preview to prefill the authoritative position-opening workflow with code, asset type, name, entry price, quantity, fees, and stop configuration. Position creation MUST remain a separate explicit submission using the normal position API and validation.

#### Scenario: Continue from preview
- **WHEN** the user selects the continue action on a valid plan
- **THEN** the position form is prefilled but no position exists until the user reviews and submits it

#### Scenario: Preview becomes stale before submission
- **WHEN** portfolio data or settings change after preview and the user submits the position form
- **THEN** normal position creation remains authoritative and the interface does not claim that the earlier risk capacity is reserved
