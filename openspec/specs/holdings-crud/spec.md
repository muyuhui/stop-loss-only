# Holdings CRUD

## Purpose

Manage investment holdings (A-share stocks and funds) with create, read, update, delete, and manual close operations.

## Requirements

### Requirement: Create a holding
The system SHALL allow users to create a new holding with asset code, name, type (stock/fund), buy price, quantity, buy date, stop-loss method, and stop-loss value.

#### Scenario: Create stock holding with fixed stop-loss
- **WHEN** user submits {code: "000001", name: "平安银行", type: "stock", buy_price: 10.00, quantity: 1000, buy_date: "2026-01-15", stop_loss_method: "fixed", stop_loss_value: 9.00}
- **THEN** a new holding is created with status "holding" and highest_price initialized to buy_price

#### Scenario: Create fund holding with percentage stop-loss
- **WHEN** user submits {code: "510050", name: "上证50ETF", type: "fund", buy_price: 2.50, quantity: 10000, buy_date: "2026-01-10", stop_loss_method: "percentage", stop_loss_value: 10}
- **THEN** a new holding is created with stop_loss_method "percentage" and stop_loss_value 10

#### Scenario: Create holding with trailing stop-loss
- **WHEN** user submits {type: "stock", stop_loss_method: "trailing", stop_loss_value: 8}
- **THEN** a new holding is created with stop_loss_method "trailing" and stop_loss_value 8

#### Scenario: Create holding with invalid data
- **WHEN** user submits a holding with missing required fields (e.g., no code)
- **THEN** system returns 422 with validation error details

### Requirement: List all holdings
The system SHALL return a paginated list of all holdings ordered by creation date descending.

#### Scenario: List holdings with default pagination
- **WHEN** user requests GET /api/holdings
- **THEN** system returns the first page of holdings with total count

#### Scenario: Filter holdings by status
- **WHEN** user requests GET /api/holdings?status=holding
- **THEN** system returns only holdings with status "holding"

### Requirement: Get holding detail
The system SHALL return the full detail of a single holding by ID, including calculated stop-loss price and current profit/loss percentage.

#### Scenario: Get an existing holding
- **WHEN** user requests GET /api/holdings/{id} for an existing holding
- **THEN** system returns the holding with all fields including current_price, stop_loss_price, profit_loss_pct, stop_loss_distance_pct

#### Scenario: Get a non-existent holding
- **WHEN** user requests GET /api/holdings/{id} for a non-existent ID
- **THEN** system returns 404

### Requirement: Update holding
The system SHALL allow users to update a holding's stop-loss settings (method, value) and optionally name or other metadata fields.

#### Scenario: Change stop-loss method from fixed to trailing
- **WHEN** user updates a holding's stop_loss_method to "trailing" and stop_loss_value to 10
- **THEN** the holding's stop-loss config is updated and highest_price is recalculated if needed

#### Scenario: Update a stopped-out holding
- **WHEN** user attempts to update a holding with status "stopped_out"
- **THEN** system returns 400 with message "已止损的持仓不可修改"

### Requirement: Delete a holding
The system SHALL allow users to delete a holding record.

#### Scenario: Delete an active holding
- **WHEN** user requests DELETE /api/holdings/{id}
- **THEN** the holding is removed from the database and returns 204

### Requirement: Manually close a holding
The system SHALL allow users to manually close a holding without triggering a stop-loss alert.

#### Scenario: Close a holding at current market price
- **WHEN** user requests POST /api/holdings/{id}/close with close_price
- **THEN** the holding status changes to "stopped_out" with the close_price recorded
