# Stop-Loss Engine

## Purpose

Calculate stop-loss prices and detect triggers using three methods: fixed price, percentage, and trailing (moving) stop-loss.

## Requirements

### Requirement: Calculate fixed-price stop-loss
The system SHALL calculate the stop-loss price as a user-defined absolute price when method is "fixed".

#### Scenario: Fixed stop-loss at a specific price
- **WHEN** holding has buy_price=10.00, method="fixed", stop_loss_value=9.00
- **THEN** stop_loss_price SHALL equal 9.00

#### Scenario: Fixed stop-loss value above buy price
- **WHEN** holding has buy_price=10.00, method="fixed", stop_loss_value=11.00
- **THEN** system returns a validation error because stop-loss must be below buy price

### Requirement: Calculate percentage stop-loss
The system SHALL calculate the stop-loss price as buy_price x (1 - stop_loss_value / 100) when method is "percentage".

#### Scenario: 10% stop-loss below buy price
- **WHEN** holding has buy_price=10.00, method="percentage", stop_loss_value=10
- **THEN** stop_loss_price SHALL equal 9.00

#### Scenario: Invalid percentage value
- **WHEN** stop_loss_value is outside the range 1-99
- **THEN** system returns a validation error

### Requirement: Calculate trailing stop-loss
The system SHALL calculate the stop-loss price as highest_price x (1 - stop_loss_value / 100) when method is "trailing". The trailing stop-loss price SHALL never decrease.

#### Scenario: Initial trailing stop-loss at buy price
- **WHEN** holding has buy_price=10.00, highest_price=10.00 (just bought), method="trailing", stop_loss_value=10
- **THEN** stop_loss_price SHALL equal 9.00

#### Scenario: Trailing stop-loss rises with price
- **WHEN** holding has buy_price=10.00, highest_price=18.00, method="trailing", stop_loss_value=10
- **THEN** stop_loss_price SHALL equal 16.20

#### Scenario: Trailing stop-loss never decreases even if price drops
- **WHEN** holding has highest_price=18.00, but current_price drops to 17.00
- **THEN** stop_loss_price remains at 16.20 (based on highest_price, not current_price)

### Requirement: Detect stop-loss trigger
The system SHALL compare current_price to stop_loss_price and trigger a stop-loss when current_price <= stop_loss_price.

#### Scenario: Price drops below stop-loss
- **WHEN** current_price=8.80 and stop_loss_price=9.00
- **THEN** the holding status SHALL change to "stopped_out" and an alert SHALL be created

#### Scenario: Price equals stop-loss exactly
- **WHEN** current_price=9.00 and stop_loss_price=9.00
- **THEN** the holding status SHALL change to "stopped_out"

#### Scenario: Price above stop-loss - no trigger
- **WHEN** current_price=10.50 and stop_loss_price=9.00
- **THEN** holding status remains "holding" and no alert is created

### Requirement: Update highest price for trailing stop
The system SHALL update highest_price whenever current_price exceeds the existing highest_price for trailing stop holdings.

#### Scenario: New high reached
- **WHEN** holding has highest_price=15.00, current_price=16.00, method="trailing"
- **THEN** highest_price SHALL be updated to 16.00

#### Scenario: Price below highest
- **WHEN** holding has highest_price=15.00, current_price=14.00
- **THEN** highest_price remains 15.00
