## ADDED Requirements

### Requirement: Portfolio summary
The system SHALL calculate and display a portfolio summary including total market value, total cost, total profit/loss, and profit/loss percentage.

#### Scenario: Dashboard with multiple holdings
- **WHEN** user requests GET /api/dashboard
- **THEN** system returns {total_cost, total_market_value, total_profit_loss, total_profit_loss_pct, holding_count, active_alerts_count}

#### Scenario: Dashboard with no holdings
- **WHEN** user requests GET /api/dashboard with an empty portfolio
- **THEN** system returns all values as zero and holding_count=0

### Requirement: Holdings overview list
The system SHALL include a list of all holdings with key metrics in the dashboard response: code, name, type, current price, stop-loss price, profit/loss percentage, and stop-loss distance percentage.

#### Scenario: Dashboard with holdings
- **WHEN** user requests GET /api/dashboard
- **THEN** each holding includes {id, code, name, type, buy_price, current_price, quantity, stop_loss_price, stop_loss_method, profit_loss_pct, stop_loss_distance_pct, status}

### Requirement: Today's alert summary
The system SHALL include today's alert count and the most recent alert details in the dashboard.

#### Scenario: Alerts exist for today
- **WHEN** user requests GET /api/dashboard on a day with triggered alerts
- **THEN** system returns today_alert_count and the latest alert details

### Requirement: Frontend dashboard layout
The frontend SHALL display the dashboard as a grid with: portfolio summary cards at top, holdings table in middle, and alert summary at bottom.

#### Scenario: Dashboard loads successfully
- **WHEN** user navigates to the dashboard page
- **THEN** the page displays summary cards, a holdings table with real-time prices, and today's alert summary

### Requirement: Real-time frontend refresh
The frontend SHALL poll the dashboard API at a configurable interval (default 30 seconds) to refresh price and status data.

#### Scenario: Automatic dashboard refresh
- **WHEN** the polling interval elapses
- **THEN** the dashboard data refreshes without requiring a manual page reload

#### Scenario: Stop polling when leaving dashboard
- **WHEN** user navigates away from the dashboard page
- **THEN** polling stops to conserve resources
